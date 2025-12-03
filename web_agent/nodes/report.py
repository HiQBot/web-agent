"""
Report Node - Generate final test report with Judge evaluation and GIF

This node:
1. Collects all step results from workflow history
2. Generates judge evaluation (LLM-based quality assessment)
3. Creates animated GIF visualization of execution
4. Formats comprehensive final report
5. Cleans up browser session

Integration Notes:
- Judge evaluates task completion, output quality, and agent reasoning
- GIF visualizes agent trajectory with task overlay and step goals
- Both features work natively with OnKernal's QAAgentState structure
"""
import logging
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
from web_agent.state import QAAgentState
from web_agent.config import settings
from web_agent.utils.browser_manager import cleanup_browser_session

logger = logging.getLogger(__name__)


def _extract_final_result_from_history(history: List[Dict[str, Any]]) -> str:
	"""
	Extract final result from workflow history.

	Looks for:
	1. done action with completion message
	2. extract action results
	3. Last step's summary

	Args:
		history: Workflow execution history

	Returns:
		Final result string for judge evaluation
	"""
	if not history:
		return "No execution history available"

	final_result_parts = []

	# Iterate backwards to find most recent results
	for entry in reversed(history):
		if not isinstance(entry, dict):
			continue

		# Check for task completion in think node
		if entry.get("node") == "think" and entry.get("task_completed"):
			completion_msg = entry.get("completion_message", "")
			if completion_msg:
				final_result_parts.append(f"Task completed: {completion_msg}")
				break

		# Check for action results in act node
		if entry.get("node") == "act":
			action_results = entry.get("action_results", [])
			for result in action_results:
				if isinstance(result, dict):
					# Extract done action result
					if result.get("is_done"):
						extracted = result.get("extracted_content", "")
						if extracted:
							final_result_parts.append(extracted)

					# Extract any long-term memory (accumulated knowledge)
					memory = result.get("long_term_memory", "")
					if memory:
						final_result_parts.append(memory)

	# If nothing found, summarize from history
	if not final_result_parts:
		total_actions = sum(1 for e in history if e.get("node") == "act")
		total_steps = len([e for e in history if e.get("node") == "think"])
		final_result_parts.append(
			f"Executed {total_actions} actions across {total_steps} steps. "
			"No explicit completion result found in history."
		)

	return "\n\n".join(final_result_parts)


def _format_agent_steps_from_history(history: List[Dict[str, Any]]) -> List[str]:
	"""
	Format agent steps for judge evaluation.

	Creates human-readable step descriptions from workflow history.

	Args:
		history: Workflow execution history

	Returns:
		List of formatted step descriptions
	"""
	agent_steps = []
	step_number = 0

	for entry in history:
		if not isinstance(entry, dict):
			continue

		node_type = entry.get("node", "unknown")

		# Format think node steps (planning)
		if node_type == "think":
			step_number += 1
			goal = entry.get("current_goal", "No goal specified")
			actions_count = len(entry.get("actions", []))

			step_text = f"Step {step_number}: {goal}"
			if actions_count > 0:
				step_text += f" (planned {actions_count} actions)"

			agent_steps.append(step_text)

		# Format act node steps (execution)
		elif node_type == "act":
			executed_actions = entry.get("executed_actions", [])
			action_results = entry.get("action_results", [])

			if executed_actions:
				actions_summary = []
				for i, action in enumerate(executed_actions):
					if isinstance(action, dict):
						action_type = list(action.keys())[0] if action else "unknown"
						actions_summary.append(action_type)

				if actions_summary:
					step_text = f"  → Executed: {', '.join(actions_summary)}"

					# Add success/failure indicators
					if action_results:
						failed = sum(1 for r in action_results if isinstance(r, dict) and r.get("error"))
						if failed > 0:
							step_text += f" ({failed} failed)"

					agent_steps.append(step_text)

	return agent_steps if agent_steps else ["No agent steps recorded"]


