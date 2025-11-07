"""
Act Node - Execute planned actions

This node:
1. Receives planned actions from Think node
2. Initializes Tools instance with BrowserSession
3. Executes actions via browser-use Tools
4. Captures action results
5. Persists FileSystem state (LLM decides when to update todo.md via replace_file action)
"""
import logging
from typing import Dict, Any
from qa_agent.state import QAAgentState
from qa_agent.config import settings
from qa_agent.utils.session_registry import get_session
from qa_agent.tools.service import Tools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from qa_agent.agent.views import ActionModel

logger = logging.getLogger(__name__)


async def act_node(state: QAAgentState) -> Dict[str, Any]:
	"""
	Act node: Execute planned actions using browser-use Tools

	Args:
		state: Current QA agent state

	Returns:
		Updated state with executed actions and results
	"""
	logger.info(f"Act node - Step {state.get('step_count', 0)}")

	# Get browser session from registry
	browser_session_id = state.get("browser_session_id")
	if not browser_session_id:
		logger.error("No browser_session_id in state")
		return {
			"error": "No browser session ID - INIT node must run first",
			"executed_actions": [],
			"action_results": [],
		}

	session = get_session(browser_session_id)
	if not session:
		logger.error(f"Browser session {browser_session_id} not found in registry")
		return {
			"error": f"Browser session {browser_session_id} not found",
			"executed_actions": [],
			"action_results": [],
		}

	# Get planned actions
	planned_actions = state.get("planned_actions", [])

	print(f"\n{'='*80}")
	print(f"🎭 ACT NODE - Executing Actions via browser-use Tools")
	print(f"{'='*80}")
	print(f"📋 Planned Actions: {len(planned_actions)}")
	print(f"🌐 Browser Session: {browser_session_id[:16]}...")

	if not planned_actions:
		logger.warning("No planned actions to execute")
		print(f"⚠️  No actions to execute\n")
		return {
			"executed_actions": [],
			"action_results": [],
		}

	# CRITICAL: Get tabs BEFORE actions to detect new tabs opened by actions
	# Browser-use pattern: Compare tabs before/after to detect new tabs
	logger.info("📋 Getting tabs BEFORE actions (for new tab detection)...")
	try:
		browser_state_before = await session.get_browser_state_summary(include_screenshot=False, cached=True)
		tabs_before = browser_state_before.tabs if browser_state_before.tabs else []
		previous_tabs = [t.target_id for t in tabs_before]
		initial_tab_count = len(previous_tabs)
		logger.info(f"   Tabs before actions: {initial_tab_count} tabs")
	except Exception as e:
		logger.warning(f"Could not get tabs before actions: {e}")
		previous_tabs = state.get("previous_tabs", [])
		initial_tab_count = len(previous_tabs) if previous_tabs else state.get("tab_count", 1)

	# Initialize Tools instance
	logger.info("Initializing browser-use Tools")
	tools = Tools()
	
	# planned_actions is already list[ActionModel] from think node
	# No conversion needed - LangChain with_structured_output() returns validated Pydantic objects
	# Execute actions sequentially
	executed_actions = []
	action_results = []

	for i, action_model in enumerate(planned_actions, 1):
		# action_model is already ActionModel - get action type from model dump
		action_dump = action_model.model_dump(exclude_unset=True)
		action_type = list(action_dump.keys())[0] if action_dump else "unknown"
		print(f"\n  [{i}/{len(planned_actions)}] Executing: {action_type}")

		try:

			# Execute action via browser-use Tools
			# Browser-use extract action requires page_extraction_llm
			# Get LLM instance for extract actions (browser-use pattern)
			page_extraction_llm = None
			if action_type == "extract":
				from qa_agent.llm import get_llm
				page_extraction_llm = get_llm()
				logger.info(f"Extract action detected - providing page_extraction_llm to Tools.act()")
			
			# Get file_system from state (created in think node)
			file_system = None
			if action_type == "extract" or action_type in ["write_file", "read_file", "replace_file"]:
				# File system is needed for extract and file operations
				# CRITICAL: Restore FileSystem from state for todo.md persistence (Phase 1)
				from qa_agent.filesystem.file_system import FileSystem
				from pathlib import Path
				
				# Restore FileSystem from state if it exists
				file_system_state = state.get("file_system_state")
				if file_system_state:
					# Restore existing FileSystem from persisted state
					file_system = FileSystem.from_state(file_system_state)
					logger.debug("Restored FileSystem from state in act_node (todo.md preserved)")
				else:
					# Fallback: Create new FileSystem if state not available
					browser_session_id = state.get("browser_session_id", "unknown")
					file_system_dir = Path("qa_agent_workspace") / f"session_{browser_session_id[:8]}"
					file_system = FileSystem(base_dir=file_system_dir, create_default_files=False)  # Don't recreate files
					logger.debug("Created new FileSystem in act_node (fallback)")

			logger.info(f"Executing {action_type} via Tools.act()")
			result = await tools.act(
				action=action_model,
				browser_session=session,
				page_extraction_llm=page_extraction_llm,  # Required for extract actions
				file_system=file_system,  # Required for extract and file operations
			)

			# Extract all result data (browser-use ActionResult fields)
			success = result.error is None
			extracted_content = result.extracted_content
			error_msg = result.error
			is_done = result.is_done
			long_term_memory = result.long_term_memory
			include_extracted_content_only_once = result.include_extracted_content_only_once
			images = result.images
			metadata = result.metadata
			success_flag = result.success  # May be None for non-done actions

			logger.info(f"Action {action_type} {'succeeded' if success else 'failed'}: {extracted_content or error_msg}")
			print(f"    ✅ {action_type} completed" if success else f"    ❌ {action_type} failed: {error_msg}")

			# Store complete result (all browser-use ActionResult fields)
			# Store action as dict for history serialization
			action_results.append({
				"success": success,
				"action": action_dump,  # Store as dict for JSON serialization
				"extracted_content": extracted_content,
				"error": error_msg,
				"is_done": is_done,
				"long_term_memory": long_term_memory,
				"include_extracted_content_only_once": include_extracted_content_only_once,
				"images": images,
				"metadata": metadata,
				"success_flag": success_flag,  # Browser-use success flag (None for regular actions)
			})
			executed_actions.append(action_dump)  # Store as dict for later checks

		except Exception as e:
			# Browser-use pattern: Tools.act() catches BrowserError, TimeoutError, and general exceptions
			# and returns ActionResult with error field set
			# If we get here, it's an exception during action execution
			logger.error(f"Error executing action {action_type}: {e}", exc_info=True)
			print(f"    ❌ Exception: {str(e)[:100]}")
			action_results.append({
				"success": False,
				"action": action_dump,  # Store as dict for JSON serialization
				"error": str(e),
				"extracted_content": None,
				"is_done": False,
				"long_term_memory": None,
				"include_extracted_content_only_once": False,
				"images": None,
				"metadata": None,
			})

	print(f"\n✅ Executed {len(executed_actions)}/{len(planned_actions)} actions")
	print(f"{'='*80}\n")

	# CRITICAL: Wait for DOM stability after actions (browser-use pattern)
	# This ensures dropdowns, modals, and dynamic content are fully rendered
	# before Think node analyzes the page
	logger.info("⏳ Waiting for DOM stability after actions...")
	from qa_agent.utils.dom_stability import wait_for_dom_stability, clear_cache_if_needed
	
	# Get previous URL before actions for cache clearing
	previous_url = state.get("current_url") or state.get("previous_url")
	
	# Clear cache if actions might have changed the page/DOM
	# Check all executed actions to see if any are page-changing
	# executed_actions contains action dicts (from action_dump)
	page_changing_action_types = ["navigate", "switch", "go_back"]
	dom_changing_action_types = ["click", "input", "scroll"]

	has_page_changing_action = any(
		list(a.keys())[0] in page_changing_action_types if a else False
		for a in executed_actions
	)
	has_dom_changing_action = any(
		list(a.keys())[0] in dom_changing_action_types if a else False
		for a in executed_actions
	)

	if has_page_changing_action or has_dom_changing_action:
		# Clear cache for any action that might change DOM
		action_type = list(executed_actions[-1].keys())[0] if executed_actions and executed_actions[-1] else "unknown"
		await clear_cache_if_needed(session, action_type, previous_url)
	
	# Wait for network idle and DOM stability (browser-use pattern from DOMWatchdog)
	await wait_for_dom_stability(session, max_wait_seconds=3.0)
	
	# CRITICAL: Fetch fresh browser state AFTER actions and DOM stability wait
	# This ensures Think node sees the CURRENT page state (dropdowns, modals, new content)
	# Browser-use pattern: Always get fresh state at start of next step
	logger.info("🔄 Fetching fresh browser state after actions (for Think node)...")
	fresh_browser_state = await session.get_browser_state_summary(
		include_screenshot=False,
		cached=False  # Force fresh state - critical after actions
	)
	
	# Extract key info from fresh state
	current_url = fresh_browser_state.url
	current_title = fresh_browser_state.title
	selector_map = fresh_browser_state.dom_state.selector_map if fresh_browser_state.dom_state else {}
	element_count = len(selector_map)
	
	logger.info(f"✅ Fresh state retrieved: {current_title[:50]} ({current_url[:60]})")
	logger.info(f"   Interactive elements: {element_count}")
	logger.info(f"   💾 Passing fresh state to Think node - LLM will see CURRENT page structure")
	
	# Check for new tabs opened by actions (e.g., ChatGPT login opens new tab)
	# Browser-use pattern: detect new tabs by comparing before/after tab lists
	new_tab_id = None
	new_tab_url = None
	try:
		# Use fresh state we just fetched
		current_tabs = fresh_browser_state.tabs if fresh_browser_state.tabs else []
		current_tab_ids = [t.target_id for t in current_tabs]
		
		# Use tabs_before we captured at the start of this function
		# previous_tabs and initial_tab_count are already set above
		
		logger.info(f"📋 Comparing tabs: BEFORE={initial_tab_count} tabs, AFTER={len(current_tab_ids)} tabs")
		
		# Check if new tab was opened by comparing tab counts and IDs
		if len(current_tab_ids) > initial_tab_count:
			# Find the new tab (IDs not in previous tabs)
			logger.info(f"New tab detected: {len(current_tab_ids)} tabs (was {initial_tab_count})")
			# Get the current active tab to compare
			current_target_id = session.current_target_id
			
			# Find tabs that are new (not in previous list and not the current tab)
			new_tabs = [t for t in current_tabs if t.target_id not in previous_tabs and t.target_id != current_target_id]
			
			if new_tabs:
				# Get the most recent new tab (last in list)
				new_tab = new_tabs[-1]
				new_tab_id = new_tab.target_id
				new_tab_url = new_tab.url
				logger.info(f"New tab detected: ID={new_tab_id[-4:]}, URL={new_tab_url}")
		else:
			# No new tabs - update previous_tabs for next check
			previous_tabs = current_tab_ids.copy()
	except Exception as e:
		logger.warning(f"Could not detect new tabs: {e}", exc_info=True)
		# Fallback: use fresh state we already fetched
		try:
			current_tabs = fresh_browser_state.tabs if fresh_browser_state.tabs else []
			current_tab_ids = [t.target_id for t in current_tabs]
			previous_tabs = current_tab_ids.copy()
		except:
			current_tab_ids = []
			previous_tabs = []

	# Track consecutive failures (browser-use pattern: service.py:793-800)
	# Browser-use checks: if single action AND it has error, increment failure counter
	# If success (no error), reset failure counter to 0
	consecutive_failures = state.get("consecutive_failures", 0)

	if len(action_results) == 1 and action_results[0].get("error"):
		# Single action failed - increment consecutive failures
		consecutive_failures += 1
		logger.debug(f"🔄 Step {state.get('step_count', 0)}: Action failed, consecutive failures: {consecutive_failures}")
	else:
		# Success or multiple actions - reset consecutive failures
		if consecutive_failures > 0:
			logger.debug(f"🔄 Step {state.get('step_count', 0)}: Action succeeded, resetting consecutive failures from {consecutive_failures} to 0")
			consecutive_failures = 0

	# Update history
	existing_history = state.get("history", [])
	new_history_entry = {
		"step": state.get("step_count", 0),
		"node": "act",
		"executed_actions": executed_actions,
		"action_results": action_results,
		"success_count": sum(1 for r in action_results if r.get("success")),
		"total_count": len(action_results),
		"new_tab_id": new_tab_id,  # Track if new tab was opened
		"consecutive_failures": consecutive_failures,  # Track failure count
	}

	# Update previous_tabs for next step comparison
	previous_tabs = current_tab_ids if 'current_tab_ids' in locals() else state.get("previous_tabs", [])
	
	# Check if any executed action was a tab switch - mark it for enhanced LLM context
	# This ensures think node provides context about the new page structure
	just_switched_tab = any(a.get("action") == "switch" for a in executed_actions)
	
	# Build return state with fresh browser state info
	return_state = {
		"executed_actions": executed_actions,
		"action_results": action_results,
		"history": [new_history_entry],  # operator.add will append to existing (LangGraph reducer pattern)
		"consecutive_failures": consecutive_failures,  # NEW: Track failure count (browser-use pattern)
		"tab_count": len(current_tab_ids) if 'current_tab_ids' in locals() else state.get("tab_count", 1),
		"previous_tabs": previous_tabs,  # Track tabs for next comparison
		"new_tab_id": new_tab_id,  # Pass to next node for tab switching
		"new_tab_url": new_tab_url,  # Pass URL for context
		# CRITICAL: Pass fresh state to Think node (browser-use pattern: backend 1 step ahead)
		"fresh_state_available": True,  # Flag to tell Think node we have fresh state
		"page_changed": has_page_changing_action or (previous_url and current_url != previous_url),
		"current_url": current_url,  # Update current URL
		"browser_state_summary": {  # Store summary for Think node
			"url": current_url,
			"title": current_title,
			"element_count": element_count,
			"tabs": [{"id": t.target_id[-4:], "title": t.title, "url": t.url} for t in current_tabs],
		},
		"dom_selector_map": selector_map,  # Cache selector map for Think node
		"previous_url": current_url,  # Track URL for next step comparison
		"previous_element_count": element_count,  # Track element count for change detection
	}
	
	# If we explicitly switched tabs, mark it so think node provides enhanced context
	if just_switched_tab:
		return_state["just_switched_tab"] = True
		# Use fresh state we already fetched
		return_state["tab_switch_url"] = current_url
		return_state["tab_switch_title"] = current_title
		logger.info(f"💾 Marked explicit tab switch in state - think node will provide enhanced context")
		logger.info(f"   Switch context: {current_title} ({current_url})")
	
	# CRITICAL: Update todo.md based on successful actions (moved from VERIFY since it's never called)
	# Use LLM to intelligently match successful actions to todo steps
	file_system_state = state.get("file_system_state")
	steps_marked_complete = 0
	
	# Check if we have successful actions and todo.md to update
	# Filter for successful actions only (actions that completed without errors)
	successful_actions = [r for r in action_results if r.get("success") and not r.get("error")]
	logger.info(f"ACT: Found {len(successful_actions)} successful actions out of {len(action_results)} total actions")
	
	if successful_actions and file_system_state:
		try:
			import re
			from qa_agent.filesystem.file_system import FileSystem
			file_system = FileSystem.from_state(file_system_state)
			
			# Get todo.md content
			todo_content = file_system.get_todo_contents()
			if todo_content and todo_content != '[empty todo.md, fill it when applicable]':
				# Parse current todo.md to get steps
				todo_lines = todo_content.split('\n')
				todo_steps = []
				for line in todo_lines:
					line_stripped = line.strip()
					# Handle malformed checkboxes (e.g., "- [x] - [ ]" should become "- [ ]")
					# Remove ALL checkbox patterns until we find the actual step text
					cleaned_line = line_stripped
					while re.match(r'^\s*-\s*\[[xX ]\]\s*', cleaned_line):
						cleaned_line = re.sub(r'^\s*-\s*\[[xX ]\]\s*', '', cleaned_line)
					
					# Check if this is a todo line (has checkbox pattern originally)
					if line_stripped.startswith('- [') and ('[ ]' in line_stripped or '[x]' in line_stripped or '[X]' in line_stripped):
						# Extract step text (after removing all checkbox patterns)
						step_text = cleaned_line.strip()
						if step_text:
							todo_steps.append(step_text)
				
				# Use LLM to intelligently match successful actions to todo steps
				# Only use successful actions (actions that completed without errors)
				if todo_steps and successful_actions:
					from qa_agent.utils.llm_todo_updater import llm_match_actions_to_todo_steps
					from qa_agent.llm import get_llm
					
					# Prepare successful actions with extracted_content for better LLM matching
					# successful_actions are from action_results, which have extracted_content
					# We need to convert them back to action dict format for the LLM matcher
					enriched_actions = []
					for result in successful_actions:
						# result has: {"success": True, "action": {"click": {...}}, "extracted_content": "..."}
						action_dict = result.get("action", {})
						if action_dict:
							enriched_action = action_dict.copy()
							# Add extracted_content for better matching
							if result.get("extracted_content"):
								enriched_action["extracted_content"] = result["extracted_content"]
							enriched_action["success"] = True
							enriched_actions.append(enriched_action)
					
					logger.info(f"ACT: Matching {len(enriched_actions)} actions to {len(todo_steps)} todo steps")
					logger.debug(f"ACT: Todo steps: {todo_steps[:3]}...")  # Log first 3 steps
					
					# Get LLM for todo matching
					todo_llm = get_llm()
					
					# LLM analyzes successful actions and determines which steps are complete
					completed_indices = await llm_match_actions_to_todo_steps(
						executed_actions=enriched_actions,
						todo_steps=todo_steps,
						llm=todo_llm,
					)
					
					logger.info(f"ACT: LLM returned {len(completed_indices)} completed step indices: {completed_indices}")
					
					# Update todo.md content using replace_file_str (browser-use style)
					if completed_indices:
						for step_idx in completed_indices:
							if step_idx < len(todo_steps):
								step_text = todo_steps[step_idx]
								
								# Find the exact line in todo_content (handle whitespace variations and malformed checkboxes)
								for line in todo_lines:
									line_stripped = line.strip()
									
									# Check if this line contains the step text
									# Handle malformed checkboxes: clean the line to extract step text for comparison
									cleaned_line_for_match = line_stripped
									while re.match(r'^\s*-\s*\[[xX ]\]\s*', cleaned_line_for_match):
										cleaned_line_for_match = re.sub(r'^\s*-\s*\[[xX ]\]\s*', '', cleaned_line_for_match)
									
									# Match if step text is in the cleaned line (flexible matching)
									step_text_normalized = step_text.strip().lower()
									cleaned_line_normalized = cleaned_line_for_match.strip().lower()
									
									# Use flexible matching: step text should be contained in line, or vice versa for short steps
									# Also check if key words match (for better semantic matching)
									step_words = set(step_text_normalized.split())
									line_words = set(cleaned_line_normalized.split())
									
									# Match if: step text is substring of line, OR line is substring of step, OR significant word overlap
									matches = (
										step_text_normalized in cleaned_line_normalized or
										cleaned_line_normalized in step_text_normalized or
										(len(step_words) > 0 and len(step_words & line_words) >= min(3, len(step_words) * 0.6))
									)
									
									if matches:
										# Check if line has unchecked checkbox AND not already checked
										has_unchecked = '[ ]' in line_stripped
										has_checked = '[x]' in line_stripped or '[X]' in line_stripped
										
										# Only update if it has unchecked checkbox AND not already fully checked
										if has_unchecked and not (has_checked and not has_unchecked):
											# Use the exact line from file (preserves whitespace)
											old_str = line.rstrip()  # Remove trailing newline but keep leading spaces
											
											# Fix malformed checkboxes: clean up to single - [x] format
											# Extract the actual step text (after all checkbox patterns)
											step_text_only = cleaned_line_for_match.strip()
											
											# Build clean new line: - [x] + step text
											new_str = f'- [x] {step_text_only}'
											
											# Preserve leading whitespace from original line
											leading_spaces = len(line) - len(line.lstrip())
											new_str = ' ' * leading_spaces + new_str
											
											# Use replace_file_str (browser-use method)
											result = await file_system.replace_file_str("todo.md", old_str, new_str)
											if "Successfully" in result:
												steps_marked_complete += 1
												logger.info(f"ACT: Marked todo step as complete (fixed malformed checkbox): {step_text[:50]}")
												break  # Found and updated, move to next step
						
						if steps_marked_complete > 0:
							# Save FileSystem state after todo.md updates
							file_system_state = file_system.get_state()
							logger.info(f"ACT: LLM marked {steps_marked_complete} todo step(s) as complete using replace_file (browser-use style)")
		except Exception as e:
			logger.warning(f"ACT: Failed to update todo.md with LLM: {e}", exc_info=True)
			# Continue - todo.md update is important but don't break workflow
	
	# Persist FileSystem state (always preserve, even if no file operations in this node)
	if file_system_state:
		# Always preserve FileSystem state (carry forward todo.md updates)
		return_state["file_system_state"] = file_system_state
		logger.debug("Preserved FileSystem state in act_node (todo.md preserved)")
	
	# Also persist if file operations were performed (LLM's file operations)
	file_operations_performed = any(
		a.get("action") in ["write_file", "read_file", "replace_file"]
		for a in executed_actions
	)
	
	if file_operations_performed and file_system_state:
		# Update FileSystem state if LLM performed file operations
		from qa_agent.filesystem.file_system import FileSystem
		file_system = FileSystem.from_state(file_system_state)
		file_system_state = file_system.get_state()
		return_state["file_system_state"] = file_system_state
		logger.debug("Updated FileSystem state in act_node (file operations performed)")
	
	return return_state


