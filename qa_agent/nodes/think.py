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
from qa_agent.prompts.browser_use_prompts import SystemPrompt, AgentMessagePrompt

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
        
        # Get browser state from browser BrowserSession
        from qa_agent.utils.session_registry import get_session

        browser_session_id = state.get("browser_session_id")
        if not browser_session_id:
            raise ValueError("No browser_session_id in state - INIT node must run first")

        browser_session = get_session(browser_session_id)
        if not browser_session:
            raise ValueError(f"Browser session {browser_session_id} not found in registry")

        # Get browser state summary with DOM extraction (browser native call)
        # browser pattern: ALWAYS get fresh state at start of each step (see agent/service.py _prepare_context)
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

            # FIX: Use the ACTUAL BrowserStateSummary object ACT already fetched
            # This eliminates the "1 step ahead" race condition
            browser_state = state.get("fresh_browser_state_object")

            if browser_state:
                logger.info("✅ Using ACTUAL fresh_browser_state_object from ACT (no re-fetch, perfect sync)")
                act_node_url = state.get("current_url")
                if act_node_url and browser_state.url == act_node_url:
                    logger.info(f"✅ URL verified: {act_node_url[:60]}")
            else:
                # Fallback: ACT didn't pass the object (older code), fetch it
                logger.warning("⚠️ fresh_browser_state_object not found, falling back to re-fetch")
                browser_state = await browser_session.get_browser_state_summary(
                    include_screenshot=False,
                    include_recent_events=False,
                    cached=False
                )
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

        # Extract DOM data for logging/history (browser handles DOM internally in AgentMessagePrompt)
        current_url = browser_state.url
        current_title = browser_state.title
        # Defensive check: ensure selector_map is always a dict (browser should return dict)
        selector_map = {}
        if browser_state.dom_state and hasattr(browser_state.dom_state, 'selector_map'):
            selector_map_raw = browser_state.dom_state.selector_map
            if isinstance(selector_map_raw, dict):
                selector_map = selector_map_raw
            else:
                logger.warning(f"selector_map is not a dict (type: {type(selector_map_raw)}), using empty dict")
        
        # Check for new tabs opened by previous actions (browser pattern: check tabs from state)
        # This ensures we're aware of tabs opened by actions, even if we haven't switched yet
        # Defensive check: ensure current_tabs is always a list
        current_tabs = []
        if browser_state.tabs:
            if isinstance(browser_state.tabs, list):
                current_tabs = browser_state.tabs
            else:
                logger.warning(f"browser_state.tabs is not a list (type: {type(browser_state.tabs)}), using empty list")
        tab_info = [{"id": t.target_id[-4:], "title": t.title, "url": t.url} for t in current_tabs]
        
        # Detect if this is a retry after failure OR if we just switched tabs (browser pattern: always verify current state)
        history = state.get("history", [])
        is_retry = False
        just_switched_tab = state.get("just_switched_tab", False)
        tab_switch_url = state.get("tab_switch_url")
        tab_switch_title = state.get("tab_switch_title")
        previous_url = None
        previous_tab_id = None
        
        # Check if verify node just switched tabs (browser pattern: fresh state is automatically sent)
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
                    # browser pattern: compare current state with previous state to detect changes
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
        
        # browser pattern: get_browser_state_summary() already handles:
        # - URL detection via get_current_page_url() (CDP-based, reliable)
        # - Network idle detection via DOMWatchdog._get_pending_network_requests()
        # - Page stability waiting (1s if pending requests exist)
        # - DOM building and element extraction
        # We trust browser's built-in mechanisms - no need to re-implement URL/page loading detection
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

        # GOAL TRACKING: Page state detection + informational context (Phase 4: browser pattern)
        # Goals track major phase transitions (e.g., "we're on dashboard, signup done")
        # LLM sees goals in history/context but decides next steps via todo.md and next_goal field
        # This matches browser pattern: goals inform LLM, but LLM generates next_goal itself
        goals = state.get("goals", [])
        completed_goals = state.get("completed_goals", [])
        current_goal_index = state.get("current_goal_index", 0)
        new_completed_goal_id = None  # Track if we completed a goal this step

        # Track goals for informational context - LLM can see them in history
        # But don't modify task context - LLM manages progression via todo.md
        if goals and current_goal_index < len(goals):
            current_goal_obj = goals[current_goal_index]
            goal_id = current_goal_obj.get("id", "")
            goal_desc = current_goal_obj.get("description", "")
            completion_signals = current_goal_obj.get("completion_signals", [])

            logger.info(f"📊 GOAL TRACKING: {len(completed_goals)}/{len(goals)} goals completed, current index: {current_goal_index}")
            logger.info(f"   Current goal: [{goal_id}] {goal_desc}")

            # Check if current goal appears complete based on page state (URL/title)
            # This detects major phase transitions (e.g., "now on dashboard")
            current_url_str = current_url or ""
            current_title_str = current_title or ""
            is_goal_complete = any(
                signal.lower() in current_url_str.lower() or signal.lower() in current_title_str.lower()
                for signal in completion_signals
            )

            logger.info(f"   URL: {current_url}")
            logger.info(f"   Title: {current_title}")
            logger.info(f"   Goal complete? {is_goal_complete}")

            if is_goal_complete and goal_id not in completed_goals:
                # Goal phase detected - track it for informational context
                logger.info(f"🎯 Goal '{goal_id}' COMPLETED! (detected by URL/title signals)")
                logger.info(f"   Progress: {len(completed_goals) + 1}/{len(goals)} goals completed")
                
                # Track completion for state consistency (reducer will append)
                new_completed_goal_id = goal_id
                current_goal_index = current_goal_index + 1
                completed_goals = completed_goals + [goal_id]  # For local use, reducer handles accumulation

                # Informational context: Show what's been completed and what's next
                # This helps LLM understand phase transitions, but LLM still decides actions via todo.md
                if current_goal_index < len(goals):
                    next_goal_obj = goals[current_goal_index]
                    next_goal_desc = next_goal_obj.get("description", "")
                    logger.info(f"   Next goal phase: {next_goal_desc}")
                    # Note: We log this but don't modify task - LLM sees goals in history
                else:
                    logger.info(f"   ✅ ALL GOAL PHASES COMPLETED!")
                    # Note: LLM still manages final steps via todo.md
            else:
                # Goal still in progress - log for context
                if completed_goals:
                    logger.info(f"💡 Current phase: {goal_desc} (already completed {len(completed_goals)} phases)")
                else:
                    logger.info(f"💡 Starting first phase: {goal_desc}")

        # browser pattern: On retry, emphasize that LLM should use CURRENT browser_state
        # The browser_state sent in this step contains FRESH element indices from the current page
        # Human QA approach: Look at the page, see what's there, then interact with the right elements
        if is_retry:
            logger.info(f"🔄 RETRY STEP {step_count}: Sending fresh browser_state with {len(selector_map)} interactive elements")
            logger.info(f"   LLM will see CURRENT page state and can adapt actions based on what's actually available")
            logger.info(f"   Previous failure context is included in agent_history above")

        # Build prompt using browser SystemPrompt and AgentMessagePrompt
        logger.info(f"Building prompt for task using browser prompts: {task[:100]}...")

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

        # Format history for agent_history_description (browser HistoryItem format)
        # browser format: <step_N>\nevaluation\nmemory\nnext_goal\nResult\naction_results\n</step_N>
        agent_history_description = ""
        read_state_description = ""  # Track extract() results separately (browser pattern)
        read_state_idx = 0
        
        if history:
            # Get last 5 steps (browser uses max_history_items)
            recent_steps = history[-5:]
            for step_entry in recent_steps:
                step_num = step_entry.get("step", 0)
                node = step_entry.get("node", "unknown")
                
                # Build HistoryItem format (browser pattern)
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
                        # browser pattern: prefer long_term_memory, fallback to extracted_content
                        long_term_memory = result.get("long_term_memory")
                        extracted_content = result.get("extracted_content")
                        include_only_once = result.get("include_extracted_content_only_once", False)
                        error = result.get("error")
                        
                        # Handle read_state (extract() results) - browser pattern
                        if include_only_once and extracted_content:
                            read_state_description += f'<read_state_{read_state_idx}>\n{extracted_content}\n</read_state_{read_state_idx}>\n'
                            read_state_idx += 1
                        
                        # Build action_results text (browser pattern)
                        if long_term_memory:
                            action_results_text += f'{long_term_memory}\n'
                        elif extracted_content and not include_only_once:
                            # Detect if extracted_content contains error-like messages
                            # Some actions return error messages via extracted_content (e.g., "Element index X not available")
                            error_indicators = [
                                "not available",
                                "not found",
                                "failed",
                                "error",
                                "cannot",
                                "unable",
                                "invalid",
                                "does not exist",
                                "not available - page may have changed"
                            ]
                            is_error_message = any(indicator.lower() in extracted_content.lower() for indicator in error_indicators)
                            
                            if is_error_message:
                                # Format as error so LLM recognizes it as a failure
                                error_text = extracted_content[:200] + '......' + extracted_content[-100:] if len(extracted_content) > 200 else extracted_content
                                action_results_text += f'Error: {error_text}\n'
                            else:
                                action_results_text += f'{extracted_content}\n'
                        
                        if error:
                            error_text = error[:200] + '......' + error[-100:] if len(error) > 200 else error
                            action_results_text += f'Error: {error_text}\n'

                    # FORM INCOMPLETE WARNING: Add explicit instructions if form has issues
                    form_incomplete = state.get("form_incomplete", False)
                    form_state = state.get("form_state", {})
                    validation_errors_count = state.get("validation_errors_count", 0)
                    blocking_errors_count = state.get("blocking_errors_count", 0)

                    if form_incomplete and (validation_errors_count > 0 or blocking_errors_count > 0):
                        # Add explicit form completion warning
                        incomplete_fields = form_state.get("required_empty_fields", [])
                        validation_errors = form_state.get("validation_errors", [])

                        form_warning = "\n⚠️ FORM INCOMPLETE - MUST FIX BEFORE PROCEEDING:\n"
                        if validation_errors:
                            form_warning += f"  • Validation errors: {'; '.join(validation_errors[:2])}\n"
                        if incomplete_fields:
                            field_labels = [f['label'] for f in incomplete_fields[:3]]
                            form_warning += f"  • {len(incomplete_fields)} required fields still empty: {', '.join(field_labels)}"
                            if len(incomplete_fields) > 3:
                                form_warning += f", +{len(incomplete_fields)-3} more"
                            form_warning += "\n"
                        form_warning += "  • DO NOT click Submit or navigate away until form is complete\n"
                        form_warning += "  • Review CURRENT <browser_state> to see correct field indices\n"
                        form_warning += "  • Fix validation errors FIRST, then fill remaining required fields\n"

                        action_results_text += form_warning

                    if action_results_text:
                        step_content_parts.append(f'Result\n{action_results_text.strip()}')
                
                # Add verification failure details (critical for retry - LLM needs to know WHY it failed)
                # browser pattern: On retry, LLM sees fresh browser_state with CURRENT element indices
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
                            # browser pattern: Guide LLM to use CURRENT browser_state (sent in this step)
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

                # Format as browser HistoryItem: <step_N>...</step_N>
                if step_content_parts:
                    content = '\n'.join(step_content_parts)
                    agent_history_description += f'<step_{step_num}>\n{content}\n</step_{step_num}>\n'

        # Inject tab switch system message if we just switched tabs
        # This ensures LLM sees the warning BEFORE processing the new browser_state
        if tab_switch_system_message:
            agent_history_description += f'\n{tab_switch_system_message}\n'

        # Clean up read_state_description
        read_state_description = read_state_description.strip('\n') if read_state_description else None

        # Get page-filtered actions (browser pattern: show only relevant actions per page)
        page_filtered_actions = None
        try:
            from qa_agent.tools.service import Tools
            tools = Tools()
            page_filtered_actions = tools.registry.get_prompt_description(page_url=current_url)
        except Exception as e:
            logger.debug(f"Could not get page-filtered actions: {e}")
        
        # browser pattern: Force done action after max_failures (service.py:902-913)
        # Check if we've reached max consecutive failures
        consecutive_failures = state.get("consecutive_failures", 0)
        max_failures = state.get("max_failures", 3)
        final_response_after_failure = state.get("final_response_after_failure", True)

        # browser pattern: Don't add hard-coded guidance - just send the browser state
        # The LLM will analyze the current browser_state and decide actions based on what it sees
        # If we switched tabs, the browser_state already contains the new page's elements
        # The LLM can see all interactive elements and their indices, so it can adapt dynamically
        enhanced_task = task

        # Force done action after max failures (browser pattern: service.py:905-913)
        if consecutive_failures >= max_failures and final_response_after_failure:
            logger.warning(f"🛑 Max consecutive failures reached ({consecutive_failures}/{max_failures}), forcing done action")
            # Create forced done message (browser pattern)
            force_done_msg = f'You failed {max_failures} times. Therefore we terminate the agent.\n'
            force_done_msg += 'Your only tool available is the "done" tool. No other tool is available. All other tools which you see in history or examples are not available.\n'
            force_done_msg += 'If the task is not yet fully finished as requested by the user, set success in "done" to false! E.g. if not all steps are fully completed. Else success to true.\n'
            force_done_msg += 'Include everything you found out for the ultimate task in the done text.\n'
            force_done_msg += f'\nOriginal task: {task}'
            enhanced_task = force_done_msg
        
        # Restore or create file system for extract() action support
        # browser pattern: FileSystem handles saving extracted content to files
        # CRITICAL: Persist FileSystem state across steps for todo.md tracking
        from qa_agent.filesystem.file_system import FileSystem
        from pathlib import Path
        
        # Restore FileSystem from state if it exists (Phase 1: FileSystem persistence)
        file_system_state = state.get("file_system_state")
        if file_system_state:
            # Restore existing FileSystem from persisted state
            file_system = FileSystem.from_state(file_system_state)
            logger.debug("Restored FileSystem from state (todo.md preserved)")
        else:
            # Create new FileSystem on first step
            # CRITICAL: Don't clean data_dir if it already exists (might have files from INIT)
            file_system_dir = Path("qa_agent_workspace") / f"session_{browser_session_id[:8]}"
            file_system = FileSystem(base_dir=file_system_dir, create_default_files=True, clean_data_dir=False)
            logger.debug("Created new FileSystem (first step, preserving existing files)")

        # Phase 3 + 4: Robust task context enhancement with conflict resolution
        # Priority system: todo.md (PRIMARY) + goals (SECONDARY hints)
        # This makes our QA agent better than browser by providing page state hints
        # while maintaining LLM-driven task progression via todo.md
        
        # Start with original task
        enhanced_task = task
        
        # Step 1: Build goal context (informational hints, not task modification)
        goal_context = ""
        if goals and (completed_goals or current_goal_index < len(goals)):
            goal_context = "\n📊 PAGE STATE HINTS (informational - may not align with todo.md):\n"
            if completed_goals:
                goal_context += f"  ✅ Detected phases: {', '.join(completed_goals)}\n"
            if current_goal_index < len(goals):
                current_goal_obj = goals[current_goal_index]
                goal_context += f"  📍 Current phase hint: {current_goal_obj.get('description', '')}\n"
            goal_context += "  ⚠️ Note: These are page state detection hints. Task progression is tracked via todo.md below.\n"
            goal_context += "  💡 If hints conflict with todo.md, trust todo.md (it's LLM-driven and more accurate).\n"
        
        # Step 2: Build todo.md context (PRIMARY - LLM-driven task progression)
        todo_context = ""
        if file_system and not (consecutive_failures >= max_failures and final_response_after_failure):
            try:
                todo_content = file_system.get_todo_contents()
                # Check if todo.md is empty or just the default placeholder
                is_empty = not todo_content or todo_content.strip() == '' or todo_content.strip() == '[empty todo.md, fill it when applicable]'
                
                if not is_empty:
                    # Parse completed vs remaining items from todo.md (handle malformed checkboxes)
                    import re
                    completed_items = []
                    remaining_items = []
                    for line in todo_content.split('\n'):
                        line_stripped = line.strip()
                        
                        # Handle malformed checkboxes (e.g., "- [x] - [ ]" should be cleaned)
                        # Remove ALL checkbox patterns until we find the actual step text
                        cleaned_line = line_stripped
                        while re.match(r'^\s*-\s*\[[xX ]\]\s*', cleaned_line):
                            cleaned_line = re.sub(r'^\s*-\s*\[[xX ]\]\s*', '', cleaned_line)
                        
                        # Check if this is a todo line (has checkbox pattern)
                        if line_stripped.startswith('- [') and ('[ ]' in line_stripped or '[x]' in line_stripped or '[X]' in line_stripped):
                            # Determine if completed or remaining based on checkbox state
                            has_checked = '[x]' in line_stripped or '[X]' in line_stripped
                            has_unchecked = '[ ]' in line_stripped
                            
                            # Extract item text (after removing all checkbox patterns)
                            item_text = cleaned_line.strip()
                            
                            if item_text:
                                # If it has checked checkbox and no unchecked, it's completed
                                if has_checked and not has_unchecked:
                                    completed_items.append(item_text)
                                # If it has unchecked checkbox (even if also has checked - malformed), it's remaining
                                elif has_unchecked:
                                    remaining_items.append(item_text)
                                # Edge case: if only checked exists, mark as completed
                                elif has_checked:
                                    completed_items.append(item_text)
                    
                    # Build todo.md context (PRIMARY)
                    if completed_items or remaining_items:
                        todo_context = "✅ TASK PROGRESSION (from todo.md - PRIMARY source):\n\n"
                        
                        if completed_items:
                            todo_context += "✅ COMPLETED STEPS:\n"
                            # Show max 5 completed items to avoid context overload
                            for item in completed_items[:5]:
                                todo_context += f"  ✓ {item}\n"
                            if len(completed_items) > 5:
                                todo_context += f"  ... and {len(completed_items) - 5} more completed\n"
                            todo_context += "\n"
                        
                        if remaining_items:
                            todo_context += "📍 REMAINING STEPS:\n"
                            # Show max 10 remaining items
                            for item in remaining_items[:10]:
                                todo_context += f"  → {item}\n"
                            if len(remaining_items) > 10:
                                todo_context += f"  ... and {len(remaining_items) - 10} more remaining\n"
                            todo_context += "\n"
                        
                        logger.info(f"Enhanced task context with todo.md progress: {len(completed_items)} completed, {len(remaining_items)} remaining")
                    else:
                        # todo.md exists but has no checklist items - might be malformed
                        logger.warning("todo.md exists but has no checklist items - might be empty or malformed")
                else:
                    # todo.md is empty - INIT should have created it, but didn't
                    logger.warning("todo.md is empty - INIT node should have created it. LLM will need to create it.")
            except Exception as e:
                # If todo.md parsing fails, just skip enhancement (don't break prompt)
                logger.debug(f"Could not enhance task context with todo.md: {e}")
        
        # Phase 1: Add action context if available (shows which action caused new elements)
        action_context = state.get("action_context")
        action_context_text = ""
        if action_context:
            action_type = action_context.get("action_type", "unknown")
            action_index = action_context.get("action_index")
            new_elements_count = action_context.get("new_elements_count", 0)
            
            if new_elements_count > 0:
                action_context_text = f"\n<action_context>\n"
                action_context_text += f"Last action: {action_type}"
                if action_index:
                    action_context_text += f" on element {action_index}"
                action_context_text += f"\nNew elements appeared: {new_elements_count} elements (marked with *[index])\n"
                action_context_text += f"These elements are likely in a container opened by your last action.\n"
                action_context_text += f"When multiple elements match your goal, prioritize these NEW elements.\n"
                action_context_text += f"</action_context>\n"
                logger.info(f"📊 Adding action context: {action_type} → {new_elements_count} new elements")
        
        # Step 3: Merge with priority (todo.md first, then action context, then goals, then full task)
        if todo_context:
            # Priority: todo.md context (PRIMARY)
            enhanced_task = f"{todo_context}📋 FULL TASK (for reference):\n{task}"
            if action_context_text:
                # Add action context after todo (high priority for element selection)
                enhanced_task = f"{todo_context}{action_context_text}📋 FULL TASK (for reference):\n{task}"
            if goal_context:
                # Add goal hints as secondary information
                enhanced_task += goal_context
        elif action_context_text:
            # Fallback: Action context if no todo.md
            enhanced_task = f"{action_context_text}{task}"
            if goal_context:
                enhanced_task += goal_context
        elif goal_context:
            # Fallback: Only goals if no todo.md or action context
            enhanced_task = f"{task}{goal_context}"
        # else: enhanced_task = task (no enhancement)

        # Create AgentMessagePrompt (uses BrowserStateSummary directly!)
        agent_message_prompt = AgentMessagePrompt(
            browser_state_summary=browser_state,  # Pass the actual BrowserStateSummary object
            file_system=file_system,  # FileSystem for extract() action and file operations
            agent_history_description=agent_history_description,
            read_state_description=read_state_description,  # Extract() results (browser pattern)
            task=enhanced_task,  # Use enhanced task with tab switch context if applicable
            include_attributes=None,  # Use default attributes
            step_info=step_info,
            page_filtered_actions=page_filtered_actions,  # Page-specific actions (browser pattern)
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
        # browser pattern: AgentMessagePrompt.get_user_message() includes:
        # - <agent_history> with previous steps
        # - <agent_state> with user_request, step_info, etc.
        # - <browser_state> with FULL DOM structure via llm_representation() - ALL interactive elements with indices
        # - <read_state> if extract() was called
        # - <page_specific_actions> filtered by current URL
        # The LLM sees the complete page structure BEFORE deciding actions - just like human QA analyzes the page first
        system_message = system_prompt.get_system_message()
        user_message = agent_message_prompt.get_user_message(use_vision=False)
        
        # Log that LLM is receiving full DOM structure (for debugging/verification)
        # browser pattern: AgentMessagePrompt includes FULL DOM via llm_representation()
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
        print(f"📤 SENDING TO LLM (Step {step_count}) - Using browser prompts")
        print(f"{'='*80}")
        print(f"\n📝 System Message (browser):\n{system_content[:500]}...")
        print(f"\n💬 User Message (browser):\n{user_content[:500]}...")
        print(f"\n💾 Saving prompt to: {log_file}")

        # Initialize LLM and call
        logger.info("Calling LLM to generate action plan with browser prompts...")
        llm = get_llm()

        # Convert browser messages to LangChain format
        from langchain_core.messages import SystemMessage as LCSystemMessage, HumanMessage
        langchain_messages = [
            LCSystemMessage(content=system_content),
            HumanMessage(content=user_content if isinstance(user_content, str) else str(user_content))
        ]

        # Call LLM with structured output (LangChain pattern)
        from qa_agent.views import AgentOutput

        # Create dynamic ActionModel with current page's actions (browser pattern)
        # This gives LLM precise schema of available actions
        action_model = tools.registry.create_action_model(page_url=current_url)

        # Create dynamic AgentOutput with the action model
        dynamic_agent_output = AgentOutput.type_with_custom_actions(action_model)

        print(f"\n🤖 Calling LLM ({settings.llm_model}) with structured output...")
        logger.info(f"Using dynamic ActionModel with {len([a for a in tools.registry.registry.actions.keys()])} registered actions")

        # LangChain uses with_structured_output() method, NOT output_format parameter
        # Use function_calling method for OpenAI compatibility with complex nested schemas
        structured_llm = llm.with_structured_output(dynamic_agent_output, method="function_calling")
        raw_response = await structured_llm.ainvoke(langchain_messages)
        
        # browser pattern: Manually validate the response to match schema (chat_browser_use.py:178)
        # LangChain's with_structured_output() may return dict or Pydantic model
        # Convert to dict if needed, then validate against AgentOutput schema
        try:
            if isinstance(raw_response, dict):
                # Already a dict - validate directly
                completion_data = raw_response
            else:
                # Pydantic model or other object - convert to dict
                completion_data = raw_response.model_dump() if hasattr(raw_response, 'model_dump') else dict(raw_response)
            
            # Validate against schema (browser pattern)
            parsed: AgentOutput = dynamic_agent_output.model_validate(completion_data)
        except Exception as e:
            logger.error(f"Failed to validate LLM response against AgentOutput schema: {e}")
            logger.error(f"Raw response type: {type(raw_response)}")
            logger.error(f"Raw response value: {raw_response}")
            # Re-raise as ValidationError to match browser pattern
            from pydantic import ValidationError
            raise ValidationError(f"LLM response validation failed: {e}") from e

        logger.info(f"LLM response received and validated: {parsed}")

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

        # parsed.action is already list[ActionModel] - use directly!
        # LangChain with_structured_output() returns validated Pydantic objects
        # No conversion needed - act node can use ActionModel objects directly
        planned_actions = parsed.action

        logger.info(f"✅ Structured output: {len(planned_actions)} actions extracted")
        for i, action in enumerate(planned_actions, 1):
            logger.debug(f"  Action {i}: {action}")

        # With structured output, no JSON parsing or error handling needed!
        # The LLM provider validates the response against the Pydantic schema
        
        logger.debug(f"Parsed {len(planned_actions)} actions: {planned_actions}")

        # Save parsed actions (convert ActionModel to dict for JSON serialization)
        log_data["parsed_actions"] = [a.model_dump(exclude_unset=True) for a in planned_actions]
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
        
        # Check for "done" action from LLM
        # planned_actions is list[ActionModel] - check using model_dump()
        has_done_action = any(
            "done" in action.model_dump(exclude_unset=True)
            for action in planned_actions
        )

        # Get existing history early (needed for multiple return paths)
        existing_history = state.get("history", [])

        # browser pattern: Title and URL are ALREADY in browser_state (<browser_state>)
        # System prompt says: "Call extract only if the information you are looking for is not visible
        # in your <browser_state> otherwise always just use the needed text from the <browser_state>."
        # So if LLM tries to extract title/URL, auto-complete since they're already available
        extract_actions = [a for a in planned_actions if "extract" in a.model_dump(exclude_unset=True)]
        for extract_action in extract_actions:
            action_dump = extract_action.model_dump(exclude_unset=True)
            extract_params = action_dump.get("extract", {})
            query = str(extract_params.get("query", "")).lower()
            # Check if query asks for title/URL (which are already in browser state)
            if ("title" in query and "url" in query) or ("page title" in query and "url" in query) or \
               (query == "extract the page title and url"):
                # Check if we're on a valid page (not about:blank or empty)
                if current_url and current_url not in ["about:blank", ""] and current_title:
                    logger.info("LLM wants to extract title/URL - these are already in browser_state, auto-completing")
                    # Auto-complete with the current title and URL (browser pattern)
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
                if "done" in a.model_dump(exclude_unset=True)
            ), None)
            if done_action:
                done_params = done_action.model_dump(exclude_unset=True).get("done", {})
                done_message = done_params.get("text", "Task completed")
            else:
                done_message = "Task completed"
            print(f"\n✅ LLM signaled task completion: {done_message}")
            logger.info(f"LLM completed task: {done_message}")
            
            # Save completion (convert ActionModel to dict for JSON serialization)
            log_data["validated_actions"] = [a.model_dump(exclude_unset=True) for a in planned_actions]
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
        
        # No validation needed - LangChain with_structured_output() already validated via Pydantic
        # ActionModel objects are guaranteed to be valid by the Pydantic schema
        valid_actions = planned_actions

        # Save validated actions (convert to dicts for JSON serialization in logs)
        log_data["validated_actions"] = [a.model_dump(exclude_unset=True) for a in valid_actions]

        if not valid_actions:
            logger.error("No actions returned from LLM response.")
            print("\n❌ ERROR: No actions returned from LLM response!")

            # Save error to log file
            log_data["error"] = "No actions parsed"
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2)

            return {
                "error": "No actions returned from LLM response.",
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
        # Store structured fields for proper history formatting (browser HistoryItem format)
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
                first_action_dump = valid_actions[0].model_dump(exclude_unset=True)
                action_name = list(first_action_dump.keys())[0] if first_action_dump else 'unknown'
                current_goal += f" - Next: {action_name}"
        else:
            if valid_actions:
                first_action_dump = valid_actions[0].model_dump(exclude_unset=True)
                # Try to get reasoning from action params if available
                action_params = list(first_action_dump.values())[0] if first_action_dump else {}
                reasoning = action_params.get('reasoning', '') if isinstance(action_params, dict) else ''
                current_goal = f"Executing step {step_count}: {reasoning[:50]}"
            else:
                current_goal = f"Executing step {step_count}"
        
        # Action repetition detection (prevent infinite loops of same action)
        # Compare current action with previous action from history
        previous_action = None
        if existing_history:
            # Get most recent think node action (stored as ActionModel in state)
            for entry in reversed(existing_history):
                if entry.get("node") == "think" and entry.get("planned_actions"):
                    prev_actions = entry["planned_actions"]
                    previous_action = prev_actions[0] if prev_actions else None
                    break

        current_action = valid_actions[0] if valid_actions else None
        action_repetition_count = state.get("action_repetition_count", 0)

        # Check if repeating same action (same action type and same index)
        if previous_action and current_action:
            # Both are ActionModel objects - compare their dumps
            prev_dump = previous_action.model_dump(exclude_unset=True) if hasattr(previous_action, 'model_dump') else previous_action
            curr_dump = current_action.model_dump(exclude_unset=True)

            # Get action name and index from both
            prev_action_name = list(prev_dump.keys())[0] if prev_dump else None
            curr_action_name = list(curr_dump.keys())[0] if curr_dump else None

            if prev_action_name == curr_action_name:
                prev_params = prev_dump.get(prev_action_name, {}) if isinstance(prev_dump, dict) else {}
                curr_params = curr_dump.get(curr_action_name, {})
                prev_index = prev_params.get('index') if isinstance(prev_params, dict) else None
                curr_index = curr_params.get('index')

                if prev_index is not None and prev_index == curr_index:
                    action_repetition_count += 1
                    logger.warning(f"⚠️ Action repeated {action_repetition_count} times: {curr_action_name} on index {curr_index}")

                    # Force done if repeated 3+ times
                    if action_repetition_count >= 3:
                        logger.error(f"🛑 Action repeated {action_repetition_count} times, forcing completion")
                        return {
                            "error": f"Action '{curr_action_name}' on index {curr_index} repeated {action_repetition_count} times without success",
                            "completed": True,
                            "step_count": step_count,
                        }
                else:
                    # Different index - reset counter
                    action_repetition_count = 0
            else:
                # Different action - reset counter
                action_repetition_count = 0
        else:
            action_repetition_count = 0

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
            # Note: completed_goals uses reducer (operator.add), so we return only NEW items
            # The reducer will append them to the existing list automatically
            "completed_goals": [new_completed_goal_id] if new_completed_goal_id else [],
            "current_goal_index": current_goal_index,
            # Action repetition tracking
            "action_repetition_count": action_repetition_count,
        }
        
        # Clear tab switch flags after processing
        if just_switched_tab:
            state_updates["just_switched_tab"] = False
            state_updates["tab_switch_url"] = None
            state_updates["tab_switch_title"] = None
        
        # Clear fresh_state_available flag after using it (so it doesn't persist)
        if fresh_state_available:
            state_updates["fresh_state_available"] = False
            state_updates["fresh_browser_state_object"] = None  # Clear object to free memory
            state_updates["page_changed"] = False
        
        # CRITICAL: Persist FileSystem state for todo.md tracking (Phase 1)
        # Save FileSystem state so it persists across steps
        file_system_state = file_system.get_state()
        state_updates["file_system_state"] = file_system_state
        logger.debug("Saved FileSystem state (todo.md will persist)")
        
        return state_updates
    except Exception as e:
        logger.error(f"Error in think node: {e}", exc_info=True)
        return {
            "error": f"Think node error: {str(e)}",
            "step_count": state.get("step_count", 0),
            "planned_actions": [],
        }