def _collect_screenshot_paths_from_history(history: List[Dict[str, Any]]) -> List[str]:
	"""
	Collect screenshot file paths from history.

	Looks for screenshots stored as file paths in history entries.
	Note: Current OnKernal may store screenshots as base64 in state.
	This function prepares for future file-based screenshot storage.

	Args:
		history: Workflow execution history

	Returns:
		List of screenshot file paths
	"""
	screenshot_paths = []

	for entry in history:
		if not isinstance(entry, dict):
			continue

		# Check for screenshot path in entry
		screenshot_path = entry.get("screenshot_path")
		if screenshot_path and isinstance(screenshot_path, (str, Path)):
			path_obj = Path(screenshot_path)
			if path_obj.exists():
				screenshot_paths.append(str(path_obj))

		# Check for screenshots in browser state
		browser_state = entry.get("browser_state_summary")
		if browser_state and isinstance(browser_state, dict):
			screenshot_path = browser_state.get("screenshot_path")
			if screenshot_path and isinstance(screenshot_path, (str, Path)):
				path_obj = Path(screenshot_path)
				if path_obj.exists():
					screenshot_paths.append(str(path_obj))

	return screenshot_paths


def _convert_state_history_to_agent_history_list(state: QAAgentState):
	"""
	Convert QAAgentState history to AgentHistoryList format for GIF generation.

	This adapts OnKernal's workflow state to browser's AgentHistoryList
	format required by create_history_gif().

	Args:
		state: Current QAAgentState

	Returns:
		AgentHistoryList compatible with gif.py
	"""
	from web_agent.agent.views import AgentHistory, AgentHistoryList, AgentOutput, ActionResult
	from web_agent.browser.views import BrowserStateHistory

	history_items = []
	workflow_history = state.get("history", [])

	# Group by step: each step has think + act nodes
	current_step_data = {}

	for entry in workflow_history:
		if not isinstance(entry, dict):
			continue

		node_type = entry.get("node", "")
		step_num = entry.get("step", 0)

		# Initialize step data
		if step_num not in current_step_data:
			current_step_data[step_num] = {
				"model_output": None,
				"result": [],
				"url": "",
				"title": "",
				"screenshot": None,
			}

		# Collect think node data (model output)
		if node_type == "think":
			think_actions = entry.get("actions", [])
			current_goal = entry.get("current_goal", "")

			if think_actions:
				model_output = AgentOutput(
					thinking=entry.get("thinking", ""),
					evaluation_previous_goal=entry.get("evaluation_previous_goal", ""),
					memory=entry.get("memory", ""),
					next_goal=current_goal or "Continue task execution",
					action=[],
				)
				current_step_data[step_num]["model_output"] = model_output

		# Collect act node data (results and browser state)
		elif node_type == "act":
			action_results = entry.get("action_results", [])
			browser_state = entry.get("browser_state_summary", {})

			# Convert action results
			results = []
			for result_data in action_results:
				if isinstance(result_data, dict):
					results.append(ActionResult(**result_data))

			current_step_data[step_num]["result"] = results

			# Extract browser state
			if isinstance(browser_state, dict):
				current_step_data[step_num]["url"] = browser_state.get("url", "")
				current_step_data[step_num]["title"] = browser_state.get("title", "")
				current_step_data[step_num]["screenshot"] = browser_state.get("screenshot")

	# Build AgentHistory items
	for step_num in sorted(current_step_data.keys()):
		step_data = current_step_data[step_num]

		# Only add if we have meaningful data
		if step_data["model_output"] or step_data["result"]:
			browser_state_history = BrowserStateHistory(
				url=step_data["url"] or "about:blank",
				title=step_data["title"] or "Untitled",
				tabs=[],  # GIF doesn't use tabs info
				interacted_element=[],  # GIF doesn't need this
				screenshot_path=None  # Screenshots stored as base64 in OnKernal (TODO: save to files)
			)

			history_item = AgentHistory(
				model_output=step_data["model_output"],
				result=step_data["result"] if step_data["result"] else [],
				state=browser_state_history,
				metadata=None  # GIF doesn't use metadata
			)
			history_items.append(history_item)

	return AgentHistoryList(history=history_items, usage=None)


