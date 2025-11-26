"""
ACT Wrapper - Bridge between minimal THINK and action execution

This wrapper:
1. Takes think_output from minimal THINK node
2. Gets fresh browser state and validates page context
3. Generates actions using LLM + fresh DOM
4. Calls the original act_node logic to execute
5. Returns structured feedback with page validation info

This allows us to keep the existing act_node while adapting it for hierarchical flow.
"""
import logging
from typing import Dict, Any, Optional, Tuple

from web_agent.state import QAAgentState
from web_agent.llm import get_llm
from web_agent.utils.session_registry import get_session
from web_agent.tools.service import Tools
from web_agent.filesystem.file_system import FileSystem
from web_agent.prompts.browser_prompts import SystemPrompt, AgentMessagePrompt
from web_agent.agent.views import AgentStepInfo, AgentOutput
from web_agent.utils.page_context import PageContextAnalyzer, compare_dom_states
from web_agent.utils.todo_parser import get_todo_progress, get_current_step
from web_agent.utils.error_detector import ErrorDetector
from pathlib import Path

logger = logging.getLogger(__name__)


async def validate_page_context(
	browser_state: Any,
	file_system: FileSystem,
	think_output: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
	"""
	Validate if current page matches the expected page for the todo step.

	Args:
		browser_state: Fresh browser state
		file_system: FileSystem with todo.md
		think_output: Strategic decision from THINK

	Returns:
		(is_valid, inferred_page, recovery_suggestion)
		- is_valid: True if on correct page
		- inferred_page: Detected page type
		- recovery_suggestion: Navigation hint if page mismatch (None if valid)
	"""
	try:
		# Get current todo step
		todo_contents = file_system.get_todo_contents()
		if not todo_contents or todo_contents.strip() == '[empty todo.md, fill it when applicable]':
			logger.info("📄 No todo.md yet - skipping page validation")
			return True, "unknown", None

		progress = get_todo_progress(todo_contents)
		current_step = progress.get("current_step")

		if not current_step:
			logger.info("✅ All steps completed - skipping page validation")
			return True, "unknown", None

		current_step_text = current_step.get("text", "")

		# Special case: If step is a URL navigation, skip page validation
		# Navigation actions can happen from anywhere and the browser will handle the page change
		step_lower = current_step_text.lower()
		if any(kw in step_lower for kw in ["navigate to", "go to", "visit", "http", "https://"]):
			logger.info(f"📄 Navigation step detected - skipping page validation (page will change on navigation)")
			return True, "unknown", None

		# Analyze page context
		analyzer = PageContextAnalyzer(browser_state)
		inferred_page = analyzer.infer_current_page()

		# Validate page against todo step
		is_valid, validation_reason = analyzer.validate_against_todo_step(current_step_text)

		logger.info(f"🔍 Page Validation:")
		logger.info(f"   Inferred page: {inferred_page}")
		logger.info(f"   Step: {current_step_text[:80]}")
		logger.info(f"   Validation: {validation_reason}")

		if not is_valid:
			recovery = analyzer.suggest_recovery(current_step_text)
			logger.warning(f"⚠️  Page mismatch! Recovery suggestion: {recovery}")
			return False, inferred_page, recovery

		return True, inferred_page, None

	except Exception as e:
		logger.warning(f"⚠️  Could not validate page context: {e}")
		return True, "unknown", None  # Don't block execution on validation error


async def generate_actions_from_think(
	think_output: str,
	task: str,
	browser_session,
	browser_state,
	step_count: int,
	max_steps: int,
	file_system,
	llm,
	tools,
) -> list:
	"""
	Generate specific actions from THINK's strategic decision + fresh DOM.

	Args:
		think_output: Strategic decision from THINK (e.g., "Click login button")
		task: Original task
		browser_session: Current browser session
		browser_state: Fresh browser state with current DOM
		step_count: Current step number
		max_steps: Max steps allowed
		file_system: FileSystem instance
		llm: LLM instance
		tools: Tools instance

	Returns:
		List of ActionModel objects ready for execution
	"""
	try:
		logger.info(f"🔧 Generating actions from THINK output: {think_output}")

		# Build ACT-specific prompt
		system_prompt = SystemPrompt(
			max_actions_per_step=3,  # Default from settings
			use_thinking=False,
			flash_mode=False,
		)

		# Create enhanced task that includes THINK output
		enhanced_task = f"""STRATEGY FROM THINK NODE:
→ {think_output}

Your job is to EXECUTE this strategy using the browser below.
Analyze the current page, find the right element, and perform the action.

Original task: {task}
"""

		step_info = AgentStepInfo(step_number=step_count, max_steps=max_steps)

		agent_message_prompt = AgentMessagePrompt(
			browser_state_summary=browser_state,
			file_system=file_system,
			agent_history_description=None,
			read_state_description=None,
			task=enhanced_task,
			step_info=step_info,
			max_clickable_elements_length=40000,
		)

		# Get messages
		system_message = system_prompt.get_system_message()
		user_message = agent_message_prompt.get_user_message(use_vision=False)

		system_content = system_message.content if hasattr(system_message, 'content') else str(system_message)
		user_content = user_message.content if hasattr(user_message, 'content') else str(user_message)

		# Convert to LangChain format
		from langchain_core.messages import SystemMessage as LCSystemMessage, HumanMessage

		langchain_messages = [
			LCSystemMessage(content=system_content),
			HumanMessage(content=user_content if isinstance(user_content, str) else str(user_content))
		]

		# Call LLM to generate actions
		action_model_class = tools.registry.create_action_model(page_url=browser_state.url)
		dynamic_agent_output = AgentOutput.type_with_custom_actions(action_model_class)

		logger.info(f"💭 Calling LLM to generate actions...")
		structured_llm = llm.with_structured_output(dynamic_agent_output, method="function_calling")
		raw_response = await structured_llm.ainvoke(langchain_messages)

		# Validate and extract
		if isinstance(raw_response, dict):
			completion_data = raw_response
		else:
			completion_data = raw_response.model_dump() if hasattr(raw_response, 'model_dump') else dict(raw_response)

		parsed = dynamic_agent_output.model_validate(completion_data)
		planned_actions = parsed.action if hasattr(parsed, 'action') else []

		logger.info(f"✅ Generated {len(planned_actions)} actions")
		return planned_actions

	except Exception as e:
		logger.error(f"❌ Failed to generate actions from THINK output: {e}", exc_info=True)
		return []


async def act_wrapper_node(state: QAAgentState) -> Dict[str, Any]:
	"""
	ACT Wrapper: Generate actions from THINK output, then execute them.

	This bridges minimal THINK (strategic) with execution (tactical).

	Args:
		state: Current QA agent state

	Returns:
		Updated state with executed actions and feedback
	"""
	try:
		step_count = state.get("step_count", 0)
		logger.info(f"\n{'='*80}")
		logger.info(f"🎭 ACT WRAPPER - Step {step_count}")
		logger.info(f"{'='*80}")

		# ===== Get Session =====
		browser_session_id = state.get("browser_session_id")
		if not browser_session_id:
			raise ValueError("No browser_session_id")

		browser_session = get_session(browser_session_id)
		if not browser_session:
			raise ValueError(f"Browser session not found")

		# ===== Get THINK Output =====
		think_output = state.get("think_output")
		if not think_output:
			logger.warning("⚠️  No think_output")
			think_output = "Continue with next action"

		logger.info(f"📋 THINK Output: {think_output}")

		# ===== Get Fresh Browser State =====
		logger.info("🌐 Getting fresh browser state...")
		browser_state = await browser_session.get_browser_state_summary(
			include_screenshot=False,
			cached=False
		)

		# ===== Setup =====
		task = state.get("task", "")
		max_steps = state.get("max_steps", 50)
		file_system_state = state.get("file_system_state")

		if file_system_state:
			file_system = FileSystem.from_state(file_system_state)
		else:
			file_system_dir = Path("web_agent_workspace") / f"session_{browser_session_id[:8]}"
			file_system = FileSystem(base_dir=file_system_dir, create_default_files=False)

		llm = get_llm()
		tools = Tools()

		# ===== Validate Page Context =====
		logger.info("📍 Validating page context against todo step...")
		is_page_valid, inferred_page, recovery_suggestion = await validate_page_context(
			browser_state=browser_state,
			file_system=file_system,
			think_output=think_output,
		)

		page_validation_info = {
			"is_valid": is_page_valid,
			"inferred_page": inferred_page,
			"recovery_suggestion": recovery_suggestion,
		}

		# If page is invalid and we have a recovery suggestion, pass it to THINK
		if not is_page_valid and recovery_suggestion:
			logger.error(f"❌ Page validation failed: {recovery_suggestion}")
			return {
				"executed_actions": [],
				"action_results": [],
				"act_feedback": {
					"success": False,
					"error": f"Page mismatch: {recovery_suggestion}",
					"page_validation": page_validation_info,
				},
				"act_error_context": recovery_suggestion,
				"last_act_result_success": False,
				"page_validation": page_validation_info,
			}

		# ===== Generate Actions from THINK Output =====
		planned_actions = await generate_actions_from_think(
			think_output=think_output,
			task=task,
			browser_session=browser_session,
			browser_state=browser_state,
			step_count=step_count,
			max_steps=max_steps,
			file_system=file_system,
			llm=llm,
			tools=tools,
		)

		if not planned_actions:
			logger.warning("⚠️  No actions generated from THINK output")
			return {
				"executed_actions": [],
				"action_results": [],
				"act_feedback": {
					"success": False,
					"error": "No actions generated",
				},
				"act_error_context": "LLM could not generate actions from THINK decision",
				"last_act_result_success": False,
			}

		# ===== Execute Actions =====
		logger.info(f"⚙️  Executing {len(planned_actions)} actions...")

		# Add planned_actions to state for original act_node logic
		state_with_actions = {**state, "planned_actions": planned_actions}

		# Import and call original act_node
		from web_agent.nodes.act import act_node as original_act_node

		result = await original_act_node(state_with_actions)

		# ===== Build Feedback =====
		executed_actions = result.get("executed_actions", [])
		action_results = result.get("action_results", [])

		all_succeeded = all(r.get("success", False) for r in action_results) if action_results else len(executed_actions) > 0

		# Find last result summary
		last_result_summary = ""
		if action_results:
			for r in reversed(action_results):
				if r.get("extracted_content"):
					last_result_summary = r.get("extracted_content")
					break
				elif r.get("long_term_memory"):
					last_result_summary = r.get("long_term_memory")
					break

		# ===== Extract Error Context (Smart Error Detection) =====
		error_context = None
		detected_errors = []

		# 1. Check action results for explicit errors
		if not all_succeeded:
			for r in action_results:
				if r.get("error"):
					error_context = r.get("error")
					break

		# 2. Scan browser state for DOM + Console errors (new feature)
		try:
			dom_errors = ErrorDetector.extract_errors_from_dom(
				browser_state=browser_state,
				browser_session=browser_session  # Pass session for console error access
			)
			if dom_errors:
				detected_errors.extend(dom_errors)
				logger.info(f"🚨 Detected {len(dom_errors)} error message(s) on page:")
				for err in dom_errors:
					logger.info(f"   - [{err.error_type}] {err.message[:70]}")
		except Exception as e:
			logger.warning(f"⚠️  Error detection scan failed: {e}")

		# 3. Extract errors from action results
		for r in action_results:
			result_errors = ErrorDetector.extract_errors_from_action_result(r)
			detected_errors.extend(result_errors)

		# 4. Build comprehensive error context
		if detected_errors:
			# Sort by severity (high > medium > low)
			severity_order = {"high": 0, "medium": 1, "low": 2}
			detected_errors.sort(key=lambda e: severity_order.get(e.severity, 3))

			# Use the most severe error as primary error context
			primary_error = detected_errors[0]
			error_context = f"[{primary_error.error_type.upper()}] {primary_error.message}"

			# If there's a recovery hint, include it
			if primary_error.recovery_hint:
				error_context += f" → Recovery: {primary_error.recovery_hint}"

		# Build feedback with page validation info and error details
		act_feedback = {
			"success": all_succeeded,
			"action_count": len(executed_actions),
			"result_summary": last_result_summary,
			"actions_executed": [a.get("action") for a in executed_actions],
			"page_validation": page_validation_info,
			"detected_errors": [
				{
					"type": e.error_type,
					"message": e.message,
					"severity": e.severity,
					"recovery_hint": e.recovery_hint,
				}
				for e in detected_errors
			],
		}

		logger.info(f"📊 ACT Result: success={all_succeeded}, actions={len(executed_actions)}")
		logger.info(f"📍 Page info: {inferred_page} (valid={is_page_valid})")
		logger.info(f"{'='*80}\n")

		return {
			"executed_actions": executed_actions,
			"action_results": action_results,
			"act_feedback": act_feedback,
			"act_error_context": error_context,
			"last_act_result_success": all_succeeded,
			"file_system_state": file_system.get_state(),
			"page_validation": page_validation_info,
			"inferred_page": inferred_page,
			"think_retries": 0,  # Reset retry counter on success
			"history": result.get("history", []),  # From original act_node
		}

	except Exception as e:
		logger.error(f"❌ ACT Wrapper error: {e}", exc_info=True)

		return {
			"executed_actions": [],
			"action_results": [],
			"act_feedback": {
				"success": False,
				"error": str(e),
				"page_validation": {
					"is_valid": False,
					"inferred_page": "unknown",
					"recovery_suggestion": "ACT wrapper encountered an error. Please check logs.",
				},
			},
			"act_error_context": str(e),
			"last_act_result_success": False,
			"error": str(e),
		}
