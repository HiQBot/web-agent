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
from qa_agent.prompts.browser_use_prompts import SystemPrompt, AgentMessagePrompt
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
        
        # Get browser state from browser-use BrowserSession
        from qa_agent.utils.session_registry import get_session

        browser_session_id = state.get("browser_session_id")
        if not browser_session_id:
            raise ValueError("No browser_session_id in state - INIT node must run first")

        browser_session = get_session(browser_session_id)
        if not browser_session:
            raise ValueError(f"Browser session {browser_session_id} not found in registry")

        # Get browser state summary with DOM extraction (browser-use native call)
        logger.info("Extracting browser state with DOM...")
        browser_state = await browser_session.get_browser_state_summary(
            include_screenshot=False,  # Set True if using vision model
            include_recent_events=False
        )

        # Extract DOM data for logging/history (browser-use handles DOM internally in AgentMessagePrompt)
        current_url = browser_state.url
        current_title = browser_state.title
        selector_map = browser_state.dom_state.selector_map if browser_state.dom_state else {}

        logger.info(f"DOM extraction complete: {len(selector_map)} interactive elements at {current_url}")

        # Build browser state summary for our own logging/history tracking
        browser_state_summary = {
            "url": current_url,
            "title": current_title,
            "element_count": len(selector_map),
            "tabs": [{"id": t.target_id, "title": t.title, "url": t.url} for t in browser_state.tabs] if browser_state.tabs else [],
        }
        
        # Get task and history
        task = state.get("task", "")
        current_goal = state.get("current_goal")
        history = state.get("history", [])
        max_steps = state.get("max_steps", 50)

        # Build prompt using browser-use SystemPrompt and AgentMessagePrompt
        logger.info(f"Building prompt for task using browser-use prompts: {task[:100]}...")

        # Create SystemPrompt (loads from system_prompt.md)
        system_prompt = SystemPrompt(
            max_actions_per_step=settings.max_actions_per_step,
            use_thinking=True,  # Use thinking mode for better reasoning
            flash_mode=False,
        )

        # Create AgentStepInfo
        from dataclasses import dataclass
        @dataclass
        class AgentStepInfo:
            step_number: int
            max_steps: int

        step_info = AgentStepInfo(step_number=step_count, max_steps=max_steps)

        # Format history for agent_history_description (browser-use format)
        agent_history_description = ""
        if history:
            for i, step in enumerate(history[-5:], 1):  # Last 5 steps
                step_num = step.get("step", i)
                node = step.get("node", "unknown")

                if node == "think":
                    actions = step.get("planned_actions", [])
                    agent_history_description += f'Step {step_num}: Planned {len(actions)} actions\\n'
                elif node == "act":
                    results = step.get("action_results", [])
                    success_count = sum(1 for r in results if r.get("success", False))
                    agent_history_description += f'Step {step_num}: Executed {len(results)} actions, {success_count} successful\\n'
                elif node == "verify":
                    status = step.get("verification_status", "unknown")
                    agent_history_description += f'Step {step_num}: Verification {status}\\n'

        # Create AgentMessagePrompt (uses BrowserStateSummary directly!)
        agent_message_prompt = AgentMessagePrompt(
            browser_state_summary=browser_state,  # Pass the actual BrowserStateSummary object
            file_system=None,  # TODO: Add file system support later
            agent_history_description=agent_history_description,
            read_state_description=None,
            task=task,
            include_attributes=None,  # Use default attributes
            step_info=step_info,
            page_filtered_actions=None,
            max_clickable_elements_length=40000,
            sensitive_data=None,
            available_file_paths=None,
            screenshots=None,  # TODO: Add screenshot support when using vision model
            vision_detail_level='auto',
            include_recent_events=False,
            sample_images=None,
            read_state_images=None,
        )

        # Get formatted messages
        system_message = system_prompt.get_system_message()
        user_message = agent_message_prompt.get_user_message(use_vision=False)
        
        # Save prompt to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"llm_interaction_{timestamp}_step{step_count}.json"
        
        # Extract message content for logging
        system_content = system_message.content if hasattr(system_message, 'content') else str(system_message)
        # user_message can be text or list of content parts
        if hasattr(user_message, 'content'):
            if isinstance(user_message.content, str):
                user_content = user_message.content
            elif isinstance(user_message.content, list):
                # Extract text parts only for logging
                user_content = ' '.join([
                    part.get('text', '') if isinstance(part, dict) else str(part)
                    for part in user_message.content
                ])
            else:
                user_content = str(user_message.content)
        else:
            user_content = str(user_message)

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "step": step_count,
            "task": task,
            "prompt_to_llm": {
                "system_message": system_content,
                "user_message": user_content[:5000],  # Limit for logging
            },
            "llm_response": None,  # Will be filled after LLM call
            "parsed_actions": None,  # Will be filled after parsing
            "validated_actions": None,  # Will be filled after validation
        }

        print(f"\n{'='*80}")
        print(f"📤 SENDING TO LLM (Step {step_count}) - Using browser-use prompts")
        print(f"{'='*80}")
        print(f"\n📝 System Message (browser-use):\n{system_content[:500]}...")
        print(f"\n💬 User Message (browser-use):\n{user_content[:500]}...")
        print(f"\n💾 Saving prompt to: {log_file}")

        # Initialize LLM and call
        logger.info("Calling LLM to generate action plan with browser-use prompts...")
        llm = get_llm()

        # Convert browser-use messages to LangChain format
        from langchain_core.messages import SystemMessage as LCSystemMessage, HumanMessage
        langchain_messages = [
            LCSystemMessage(content=system_content),
            HumanMessage(content=user_content if isinstance(user_content, str) else str(user_content))
        ]

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
        
        # Check for "done" action from LLM (supports both "action" and "type" keys)
        has_done_action = any(
            action.get("action") == "done" or action.get("type") == "done"
            for action in planned_actions
        )

        if has_done_action:
            done_action = next((
                a for a in planned_actions
                if a.get("action") == "done" or a.get("type") == "done"
            ), None)
            done_message = done_action.get("text") or done_action.get("message", "Task completed") if done_action else "Task completed"
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
                "dom_selector_map": selector_map,  # Cache for ACT node
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
            "dom_selector_map": selector_map,  # Cache for ACT node element lookups
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

