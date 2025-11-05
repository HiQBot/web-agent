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

	# Initialize Tools instance
	logger.info("Initializing browser-use Tools")
	tools = Tools()
	
	# Get dynamic ActionModel class from Tools registry
	# This ActionModel has the actual action fields (click, input, navigate, etc.)
	from pydantic import create_model
	from qa_agent.agent.views import ActionModel as BaseActionModel
	from qa_agent.tools.views import ClickElementAction, InputTextAction, NavigateAction, DoneAction, ScrollAction, SendKeysAction, SwitchTabAction, CloseTabAction, ExtractAction, SearchAction
	
	# Create a dynamic ActionModel that accepts all our action types
	# Browser-use creates this dynamically, but we'll create it manually for simplicity
	DynamicActionModel = create_model(
		'DynamicActionModel',
		__base__=BaseActionModel,
		click=(ClickElementAction, None),
		input=(InputTextAction, None),
		navigate=(NavigateAction, None),
		done=(DoneAction, None),
		scroll=(ScrollAction, None),
		send_keys=(SendKeysAction, None),
		switch_tab=(SwitchTabAction, None),
		close_tab=(CloseTabAction, None),
		extract=(ExtractAction, None),
		search=(SearchAction, None),
	)

	# Execute actions sequentially
	executed_actions = []
	action_results = []

	for i, action_dict in enumerate(planned_actions, 1):
		action_type = action_dict.get("action") or action_dict.get("type")
		print(f"\n  [{i}/{len(planned_actions)}] Executing: {action_type}")

		try:
			# Convert our action dict to browser-use ActionModel
			action_model = convert_to_action_model(action_dict, DynamicActionModel)

			if not action_model:
				logger.warning(f"Could not convert action to ActionModel: {action_dict}")
				print(f"    ⚠️  Skipping invalid action: {action_type}")
				action_results.append({
					"success": False,
					"action": action_dict,
					"error": "Invalid action format",
				})
				continue

			# Execute action via browser-use Tools
			logger.info(f"Executing {action_type} via Tools.act()")
			result = await tools.act(action=action_model, browser_session=session)

			# Extract result data
			success = result.error is None
			extracted_content = result.extracted_content
			error_msg = result.error
			is_done = result.is_done

			logger.info(f"Action {action_type} {'succeeded' if success else 'failed'}: {extracted_content or error_msg}")
			print(f"    ✅ {action_type} completed" if success else f"    ❌ {action_type} failed: {error_msg}")

			# Store result
			action_results.append({
				"success": success,
				"action": action_dict,
				"extracted_content": extracted_content,
				"error": error_msg,
				"is_done": is_done,
			})
			executed_actions.append(action_dict)

		except Exception as e:
			logger.error(f"Error executing action {action_type}: {e}", exc_info=True)
			print(f"    ❌ Exception: {str(e)[:100]}")
			action_results.append({
				"success": False,
				"action": action_dict,
				"error": str(e),
			})

	print(f"\n✅ Executed {len(executed_actions)}/{len(planned_actions)} actions")
	print(f"{'='*80}\n")

	# Update history
	existing_history = state.get("history", [])
	new_history_entry = {
		"step": state.get("step_count", 0),
		"node": "act",
		"executed_actions": executed_actions,
		"action_results": action_results,
		"success_count": sum(1 for r in action_results if r.get("success")),
		"total_count": len(action_results),
	}

	return {
		"executed_actions": executed_actions,
		"action_results": action_results,
		"history": existing_history + [new_history_entry],
	}


def convert_to_action_model(action_dict: Dict[str, Any], ActionModelClass: type = None) -> ActionModel | None:
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
			index = action_dict.get("index") or action_dict.get("element_index")
			text = action_dict.get("text") or action_dict.get("value", "")
			if index is None:
				logger.warning(f"No index for input action: {action_dict}")
				return None
			clear = action_dict.get("clear", True)
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

		elif action_type == "switch_tab":
			tab_id = action_dict.get("tab_id", "")
			return ActionModelClass(switch_tab=SwitchTabAction(tab_id=str(tab_id)))

		elif action_type == "close_tab":
			tab_id = action_dict.get("tab_id", "")
			return ActionModelClass(close_tab=CloseTabAction(tab_id=str(tab_id)))

		elif action_type == "extract":
			query = action_dict.get("query", "")
			return ActionModelClass(extract=ExtractAction(query=str(query)))

		elif action_type == "search":
			query = action_dict.get("query", "")
			engine = action_dict.get("engine", "duckduckgo")
			return ActionModelClass(search=SearchAction(query=str(query), engine=engine))

		else:
			logger.warning(f"Unknown action type: {action_type}")
			return None

	except Exception as e:
		logger.error(f"Error converting action {action_type} to ActionModel: {e}")
		return None
