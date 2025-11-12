"""
PLAN Node - browser todo.md pattern (pure LLM-driven)

This node does MINIMAL work - it just passes through and lets the LLM naturally
create todo.md on its first step. This follows browser's design philosophy:

System prompt already says:
"If todo.md is empty and the task is multi-step, generate a stepwise plan in todo.md using file tools."

The LLM will:
1. See the task in <user_request>
2. See empty todo.md in <todo_contents>
3. Recognize it's multi-step
4. Call write_file to create todo.md with checkboxes
5. Mark items complete as it progresses

We only add lightweight goal tracking for PAGE STATE detection to prevent loops.
"""
import logging
from typing import Dict, Any
from qa_agent.state import QAAgentState
from qa_agent.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


async def plan_node(state: QAAgentState) -> Dict[str, Any]:
	"""
	Plan node: Lightweight goal extraction for loop prevention

	This node does TWO things:
	1. Let LLM manage todo.md naturally (browser pattern)
	2. Extract high-level goals for PAGE STATE-based completion detection

	The goals are ONLY used to detect "we're on dashboard now, signup must be done"
	to prevent repeating completed steps.

	Args:
		state: Current QA agent state

	Returns:
		Updated state with lightweight goals for page state detection
	"""
	try:
		task = state.get("task", "")

		# CRITICAL: Preserve file_system_state from INIT node (contains todo.md)
		file_system_state = state.get("file_system_state")
		
		# CRITICAL: Check if goals already exist - PLAN should only run once!
		# If goals exist, just preserve state and return (no LLM call needed)
		existing_goals = state.get("goals", [])
		if existing_goals:
			logger.info(f"PLAN: Goals already exist ({len(existing_goals)} goals), skipping LLM call")
			logger.info("PLAN: Preserving existing goals and file_system_state")
			# CRITICAL: For reducer fields (Annotated), return ONLY new items or omit field
			# completed_goals has reducer (operator.add), so we return [] (no new items) or omit
			# goals has NO reducer, so we return full value to replace
			return {
				"goals": existing_goals,  # No reducer - return full value to preserve
				# completed_goals: Omit field - no new goals completed in PLAN node
				"current_goal_index": state.get("current_goal_index", 0),
				"file_system_state": file_system_state,  # CRITICAL: Preserve todo.md from INIT
			}

		logger.info(f"PLAN: Analyzing task for goal extraction...")

		# Simple heuristic: Check if task is complex enough
		task_lower = task.lower()
		sequencing_words = ["then", "after", "next", "once", "when", "wait"]
		has_sequencing = any(word in task_lower for word in sequencing_words)
		is_long_task = len(task) > 400
		
		if not (has_sequencing or is_long_task):
			logger.info("PLAN: Simple task, no goal tracking needed")
			logger.info("PLAN: LLM will handle via todo.md if needed")
			# CRITICAL: For reducer fields, return [] (no new items) or omit field
			# completed_goals has reducer - return [] means "no new items to add"
			return {
				"goals": [],  # No reducer - replace with empty list
				"completed_goals": [],  # Reducer field - [] means "no new items" (correct)
				"current_goal_index": 0,
				"file_system_state": file_system_state,  # CRITICAL: Preserve todo.md from INIT
			}

		# Complex task - extract lightweight goals for PAGE STATE detection
		logger.info("PLAN: Complex task, extracting goals for page state tracking...")

		llm = get_llm()

		# Lightweight planning prompt - just extract major phases
		planning_prompt = f"""Extract high-level phases from this QA task for progress tracking.

**Task:**
{task}

**Goal:**
Identify 2-5 major phases that can be detected by page state changes (URL/title changes).

**IMPORTANT**:
- Completion signals must be EXACT URL path segments or title keywords that appear when goal is done
- Look for URL paths like "/login", "/signup", "/dashboard", "/add", not vague terms
- Consider both success path AND error handling paths (e.g., "if account exists, go to login")

**Output JSON:**
```json
{{
  "goals": [
    {{
      "id": "short_id",
      "description": "Brief description",
      "completion_signals": ["url_path_or_exact_title_keyword"]
    }}
  ]
}}
```

**Example 1:**
For "Sign up, then login, then add item":
```json
{{
  "goals": [
    {{"id": "signup", "description": "Complete signup", "completion_signals": ["/login", "login"]}},
    {{"id": "login", "description": "Log in", "completion_signals": ["/dashboard", "dashboard"]}},
    {{"id": "add_item", "description": "Add item", "completion_signals": ["success", "confirmation"]}}
  ]
}}
```

**Example 2:**
For "Try signup, if exists then login":
```json
{{
  "goals": [
    {{"id": "attempt_signup", "description": "Attempt signup or detect existing account", "completion_signals": ["/login", "login"]}},
    {{"id": "login", "description": "Log in with credentials", "completion_signals": ["/dashboard", "welcome"]}}
  ]
}}
```

Extract goals now:"""

		messages = [
			SystemMessage(content="You extract high-level phases from tasks for progress tracking."),
			HumanMessage(content=planning_prompt)
		]

		response = await llm.ainvoke(messages)
		response_text = response.content if hasattr(response, 'content') else str(response)

		# Parse JSON
		import json
		import re

		json_match = re.search(r'\{[\s\S]*"goals"[\s\S]*\}', response_text)
		if json_match:
			try:
				plan_data = json.loads(json_match.group(0))
				goals = plan_data.get("goals", [])

				if goals:
					logger.info(f"PLAN: Extracted {len(goals)} goals for page state tracking:")
					for i, goal in enumerate(goals, 1):
						logger.info(f"  {i}. [{goal['id']}] {goal['description']}")

					logger.info("PLAN: ✅ LLM will manage detailed steps via todo.md")
					logger.info("PLAN: ✅ Goals used ONLY for page state-based completion detection")

					# CRITICAL: completed_goals has reducer (operator.add)
					# Return [] means "no new goals completed" (correct for PLAN node)
					return {
						"goals": goals,  # No reducer - replace with new goals
						"completed_goals": [],  # Reducer field - [] means "no new items" (correct)
						"current_goal_index": 0,
						"file_system_state": file_system_state,  # CRITICAL: Preserve todo.md from INIT
					}
			except (json.JSONDecodeError, KeyError) as e:
				logger.warning(f"PLAN: Could not parse goals: {e}")

		# Fallback: Pure browser pattern (no goal tracking)
		logger.info("PLAN: No goals extracted, using pure browser todo.md pattern")
		# CRITICAL: completed_goals has reducer - return [] means "no new items"
		return {
			"goals": [],  # No reducer - replace with empty list
			"completed_goals": [],  # Reducer field - [] means "no new items" (correct)
			"current_goal_index": 0,
			"file_system_state": file_system_state,  # CRITICAL: Preserve todo.md from INIT
		}

	except Exception as e:
		logger.error(f"Error in plan node: {e}", exc_info=True)
		# CRITICAL: Preserve file_system_state even on error
		file_system_state = state.get("file_system_state")
		# CRITICAL: completed_goals has reducer - return [] means "no new items"
		return {
			"goals": [],  # No reducer - replace with empty list
			"completed_goals": [],  # Reducer field - [] means "no new items" (correct)
			"current_goal_index": 0,
			"file_system_state": file_system_state,  # CRITICAL: Preserve todo.md from INIT
		}
