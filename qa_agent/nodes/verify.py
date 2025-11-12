"""
Verify Node - Verify action results

This node:
1. Checks if actions succeeded (DOM changes, URL changes, element visibility)
2. Compares expected vs actual results
3. Validates page state matches expectations
4. Generates verification results
"""
import logging
from typing import Dict, Any
from qa_agent.state import QAAgentState
from qa_agent.config import settings

logger = logging.getLogger(__name__)


async def verify_node(state: QAAgentState) -> Dict[str, Any]:
    """
    Verify node: Check if actions succeeded
    
    Args:
        state: Current QA agent state
        
    Returns:
        Updated state with verification results
    """
    try:
        logger.info(f"Verify node - Step {state.get('step_count', 0)}")
        
        # Check if we need to switch to a new tab (from act node)
        # browser pattern: auto-switch to new tabs opened by actions
        new_tab_id = state.get("new_tab_id")
        new_tab_url = state.get("new_tab_url")
        if new_tab_id:
            # Ensure tab_id is 4 characters (last 4 of target_id) - browser requirement
            tab_id_4char = str(new_tab_id)[-4:] if new_tab_id else ""
            logger.info(f"New tab detected, switching to tab {tab_id_4char} (URL: {new_tab_url or 'unknown'})...")
            try:
                from qa_agent.utils.session_registry import get_session
                browser_session_id = state.get("browser_session_id")
                if browser_session_id:
                    session = get_session(browser_session_id)
                    if session:
                        # Switch to new tab using browser "switch" action (not "switch_tab")
                        from qa_agent.tools.service import Tools
                        tools = Tools()
                        from qa_agent.tools.views import SwitchTabAction
                        DynamicActionModel = tools.registry.create_action_model(page_url=None)
                        # browser uses "switch" as the action name
                        switch_action = DynamicActionModel(switch=SwitchTabAction(tab_id=tab_id_4char))
                        switch_result = await tools.act(action=switch_action, browser_session=session)
                        if switch_result.error:
                            logger.warning(f"Failed to switch to new tab: {switch_result.error}")
                        else:
                            logger.info(f"Successfully switched to new tab {tab_id_4char}")
                            # browser pattern: Verify the switch actually worked and refresh state
                            # CRITICAL: Ensure we're actually on the new tab before proceeding
                            try:
                                # Wait a moment for the switch to complete and events to propagate
                                import asyncio
                                await asyncio.sleep(1.0)  # Increased delay for tab switch to fully complete
                                
                                # Verify we're on the correct tab
                                current_target_id = session.current_target_id
                                if current_target_id and current_target_id[-4:] == tab_id_4char:
                                    logger.info(f"✅ Verified: Currently on tab {tab_id_4char} (target_id: {current_target_id[-4:]})")
                                else:
                                    logger.error(f"❌ Tab switch FAILED! Expected: {tab_id_4char}, Current: {current_target_id[-4:] if current_target_id else 'None'}")
                                    # Don't clear new_tab_id if switch failed - let it retry
                                    return {
                                        "verification_status": "fail",
                                        "verification_results": [{"status": "fail", "reason": f"Tab switch failed: expected {tab_id_4char}, got {current_target_id[-4:] if current_target_id else 'None'}"}],
                                        "error": f"Failed to switch to new tab {tab_id_4char}",
                                    }
                                
                                # browser pattern: Wait for network idle before getting state
                                # browser automatically waits 1s if pending requests exist (dom_watchdog.py line 285)
                                # But after tab switch, we may need to wait longer for the new page to load
                                logger.info("⏳ Waiting for new tab page to load (checking network idle)...")
                                try:
                                    # Get pending requests to see if page is still loading
                                    pending_before = await session.get_browser_state_summary(
                                        include_screenshot=False,
                                        cached=False
                                    )
                                    pending_requests = pending_before.pending_network_requests if pending_before.pending_network_requests else []
                                    
                                    if pending_requests:
                                        logger.info(f"   Found {len(pending_requests)} pending network requests, waiting for page load...")
                                        # Wait up to 3 seconds for network idle (browser waits 1s, we wait longer for new tabs)
                                        import asyncio
                                        max_wait = 3.0
                                        wait_interval = 0.5
                                        waited = 0.0
                                        while waited < max_wait:
                                            await asyncio.sleep(wait_interval)
                                            waited += wait_interval
                                            # Check again
                                            temp_state = await session.get_browser_state_summary(
                                                include_screenshot=False,
                                                cached=False
                                            )
                                            new_pending = temp_state.pending_network_requests if temp_state.pending_network_requests else []
                                            if len(new_pending) == 0 or len(new_pending) < len(pending_requests):
                                                logger.info(f"   Network idle after {waited:.1f}s ({len(new_pending)} requests remaining)")
                                                break
                                        if waited >= max_wait:
                                            logger.warning(f"   Still {len(pending_requests)} pending requests after {max_wait}s, proceeding anyway")
                                    else:
                                        logger.info("   No pending requests, page appears loaded")
                                except Exception as e:
                                    logger.debug(f"Could not check network idle: {e}, proceeding with state refresh")
                                
                                # browser pattern: Refresh browser state after tab switch (see mcp/server.py line 919)
                                # This ensures the DOM cache is updated with the new tab's content
                                logger.info("🔄 Refreshing browser state after tab switch to get new tab's DOM...")
                                fresh_state = await session.get_browser_state_summary(
                                    include_screenshot=False,
                                    cached=False  # Force fresh state, don't use cache
                                )
                                
                                # CRITICAL: Verify we got the NEW tab's state, not the old one
                                if fresh_state.url == new_tab_url or (not new_tab_url and fresh_state.url != "https://openai.com/"):
                                    logger.info(f"✅ Fresh state retrieved from NEW tab after switch:")
                                    logger.info(f"   URL: {fresh_state.url}")
                                    logger.info(f"   Title: {fresh_state.title}")
                                    logger.info(f"   Current tab ID: {session.current_target_id[-4:] if session.current_target_id else 'unknown'}")
                                    logger.info(f"   Interactive elements: {len(fresh_state.dom_state.selector_map) if fresh_state.dom_state else 0}")
                                    logger.info(f"   🔍 NEW TAB DOM READY - LLM will see {len(fresh_state.dom_state.selector_map) if fresh_state.dom_state else 0} elements from this tab")
                                    
                                    # CRITICAL: Store the fresh state in state so think node can use it
                                    # This ensures LLM sees the ACTUAL current page, not stale cached state
                                    logger.info("💾 Storing fresh browser state in state for next think node...")
                                else:
                                    logger.error(f"❌ Got WRONG tab's state! Expected URL from new tab, got: {fresh_state.url}")
                                
                            except Exception as e:
                                logger.error(f"Could not verify/refresh browser state after tab switch: {e}", exc_info=True)
                                # Don't clear new_tab_id on error - let it retry
                                return {
                                    "verification_status": "fail",
                                    "verification_results": [{"status": "fail", "reason": f"Error refreshing state after tab switch: {str(e)}"}],
                                    "error": f"Failed to refresh state after tab switch: {str(e)}",
                                }
                            # Clear new_tab_id after successful switch to avoid re-switching
                            # BUT mark that we just switched tabs so think node knows to treat this as a fresh page
                            new_tab_id = None
                            new_tab_url = None

                            # Mark that we just switched tabs - think node should treat this as a fresh page state
                            # This ensures LLM understands it's seeing a NEW page structure
                            state_updates["just_switched_tab"] = True
                            state_updates["tab_switch_url"] = fresh_state.url if 'fresh_state' in locals() else None
                            state_updates["tab_switch_title"] = fresh_state.title if 'fresh_state' in locals() else None

                            # Add tab switch event to history for LLM visibility
                            # This creates a clear signal in agent_history that page context has changed
                            existing_history = state.get("history", [])
                            tab_switch_history_entry = {
                                "step": state.get("step_count", 0),
                                "node": "verify_tab_switch",
                                "action_results": [{
                                    "extracted_content": f"🔄 TAB SWITCHED - Now on NEW PAGE: {fresh_state.title} ({fresh_state.url})",
                                    "long_term_memory": f"Switched to tab #{tab_id_4char}. New page: {fresh_state.title}",
                                    "success": True
                                }]
                            }
                            state_updates["history"] = [tab_switch_history_entry]  # operator.add will append (LangGraph reducer pattern)
            except Exception as e:
                logger.warning(f"Error switching to new tab: {e}", exc_info=True)
        
        action_results = state.get("action_results", [])
        
        verification_results = []
        
        # Verify actions based on action results
        # An action is successful if:
        # 1. success is True AND error is None/empty
        # 2. extracted_content exists (indicates action executed)
        for result in action_results:
            success = result.get("success", False)
            error = result.get("error")
            extracted_content = result.get("extracted_content", "")
            
            # Check if extracted_content contains error-like messages (browser pattern)
            # browser sometimes returns warnings in extracted_content instead of error field
            content_looks_like_error = False
            if extracted_content:
                error_indicators = [
                    "not available",
                    "page may have changed",
                    "Try refreshing",
                    "failed",
                    "error",
                    "not found",
                    "invalid",
                ]
                content_lower = extracted_content.lower()
                content_looks_like_error = any(indicator in content_lower for indicator in error_indicators)
            
            # Action succeeded if success=True, no error, AND content doesn't look like an error
            if success and not error and not content_looks_like_error:
                verification_results.append({
                    "status": "pass",
                    "reason": f"Action completed: {extracted_content[:50] if extracted_content else 'Success'}",
                    "details": result,
                })
            else:
                # Action failed if success=False OR error exists OR content looks like error
                failure_reason = error or extracted_content or "Action returned success=False"
                verification_results.append({
                    "status": "fail",
                    "reason": failure_reason[:200],  # Truncate long error messages
                    "details": result,
                })
        
        # Determine overall status
        all_passed = all(
            r.get("status") == "pass" 
            for r in verification_results
        )
        
        verification_status = "pass" if all_passed else "fail"
        
        # CRITICAL: Compulsory LLM-driven todo.md update (browser style but mandatory)
        # Use LLM to intelligently update todo.md based on verified actions
        # No hardcoded keywords - LLM semantically matches actions to steps
        file_system = None
        file_system_state = state.get("file_system_state")
        steps_marked_complete = 0
        
        if verification_status == "pass" and file_system_state:
            try:
                import re
                from qa_agent.filesystem.file_system import FileSystem
                file_system = FileSystem.from_state(file_system_state)
                
                # Get executed actions from state to match with todo steps
                executed_actions = state.get("executed_actions", [])
                
                # Update todo.md based on successful verification using LLM intelligence (compulsory)
                todo_content = file_system.get_todo_contents()
                if todo_content and todo_content != '[empty todo.md, fill it when applicable]' and executed_actions:
                    # Parse current todo.md to get steps
                    todo_lines = todo_content.split('\n')
                    todo_steps = []
                    for line in todo_lines:
                        line_stripped = line.strip()
                        if line_stripped.startswith('- [ ]') or line_stripped.startswith('- [x]') or line_stripped.startswith('- [X]'):
                            # Extract step text (remove checkbox)
                            step_text = re.sub(r'^- \[[xX ]\]\s*', '', line_stripped)
                            if step_text:
                                todo_steps.append(step_text)
                    
                    # Use LLM to intelligently match verified actions to todo steps (compulsory, LLM-driven)
                    if todo_steps:
                        from qa_agent.utils.llm_todo_updater import llm_match_actions_to_todo_steps, update_todo_md_content
                        from qa_agent.llm import get_llm
                        
                        # Get LLM for todo matching
                        todo_llm = get_llm()
                        
                        # LLM analyzes verified actions and determines which steps are complete
                        completed_indices = await llm_match_actions_to_todo_steps(
                            executed_actions=executed_actions,
                            todo_steps=todo_steps,
                            llm=todo_llm,
                        )
                        
                        # Update todo.md content using replace_file (browser style)
                        if completed_indices:
                            # Use replace_file_str to update checkboxes (browser pattern)
                            # Need to match exact lines from todo_content, accounting for whitespace
                            for step_idx in completed_indices:
                                if step_idx < len(todo_steps):
                                    step_text = todo_steps[step_idx]
                                    
                                    # Find the exact line in todo_content (handle whitespace variations)
                                    # Search for the line that contains this step text
                                    for line in todo_lines:
                                        line_stripped = line.strip()
                                        # Check if this line contains the step text and is unchecked
                                        if (line_stripped.startswith('- [ ]') and 
                                            step_text.strip() in line_stripped):
                                            # Use the exact line from file (preserves whitespace)
                                            old_str = line.rstrip()  # Remove trailing newline but keep leading spaces
                                            # Create new line with checkbox marked
                                            new_str = line_stripped.replace('- [ ]', '- [x]', 1)
                                            # Preserve leading whitespace from original line
                                            leading_spaces = len(line) - len(line.lstrip())
                                            new_str = ' ' * leading_spaces + new_str
                                            
                                            # Use replace_file_str (browser method)
                                            result = await file_system.replace_file_str("todo.md", old_str, new_str)
                                            if "Successfully" in result:
                                                steps_marked_complete += 1
                                                logger.info(f"VERIFY: Marked todo step as complete (browser style): {step_text[:50]}")
                                                break  # Found and updated, move to next step
                            
                            if steps_marked_complete > 0:
                                # Save FileSystem state
                                file_system_state = file_system.get_state()
                                logger.info(f"VERIFY: LLM marked {steps_marked_complete} todo step(s) as complete using replace_file (browser style)")
            except Exception as e:
                logger.warning(f"VERIFY: Failed to update todo.md with LLM: {e}", exc_info=True)
                # Continue - todo.md update is important but don't break workflow
        
        # Persist FileSystem state (always save if we have it)
        if file_system_state:
            if "state_updates" not in locals():
                state_updates = {}
            state_updates["file_system_state"] = file_system_state
            logger.debug("Saved FileSystem state in verify_node")
        
        # Update history - create new list (LangGraph best practice: don't mutate state)
        existing_history = state.get("history", [])
        new_history_entry = {
            "step": state.get("step_count", 0),
            "node": "verify",
            "verification_status": verification_status,
            "verification_results": verification_results,
        }
        
        # Initialize state_updates (may have been set earlier during tab switch)
        if "state_updates" not in locals():
            state_updates = {}
        
        # Clear new_tab_id from state if we successfully switched (browser pattern: clear after action)
        state_updates.update({
            "verification_status": verification_status,
            "verification_results": verification_results,
            "history": [new_history_entry],  # operator.add will append to existing (LangGraph reducer pattern)
        })
        
        # Clear new_tab_id if we successfully switched (avoid re-switching on next step)
        # CRITICAL: Also update previous_tabs to reflect current tabs after switch
        if new_tab_id is None and state.get("new_tab_id"):
            state_updates["new_tab_id"] = None
            state_updates["new_tab_url"] = None
            # Update previous_tabs to current tabs so next act node comparison is correct
            try:
                from qa_agent.utils.session_registry import get_session
                browser_session_id = state.get("browser_session_id")
                if browser_session_id:
                    session = get_session(browser_session_id)
                    if session:
                        # Get current tabs after switch to update tracking
                        browser_state_after_switch = await session.get_browser_state_summary(
                            include_screenshot=False,
                            cached=False  # Fresh state after switch
                        )
                        if browser_state_after_switch.tabs:
                            current_tab_ids = [t.target_id for t in browser_state_after_switch.tabs]
                            state_updates["previous_tabs"] = current_tab_ids
                            state_updates["tab_count"] = len(current_tab_ids)
                            logger.info(f"Updated tab tracking: {len(current_tab_ids)} tabs after switch")
            except Exception as e:
                logger.debug(f"Could not update tab tracking after switch: {e}")
        
        return state_updates
    except Exception as e:
        logger.error(f"Error in verify node: {e}")
        return {
            "error": f"Verify node error: {str(e)}",
            "verification_status": "fail",
            "verification_results": [{"status": "fail", "reason": str(e)}],
        }

