"""
Minimal THINK Node - Strategic Planning with Page Awareness

This node:
1. Reads todo.md to identify current incomplete step
2. Gets previous ACT result (if any), including page validation info
3. Handles page mismatches intelligently
4. Calls LLM with MINIMAL prompt (strategic decision only)
5. Outputs think_output (what to do next, not how)
6. Returns quickly (~1 second) with ~300 tokens

The actual action execution is handled by ACT node with fresh DOM.
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from qa_agent.state import QAAgentState
from qa_agent.config import settings
from qa_agent.llm import get_llm
from qa_agent.filesystem.file_system import FileSystem
from qa_agent.utils.session_registry import get_session
from qa_agent.utils.todo_parser import get_current_step, get_todo_progress, format_todo_for_think_node
from qa_agent.prompts.minimal_think_builder import MinimalThinkPromptBuilder, MinimalThinkResponse

logger = logging.getLogger(__name__)

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


async def think_node(state: QAAgentState) -> Dict[str, Any]:
	"""
	Minimal THINK node: Strategic planning only (fast, cheap).

	Input: task + todo.md + previous ACT result
	Output: think_output (strategic decision)

	NOT responsible for: DOM analysis, action generation, element selection
	(That's ACT node's job with fresh state)

	Args:
		state: Current QA agent state

	Returns:
		Updated state with think_output
	"""
	try:
		step_count = state.get("step_count", 0) + 1
		logger.info(f"\n{'='*80}")
		logger.info(f"🧠 MINIMAL THINK NODE - Step {step_count} (Strategic Planning)")
		logger.info(f"{'='*80}")

		# ===== 1. Get Browser Session & FileSystem =====
		browser_session_id = state.get("browser_session_id")
		if not browser_session_id:
			raise ValueError("No browser_session_id in state - INIT node must run first")

		browser_session = get_session(browser_session_id)
		if not browser_session:
			raise ValueError(f"Browser session {browser_session_id} not found")

		# Restore FileSystem from state
		file_system_state = state.get("file_system_state")
		if file_system_state:
			file_system = FileSystem.from_state(file_system_state)
			logger.info("✅ Restored FileSystem with todo.md")
		else:
			# First run: create FileSystem
			file_system_dir = Path("qa_agent_workspace") / f"session_{browser_session_id[:8]}"
			file_system = FileSystem(base_dir=file_system_dir, create_default_files=True, clean_data_dir=False)
			logger.info("✅ Created new FileSystem")

		# ===== 2. Get Task & Todo Information =====
		task = state.get("task", "")
		todo_contents = file_system.get_todo_contents()

		if not todo_contents or todo_contents.strip() == '[empty todo.md, fill it when applicable]':
			logger.warning("⚠️  No todo.md yet - INIT should create it, but continuing...")
			todo_contents = f"## Goal\n{task}\n\n## Tasks:\n- [ ] Complete the task\n"

		# Get progress
		progress = get_todo_progress(todo_contents)
		logger.info(f"📊 Todo Progress: {progress['completed']}/{progress['total']} steps completed")

		current_step = progress.get("current_step")
		if not current_step:
			logger.info("✅ All steps completed!")
			return {
				"step_count": step_count,
				"think_output": "All todo items completed",
				"think_reasoning": "No pending tasks remain",
				"completed": True,
				"planned_actions": [],
			}

		logger.info(f"📍 Current Step [{current_step['index'] + 1}]: {current_step['text']}")

		# ===== 3. Get Previous ACT Result =====
		previous_result = state.get("act_feedback")
		last_success = state.get("last_act_result_success", False)
		last_error = state.get("act_error_context")
		think_retries = state.get("think_retries", 0)
		page_validation = state.get("page_validation", {})

		if previous_result:
			logger.info(f"📋 Previous ACT Result:")
			logger.info(f"   Success: {last_success}")
			if last_error:
				logger.info(f"   Error: {last_error[:100]}")
		else:
			logger.info("📋 First step (no previous result)")

		# ===== 3.5. Handle Smart Error Recovery =====
		# First: Check for detected errors from ACT (intelligent error handling)
		detected_errors = previous_result.get("detected_errors", []) if previous_result else []

		if detected_errors and not last_success:
			logger.warning(f"🚨 Smart Error Recovery Triggered!")
			logger.warning(f"   Detected {len(detected_errors)} error(s) from ACT")

			# Analyze the primary error to make intelligent decision
			primary_error = detected_errors[0]
			error_type = primary_error.get("type")
			error_msg = primary_error.get("message")
			recovery_hint = primary_error.get("recovery_hint")

			logger.warning(f"   Error Type: {error_type}")
			logger.warning(f"   Message: {error_msg[:80]}")

			# Increment retry counter for smart recovery
			think_retries += 1

			# Generate intelligent recovery strategy based on error type
			if error_type == "already_exists":
				# Email/username already exists - suggest switching to login
				think_output = f"The {error_msg[:50]} Try switching to login with these credentials instead."
				reasoning = f"Error indicates account exists. Suggest login instead of signup. (Retry {think_retries}/3)"

			elif error_type == "permission_denied":
				# Permission issue - check if we need to sign out and sign in as different user
				think_output = "Permission denied. Try logging in with appropriate account or adjust access settings."
				reasoning = f"Permission error detected. Check account permissions. (Retry {think_retries}/3)"

			elif error_type == "invalid_input":
				# Invalid input - suggest correcting the input
				think_output = f"Previous action had validation error: {error_msg[:80]}. Try with corrected input."
				reasoning = f"Validation error detected. Suggest correcting input. (Retry {think_retries}/3)"

			elif error_type == "network_error":
				# Network issue - retry the action
				think_output = "Network error detected. Let me retry the action."
				reasoning = f"Network issue detected. Retrying action. (Retry {think_retries}/3)"

			elif error_type == "server_error":
				# Server error - wait and retry
				think_output = "Server error detected. Let me retry after a moment."
				reasoning = f"Server error detected. Will retry action. (Retry {think_retries}/3)"

			else:
				# Generic error - use recovery hint if available
				think_output = recovery_hint or f"Error occurred: {error_msg[:60]}. Let me try again."
				reasoning = f"Error detected: {error_type}. Attempting recovery. (Retry {think_retries}/3)"

			# If too many retries with same error, mark as blocked
			if think_retries > 3:
				logger.error(f"❌ Too many retries (>{3}) for error type '{error_type}'. Task may be stuck.")
				think_output = f"Unable to recover from error: {error_type}. {recovery_hint or 'Please check the page manually.'}"
				reasoning = f"Failed to recover after {think_retries} attempts"

			logger.info(f"🔧 Smart Recovery Strategy: {think_output[:80]}")
			logger.info(f"{'='*80}\n")

			# Build history entry
			history_entry = {
				"step": step_count,
				"node": "think",
				"think_output": think_output,
				"thinking": reasoning,
				"current_step_index": current_step['index'],
				"current_step_text": current_step['text'],
				"error_recovery": True,
				"error_type": error_type,
				"error_message": error_msg,
				"retry_count": think_retries,
				"todo_progress": progress,
			}

			return {
				"step_count": step_count,
				"think_output": think_output,
				"think_reasoning": reasoning,
				"file_system_state": file_system.get_state() if file_system else file_system_state,
				"planned_actions": [],
				"history": [history_entry],
				"think_retries": think_retries,
				"detected_errors": detected_errors,
				"completed": False,
			}

		# ===== 3.6. Handle Page Mismatch from ACT =====
		# If ACT detected page mismatch, generate recovery navigation action
		page_validation_info = previous_result.get("page_validation") if previous_result else None

		if page_validation_info and not page_validation_info.get("is_valid"):
			recovery_suggestion = page_validation_info.get("recovery_suggestion")
			inferred_page = page_validation_info.get("inferred_page")

			logger.warning(f"⚠️  Page mismatch detected by ACT!")
			logger.warning(f"   Current page: {inferred_page}")
			logger.warning(f"   Recovery: {recovery_suggestion}")

			# Increment retry counter
			think_retries += 1

			# If we've retried too many times, mark as blocked
			if think_retries > 3:
				logger.error(f"❌ Too many retries (>{3}). Page navigation may be stuck.")
				think_output = f"Unable to navigate to required page. {recovery_suggestion}"
				reasoning = f"Attempted {think_retries} times, page mismatch persists"
			else:
				# Use recovery suggestion as think_output
				think_output = recovery_suggestion
				reasoning = f"Page mismatch detected. Retry {think_retries}/3: {recovery_suggestion}"

				logger.info(f"🔄 Generating recovery navigation action (retry {think_retries}/3)")
				logger.info(f"{'='*80}\n")

				# Build history entry
				history_entry = {
					"step": step_count,
					"node": "think",
					"think_output": think_output,
					"thinking": reasoning,
					"current_step_index": current_step['index'],
					"current_step_text": current_step['text'],
					"page_mismatch_recovery": True,
					"inferred_page": inferred_page,
					"retry_count": think_retries,
					"todo_progress": progress,
				}

				return {
					"step_count": step_count,
					"think_output": think_output,
					"think_reasoning": reasoning,
					"file_system_state": file_system.get_state() if file_system else file_system_state,
					"planned_actions": [],
					"history": [history_entry],
					"think_retries": think_retries,
					"page_validation": page_validation_info,
					"completed": False,
				}

		# ===== 4. Build Minimal Prompt =====
		logger.info("🔨 Building minimal prompt...")

		prompt_builder = MinimalThinkPromptBuilder()
		messages = prompt_builder.build_messages(
			task=task,
			todo_contents=format_todo_for_think_node(todo_contents),
			previous_result=previous_result
		)

		logger.info(f"   System message: ~{len(messages[0].content)} chars")
		logger.info(f"   User message: ~{len(messages[1].content)} chars")

		# ===== 5. Call LLM (Fast & Cheap) =====
		logger.info("🤖 Calling LLM for strategic decision...")
		llm = get_llm()

		llm_response = await llm.ainvoke(messages)
		response_text = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

		logger.info(f"✅ LLM Response received ({len(response_text)} chars)")

		# ===== 6. Parse Response =====
		logger.info("📝 Parsing THINK response...")
		parsed_response = MinimalThinkResponse(response_text)

		if not parsed_response.is_valid():
			logger.warning("⚠️  Invalid THINK response, using fallback")
			think_output = f"Continue with: {current_step['text']}"
			reasoning = "LLM response parsing failed, using current step"
		else:
			think_output = parsed_response.next_step
			reasoning = parsed_response.reasoning

		logger.info(f"🎯 THINK Decision: {think_output}")
		logger.info(f"   Reasoning: {reasoning}")

		# ===== 7. Prepare Return State =====
		# Persist FileSystem state for next node
		file_system_state = file_system.get_state()

		# Build history entry
		history_entry = {
			"step": step_count,
			"node": "think",
			"think_output": think_output,
			"thinking": reasoning,
			"current_step_index": current_step['index'],
			"current_step_text": current_step['text'],
			"todo_progress": progress,
			"retry_count": think_retries,
		}

		# Determine if task is done (all steps completed)
		task_complete = progress["all_done"]

		logger.info(f"{'✅ TASK COMPLETE' if task_complete else '⏳ Continuing...'}")
		logger.info(f"{'='*80}\n")

		return {
			"step_count": step_count,
			"think_output": think_output,  # Strategic decision for ACT node
			"think_reasoning": reasoning,  # Reasoning (for debugging)
			"file_system_state": file_system_state,  # Persist todo.md
			"planned_actions": [],  # NOT generated by minimal THINK
			"history": [history_entry],  # Reducer: accumulate
			"completed": task_complete,  # Done if all todo items complete
			"think_retries": 0,  # Reset retries on successful planning
		}

	except Exception as e:
		logger.error(f"❌ THINK node error: {e}", exc_info=True)

		# Fallback: return safe state
		return {
			"step_count": state.get("step_count", 0) + 1,
			"think_output": "Error in THINK node - proceeding with next step",
			"error": str(e),
			"planned_actions": [],
			"history": [{
				"step": state.get("step_count", 0) + 1,
				"node": "think",
				"error": str(e),
			}],
		}
