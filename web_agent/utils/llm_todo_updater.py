"""
LLM-Driven Todo Updater - Intelligently match actions to todo.md steps

This uses LLM intelligence to determine which todo items should be marked complete
based on executed actions, without hardcoded keyword matching.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TodoUpdateResponse(BaseModel):
    """LLM response indicating which todo steps should be marked complete"""
    completed_step_indices: List[int] = Field(
        description="List of zero-based indices of todo steps that should be marked as complete based on the executed actions"
    )
    reasoning: str = Field(
        description="Brief explanation of why these steps are being marked complete"
    )


async def llm_match_actions_to_todo_steps(
    executed_actions: List[Dict[str, Any]],
    todo_steps: List[str],
    llm,
) -> List[int]:
    """
    Use LLM to intelligently match executed actions to todo.md steps.
    
    This replaces hardcoded keyword matching with LLM-driven analysis that works
    for any website, any task, any language.
    
    Args:
        executed_actions: List of executed action dictionaries
        todo_steps: List of todo step descriptions (without checkboxes)
        llm: LLM instance for analysis
        
    Returns:
        List of zero-based indices of steps that should be marked complete
    """
    if not executed_actions or not todo_steps:
        return []
    
    # Build context for LLM
    actions_summary = []
    for i, action_dict in enumerate(executed_actions):
        if not action_dict:
            continue
        action_type = list(action_dict.keys())[0]
        action_params = action_dict.get(action_type, {})
        
        # Build readable action description with more context
        if action_type == "click":
            index = action_params.get("index", "?")
            text = action_params.get("text", "")
            extracted = action_dict.get("extracted_content", "")
            # Include extracted content for better matching (e.g., "Clicked button 'Sign In'")
            if extracted:
                actions_summary.append(f"Action {i+1}: {extracted}")
            else:
                actions_summary.append(f"Action {i+1}: Clicked element {index}" + (f" ({text})" if text else ""))
        elif action_type == "input":
            index = action_params.get("index", "?")
            value = action_params.get("value", "")[:50]  # Truncate long values
            extracted = action_dict.get("extracted_content", "")
            if extracted:
                actions_summary.append(f"Action {i+1}: {extracted}")
            else:
                actions_summary.append(f"Action {i+1}: Input '{value}' into element {index}")
        elif action_type == "navigate":
            url = action_params.get("url", "")
            actions_summary.append(f"Action {i+1}: Navigated to {url}")
        elif action_type == "switch":
            tab_id = action_params.get("tab_id", "")
            actions_summary.append(f"Action {i+1}: Switched to tab {tab_id}")
        elif action_type == "wait":
            seconds = action_params.get("seconds", 0)
            actions_summary.append(f"Action {i+1}: Waited {seconds} seconds")
        elif action_type == "select_dropdown":
            index = action_params.get("index", "?")
            text = action_params.get("text", "")
            extracted = action_dict.get("extracted_content", "")
            if extracted:
                actions_summary.append(f"Action {i+1}: {extracted}")
            else:
                actions_summary.append(f"Action {i+1}: Selected '{text}' from dropdown at index {index}")
        else:
            extracted = action_dict.get("extracted_content", "")
            if extracted:
                actions_summary.append(f"Action {i+1}: {extracted}")
            else:
                actions_summary.append(f"Action {i+1}: {action_type} with params {action_params}")
    
    # Build todo steps list for LLM
    todo_list = "\n".join([f"{i}. {step}" for i, step in enumerate(todo_steps)])
    
    # Create LLM prompt
    from langchain_core.messages import SystemMessage, HumanMessage
    
    system_prompt = """You are an AI assistant that analyzes browser automation actions and determines which todo.md checklist items should be marked as complete.

Your task:
1. Analyze the executed actions
2. Match them to the todo steps
3. Identify which steps have been completed based on the actions
4. Return the indices (0-based) of completed steps

Guidelines:
- Mark steps as complete if the actions clearly indicate completion
- Consider semantic meaning, not just exact keyword matching
- A step can be complete even if the exact wording doesn't match (e.g., "Click Sign In" matches "Click the Sign In button")
- Be PROACTIVE - mark steps that are clearly done based on actions
- Consider the sequence: earlier steps must be complete before later ones
- If multiple actions complete a single step, mark it complete
- If a step says "Fill form with X, Y, Z" and actions show inputs for X, Y, Z, mark it complete
- Navigation actions often complete "Navigate to..." steps
- Click actions often complete "Click..." steps
- Input actions often complete "Fill..." or "Enter..." steps

