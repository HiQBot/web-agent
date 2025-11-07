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
import re
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
        # Browser-use pattern: ALWAYS get fresh state at start of each step (see agent/service.py _prepare_context)
        # CRITICAL: On retry or after tab switch, this ensures we see the ACTUAL current page state, not stale state
        
        # OPTIMIZATION: Check if act node already provided fresh state after actions
        # This is the "backend 1 step ahead" pattern - Act node waits for DOM stability and fetches fresh state
        # Think node can reuse it to avoid duplicate work
        fresh_state_available = state.get("fresh_state_available", False)
        page_changed = state.get("page_changed", False)

        # Track tab before state retrieval for comparison
        current_tab_before_state = browser_session.current_target_id
        
        if fresh_state_available:
            # Act node already fetched fresh state after actions and DOM stability wait
            # This ensures we see dropdowns, modals, and dynamic content that appeared after actions
            logger.info("✅ Using pre-fetched fresh state from act node (after DOM stability wait)")
            logger.info("   This ensures LLM sees CURRENT page structure (dropdowns, modals, new content)")
            
            # Still need to get full BrowserStateSummary object for LLM (not just summary dict)
            # But we can use cached=False to ensure consistency
            browser_state = await browser_session.get_browser_state_summary(
                include_screenshot=False,
                include_recent_events=False,
                cached=False  # Force fresh to ensure consistency with Act node's state
            )
            
            # Verify we got the same URL as Act node reported (sanity check)
            act_node_url = state.get("current_url")
            if act_node_url and browser_state.url != act_node_url:
                logger.warning(f"⚠️ URL mismatch: Act node reported {act_node_url}, Think node got {browser_state.url}")
        else:
            # Normal flow: fetch fresh state (first step, or if Act node didn't provide state)
            # CRITICAL: Check if verify node just switched tabs - log current tab before getting state
            # This helps debug if we're getting the wrong tab's DOM
            logger.info(f"Getting browser state (current tab before: {current_tab_before_state[-4:] if current_tab_before_state else 'unknown'})...")

            logger.info("Extracting browser state with DOM (forcing fresh state, no cache)...")
            browser_state = await browser_session.get_browser_state_summary(
                include_screenshot=False,  # Set True if using vision model
                include_recent_events=False,
                cached=False  # Always get fresh state - critical after tab switches
            )
        
        # Verify we got state from the correct tab
        current_tab_after_state = browser_session.current_target_id
        logger.info(f"State retrieved (current tab after: {current_tab_after_state[-4:] if current_tab_after_state else 'unknown'})")
        if current_tab_before_state and current_tab_after_state and current_tab_before_state != current_tab_after_state:
            logger.warning(f"⚠️ Tab changed during state retrieval: {current_tab_before_state[-4:]} → {current_tab_after_state[-4:]}")

        # Extract DOM data for logging/history (browser-use handles DOM internally in AgentMessagePrompt)
        current_url = browser_state.url
        current_title = browser_state.title
        # Defensive check: ensure selector_map is always a dict (browser-use should return dict)
        selector_map = {}
        if browser_state.dom_state and hasattr(browser_state.dom_state, 'selector_map'):
            selector_map_raw = browser_state.dom_state.selector_map
            if isinstance(selector_map_raw, dict):
                selector_map = selector_map_raw
            else:
                logger.warning(f"selector_map is not a dict (type: {type(selector_map_raw)}), using empty dict")
        
        # Check for new tabs opened by previous actions (browser-use pattern: check tabs from state)
        # This ensures we're aware of tabs opened by actions, even if we haven't switched yet
        # Defensive check: ensure current_tabs is always a list
        current_tabs = []
        if browser_state.tabs:
            if isinstance(browser_state.tabs, list):
                current_tabs = browser_state.tabs
            else:
                logger.warning(f"browser_state.tabs is not a list (type: {type(browser_state.tabs)}), using empty list")
        tab_info = [{"id": t.target_id[-4:], "title": t.title, "url": t.url} for t in current_tabs]
        
        # Detect if this is a retry after failure OR if we just switched tabs (browser-use pattern: always verify current state)
        history = state.get("history", [])
        is_retry = False
        just_switched_tab = state.get("just_switched_tab", False)
        tab_switch_url = state.get("tab_switch_url")
        tab_switch_title = state.get("tab_switch_title")
        previous_url = None
        previous_tab_id = None
        
        # Check if verify node just switched tabs (browser-use pattern: fresh state is automatically sent)
        # The browser_state already contains all elements from the new page - LLM will analyze dynamically
        tab_switch_system_message = None
        if just_switched_tab:
            logger.info(f"🔄 DETECTED TAB SWITCH - Fresh browser state retrieved: {tab_switch_title} ({tab_switch_url})")
            logger.info(f"   Interactive elements available: {len(selector_map)}")
            logger.info("   LLM will analyze browser_state and adapt actions based on current page structure.")

            # Create system message to inject into agent_history
            # This will make the LLM explicitly aware that it's on a new page
            tab_switch_system_message = (
                f"<sys>🔄 TAB SWITCH DETECTED: You are now on a COMPLETELY NEW PAGE.\n"
                f"- New URL: {tab_switch_url}\n"
                f"- New Title: {tab_switch_title}\n"
                f"- Available elements: {len(selector_map)} interactive elements\n"
                f"CRITICAL: The <browser_state> below shows THIS new page's elements with NEW indices.\n"
                f"DO NOT reuse element indices from previous steps - they are from the OLD page.\n"
                f"ANALYZE the CURRENT page structure FIRST before deciding your next action.</sys>"
            )
        
        # Check if last step was a verification failure
        if history:
            last_entry = history[-1]
            if isinstance(last_entry, dict) and last_entry.get("node") == "verify":
                if last_entry.get("verification_status") == "fail":
                    is_retry = True
                    # Get previous URL/tab from history for comparison
                    # Browser-use pattern: compare current state with previous state to detect changes
                    for entry in reversed(history):
                        if isinstance(entry, dict) and entry.get("node") == "think":
                            browser_state_prev = entry.get("browser_state") or entry.get("browser_state_summary", {})
                            previous_url = browser_state_prev.get("url") if isinstance(browser_state_prev, dict) else None
                            break
        
        # Get current active tab ID for comparison
        current_tab_id = browser_session.current_target_id if hasattr(browser_session, 'current_target_id') else None
        
        # Log current state prominently, especially on retry
        logger.info(f"{'🔄 RETRY: ' if is_retry else ''}Current page state:")
        logger.info(f"  URL: {current_url}")
        logger.info(f"  Title: {current_title[:80]}")
        logger.info(f"  Tab ID: {current_tab_id[-4:] if current_tab_id else 'unknown'}")
        logger.info(f"  Interactive elements: {len(selector_map)}")
        
        # Detect unexpected URL/tab changes (critical for retry scenarios)
        if is_retry and previous_url:
            if current_url != previous_url:
                logger.warning(f"⚠️  URL CHANGED on retry: {previous_url} → {current_url}")
                logger.warning("   This may indicate a redirect or navigation occurred")
        
        logger.info(f"Current tabs: {len(current_tabs)} tabs available")
        for tab in current_tabs:
            is_active = (current_tab_id and tab.target_id == current_tab_id)
            active_marker = " [ACTIVE]" if is_active else ""
            logger.debug(f"  Tab {tab.target_id[-4:]}{active_marker}: {tab.title[:50]} - {tab.url[:80]}")

        logger.info(f"DOM extraction complete: {len(selector_map)} interactive elements at {current_url}")

        # Build browser state summary for our own logging/history tracking
        browser_state_summary = {
            "url": current_url,
            "title": current_title,
            "element_count": len(selector_map),
            "tabs": tab_info,  # Use pre-formatted tab info with 4-char IDs
            "is_retry": is_retry,  # Track if this is a retry for context
            "previous_url": previous_url,  # Track previous URL for comparison
        }
        
        # Check if we need to switch to a new tab (from previous act node)
        # Note: If verify node already switched, new_tab_id will be cleared
        # But we should still log the current tab state to ensure LLM sees it
        new_tab_id = state.get("new_tab_id")
        new_tab_url = state.get("new_tab_url")
        if new_tab_id:
            logger.info(f"⚠️ New tab detected from previous action (not yet switched): {new_tab_id[-4:]} - {new_tab_url or 'unknown URL'}")
            logger.info(f"   Current tab: {current_tab_id[-4:] if current_tab_id else 'unknown'}")
            logger.info(f"   This will be handled by verify node - LLM should see tab info in browser_state")
        
        # Browser-use pattern: get_browser_state_summary() already handles:
        # - URL detection via get_current_page_url() (CDP-based, reliable)
        # - Network idle detection via DOMWatchdog._get_pending_network_requests()
        # - Page stability waiting (1s if pending requests exist)
        # - DOM building and element extraction
        # We trust browser-use's built-in mechanisms - no need to re-implement URL/page loading detection
        # DOMWatchdog.on_BrowserStateRequestEvent() handles all of this automatically
        
        # CRITICAL: Log current tab state prominently so we can verify LLM gets correct tab's DOM
        logger.info(f"🔍 Current browser state for LLM:")
        logger.info(f"   Active tab ID: {current_tab_id[-4:] if current_tab_id else 'unknown'}")
        logger.info(f"   URL: {current_url}")
        logger.info(f"   Title: {current_title}")
        logger.info(f"   Interactive elements: {len(selector_map)}")
        logger.info(f"   Total tabs: {len(current_tabs)}")
        for tab in current_tabs:
            is_current = (current_tab_id and tab.target_id == current_tab_id)
            marker = " [CURRENT]" if is_current else ""
            logger.info(f"      Tab {tab.target_id[-4:]}{marker}: {tab.title[:40]} - {tab.url[:60]}")
        
        # Get task and history (history already retrieved above for retry detection)
        task = state.get("task", "")
        current_goal = state.get("current_goal")
        max_steps = state.get("max_steps", 50)

        # GOAL TRACKING: Check if current goal is complete and update task context
        # This prevents the agent from repeating completed steps (e.g., signup after successful login)
        goals = state.get("goals", [])
        completed_goals = state.get("completed_goals", [])
        current_goal_index = state.get("current_goal_index", 0)

        logger.info(f"📊 GOAL TRACKING: {len(completed_goals)}/{len(goals)} goals completed, current index: {current_goal_index}")

        if goals and current_goal_index < len(goals):
            current_goal_obj = goals[current_goal_index]
            goal_id = current_goal_obj.get("id", "")
            goal_desc = current_goal_obj.get("description", "")
            completion_signals = current_goal_obj.get("completion_signals", [])

            logger.info(f"   Current goal: [{goal_id}] {goal_desc}")
            logger.info(f"   Completion signals: {completion_signals}")

            # Check if current goal appears complete based on page state (URL/title)
            is_goal_complete = any(
                signal.lower() in current_url.lower() or signal.lower() in current_title.lower()
                for signal in completion_signals
            )

            logger.info(f"   URL: {current_url}")
            logger.info(f"   Title: {current_title}")
            logger.info(f"   Goal complete? {is_goal_complete}")

            if is_goal_complete and goal_id not in completed_goals:
                # Goal just completed! Mark it and move to next goal
                logger.info(f"🎯 Goal '{goal_id}' COMPLETED! (detected by URL/title signals)")
                logger.info(f"   Marking goal as complete and advancing to next goal")

                # Update state to mark goal complete and advance
                completed_goals = completed_goals + [goal_id]
                current_goal_index = current_goal_index + 1

                logger.info(f"   Progress: {len(completed_goals)}/{len(goals)} goals completed")

                # Update task context for next goal
                if current_goal_index < len(goals):
                    next_goal_obj = goals[current_goal_index]
                    next_goal_desc = next_goal_obj.get("description", "")
                    logger.info(f"   Next goal: {next_goal_desc}")
                    task = f"CURRENT GOAL: {next_goal_desc}\n\nCompleted goals: {', '.join(completed_goals)}\n\nFull task for context:\n{task}"
                else:
                    logger.info(f"   ✅ ALL GOALS COMPLETED!")
                    task = f"All major goals completed. Complete any remaining cleanup.\n\nOriginal task: {task}"
            else:
                # Goal still in progress - update task to focus LLM on current goal
                if completed_goals:
                    logger.info(f"💡 Focusing LLM on current goal (already completed {len(completed_goals)} goals)")
                    task = f"CURRENT GOAL: {goal_desc}\n\nCompleted goals: {', '.join(completed_goals)}\n\nFull task for context:\n{task}"
                else:
                    logger.info(f"💡 Working on first goal (no goals completed yet)")

        # Browser-use pattern: On retry, emphasize that LLM should use CURRENT browser_state
        # The browser_state sent in this step contains FRESH element indices from the current page
        # Human QA approach: Look at the page, see what's there, then interact with the right elements
        if is_retry:
            logger.info(f"🔄 RETRY STEP {step_count}: Sending fresh browser_state with {len(selector_map)} interactive elements")
            logger.info(f"   LLM will see CURRENT page state and can adapt actions based on what's actually available")
            logger.info(f"   Previous failure context is included in agent_history above")

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

        # Format history for agent_history_description (browser-use HistoryItem format)
        # Browser-use format: <step_N>\nevaluation\nmemory\nnext_goal\nResult\naction_results\n</step_N>
        agent_history_description = ""
        read_state_description = ""  # Track extract() results separately (browser-use pattern)
        read_state_idx = 0
        
        if history:
            # Get last 5 steps (browser-use uses max_history_items)
            recent_steps = history[-5:]
            for step_entry in recent_steps:
                step_num = step_entry.get("step", 0)
                node = step_entry.get("node", "unknown")
                
                # Build HistoryItem format (browser-use pattern)
                step_content_parts = []
                
                # Extract evaluation/memory/goal from previous think node if available
                if node == "think":
                    # Try to extract from LLM response if structured
                    llm_preview = step_entry.get("llm_response_preview", "")
                    evaluation = step_entry.get("evaluation_previous_goal")
                    memory = step_entry.get("memory")
                    next_goal = step_entry.get("next_goal")
                    
                    # Try parsing JSON from LLM response if available
                    if llm_preview and not evaluation:
                        try:
                            # Try to find JSON in response
                            json_match = re.search(r'\{[^{}]*"evaluation_previous_goal"[^{}]*\}', llm_preview, re.DOTALL)
                            if json_match:
                                llm_data = json.loads(json_match.group(0))
                                evaluation = llm_data.get("evaluation_previous_goal")
                                memory = llm_data.get("memory")
                                next_goal = llm_data.get("next_goal")
                        except Exception:
                            pass
                    
                    if evaluation:
                        step_content_parts.append(evaluation)
                    if memory:
                        step_content_parts.append(memory)
                    if next_goal:
                        step_content_parts.append(next_goal)
                
                # Add action results from act node
                if node == "act":
                    action_results_text = ""
                    results = step_entry.get("action_results", [])
                    
                    for result in results:
                        # Browser-use pattern: prefer long_term_memory, fallback to extracted_content
                        long_term_memory = result.get("long_term_memory")
                        extracted_content = result.get("extracted_content")
                        include_only_once = result.get("include_extracted_content_only_once", False)
                        error = result.get("error")
                        
                        # Handle read_state (extract() results) - browser-use pattern
                        if include_only_once and extracted_content:
                            read_state_description += f'<read_state_{read_state_idx}>\n{extracted_content}\n</read_state_{read_state_idx}>\n'
                            read_state_idx += 1
                        
                        # Build action_results text (browser-use pattern)
                        if long_term_memory:
                            action_results_text += f'{long_term_memory}\n'
                        elif extracted_content and not include_only_once:
                            action_results_text += f'{extracted_content}\n'
                        
                        if error:
                            error_text = error[:200] + '......' + error[-100:] if len(error) > 200 else error
                            action_results_text += f'Error: {error_text}\n'
                    
                    if action_results_text:
                        step_content_parts.append(f'Result\n{action_results_text.strip()}')
                
                # Add verification failure details (critical for retry - LLM needs to know WHY it failed)
                # Browser-use pattern: On retry, LLM sees fresh browser_state with CURRENT element indices
                # LLM should analyze what's actually available NOW, not use stale indices from previous step
                if node == "verify":
                    verification_status = step_entry.get("verification_status")
                    verification_results = step_entry.get("verification_results", [])
                    
                    if verification_status == "fail":
                        failure_details = []
                        failed_action_types = set()
                        for v_result in verification_results:
                            if v_result.get("status") == "fail":
                                reason = v_result.get("reason", "Unknown failure")
                                # Add action details if available for better context
                                details = v_result.get("details", {})
                                action = details.get("action", {})
                                action_type = action.get("action", "unknown")
                                failed_action_types.add(action_type)
                                failure_details.append(f"Verification failed: {reason} (Action: {action_type})")
                        
                        if failure_details:
                            step_content_parts.append(f'Result\n{"\n".join(failure_details)}')
                            # Browser-use pattern: Guide LLM to use CURRENT browser_state (sent in this step)
                            # Human QA approach: Look at what's on the page NOW, then pick the right element
                            step_content_parts.append("⚠️ RETRY: The previous action failed. Please review the CURRENT <browser_state> above to see what elements are actually available on this page. Element indices may have changed - use the indices shown in the current browser_state, not from previous steps.")
                
                # Handle tab switch history entries (verify_tab_switch node)
                # These are system messages injected by verify node when tabs switch
                if node == "verify_tab_switch":
                    action_results = step_entry.get("action_results", [])
                    for result in action_results:
                        extracted_content = result.get("extracted_content", "")
                        if extracted_content:
                            step_content_parts.append(f'Result\n{extracted_content}')

                # Format as browser-use HistoryItem: <step_N>...</step_N>
                if step_content_parts:
                    content = '\n'.join(step_content_parts)
                    agent_history_description += f'<step_{step_num}>\n{content}\n</step_{step_num}>\n'

        # Inject tab switch system message if we just switched tabs
        # This ensures LLM sees the warning BEFORE processing the new browser_state
        if tab_switch_system_message:
            agent_history_description += f'\n{tab_switch_system_message}\n'

        # Clean up read_state_description
        read_state_description = read_state_description.strip('\n') if read_state_description else None

        # Get page-filtered actions (browser-use pattern: show only relevant actions per page)
        page_filtered_actions = None
        try:
            from qa_agent.tools.service import Tools
            tools = Tools()
            page_filtered_actions = tools.registry.get_prompt_description(page_url=current_url)
        except Exception as e:
            logger.debug(f"Could not get page-filtered actions: {e}")
        
        # Browser-use pattern: Don't add hard-coded guidance - just send the browser state
        # The LLM will analyze the current browser_state and decide actions based on what it sees
        # If we switched tabs, the browser_state already contains the new page's elements
        # The LLM can see all interactive elements and their indices, so it can adapt dynamically
        enhanced_task = task
        
        # Create file system for extract() action support
        # Browser-use pattern: FileSystem handles saving extracted content to files
        from qa_agent.filesystem.file_system import FileSystem
        from pathlib import Path
        file_system_dir = Path("qa_agent_workspace") / f"session_{browser_session_id[:8]}"
        file_system = FileSystem(base_dir=file_system_dir, create_default_files=True)

        # Create AgentMessagePrompt (uses BrowserStateSummary directly!)
        agent_message_prompt = AgentMessagePrompt(
            browser_state_summary=browser_state,  # Pass the actual BrowserStateSummary object
            file_system=file_system,  # FileSystem for extract() action and file operations
            agent_history_description=agent_history_description,
            read_state_description=read_state_description,  # Extract() results (browser-use pattern)
            task=enhanced_task,  # Use enhanced task with tab switch context if applicable
            include_attributes=None,  # Use default attributes
            step_info=step_info,
            page_filtered_actions=page_filtered_actions,  # Page-specific actions (browser-use pattern)
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
        # Browser-use pattern: AgentMessagePrompt.get_user_message() includes:
        # - <agent_history> with previous steps
        # - <agent_state> with user_request, step_info, etc.
        # - <browser_state> with FULL DOM structure via llm_representation() - ALL interactive elements with indices
        # - <read_state> if extract() was called
        # - <page_specific_actions> filtered by current URL
        # The LLM sees the complete page structure BEFORE deciding actions - just like human QA analyzes the page first
        system_message = system_prompt.get_system_message()
        user_message = agent_message_prompt.get_user_message(use_vision=False)
        
        # Log that LLM is receiving full DOM structure (for debugging/verification)
        # Browser-use pattern: AgentMessagePrompt includes FULL DOM via llm_representation()
        # This gives LLM complete page structure BEFORE deciding actions - like human QA analyzes page first
        if browser_state.dom_state:
            try:
                # Get DOM representation length to verify it's being sent
                dom_repr = browser_state.dom_state.llm_representation()
                dom_repr_length = len(dom_repr)
                # Count interactive elements from DOM (more accurate than selector_map)
                interactive_count = len(browser_state.dom_state.selector_map) if browser_state.dom_state.selector_map else 0
                logger.info(f"📋 LLM receiving FULL browser_state with DOM structure:")
                logger.info(f"   DOM representation: {dom_repr_length} characters")
                logger.info(f"   Interactive elements with indices: {interactive_count}")
                logger.info(f"   Current URL: {current_url}")
                logger.info(f"   Page title: {current_title[:60]}")
                logger.info(f"   ⚡ LLM will analyze this page structure FIRST, then decide actions based on user query")
            except Exception as e:
                logger.debug(f"Could not get DOM representation length: {e}")
                logger.info(f"📋 LLM receiving browser_state with {len(selector_map)} interactive elements")
        
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

        # Call LLM with structured output (LangChain pattern)
        from qa_agent.views import AgentOutput

        # Create dynamic ActionModel with current page's actions (browser-use pattern)
        # This gives LLM precise schema of available actions
        action_model = tools.registry.create_action_model(page_url=current_url)

        # Create dynamic AgentOutput with the action model
        dynamic_agent_output = AgentOutput.type_with_custom_actions(action_model)

        print(f"\n🤖 Calling LLM ({settings.llm_model}) with structured output...")
        logger.info(f"Using dynamic ActionModel with {len([a for a in tools.registry.registry.actions.keys()])} registered actions")

        # LangChain uses with_structured_output() method, NOT output_format parameter
        structured_llm = llm.with_structured_output(dynamic_agent_output)
        parsed: AgentOutput = await structured_llm.ainvoke(langchain_messages)

        logger.info(f"LLM response received: {parsed}")

        # Save LLM response
        log_data["llm_response"] = {
            "parsed_model": parsed.model_dump(),
            "model": settings.llm_model,
        }

        print(f"\n{'='*80}")
        print(f"📥 RECEIVED FROM LLM (Structured Output)")
        print(f"{'='*80}")
        print(f"\n📄 Parsed Model:\n{parsed.model_dump_json(indent=2)}")

        print(f"\n🔍 Extracting fields from structured output...")

        # Extract fields directly from Pydantic model (no JSON parsing needed!)
        evaluation_previous_goal = parsed.evaluation_previous_goal
        memory = parsed.memory
        next_goal = parsed.next_goal
        thinking = parsed.thinking

        # Convert ActionModel list to simple dict format for act node
        # ActionModel.model_dump() returns {"click": {"index": 123}}
        # convert_browser_use_actions() converts to {"action": "click", "index": 123}
        from qa_agent.utils.response_parser import convert_browser_use_actions

        action_dicts = [action_model.model_dump(exclude_unset=True) for action_model in parsed.action]
        planned_actions = convert_browser_use_actions(action_dicts)

        logger.info(f"✅ Structured output: {len(planned_actions)} actions extracted")
        for i, action in enumerate(planned_actions, 1):
            logger.debug(f"  Action {i}: {action}")

        # With structured output, no JSON parsing or error handling needed!
        # The LLM provider validates the response against the Pydantic schema
        
        logger.debug(f"Parsed {len(planned_actions)} actions: {planned_actions}")
        
        # Save parsed actions
        log_data["parsed_actions"] = planned_actions
        log_data["extracted_fields"] = {
            "evaluation_previous_goal": evaluation_previous_goal,
            "memory": memory,
            "next_goal": next_goal,
            "thinking": thinking,
        }
        
        # Print parsed actions
        print(f"\n📋 Parsed {len(planned_actions)} actions from LLM response:")
        for i, action in enumerate(planned_actions, 1):
            print(f"  {i}. {action}")
        
        # Check for "done" action from LLM (supports both "action" and "type" keys)
        # Filter out non-dict actions (parser may return strings from malformed responses)
        has_done_action = any(
            isinstance(action, dict) and (action.get("action") == "done" or action.get("type") == "done")
            for action in planned_actions
        )

        # Get existing history early (needed for multiple return paths)
        existing_history = state.get("history", [])

        # Browser-use pattern: Title and URL are ALREADY in browser_state (<browser_state>)
        # System prompt says: "Call extract only if the information you are looking for is not visible
        # in your <browser_state> otherwise always just use the needed text from the <browser_state>."
        # So if LLM tries to extract title/URL, auto-complete since they're already available
        extract_actions = [a for a in planned_actions if isinstance(a, dict) and a.get("action") == "extract"]
        for extract_action in extract_actions:
            query = str(extract_action.get("query", "")).lower()
            # Check if query asks for title/URL (which are already in browser state)
            if ("title" in query and "url" in query) or ("page title" in query and "url" in query) or \
               (query == "extract the page title and url"):
                # Check if we're on a valid page (not about:blank or empty)
                if current_url and current_url not in ["about:blank", ""] and current_title:
                    logger.info("LLM wants to extract title/URL - these are already in browser_state, auto-completing")
                    # Auto-complete with the current title and URL (browser-use pattern)
                    done_message = f"Task completed. Page title: {current_title}, URL: {current_url}"
                    print(f"\n✅ Auto-completing: Title and URL are already in browser state - {done_message}")
                    logger.info(f"Auto-completed task: {done_message}")
                    
                    # Mark as completed
                    log_data["task_completed"] = True
                    log_data["completion_message"] = done_message
                    
                    with open(log_file, "w") as f:
                        json.dump(log_data, f, indent=2)
                    
                    return {
                        "step_count": step_count,
                        "planned_actions": [],  # No actions needed - title/URL already available
                        "completed": True,
                        "browser_state_summary": browser_state_summary,
                        "dom_selector_map": selector_map,
                        "history": [{  # operator.add will append to existing
                            "step": step_count,
                            "node": "think",
                            "planned_actions": [],
                            "task_completed": True,
                            "completion_message": done_message,
                        }],
                        "current_goal": f"Task completed: {done_message[:50]}",
                    }

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
                "previous_url": current_url,  # Store for next step comparison
                "previous_element_count": len(selector_map),  # Store for next step comparison
                "history": [{  # operator.add will append to existing
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
        # Store structured fields for proper history formatting (browser-use HistoryItem format)
        existing_history = state.get("history", [])
        new_history_entry = {
            "step": step_count,
            "node": "think",
            "browser_state": browser_state_summary,
            "planned_actions": valid_actions,
            "llm_response_preview": parsed.model_dump_json()[:200] if parsed else None,
            "evaluation_previous_goal": evaluation_previous_goal,  # For history formatting
            "memory": memory,  # For history formatting
            "next_goal": next_goal,  # For history formatting
            "thinking": thinking,  # For future use
        }
        
        # Build current goal with more context for retries
        if is_retry:
            # On retry, provide more context about current state
            current_goal = f"Retry step {step_count} - Current page: {current_title[:30]} ({current_url[:50]})"
            if valid_actions:
                current_goal += f" - Next: {valid_actions[0].get('action', 'unknown')}"
        else:
            current_goal = f"Executing step {step_count}: {valid_actions[0].get('reasoning', '')[:50] if valid_actions else ''}"
        
        # Clear tab switch flag after processing (so it doesn't persist to next step)
        state_updates = {
            "step_count": step_count,
            "planned_actions": valid_actions,
            "browser_state_summary": browser_state_summary,
            "dom_selector_map": selector_map,  # Cache for ACT node element lookups
            "history": [new_history_entry],  # operator.add will append to existing
            "current_goal": current_goal,
            "previous_url": current_url,  # Track URL for next step to detect tab/URL changes
            "previous_element_count": len(selector_map),  # Track element count for dynamic loading detection
            # Goal tracking updates
            "completed_goals": completed_goals,
            "current_goal_index": current_goal_index,
        }
        
        # Clear tab switch flags after processing
        if just_switched_tab:
            state_updates["just_switched_tab"] = False
            state_updates["tab_switch_url"] = None
            state_updates["tab_switch_title"] = None
        
        # Clear fresh_state_available flag after using it (so it doesn't persist)
        if fresh_state_available:
            state_updates["fresh_state_available"] = False
            state_updates["page_changed"] = False
        
        return state_updates
    except Exception as e:
        logger.error(f"Error in think node: {e}", exc_info=True)
        return {
            "error": f"Think node error: {str(e)}",
            "step_count": state.get("step_count", 0),
            "planned_actions": [],
        }

