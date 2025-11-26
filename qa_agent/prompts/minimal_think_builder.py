"""
Minimal THINK Prompt Builder

Constructs the minimal strategic prompt for THINK node.
Focuses on: what's the next step? (not how to execute it)
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

logger = logging.getLogger(__name__)


class MinimalThinkPromptBuilder:
	"""Build minimal THINK prompt with todo.md context."""

	def __init__(self):
		"""Initialize prompt builder and load template."""
		self.prompt_template_path = Path(__file__).parent / "minimal_think_prompt.md"
		self.prompt_template = self._load_template()

	def _load_template(self) -> str:
		"""Load minimal THINK prompt template from file."""
		try:
			if self.prompt_template_path.exists():
				content = self.prompt_template_path.read_text()
				logger.debug(f"Loaded minimal THINK prompt template ({len(content)} chars)")
				return content
			else:
				logger.warning(f"Minimal THINK prompt template not found at {self.prompt_template_path}")
				return self._get_fallback_template()
		except Exception as e:
			logger.error(f"Failed to load minimal THINK prompt template: {e}")
			return self._get_fallback_template()

	def _get_fallback_template(self) -> str:
		"""Fallback minimal prompt if file not found."""
		return """You are a strategic planner for QA web automation. Decide WHAT to do next.

## Task
{{task}}

## Current Todo Status
{{todo_contents}}

## Previous Action Result
{{previous_result}}

---

## Output (JSON only)
{
  "next_step": "Strategic description",
  "reasoning": "Why this step",
  "retry_count": 0
}
"""

	def build_messages(
		self,
		task: str,
		todo_contents: str,
		previous_result: Optional[Dict[str, Any]] = None,
	) -> list[BaseMessage]:
		"""
		Build system + user messages for THINK node.

		Args:
			task: Original user task
			todo_contents: Current todo.md contents
			previous_result: Result from previous ACT execution (if any)

		Returns:
			List of messages: [SystemMessage, HumanMessage]
		"""
		# Format previous result for readability
		if previous_result:
			if isinstance(previous_result, dict):
				success = previous_result.get("success", False)
				action_taken = previous_result.get("action_taken", "Unknown")
				result_summary = previous_result.get("result_summary", "No summary")
				error = previous_result.get("error")

				previous_result_str = (
					f"Status: {'✅ SUCCESS' if success else '❌ FAILED'}\n"
					f"Action: {action_taken}\n"
					f"Result: {result_summary}"
				)

				if error:
					previous_result_str += f"\nError: {error}"
			else:
				previous_result_str = str(previous_result)
		else:
			previous_result_str = "No previous action (first step)"

		# Substitute template variables
		prompt_content = self.prompt_template
		prompt_content = prompt_content.replace("{{task}}", task or "[No task provided]")
		prompt_content = prompt_content.replace("{{todo_contents}}", todo_contents or "[No todo.md]")
		prompt_content = prompt_content.replace("{{previous_result}}", previous_result_str)

		# Split into system (before Examples) and user (rest)
		# The template is structured to guide the model
		system_content = self._extract_system_part(prompt_content)
		user_content = self._extract_user_part(prompt_content)

		return [
			SystemMessage(content=system_content),
			HumanMessage(content=user_content),
		]

	def _extract_system_part(self, prompt: str) -> str:
		"""Extract system instruction part (before task details)."""
		# Everything up to the first "## Task" section serves as system prompt
		if "## Task" in prompt:
			parts = prompt.split("## Task", 1)
			return parts[0].strip()
		return prompt[:len(prompt)//2]  # Fallback: first half

	def _extract_user_part(self, prompt: str) -> str:
		"""Extract user input part (task details)."""
		# Everything from "## Task" onwards is user input
		if "## Task" in prompt:
			parts = prompt.split("## Task", 1)
			return "## Task" + parts[1]
		return prompt[len(prompt)//2:]  # Fallback: second half

	def build_system_message(self) -> SystemMessage:
		"""
		Get system prompt as a separate message.

		Useful if you want to use the same system prompt for multiple requests.

		Returns:
			SystemMessage with instructions
		"""
		system_part = self._extract_system_part(self.prompt_template)
		return SystemMessage(content=system_part)


class MinimalThinkResponse:
	"""Parse THINK node LLM response."""

	def __init__(self, response_text: str):
		"""
		Initialize with LLM response.

		Args:
			response_text: Raw LLM response (should be JSON)
		"""
		self.raw_response = response_text
		self.parsed = self._parse_response(response_text)

	def _parse_response(self, text: str) -> Dict[str, Any]:
		"""
		Parse LLM response (should be JSON).

		Args:
			text: Response text from LLM

		Returns:
			Parsed dict with keys: next_step, reasoning, retry_count
		"""
		import json

		# Try to extract JSON from response
		try:
			# First try direct JSON parsing
			return json.loads(text)
		except json.JSONDecodeError:
			pass

		# Try to find JSON in the response
		import re
		json_match = re.search(r'\{[^{}]*"next_step"[^{}]*\}', text, re.DOTALL)

		if json_match:
			try:
				return json.loads(json_match.group(0))
			except json.JSONDecodeError:
				pass

		# Fallback: extract as plain text
		logger.warning(f"Could not parse THINK response as JSON, using fallback")
		return {
			"next_step": text.strip()[:200],  # Take first 200 chars
			"reasoning": "Could not parse structured response",
			"retry_count": 0,
		}

	@property
	def next_step(self) -> str:
		"""Get the strategic next step."""
		return self.parsed.get("next_step", "Unknown step")

	@property
	def reasoning(self) -> str:
		"""Get the reasoning."""
		return self.parsed.get("reasoning", "")

	@property
	def retry_count(self) -> int:
		"""Get retry count."""
		return self.parsed.get("retry_count", 0)

	def is_valid(self) -> bool:
		"""Check if response is valid."""
		return bool(self.next_step and len(self.next_step) > 0)
