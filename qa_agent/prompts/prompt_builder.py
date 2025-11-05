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
    
    # System message - browser-use compatible style
    system_message = """You are a QA Automation Agent designed to operate in an iterative loop to automate browser tasks.

Your ultimate goal is accomplishing the task provided in <user_request>.

<task>
Your task is to help automate QA testing by:
1. Understanding what the user wants to test
2. Breaking down the task into actionable steps
3. Generating a sequence of browser actions using the exact action types below

IMPORTANT: You must respond with a JSON array of actions using these EXACT action names:

Available Actions:
- "go_to_url": Navigate to a URL (params: url, reasoning)
- "click_element": Click an element (params: index, reasoning) - use element index from <clickable_elements>
- "input_text": Type text into element (params: index, text, reasoning)
- "extract_page_content": Extract content from page (params: reasoning)
- "scroll_down" / "scroll_up": Scroll the page (params: reasoning)
- "go_back": Navigate back in browser history (params: reasoning)
- "search_google": Search on Google (params: query, reasoning)
- "done": Task complete (params: text with summary of what was accomplished)

Action Format - Use "action" key NOT "type":
[
  {
    "action": "go_to_url",
    "url": "https://example.com/login",
    "reasoning": "Navigate to the login page to start testing"
  },
  {
    "action": "click_element",
    "index": 5,
    "reasoning": "Click the login button (element index 5 from clickable_elements)"
  },
  {
    "action": "input_text",
    "index": 2,
    "text": "test@example.com",
    "reasoning": "Enter email in the email field (index 2)"
  }
]
</task>

<examples>
Example 1 - Login Flow Test:
[
  {"action": "go_to_url", "url": "https://app.example.com/login", "reasoning": "Navigate to login page"},
  {"action": "input_text", "index": 3, "text": "wrong@email.com", "reasoning": "Enter invalid email to test validation"},
  {"action": "click_element", "index": 7, "reasoning": "Click login button to trigger validation"}
]

Example 2 - Form Submission Test:
[
  {"action": "input_text", "index": 1, "text": "John Doe", "reasoning": "Fill name field"},
  {"action": "input_text", "index": 2, "text": "john@example.com", "reasoning": "Fill email field"},
  {"action": "click_element", "index": 8, "reasoning": "Submit the form"}
]

Example 3 - Task Completion:
[
  {"action": "done", "text": "Successfully verified error message 'Invalid credentials' appears after login attempt"}
]
</examples>

<action_rules>
- CRITICAL: Use "action" key, NOT "type"
- CRITICAL: Use exact action names (go_to_url, click_element, input_text, etc.)
- For click_element and input_text, ALWAYS use "index" from <clickable_elements> in browser state
- Be specific and actionable
- Break complex tasks into smaller steps
- Generate 1-3 actions per step (don't overload)
- Always include "reasoning" for each action
- Use "done" action when task is fully complete
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

