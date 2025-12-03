"""
Act Node - Execute planned actions

This node:
1. Receives planned actions from Think node
2. Initializes Tools instance with BrowserSession
3. Executes actions via browser Tools
4. Captures action results
"""
import logging
from typing import Any, Dict, List

from web_agent.config import settings
from web_agent.llm import get_llm
from web_agent.state import QAAgentState
from web_agent.tools.browser_actions import (
	BROWSER_TOOLS,
	BrowserToolContext,
	reset_browser_tool_context,
	set_browser_tool_context,
)
from web_agent.tools.service import Tools
from web_agent.utils.session_registry import get_session

logger = logging.getLogger(__name__)

TOOL_MAP = {tool.name: tool for tool in BROWSER_TOOLS}
FILE_SYSTEM_ACTIONS = {"extract_content", "write_file", "read_file", "upload_file", "replace_file"}
PAGE_CHANGING_ACTIONS = {"navigate", "switch", "switch_tab", "go_back"}
DOM_CHANGING_ACTIONS = {"click", "input_text", "scroll", "toggle_checkbox", "select_dropdown"}


async def act_node(state: QAAgentState) -> Dict[str, Any]:
	"""
	Act node: Execute planned actions using browser Tools

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

	# Get normalized tool-call actions
	actions = state.get("actions", [])

	print(f"\n{'='*80}")
	print(f"🎭 ACT NODE - Executing Actions via browser Tools")
	print(f"{'='*80}")
	print(f"📋 Planned Actions: {len(actions)}")
	print(f"🌐 Browser Session: {browser_session_id[:16]}...")

	if not actions:
		logger.warning("No planned actions to execute")
		print(f"⚠️  No actions to execute\n")
		return {
			"executed_actions": [],
			"action_results": [],
		}

	# CRITICAL: Get tabs AND element IDs BEFORE actions to detect changes
	# browser pattern: Compare tabs before/after to detect new tabs
	# Phase 1 & 2: Track element IDs for adaptive DOM change detection
	logger.info("📋 Getting state BEFORE actions (for change detection)...")
	try:
		browser_state_before = await session.get_browser_state_summary(include_screenshot=False, cached=True)
		tabs_before = browser_state_before.tabs if browser_state_before.tabs else []
		previous_tabs = [t.target_id for t in tabs_before]
		initial_tab_count = len(previous_tabs)
		
		# Phase 1 & 2: Capture element IDs before actions for adaptive detection
		previous_element_ids = set(
			browser_state_before.dom_state.selector_map.keys()
			if browser_state_before.dom_state and browser_state_before.dom_state.selector_map
			else []
		)
		logger.info(f"   Tabs before actions: {initial_tab_count} tabs")
		logger.info(f"   Elements before actions: {len(previous_element_ids)} elements")
	except Exception as e:
		logger.warning(f"Could not get state before actions: {e}")
		previous_tabs = state.get("previous_tabs", [])
		initial_tab_count = len(previous_tabs) if previous_tabs else state.get("tab_count", 1)
		previous_element_ids = state.get("previous_element_ids", set())

	# Initialize Tools instance
	logger.info("Initializing browser Tools")
	tools = Tools()

	# Execute actions sequentially
	executed_actions: List[Dict[str, Any]] = []
	action_results: List[Dict[str, Any]] = []
	available_file_paths = state.get("available_file_paths", [])
	sensitive_data = state.get("sensitive_data")
	file_system_cache = None

	def get_file_system():
		nonlocal file_system_cache
		if file_system_cache is None:
			from pathlib import Path
			from web_agent.filesystem.file_system import FileSystem

			file_system_dir = Path("web_agent_workspace") / f"session_{browser_session_id[:8]}"
			file_system_cache = FileSystem(base_dir=file_system_dir, create_default_files=False)
		return file_system_cache

	for i, action in enumerate(actions, 1):
		action_type = action.get("action_type")
		params = action.get("params") or {}
		tool_call_id = action.get("tool_call_id")

		if not action_type:
			logger.warning(f"Could not determine action type from: {action}")
			print("    ⚠️  Skipping action with unknown type")
			continue

		print(f"\n  [{i}/{len(actions)}] Executing: {action_type}")
		tool = TOOL_MAP.get(action_type)
		if not tool:
			logger.error(f"Unknown action: {action_type}")
			action_results.append({
				"success": False,
				"action": action,
				"error": f"Unknown action: {action_type}",
				"extracted_content": None,
				"is_done": False,
				"long_term_memory": None,
				"include_extracted_content_only_once": False,
				"images": None,
				"metadata": None,
			})
			continue

		page_extraction_llm = None
		if action_type == "extract_content":
			page_extraction_llm = get_llm()

		file_system = None
		if action_type in FILE_SYSTEM_ACTIONS:
			file_system = get_file_system()

		ctx = BrowserToolContext(
			browser_session=session,
			tools=tools,
			file_system=file_system,
			page_extraction_llm=page_extraction_llm,
			available_file_paths=available_file_paths,
			sensitive_data=sensitive_data,
		)

		token = set_browser_tool_context(ctx)
		try:
			result = await tool.ainvoke(params)
		except Exception as e:
			logger.error(f"Error executing action {action_type}: {e}", exc_info=True)
			action_results.append({
				"success": False,
				"action": action,
				"error": str(e),
				"extracted_content": None,
				"is_done": False,
				"long_term_memory": None,
				"include_extracted_content_only_once": False,
				"images": None,
				"metadata": None,
			})
			continue
		finally:
			reset_browser_tool_context(token)

		success = result.error is None
		extracted_content = result.extracted_content
		error_msg = result.error
		is_done = result.is_done
		long_term_memory = result.long_term_memory
		include_extracted_content_only_once = result.include_extracted_content_only_once
		images = result.images
		metadata = result.metadata
		success_flag = result.success

		logger.info(f"Action {action_type} {'succeeded' if success else 'failed'}: {extracted_content or error_msg}")
		print(f"    ✅ {action_type} completed" if success else f"    ❌ {action_type} failed: {error_msg}")

		action_results.append({
			"success": success,
			"action": action,
			"tool_call_id": tool_call_id,
			"extracted_content": extracted_content,
			"error": error_msg,
			"is_done": is_done,
			"long_term_memory": long_term_memory,
			"include_extracted_content_only_once": include_extracted_content_only_once,
			"images": images,
			"metadata": metadata,
			"success_flag": success_flag,
		})
		executed_actions.append(action)

	print(f"\n✅ Executed {len(executed_actions)}/{len(actions)} actions")
	print(f"{'='*80}\n")

	# CRITICAL: Wait for DOM stability after actions (browser pattern)
	# Phase 2: Use adaptive DOM change detection instead of fixed timeout
	# This ensures dropdowns, modals, and dynamic content are fully rendered
	# before Think node analyzes the page
	logger.info("⏳ Waiting for DOM stability after actions...")
	from web_agent.utils.dom_stability import (
		wait_for_dom_stability, 
		clear_cache_if_needed,
		detect_dom_changes_adaptively,
	)
	
	# Get previous URL before actions for cache clearing
	previous_url = state.get("current_url") or state.get("previous_url")
	
	# Clear cache if actions might have changed the page/DOM
	# Check all executed actions to see if any are page-changing
	page_changing_action_types = PAGE_CHANGING_ACTIONS
	dom_changing_action_types = DOM_CHANGING_ACTIONS
	
	has_page_changing_action = any(
		a.get("action_type") in page_changing_action_types 
		for a in executed_actions
	)
	has_dom_changing_action = any(
		a.get("action_type") in dom_changing_action_types 
		for a in executed_actions
	)
	
	if has_page_changing_action or has_dom_changing_action:
		# Clear cache for any action that might change DOM
		action_type = executed_actions[-1].get("action_type") if executed_actions else "unknown"
		await clear_cache_if_needed(session, action_type, previous_url)
	
	# Phase 2: Adaptive DOM change detection - wait until DOM stabilizes
	# This replaces fixed timeout with adaptive detection based on actual changes
	if has_dom_changing_action and previous_element_ids:
		logger.info("🔍 Using adaptive DOM change detection...")
		final_element_ids, passes_taken = await detect_dom_changes_adaptively(
			session, 
			previous_element_ids=previous_element_ids,
			max_passes=5,
			stability_threshold=2,
		)
		new_element_ids = final_element_ids - previous_element_ids
		logger.info(f"   Detected {len(new_element_ids)} new elements after {passes_taken} passes")
	else:
		# Fallback to network-based waiting for page-changing actions
		await wait_for_dom_stability(session, max_wait_seconds=3.0)
		final_element_ids = previous_element_ids  # Will be updated below
		new_element_ids = set()
	
	# CRITICAL: Fetch fresh browser state AFTER actions and DOM stability wait
	# This ensures Think node sees the CURRENT page state (dropdowns, modals, new content)
	# browser pattern: Always get fresh state at start of next step
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
	current_element_ids = set(selector_map.keys())
	
	# Phase 1: Track which action caused which elements to appear
	# Calculate new elements if not already calculated
	if not new_element_ids and previous_element_ids:
		new_element_ids = current_element_ids - previous_element_ids
	
	# Phase 1: Build action context for LLM with detailed new element information
	last_action = executed_actions[-1] if executed_actions else None
	action_context = None
	if last_action:
		action_type = last_action.get("action_type", "unknown")
		action_index = (
			last_action.get("params", {}).get("index")
			or last_action.get("params", {}).get("element_index")
		)

		# Build enhanced action context with new element details
		action_context = {
			"action_type": action_type,
			"action_index": action_index,
			"new_elements_count": len(new_element_ids),
			"new_element_ids": list(new_element_ids)[:20],  # Limit to first 20 for context
		}

		# Add new element details for LLM's *[index] pattern recognition
		if new_element_ids and fresh_browser_state.dom_state and fresh_browser_state.dom_state.selector_map:
			selector_map = fresh_browser_state.dom_state.selector_map
			new_elements_details = []
			for elem_id in list(new_element_ids)[:10]:  # Top 10 new elements
				if elem_id in selector_map:
					elem = selector_map[elem_id]
					try:
						elem_info = {
							"index": elem_id,
							"tag": getattr(elem, 'tag_name', ''),
							"text": getattr(elem, 'node_value', '')[:50],  # Limit text length
						}
						new_elements_details.append(elem_info)
					except Exception as e:
						logger.debug(f"Could not extract element details: {e}")

			if new_elements_details:
				action_context["new_elements_details"] = new_elements_details

		# Infer likely interaction pattern from element count change
		if len(new_element_ids) > 15:
			action_context["likely_pattern"] = "modal_or_form_opened"
		elif len(new_element_ids) > 5:
			action_context["likely_pattern"] = "dropdown_or_menu_opened"
		elif len(new_element_ids) > 0:
			action_context["likely_pattern"] = "suggestions_or_details_appeared"
		else:
			action_context["likely_pattern"] = "no_new_elements"

		logger.info(
			f"📊 Action context: {action_type} on {action_index} → "
			f"{len(new_element_ids)} new elements appeared (pattern: {action_context.get('likely_pattern')})"
		)
	
	logger.info(f"✅ Fresh state retrieved: {current_title[:50]} ({current_url[:60]})")
	logger.info(f"   Interactive elements: {element_count} ({len(new_element_ids)} new)")
	logger.info(f"   💾 Passing fresh state to Think node - LLM will see CURRENT page structure")
	
	# Check for new tabs opened by actions (e.g., ChatGPT login opens new tab)
	# browser pattern: detect new tabs by comparing before/after tab lists
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
	}

	# Update previous_tabs for next step comparison
	previous_tabs = current_tab_ids if 'current_tab_ids' in locals() else state.get("previous_tabs", [])
	
	# Check if any executed action was a tab switch - mark it for enhanced LLM context
	# This ensures think node provides context about the new page structure
	# Handle both dict format and ActionModel format
	just_switched_tab = any(
		isinstance(a, dict) and a.get("action_type") in {"switch", "switch_tab"}
		for a in executed_actions
	)
	
	# Build return state with fresh browser state info
	return_state = {
		"executed_actions": executed_actions,
		"action_results": action_results,
		"actions": [],
		"history": existing_history + [new_history_entry],
		"tab_count": len(current_tab_ids) if 'current_tab_ids' in locals() else state.get("tab_count", 1),
		"previous_tabs": previous_tabs,  # Track tabs for next comparison
		"new_tab_id": new_tab_id,  # Pass to next node for tab switching
		"new_tab_url": new_tab_url,  # Pass URL for context
		# CRITICAL: Pass fresh state to Think node (browser pattern: backend 1 step ahead)
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
		"previous_element_ids": current_element_ids,  # Phase 1 & 2: Track element IDs for adaptive detection
		"action_context": action_context,  # Phase 1: Action → element relationship context
		"new_element_ids": list(new_element_ids),  # Phase 1: New elements that appeared
	}
	
	# If we explicitly switched tabs, mark it so think node provides enhanced context
	if just_switched_tab:
		return_state["just_switched_tab"] = True
		# Use fresh state we already fetched
		return_state["tab_switch_url"] = current_url
		return_state["tab_switch_title"] = current_title
		logger.info(f"💾 Marked explicit tab switch in state - think node will provide enhanced context")
		logger.info(f"   Switch context: {current_title} ({current_url})")
	
	return return_state
