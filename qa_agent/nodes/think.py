"""
Think Node - Analyze browser state and plan actions

This node:
1. Gets current browser state (URL, DOM, interactive elements)
2. Formats prompt with browser state and task
3. Calls LLM to generate thinking and next actions
4. Parses LLM response into planned actions
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from qa_agent.state import QAAgentState
from qa_agent.config import settings
from qa_agent.llm import get_llm
from qa_agent.prompts import build_think_prompt
from qa_agent.utils import parse_llm_action_plan, validate_action

logger = logging.getLogger(__name__)

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


async def think_node(state: QAAgentState) -> Dict[str, Any]:
    """
    Think node: Analyze browser state and plan actions
    
    Args:
        state: Current QA agent state
        
    Returns:
        Updated state with planned actions
    """
    try:
        logger.info(f"Think node - Step {state.get('step_count', 0)}")
        
        # Increment step count
        step_count = state.get("step_count", 0) + 1
        
        # Get browser state (Phase 2 will enhance this)
        browser_session = state.get("browser_session")
        browser_state_summary = state.get("browser_state_summary")
        
        if browser_session:
            # TODO: Phase 2 - Call browser state extractor
            # browser_state_summary = await get_browser_state(browser_session)
            pass
        
        # Get task and history
        task = state.get("task", "")
        current_goal = state.get("current_goal")
        history = state.get("history", [])
        
        # Build prompt for LLM
        logger.info(f"Building prompt for task: {task[:100]}...")
        messages = build_think_prompt(
            task=task,
            current_goal=current_goal,
            browser_state=browser_state_summary,
            history=history,
            step_count=step_count,
            max_steps=state.get("max_steps", 50),
        )
        
        # Save prompt to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"llm_interaction_{timestamp}_step{step_count}.json"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "step": step_count,
            "task": task,
            "prompt_to_llm": {
                "system_message": messages[0]["content"] if messages else None,
                "user_message": messages[1]["content"] if len(messages) > 1 else None,
            },
            "llm_response": None,  # Will be filled after LLM call
            "parsed_actions": None,  # Will be filled after parsing
            "validated_actions": None,  # Will be filled after validation
        }
        
        print(f"\n{'='*80}")
        print(f"📤 SENDING TO LLM (Step {step_count})")
        print(f"{'='*80}")
        print(f"\n📝 System Message:\n{messages[0]['content'][:500]}...")
        print(f"\n💬 User Message:\n{messages[1]['content'][:500]}...")
        print(f"\n💾 Saving prompt to: {log_file}")
        
        # Initialize LLM and call
        logger.info("Calling LLM to generate action plan...")
        llm = get_llm()
        
        # Convert messages to LangChain format
        from langchain_core.messages import SystemMessage, HumanMessage
        langchain_messages = []
        for msg in messages:
            if msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))
            else:
                langchain_messages.append(HumanMessage(content=msg["content"]))
        
        # Call LLM
        print(f"\n🤖 Calling LLM ({settings.llm_model})...")
        response = await llm.ainvoke(langchain_messages)
        
        # Extract response content
        response_content = response.content if hasattr(response, 'content') else str(response)
        logger.info(f"LLM response received: {len(response_content)} characters")
        
        # Save LLM response
        log_data["llm_response"] = {
            "raw_response": response_content,
            "response_length": len(response_content),
            "model": settings.llm_model,
        }
        
        print(f"\n{'='*80}")
        print(f"📥 RECEIVED FROM LLM")
        print(f"{'='*80}")
        print(f"\n📄 Raw Response ({len(response_content)} chars):\n{response_content}")
        
        # Parse LLM response into actions
        print(f"\n🔍 Parsing LLM response...")
        planned_actions = parse_llm_action_plan(response_content)
        
        # Save parsed actions
        log_data["parsed_actions"] = planned_actions
        
        # Print parsed actions
        print(f"\n📋 Parsed {len(planned_actions)} actions from LLM response:")
        for i, action in enumerate(planned_actions, 1):
            print(f"  {i}. {action}")
        
        # Check for "done" action from LLM
        has_done_action = any(action.get("type") == "done" for action in planned_actions)
        
        if has_done_action:
            done_action = next((a for a in planned_actions if a.get("type") == "done"), None)
            done_message = done_action.get("message", "Task completed") if done_action else "Task completed"
            print(f"\n✅ LLM signaled task completion: {done_message}")
            logger.info(f"LLM completed task: {done_message}")
            
            # Save completion
            log_data["validated_actions"] = planned_actions
            log_data["task_completed"] = True
            log_data["completion_message"] = done_message
            
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2)
            
            return {
                "step_count": step_count,
                "planned_actions": planned_actions,
                "completed": True,  # Signal completion
                "browser_state_summary": browser_state_summary,
                "history": state.get("history", []) + [{
                    "step": step_count,
                    "node": "think",
                    "planned_actions": planned_actions,
                    "task_completed": True,
                    "completion_message": done_message,
                }],
                "current_goal": f"Task completed: {done_message[:50]}",
            }
        
        # Validate actions
        valid_actions = []
        for action in planned_actions:
            if validate_action(action):
                valid_actions.append(action)
            else:
                logger.warning(f"Invalid action skipped: {action}")
                print(f"  ⚠️  Invalid action skipped: {action}")
        
        # Save validated actions
        log_data["validated_actions"] = valid_actions
        
        if not valid_actions:
            logger.error("No valid actions parsed from LLM response. This indicates an LLM parsing issue.")
            print("\n❌ ERROR: No valid actions parsed from LLM response!")
            
            # Save error to log file
            log_data["error"] = "No valid actions parsed"
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2)
            
            return {
                "error": "Failed to parse valid actions from LLM response. Check LLM output format.",
                "step_count": step_count,
                "planned_actions": [],
            }
        
        print(f"\n✅ Validated {len(valid_actions)} actions")
        print(f"{'='*80}\n")
        
        # Save complete log to file
        log_data["summary"] = {
            "parsed_count": len(planned_actions),
            "validated_count": len(valid_actions),
            "success": True,
        }
        
        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)
        
        print(f"💾 Complete interaction saved to: {log_file}\n")
        
        logger.info(f"Generated {len(valid_actions)} planned actions")
        
        # Update history - create new list (LangGraph best practice: don't mutate state)
        existing_history = state.get("history", [])
        new_history_entry = {
            "step": step_count,
            "node": "think",
            "browser_state": browser_state_summary,
            "planned_actions": valid_actions,
            "llm_response_preview": response_content[:200] if response_content else None,
        }
        
        return {
            "step_count": step_count,
            "planned_actions": valid_actions,
            "browser_state_summary": browser_state_summary,
            "history": existing_history + [new_history_entry],  # Return new list
            "current_goal": f"Executing step {step_count}: {valid_actions[0].get('reasoning', '')[:50] if valid_actions else ''}",
        }
    except Exception as e:
        logger.error(f"Error in think node: {e}", exc_info=True)
        return {
            "error": f"Think node error: {str(e)}",
            "step_count": state.get("step_count", 0),
            "planned_actions": [],
        }

