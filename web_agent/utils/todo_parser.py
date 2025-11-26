"""
Todo.md Parser - Extract current and next steps for hierarchical THINK node

This utility helps the minimal THINK node quickly identify:
- Current incomplete step (next to execute)
- Progress (completed/pending counts)
- Todo.md status
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_todo_steps(todo_contents: str) -> Tuple[List[Dict], List[Dict]]:
	"""
	Parse todo.md contents into completed and pending steps.

	Supports browser's todo.md format:
	# Task Title
	## Goal: Description
	## Tasks:
	- [x] Completed step
	- [ ] Pending step

	Args:
		todo_contents: Raw todo.md file contents

	Returns:
		Tuple of (completed_steps, pending_steps)
		Each step is: {"index": int, "text": str, "completed": bool}
	"""
	if not todo_contents or not todo_contents.strip():
		return [], []

	completed_steps = []
	pending_steps = []

	# Split into lines and find task section
	lines = todo_contents.split('\n')

	task_section_started = False
	step_index = 0

	for line in lines:
		line_stripped = line.strip()

		# Start looking for tasks after "## Tasks:" or "## Steps:"
		if line_stripped.startswith('## Tasks') or line_stripped.startswith('## Steps'):
			task_section_started = True
			continue

		# Only process lines after Tasks section starts
		if not task_section_started:
			continue

		# Stop if we hit another section
		if line_stripped.startswith('##') and 'tasks' not in line_stripped.lower() and 'steps' not in line_stripped.lower():
			break

		# Parse checkbox items
		# Match: - [x] or - [X] (completed)
		completed_match = re.match(r'^-\s+\[(x|X)\]\s+(.+)$', line_stripped)
		if completed_match:
			step_text = completed_match.group(2).strip()
			completed_steps.append({
				"index": step_index,
				"text": step_text,
				"completed": True
			})
			step_index += 1
			continue

		# Match: - [ ] (pending)
		pending_match = re.match(r'^-\s+\[\s*\]\s+(.+)$', line_stripped)
		if pending_match:
			step_text = pending_match.group(1).strip()
			pending_steps.append({
				"index": step_index,
				"text": step_text,
				"completed": False
			})
			step_index += 1
			continue

	return completed_steps, pending_steps


def get_current_step(todo_contents: str) -> Optional[Dict]:
	"""
	Get the FIRST incomplete step from todo.md.

	This is what THINK node should focus on.

	Args:
		todo_contents: Raw todo.md file contents

	Returns:
		{"index": int, "text": str, "completed": False} or None if all done
	"""
	_, pending_steps = parse_todo_steps(todo_contents)

	if not pending_steps:
		return None

	# Return first pending step
	return pending_steps[0]


def get_todo_progress(todo_contents: str) -> Dict:
	"""
	Get todo progress summary.

	Args:
		todo_contents: Raw todo.md file contents

	Returns:
		{
			"total": int,
			"completed": int,
			"pending": int,
			"completion_percentage": float,
			"current_step": Optional[Dict],
			"all_done": bool
		}
	"""
	completed, pending = parse_todo_steps(todo_contents)

	total = len(completed) + len(pending)
	current_step = pending[0] if pending else None
	all_done = len(pending) == 0
	completion_pct = (len(completed) / total * 100) if total > 0 else 0

	return {
		"total": total,
		"completed": len(completed),
		"pending": len(pending),
		"completion_percentage": round(completion_pct, 1),
		"current_step": current_step,
		"all_done": all_done
	}


def mark_step_completed(todo_contents: str, step_index: int) -> str:
	"""
	Mark a specific step as completed in todo.md.

	Args:
		todo_contents: Raw todo.md file contents
		step_index: Index of step to mark complete (from parse_todo_steps)

	Returns:
		Updated todo.md contents with step marked as [x]
	"""
	lines = todo_contents.split('\n')

	task_section_started = False
	current_step_index = 0
	updated_lines = []

	for line in lines:
		line_stripped = line.strip()

		# Start looking for tasks
		if line_stripped.startswith('## Tasks') or line_stripped.startswith('## Steps'):
			task_section_started = True
			updated_lines.append(line)
			continue

		# Stop if we hit another section
		if line_stripped.startswith('##') and task_section_started:
			if 'tasks' not in line_stripped.lower() and 'steps' not in line_stripped.lower():
				task_section_started = False

		if not task_section_started:
			updated_lines.append(line)
			continue

		# Check if this is a checkbox item
		is_task_item = re.match(r'^-\s+\[\s*[xX]?\s*\]\s+.+$', line_stripped)

		if is_task_item:
			if current_step_index == step_index:
				# This is the step to mark complete
				updated_line = re.sub(r'^(-\s+\[)\s*[xX]?(\])', r'\1x\2', line_stripped)
				updated_lines.append(updated_line)
				current_step_index += 1
			else:
				updated_lines.append(line)
				current_step_index += 1
		else:
			updated_lines.append(line)

	return '\n'.join(updated_lines)


def format_todo_for_think_node(todo_contents: str) -> str:
	"""
	Format todo.md for THINK node input.

	Adds status indicators and progress info for clarity.

	Args:
		todo_contents: Raw todo.md file contents

	Returns:
		Formatted todo.md with progress indicators
	"""
	if not todo_contents or not todo_contents.strip():
		return "[No todo.md - task not broken down yet]"

	progress = get_todo_progress(todo_contents)
	current_step = progress.get("current_step")

	# Add progress header
	formatted = f"# Progress: {progress['completed']}/{progress['total']} steps completed ({progress['completion_percentage']:.0f}%)\n\n"

	if current_step:
		formatted += f"## Current Focus (Step {current_step['index'] + 1}):\n"
		formatted += f"→ {current_step['text']}\n\n"

	formatted += "## Full Todo:\n"
	formatted += todo_contents

	return formatted


def extract_goal_from_todo(todo_contents: str) -> Optional[str]:
	"""
	Extract the goal from todo.md.

	Args:
		todo_contents: Raw todo.md file contents

	Returns:
		Goal description or None if not found
	"""
	lines = todo_contents.split('\n')

	for line in lines:
		if line.strip().startswith('## Goal:'):
			goal = line.strip().replace('## Goal:', '').strip()
			return goal if goal else None

	return None
