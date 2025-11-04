"""
Prompt Builder for QA Agent Think Node

Builds prompts for the LLM to generate action plans in browser-use style.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime


def build_think_prompt(
    task: str,
    current_goal: Optional[str] = None,
    browser_state: Optional[str] = None,
    history: List[Dict[str, Any]] = None,
    step_count: int = 0,
    max_steps: int = 50,
) -> List[Dict[str, str]]:
    """
    Build a prompt for the think node to generate action plans
    
    Uses browser-use style XML tags for structured formatting.
    
    Args:
        task: Original user task/instruction
        current_goal: Current sub-goal being worked on
        browser_state: Serialized browser state (if available)
        history: Previous execution history
        step_count: Current step number
        max_steps: Maximum steps allowed
        
    Returns:
        List of messages for LLM (system + user messages)
    """
    history = history or []
    
    # System message - simplified browser-use style
    system_message = """You are a QA Automation Agent designed to operate in an iterative loop to automate browser tasks.

Your ultimate goal is accomplishing the task provided in <user_request>.

<task>
Your task is to help automate QA testing by:
1. Understanding what the user wants to test
2. Breaking down the task into actionable steps
3. Generating a sequence of browser actions (navigate, click, type, wait, verify)

You must respond with a JSON list of actions. Each action should have:
- "type": The action type (e.g., "navigate", "click", "type", "wait", "verify", "done")
- "target": What to interact with (URL for navigate, selector/element for click/type, etc.)
- "value": The value to input (for type actions, optional)
- "reasoning": Why you're taking this action

Special action type "done": Use this when the task is complete. Set type="done" and include a "message" field summarizing what was accomplished.

Return ONLY valid JSON array of actions. Example:
[
  {
    "type": "navigate",
    "target": "https://example.com",
    "reasoning": "Navigate to the target website"
  },
  {
    "type": "click",
    "target": "button#submit",
    "reasoning": "Click the submit button"
  }
]
</task>

<action_rules>
- Be specific and actionable
- Break complex tasks into smaller steps
- If browser state is not available, start with navigation
- Generate 1-3 actions per step (don't overload)
- Always include reasoning for each action
- Use action type "done" when the task is fully complete
- When task is complete, return: [{"type": "done", "message": "Task completed: ..."}]
</action_rules>"""
    
    # Build user message in browser-use XML tag style
    time_str = datetime.now().strftime('%Y-%m-%d')
    
    user_parts = [
        f'<user_request>\n{task}\n</user_request>\n',
        f'<step_info>\nStep {step_count + 1} maximum: {max_steps}\nToday: {time_str}\n</step_info>\n',
    ]
    
    # Add history if available
    if history:
        user_parts.append('<agent_history>\n')
        for i, step in enumerate(history[-5:], 1):  # Last 5 steps
            step_num = step.get("step", i)
            node = step.get("node", "unknown")
            
            if node == "think":
                actions = step.get("planned_actions", [])
                user_parts.append(f'<step_{step_num}>\n')
                user_parts.append(f'Node: Think\n')
                user_parts.append(f'Planned Actions: {len(actions)} actions\n')
                user_parts.append(f'</step_{step_num}>\n')
            elif node == "act":
                results = step.get("action_results", [])
                success_count = sum(1 for r in results if r.get("success", False))
                user_parts.append(f'<step_{step_num}>\n')
                user_parts.append(f'Node: Act\n')
                user_parts.append(f'Executed: {len(results)} actions, {success_count} successful\n')
                user_parts.append(f'</step_{step_num}>\n')
            elif node == "verify":
                status = step.get("verification_status", "unknown")
                user_parts.append(f'<step_{step_num}>\n')
                user_parts.append(f'Node: Verify\n')
                user_parts.append(f'Status: {status}\n')
                user_parts.append(f'</step_{step_num}>\n')
        user_parts.append('</agent_history>\n\n')
    
    # Add browser state
    if browser_state:
        user_parts.append(f'<browser_state>\n{browser_state}\n</browser_state>\n')
    else:
        user_parts.append('<browser_state>\nNo browser state available yet. Start with navigation.\n</browser_state>\n')
    
    # Add current goal if available
    if current_goal:
        user_parts.append(f'<current_goal>\n{current_goal}\n</current_goal>\n')
    
    user_parts.append('\nGenerate the next action plan to continue working towards the task.')
    
    user_message = ''.join(user_parts)
    
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

