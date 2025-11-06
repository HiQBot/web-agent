"""
Act Node - Execute planned actions

This node:
1. Receives planned actions from Think node
2. Initializes Tools instance with BrowserSession
3. Executes actions via browser-use Tools
4. Captures action results
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
	
	# Get dynamic ActionModel class from Tools registry (browser-use recommended approach)
	# This creates ActionModel with all registered actions dynamically from the registry
	# This ensures we always have the correct action fields matching registered action names
	DynamicActionModel = tools.registry.create_action_model(page_url=None)

	# Execute actions sequentially
	executed_actions = []
	action_results = []

	for i, action_dict in enumerate(planned_actions, 1):
		action_type = action_dict.get("action") or action_dict.get("type")
		print(f"\n  [{i}/{len(planned_actions)}] Executing: {action_type}")

		try:
			# Convert our action dict to browser-use ActionModel
			# Pass tools registry for param model lookups
			action_model = convert_to_action_model(action_dict, DynamicActionModel, tools.registry)

			if not action_model:
				logger.warning(f"Could not convert action to ActionModel: {action_dict}")
				print(f"    ⚠️  Skipping invalid action: {action_type}")
				action_results.append({
					"success": False,
					"action": action_dict,
					"error": "Invalid action format",
					"extracted_content": None,
					"is_done": False,
				})
				continue

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
				# It's created fresh in each think cycle
				from qa_agent.filesystem.file_system import FileSystem
				from pathlib import Path
				browser_session_id = state.get("browser_session_id", "unknown")
				file_system_dir = Path("qa_agent_workspace") / f"session_{browser_session_id[:8]}"
				file_system = FileSystem(base_dir=file_system_dir, create_default_files=False)  # Don't recreate files

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
			action_results.append({
				"success": success,
				"action": action_dict,
				"extracted_content": extracted_content,
				"error": error_msg,
				"is_done": is_done,
				"long_term_memory": long_term_memory,
				"include_extracted_content_only_once": include_extracted_content_only_once,
				"images": images,
				"metadata": metadata,
				"success_flag": success_flag,  # Browser-use success flag (None for regular actions)
			})
			executed_actions.append(action_dict)

		except Exception as e:
			# Browser-use pattern: Tools.act() catches BrowserError, TimeoutError, and general exceptions
			# and returns ActionResult with error field set
			# If we get here, it's an exception during conversion or Tools initialization
			logger.error(f"Error executing action {action_type}: {e}", exc_info=True)
			print(f"    ❌ Exception: {str(e)[:100]}")
			action_results.append({
				"success": False,
				"action": action_dict,
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
	page_changing_action_types = ["navigate", "switch", "go_back"]
	dom_changing_action_types = ["click", "input", "scroll"]
	
	has_page_changing_action = any(
		a.get("action") in page_changing_action_types 
		for a in executed_actions
	)
	has_dom_changing_action = any(
		a.get("action") in dom_changing_action_types 
		for a in executed_actions
	)
	
	if has_page_changing_action or has_dom_changing_action:
		# Clear cache for any action that might change DOM
		action_type = executed_actions[-1].get("action") if executed_actions else "unknown"
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
	just_switched_tab = any(a.get("action") == "switch" for a in executed_actions)
	
	# Build return state with fresh browser state info
	return_state = {
		"executed_actions": executed_actions,
		"action_results": action_results,
		"history": existing_history + [new_history_entry],
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
	
	return return_state


def convert_to_action_model(action_dict: Dict[str, Any], ActionModelClass: type = None, registry = None) -> Any:
	"""
	Convert our action dict to browser-use ActionModel format

	Args:
		action_dict: Our action dictionary from LLM parsing
		ActionModelClass: Dynamic ActionModel class with action fields (if None, will try to import)

	Returns:
		ActionModel instance or None if conversion fails
	"""
	action_type = action_dict.get("action") or action_dict.get("type")

	if not action_type:
		logger.warning(f"No action type in dict: {action_dict}")
		return None

	# Import action classes from browser-use
	from qa_agent.tools.views import (
		ClickElementAction,
		InputTextAction,
		NavigateAction,
		DoneAction,
		ScrollAction,
		SendKeysAction,
		SwitchTabAction,
		CloseTabAction,
		ExtractAction,
		SearchAction,
		WaitAction,
		NoParamsAction,
	)
	
	# Use provided ActionModel class or fallback to base
	if ActionModelClass is None:
		from qa_agent.agent.views import ActionModel as ActionModelClass

	try:
		# Map action types to ActionModel fields
		# IMPORTANT: Browser-use uses function names as ActionModel field names
		# Function names: click, input, navigate, scroll, done, search, extract
		# Also support legacy names: click_element, input_text, go_to_url (for backward compatibility)

		# Handle click actions (both "click" and legacy "click_element")
		if action_type == "click" or action_type == "click_element":
			index = action_dict.get("index") or action_dict.get("element_index")
			if index is None or index == 0:
				logger.warning(f"Invalid index for click action (must be > 0): {action_dict}")
				return None
			return ActionModelClass(click=ClickElementAction(index=int(index)))

		# Handle input actions (both "input" and legacy "input_text")
		elif action_type == "input" or action_type == "input_text":
			# Check for index explicitly (can be 0, which is valid for input)
			index = action_dict.get("index")
			if index is None:
				index = action_dict.get("element_index")
			text = action_dict.get("text") or action_dict.get("value", "")
			if index is None:
				logger.warning(f"No index for input action: {action_dict}")
				return None
			clear = action_dict.get("clear", True)
			# Index 0 is valid for input actions (different from click which requires > 0)
			return ActionModelClass(input=InputTextAction(index=int(index), text=str(text), clear=clear))

		# Handle navigate actions (both "navigate" and legacy "go_to_url")
		elif action_type == "navigate" or action_type == "go_to_url":
			url = action_dict.get("url") or action_dict.get("target")
			if not url:
				logger.warning(f"No URL for navigate action: {action_dict}")
				return None
			new_tab = action_dict.get("new_tab", False)
			return ActionModelClass(navigate=NavigateAction(url=str(url), new_tab=new_tab))

		elif action_type == "done":
			text = action_dict.get("text") or action_dict.get("message", "Task completed")
			success = action_dict.get("success", True)
			return ActionModelClass(done=DoneAction(text=str(text), success=success))

		elif action_type == "scroll":
			down = action_dict.get("down", True)
			pages = action_dict.get("pages", 1.0)
			index = action_dict.get("index")
			return ActionModelClass(scroll=ScrollAction(down=down, pages=float(pages), index=int(index) if index else None))

		elif action_type == "send_keys":
			keys = action_dict.get("keys", "")
			return ActionModelClass(send_keys=SendKeysAction(keys=str(keys)))

		elif action_type == "switch_tab" or action_type == "switch":
			# Browser-use uses "switch" as the action name
			tab_id = action_dict.get("tab_id", "")
			# Ensure tab_id is 4 characters (last 4 of target_id) - browser-use requirement
			if tab_id and len(str(tab_id)) > 4:
				tab_id = str(tab_id)[-4:]
			elif tab_id and len(str(tab_id)) < 4:
				logger.warning(f"Tab ID {tab_id} is less than 4 characters, may be invalid")
			return ActionModelClass(switch=SwitchTabAction(tab_id=str(tab_id)[-4:] if tab_id else ""))

		elif action_type == "close_tab":
			tab_id = action_dict.get("tab_id", "")
			return ActionModelClass(close_tab=CloseTabAction(tab_id=str(tab_id)))

		elif action_type == "extract":
			# Browser-use extract requires a non-empty query string
			query = str(action_dict.get("query", "")).strip()
			if not query:
				logger.warning("Extract action requires a non-empty query string")
				return None
			
			# Get param model from registry (browser-use pattern)
			if registry and "extract" in registry.registry.actions:
				extract_action_info = registry.registry.actions["extract"]
				param_model = extract_action_info.param_model
				
				# Browser-use registry creates param_model from function signature
				# Since extract() has params: ExtractAction as first param, the model expects:
				# extract_Params(params: ExtractAction)
				# So we need to create ExtractAction first, then wrap it in params field
				from qa_agent.tools.views import ExtractAction
				extract_action = ExtractAction(
					query=query,
					extract_links=bool(action_dict.get("extract_links", False)),
					start_from_char=int(action_dict.get("start_from_char", 0)),
				)
				
				# Check if param_model expects a 'params' field (registry-inferred pattern)
				try:
					# Try wrapping in 'params' field (registry pattern)
					validated_params = param_model(params=extract_action)
					return ActionModelClass(extract=validated_params)
				except Exception:
					# If that fails, try direct ExtractAction (shouldn't happen but fallback)
					try:
						validated_params = param_model(**extract_action.model_dump())
						return ActionModelClass(extract=validated_params)
					except Exception as e:
						logger.warning(f"Could not create extract param_model: {e}, using ExtractAction directly")
						return ActionModelClass(extract=extract_action)
			else:
				# Fallback to our ExtractAction
				extract_links = action_dict.get("extract_links", False)
				start_from_char = action_dict.get("start_from_char", 0)
				return ActionModelClass(extract=ExtractAction(query=query, extract_links=bool(extract_links), start_from_char=int(start_from_char)))

		elif action_type == "search":
			query = action_dict.get("query", "")
			engine = action_dict.get("engine", "duckduckgo")
			return ActionModelClass(search=SearchAction(query=str(query), engine=engine))

		elif action_type == "wait":
			# Get param model from registry (browser-use pattern)
			if registry and "wait" in registry.registry.actions:
				wait_action_info = registry.registry.actions["wait"]
				param_model = wait_action_info.param_model
				# Create params dict
				params_dict = {"seconds": int(action_dict.get("seconds", 3))}
				# Validate and create param instance
				validated_params = param_model(**params_dict)
				return ActionModelClass(wait=validated_params)
			else:
				# Fallback to our WaitAction
				from qa_agent.tools.views import WaitAction
				seconds = action_dict.get("seconds", 3)
				return ActionModelClass(wait=WaitAction(seconds=int(seconds)))

		elif action_type == "screenshot":
			from qa_agent.tools.views import NoParamsAction
			# Screenshot uses NoParamsAction
			return ActionModelClass(screenshot=NoParamsAction())

		elif action_type == "go_back":
			from qa_agent.tools.views import NoParamsAction
			# Go back uses NoParamsAction
			return ActionModelClass(go_back=NoParamsAction())

		else:
			logger.warning(f"Unknown action type: {action_type}")
			return None

	except Exception as e:
		logger.error(f"Error converting action {action_type} to ActionModel: {e}", exc_info=True)
		return None