async def report_node(state: QAAgentState) -> Dict[str, Any]:
	"""
	Report node: Generate final test report with judge evaluation and GIF.

	This is the final node in the OnKernal workflow. It:
	1. Extracts execution data from QAAgentState history
	2. Runs LLM judge evaluation (if enabled)
	3. Generates animated GIF visualization (if enabled)
	4. Creates comprehensive final report
	5. Cleans up browser session

	Args:
		state: Current QA agent state

	Returns:
		Updated state with final report, judgement, and GIF path
	"""
	try:
		logger.info("=" * 80)
		logger.info("REPORT NODE - Generating final report with judge & GIF")
		logger.info("=" * 80)

		# Extract core task info
		task = state.get("task", "")
		history = state.get("history", [])
		step_count = state.get("step_count", 0)

		# Initialize report
		report = {
			"task": task,
			"completed": state.get("completed", False),
			"steps": step_count,
			"max_steps": state.get("max_steps", 50),
			"final_status": state.get("verification_status"),
			"verification_results": state.get("verification_results", []),
			"error": state.get("error"),
			"timestamp": datetime.now().isoformat(),
			"executed_actions_count": len(state.get("executed_actions", [])),
			"planned_actions_count": len(state.get("actions", [])),
		}

		# ============================================================
		# JUDGE EVALUATION (LLM-based quality assessment)
		# ============================================================
		use_judge = state.get("use_judge", True)  # Default: enabled

		if use_judge and history:
			logger.info("🧑‍⚖️ Running judge evaluation...")
			try:
				from web_agent.agent.judge import construct_judge_messages
				from web_agent.agent.views import JudgementResult
				from web_agent.llm import get_llm

				# Extract data for judge
				final_result = _extract_final_result_from_history(history)
				agent_steps = _format_agent_steps_from_history(history)
				screenshot_paths = _collect_screenshot_paths_from_history(history)

				logger.info(f"  Final result length: {len(final_result)} chars")
				logger.info(f"  Agent steps: {len(agent_steps)} steps")
				logger.info(f"  Screenshots: {len(screenshot_paths)} files")

				# Construct judge messages
				judge_messages = construct_judge_messages(
					task=task,
					final_result=final_result,
					agent_steps=agent_steps,
					screenshot_paths=screenshot_paths,
					max_images=10  # Limit to last 10 screenshots
				)

				# Call judge LLM with structured output
				judge_llm = get_llm()  # TODO: Consider separate judge_llm config
				logger.info(f"  Calling judge LLM: {judge_llm.model_name if hasattr(judge_llm, 'model_name') else 'unknown'}")

				# Use LangChain structured output pattern
				structured_judge_llm = judge_llm.with_structured_output(JudgementResult)

				# Convert browser messages to LangChain format
				from langchain_core.messages import SystemMessage as LCSystemMessage, HumanMessage
				lc_messages = []
				for msg in judge_messages:
					if msg.__class__.__name__ == 'SystemMessage':
						lc_messages.append(LCSystemMessage(content=msg.content))
					elif msg.__class__.__name__ == 'UserMessage':
						# UserMessage content is a list of ContentPartTextParam and ContentPartImageParam
						# LangChain expects list of dicts for multimodal content
						if isinstance(msg.content, list):
							# Convert browser content parts to LangChain format
							lc_content = []
							for part in msg.content:
								if hasattr(part, 'text'):  # ContentPartTextParam
									lc_content.append({"type": "text", "text": part.text})
								elif hasattr(part, 'image_url'):  # ContentPartImageParam
									lc_content.append({
										"type": "image_url",
										"image_url": {"url": part.image_url.url}
									})
							lc_messages.append(HumanMessage(content=lc_content))
						else:
							lc_messages.append(HumanMessage(content=msg.content))

				judgement: JudgementResult = await structured_judge_llm.ainvoke(lc_messages)

				# Add judgement to report
				report["judgement"] = {
					"verdict": judgement.verdict,
					"reasoning": judgement.reasoning,
					"failure_reason": judgement.failure_reason,
				}

				verdict_emoji = "✅" if judgement.verdict else "❌"
				logger.info(f"{verdict_emoji} Judge verdict: {judgement.verdict}")
				if not judgement.verdict and judgement.failure_reason:
					logger.info(f"  Failure reason: {judgement.failure_reason}")

			except Exception as e:
				logger.warning(f"⚠️ Judge evaluation failed: {e}", exc_info=True)
				report["judgement"] = {
					"error": str(e),
					"verdict": None,
				}
		else:
			if not use_judge:
				logger.info("Judge evaluation disabled")
			else:
				logger.info("Judge evaluation skipped (no history)")

		# ============================================================
		# GIF GENERATION (Animated visualization)
		# ============================================================
		generate_gif = state.get("generate_gif", False)

		if generate_gif and history:
			logger.info("🎬 Generating animated GIF...")
			try:
				from web_agent.agent.gif import create_history_gif

				# Determine output path
				output_path = "agent_history.gif"
				if isinstance(generate_gif, str):
					output_path = generate_gif

				# Convert workflow state to AgentHistoryList
				logger.info("  Converting workflow history to AgentHistoryList format...")
				agent_history_list = _convert_state_history_to_agent_history_list(state)

				logger.info(f"  Converted {len(agent_history_list.history)} history items")

				# Generate GIF
				logger.info(f"  Creating GIF at: {output_path}")
				create_history_gif(
					task=task,
					history=agent_history_list,
					output_path=output_path,
					duration=3000,  # 3 seconds per frame
					show_goals=True,
					show_task=True,
				)

				# Verify GIF was created
				gif_path = Path(output_path)
				if gif_path.exists():
					gif_size_kb = gif_path.stat().st_size / 1024
					logger.info(f"✅ GIF created: {output_path} ({gif_size_kb:.1f} KB)")
					report["gif_path"] = str(gif_path)
					report["gif_size_kb"] = gif_size_kb
				else:
					logger.warning(f"⚠️ GIF file not found after generation: {output_path}")

			except Exception as e:
				logger.warning(f"⚠️ GIF generation failed: {e}", exc_info=True)
				report["gif_error"] = str(e)
		else:
			if not generate_gif:
				logger.info("GIF generation disabled")
			else:
				logger.info("GIF generation skipped (no history)")

		# ============================================================
		# BROWSER CLEANUP
		# ============================================================
		browser_session_id = state.get("browser_session_id")
		if browser_session_id:
			try:
				logger.info(f"🧹 Cleaning up browser session: {browser_session_id[:16]}...")
				await cleanup_browser_session(browser_session_id)
				logger.info("✅ Browser session cleaned up successfully")
			except Exception as e:
				logger.warning(f"⚠️ Error cleaning up browser session: {e}")

		# ============================================================
		# FINAL REPORT SUMMARY
		# ============================================================
		logger.info("=" * 80)
		logger.info(f"📊 REPORT SUMMARY:")
		logger.info(f"  Task: {task[:80]}{'...' if len(task) > 80 else ''}")
		logger.info(f"  Steps: {step_count}/{report['max_steps']}")
		logger.info(f"  Status: {'Completed' if report['completed'] else 'Incomplete'}")
		if "judgement" in report and report["judgement"].get("verdict") is not None:
			verdict_str = "PASS ✅" if report["judgement"]["verdict"] else "FAIL ❌"
			logger.info(f"  Judge: {verdict_str}")
		if "gif_path" in report:
			logger.info(f"  GIF: {report['gif_path']}")
		logger.info("=" * 80)

		return {
			"report": report,
			"completed": True,
		}

	except Exception as e:
		logger.error(f"❌ Error in report node: {e}", exc_info=True)
		return {
			"error": f"Report node error: {str(e)}",
			"completed": True,
			"report": {
				"error": str(e),
				"timestamp": datetime.now().isoformat(),
			}
		}