Examples:
- Action: "Clicked button 'Sign In'" → Step: "Click the Sign In button" → MARK COMPLETE
- Action: "Navigated to https://hostelx.pk/" → Step: "Navigate to https://hostelx.pk/" → MARK COMPLETE
- Actions: ["Input 'Hector'", "Input 'Hector'", "Input 'email@test.com'", "Input '123456'"] → Step: "Fill in the signup form with First Name: Hector, Last Name: Hector, Email: email@test.com, Phone: 123456" → MARK COMPLETE
- Action: "Selected 'Men' from dropdown" → Step: "Select 'Men' from the dropdown combo box" → MARK COMPLETE
"""
    
    user_prompt = f"""Analyze these executed actions and determine which todo steps should be marked as complete.

EXECUTED ACTIONS:
{chr(10).join(actions_summary)}

TODO STEPS:
{todo_list}

Return the zero-based indices of steps that should be marked as complete. Be PROACTIVE - if actions clearly indicate a step is done, mark it complete even if wording doesn't match exactly. Consider semantic meaning."""
    
    try:
        # Call LLM with structured output (with timeout to prevent hanging)
        import asyncio
        structured_llm = llm.with_structured_output(TodoUpdateResponse)
        response = await asyncio.wait_for(
            structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]),
            timeout=30.0  # 30 second timeout for todo matching (should be fast)
        )
        
        completed_indices = response.completed_step_indices
        logger.info(f"LLM matched actions to todo steps: {len(completed_indices)} steps marked complete - {response.reasoning}")
        
        # Validate indices are in range
        valid_indices = [idx for idx in completed_indices if 0 <= idx < len(todo_steps)]
        if len(valid_indices) != len(completed_indices):
            logger.warning(f"Some indices out of range: {completed_indices}, valid: {valid_indices}")
        
        return valid_indices
        
    except asyncio.TimeoutError:
        logger.error(f"LLM todo matching timed out after 30 seconds, using fallback matching")
        # Fallback: simple keyword-based matching
        return _fallback_match_actions_to_steps(actions_summary, todo_steps)
    except Exception as e:
        logger.error(f"Failed to use LLM for todo matching: {e}", exc_info=True)
        logger.error(f"Exception type: {type(e).__name__}, message: {str(e)}")
        # Fallback: simple keyword-based matching
        return _fallback_match_actions_to_steps(actions_summary, todo_steps)


def _fallback_match_actions_to_steps(actions_summary: List[str], todo_steps: List[str]) -> List[int]:
    """
    Fallback simple matching when LLM fails.
    Uses keyword matching to identify completed steps.
    """
    completed_indices = []
    actions_text = " ".join(actions_summary).lower()
    
    for i, step in enumerate(todo_steps):
        step_lower = step.lower()
        
        # Extract key words from step (skip common words)
        skip_words = {"the", "a", "an", "to", "in", "on", "at", "for", "with", "and", "or", "but", "if", "when", "wait", "click", "enter", "fill", "select"}
        step_words = [w for w in step_lower.split() if w not in skip_words and len(w) > 2]
        
        # Check if action text contains key words from step
        if step_words:
            matches = sum(1 for word in step_words if word in actions_text)
            # If 60% of key words match, consider it complete
            if matches >= len(step_words) * 0.6:
                completed_indices.append(i)
                logger.debug(f"Fallback matched step {i}: {step[:50]}")
    
    if completed_indices:
        logger.info(f"Fallback matching found {len(completed_indices)} completed steps: {completed_indices}")
    
    return completed_indices


def update_todo_md_content(
    todo_content: str,
    completed_indices: List[int],
) -> str:
    """
    Update todo.md content by marking specified steps as complete.
    
    Args:
        todo_content: Current todo.md content
        completed_indices: Zero-based indices of steps to mark complete
        
    Returns:
        Updated todo.md content
    """
    if not completed_indices:
        return todo_content
    
    lines = todo_content.split('\n')
    todo_step_lines = []  # (line_index, step_index, line_content)
    step_index = 0
    
    # Find all todo step lines and map them to step indices
    for line_idx, line in enumerate(lines):
        line_stripped = line.strip()
        if line_stripped.startswith('- [ ]') or line_stripped.startswith('- [x]') or line_stripped.startswith('- [X]'):
            todo_step_lines.append((line_idx, step_index, line))
            step_index += 1
    
    # Mark specified steps as complete
    updated_lines = lines.copy()
    for line_idx, step_idx, line in todo_step_lines:
        if step_idx in completed_indices and line.strip().startswith('- [ ]'):
            # Mark as complete
            updated_line = line.replace('- [ ]', '- [x]', 1)
            updated_lines[line_idx] = updated_line
            logger.debug(f"Marked todo step {step_idx} as complete: {line[:50]}")
    
    return '\n'.join(updated_lines)

