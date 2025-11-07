"""
Task Parser - Extract steps from task and generate todo.md structure

This utility parses a task string and extracts logical steps to create
a structured todo.md file. This enables deterministic task progression tracking.
"""
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def is_multi_step_task(task: str) -> bool:
    """Check if task is multi-step based on keywords and length."""
    task_lower = task.lower()
    
    # Sequencing keywords indicate multi-step tasks
    sequencing_words = ["then", "after", "next", "once", "when", "wait", "and then", "after that"]
    has_sequencing = any(word in task_lower for word in sequencing_words)
    
    # Long tasks are likely multi-step
    is_long_task = len(task) > 200
    
    # Multiple sentences indicate multiple steps
    sentence_count = len(re.split(r'[.!?]\s+', task))
    has_multiple_sentences = sentence_count > 3
    
    return has_sequencing or is_long_task or has_multiple_sentences


def parse_task_to_steps(task: str) -> List[str]:
    """
    Parse task string into logical steps.
    
    Strategy:
    1. Split by sequencing keywords (then, after, next, once, when, wait)
    2. Split by sentence boundaries
    3. Clean and normalize steps
    4. Filter out empty steps
    
    Args:
        task: Task string from user
        
    Returns:
        List of step descriptions
    """
    if not task or not task.strip():
        return []
    
    steps = []
    
    # Strategy 1: Split by sequencing keywords (preserve the keyword in the step)
    # Pattern: match "keyword" followed by optional punctuation and whitespace
    sequencing_pattern = r'\b(then|after|next|once|when|wait|and then|after that)\b[.,]?\s*'
    
    # Split by sequencing keywords but keep them in the next step
    parts = re.split(sequencing_pattern, task, flags=re.IGNORECASE)
    
    if len(parts) > 1:
        # First part is the initial step
        if parts[0].strip():
            steps.append(parts[0].strip())
        
        # Remaining parts: keyword + step content
        for i in range(1, len(parts), 2):
            if i < len(parts):
                keyword = parts[i] if i < len(parts) else ""
                content = parts[i + 1] if i + 1 < len(parts) else ""
                if content.strip():
                    # Include keyword in step for context
                    step = f"{keyword.strip()} {content.strip()}".strip()
                    steps.append(step)
    else:
        # No sequencing keywords found, split by sentences
        sentences = re.split(r'[.!?]\s+', task)
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:  # Filter very short fragments
                steps.append(sentence)
    
    # Clean steps: remove leading/trailing whitespace, normalize
    cleaned_steps = []
    for step in steps:
        step = step.strip()
        # Remove leading "and", "or", "but" if they appear
        step = re.sub(r'^\s*(and|or|but)\s+', '', step, flags=re.IGNORECASE)
        # Capitalize first letter
        if step:
            step = step[0].upper() + step[1:] if len(step) > 1 else step.upper()
            cleaned_steps.append(step)
    
    # If we have too many steps (>20), they might be too granular
    # Group related steps together
    if len(cleaned_steps) > 20:
        logger.warning(f"Task parsed into {len(cleaned_steps)} steps, may be too granular")
        # Group every 2-3 steps together
        grouped_steps = []
        for i in range(0, len(cleaned_steps), 2):
            if i + 1 < len(cleaned_steps):
                grouped = f"{cleaned_steps[i]} {cleaned_steps[i+1]}"
            else:
                grouped = cleaned_steps[i]
            grouped_steps.append(grouped)
        cleaned_steps = grouped_steps
    
    return cleaned_steps


def create_todo_md_content(task: str, steps: Optional[List[str]] = None) -> str:
    """
    Create todo.md content from task and steps.
    
    Args:
        task: Original task string
        steps: Optional pre-parsed steps. If None, will parse from task.
        
    Returns:
        Markdown content for todo.md file
    """
    if steps is None:
        steps = parse_task_to_steps(task)
    
    if not steps:
        # Fallback: create a simple todo.md with the task itself
        return f"# Task\n\n- [ ] {task}\n"
    
    # Build todo.md content
    content = "# Task Progress\n\n"
    content += f"## Goal\n{task}\n\n"
    content += "## Steps\n\n"
    
    for i, step in enumerate(steps, 1):
        content += f"- [ ] {step}\n"
    
    return content


def match_action_to_todo_step(action_type: str, action_params: Dict, todo_steps: List[str]) -> Optional[int]:
    """
    Match an executed action to a todo.md step.
    
    This helps determine which todo item should be marked as complete
    based on what action was executed.
    
    Args:
        action_type: Type of action (click, input, navigate, etc.)
        action_params: Action parameters
        todo_steps: List of todo step descriptions
        
    Returns:
        Index of matching todo step, or None if no match
    """
    # Extract keywords from action
    action_keywords = []
    
    if action_type == "click":
        # Try to extract text from action params
        element_text = action_params.get("text", "") or action_params.get("aria_label", "")
        if element_text:
            action_keywords.append(element_text.lower())
    elif action_type == "input":
        # Input actions usually complete form filling steps
        action_keywords.extend(["input", "fill", "enter", "type"])
    elif action_type == "navigate":
        action_keywords.extend(["navigate", "go", "visit"])
    elif action_type == "wait":
        action_keywords.extend(["wait"])
    
    # Match against todo steps
    for i, step in enumerate(todo_steps):
        step_lower = step.lower()
        # Check if any action keyword appears in the step
        if any(keyword in step_lower for keyword in action_keywords if keyword):
            return i
    
    return None

