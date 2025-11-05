"""
Utility functions for parsing LLM responses
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def convert_browser_use_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert browser-use action format to our simple format

    Browser-use format: {"hover": {"elements": [1820]}}
    Our format: {"action": "hover", "index": 1820}

    Args:
        actions: List of browser-use format actions

    Returns:
        List of actions in our format
    """
    converted = []

    for action_dict in actions:
        # Extract the action type (first key in dict)
        if not action_dict:
            continue

        action_type = list(action_dict.keys())[0]
        action_params = action_dict[action_type]

        # Handle shorthand format: {"click": 1820} vs full format: {"click": {"index": 1820}}
        if isinstance(action_params, (int, str)):
            # Shorthand format - action_params is just the index/value
            if action_type == "click":
                converted.append({
                    "action": "click",  # Browser-use function name
                    "index": int(action_params),
                    "reasoning": "Browser-use shorthand click"
                })
            elif action_type == "hover":
                # Convert hover to click for now
                logger.warning(f"Shorthand hover converted to click: index={action_params}")
                converted.append({
                    "action": "click",  # Browser-use function name
                    "index": int(action_params),
                    "reasoning": "Browser-use shorthand hover (converted to click)"
                })
            else:
                logger.warning(f"Unknown shorthand action type: {action_type}, skipping")
            continue

        # Full format with nested dict
        # IMPORTANT: Convert to browser-use function names (click, input, navigate)
        if action_type == "go_to_url" or action_type == "navigate":
            converted.append({
                "action": "navigate",  # Browser-use function name
                "url": action_params.get("url", ""),
                "reasoning": "Browser-use action"
            })
        elif action_type == "click_element" or action_type == "click":
            # Handle multiple formats:
            # {"click": 6438} - shorthand (handled above)
            # {"click": {"index": 6438}}
            # {"click": {"element": 6438}}
            # {"click": {"element_index": 6438}}
            index = action_params.get("index") or action_params.get("element_index") or action_params.get("element")
            if index is None:
                logger.warning(f"No index found in click action params: {action_params}")
                continue
            converted.append({
                "action": "click",  # Browser-use function name
                "index": int(index),
                "reasoning": "Browser-use action"
            })
        elif action_type == "input_text" or action_type == "input":
            converted.append({
                "action": "input",  # Browser-use function name
                "index": action_params.get("index", action_params.get("element_index", 0)),
                "text": action_params.get("text", action_params.get("value", "")),
                "reasoning": "Browser-use action"
            })
        elif action_type == "hover":
            # Browser-use hover format variations:
            # {"hover": {"elements": [1820]}}
            # {"hover": {"element_index": 1820}}
            # {"hover": {"element": 1820}}
            elements = action_params.get("elements", [])
            element_index = action_params.get("element_index") or action_params.get("element")

            # Handle both formats
            if element_index is not None:
                elements = [element_index]

            if elements and isinstance(elements, list):
                # TODO: Hover is not yet in our ACT node - for now, convert to click
                logger.warning(f"Hover action converted to click (hover not yet fully supported): index={elements[0]}")
                converted.append({
                    "action": "click",  # Browser-use function name
                    "index": elements[0],
                    "reasoning": "Browser-use hover action (converted to click)"
                })
                continue
        elif action_type == "done":
            converted.append({
                "action": "done",
                "text": action_params.get("text", "Task completed"),
                "reasoning": "Browser-use done action"
            })
        elif action_type == "scroll":
            converted.append({
                "action": "scroll",
                "down": action_params.get("down", True),
                "pages": action_params.get("pages", 1.0),
                "reasoning": "Browser-use action"
            })
        else:
            logger.warning(f"Unknown browser-use action type: {action_type}, skipping")

    return converted


def parse_llm_action_plan(response_content: str) -> List[Dict[str, Any]]:
    """
    Parse LLM response to extract action plan

    Supports both formats:
    - Browser-use format: {"thinking": "...", "action": [{action_dict}]}
    - Simple format: [{"action": "...", ...}]

    Tries multiple parsing strategies:
    1. Direct JSON parsing
    2. Extract JSON from markdown code blocks
    3. Extract JSON from text

    Args:
        response_content: Raw LLM response content

    Returns:
        List of action dictionaries converted to our format
    """
    if not response_content or not response_content.strip():
        logger.warning("Empty LLM response")
        return []

    # Strategy 1: Try direct JSON parsing
    try:
        parsed = json.loads(response_content.strip())

        # Browser-use format: {"thinking": "...", "action": [actions]}
        if isinstance(parsed, dict) and "action" in parsed:
            actions = parsed["action"]
            if isinstance(actions, list):
                return convert_browser_use_actions(actions)
            return []

        # Simple array format
        if isinstance(parsed, list):
            return parsed

        # Legacy dict format with "actions" key
        elif isinstance(parsed, dict) and "actions" in parsed:
            return parsed["actions"]

        # Handle single "done" action (both "type" and "action" keys)
        elif isinstance(parsed, dict) and (parsed.get("type") == "done" or parsed.get("action") == "done"):
            return [parsed]
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract JSON from markdown code blocks (handles both array and object formats)
    json_pattern = r'```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```'
    matches = re.findall(json_pattern, response_content, re.DOTALL)
    if matches:
        try:
            parsed = json.loads(matches[0])

            # Browser-use format in markdown
            if isinstance(parsed, dict) and "action" in parsed:
                actions = parsed["action"]
                if isinstance(actions, list):
                    return convert_browser_use_actions(actions)

            # Simple array format in markdown
            elif isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Extract JSON array from text
    json_array_pattern = r'(\[[\s\S]*?\])'
    matches = re.findall(json_array_pattern, response_content)
    for match in matches:
        try:
            actions = json.loads(match)
            if isinstance(actions, list) and len(actions) > 0:
                return actions
        except json.JSONDecodeError:
            continue
    
    # Strategy 4: Try to extract individual actions from text
    # Look for action-like structures
    actions = []
    lines = response_content.split('\n')
    current_action = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Try to extract key-value pairs
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip().strip('"\'{}')
                value = parts[1].strip().strip('"\'{},')
                
                if key in ['type', 'target', 'value', 'reasoning']:
                    current_action[key] = value
                    
                    if key == 'type' and current_action:
                        # Start new action
                        if len(current_action) > 1:  # Has more than just type
                            actions.append(current_action.copy())
                        current_action = {'type': value}
    
    # Add last action if exists
    if current_action and len(current_action) > 1:
        actions.append(current_action)
    
    if actions:
        logger.info(f"Extracted {len(actions)} actions from text parsing")
        return actions

    # No fallback - return empty list if parsing completely fails
    logger.error(f"Could not parse LLM response as JSON. Raw response: {response_content[:200]}")
    logger.error("LLM must return valid JSON array. Check prompt and model output.")

    return []


def validate_action(action: Dict[str, Any]) -> bool:
    """
    Validate action using browser-use action types

    Args:
        action: Action dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(action, dict):
        return False

    # browser-use uses "action" key, but support legacy "type" for backward compatibility
    action_type = action.get("action") or action.get("type")
    if not action_type:
        logger.warning("Action missing 'action' or 'type' key")
        return False

    # Normalize to use "action" key if only "type" exists
    if "action" not in action and "type" in action:
        action["action"] = action.pop("type")
        action_type = action["action"]

    # Valid browser-use action types (using actual function names from browser-use)
    VALID_ACTIONS = {
        "click", "input", "navigate", "scroll", "done", "search", "extract",
        "send_keys", "switch_tab", "close_tab", "wait", "screenshot",
        # Legacy names for backward compatibility (will be converted)
        "go_to_url", "click_element", "input_text", "hover"
    }

    if action_type not in VALID_ACTIONS:
        logger.warning(f"Invalid action type: {action_type}. Must be one of: {VALID_ACTIONS}")
        return False

    # "done" action only needs action type and optionally text/message
    if action_type == "done":
        return True

    # Validate required fields by action type (using browser-use function names)
    if action_type in ["navigate", "go_to_url"]:  # go_to_url is legacy, will be converted to navigate
        if "url" not in action:
            logger.warning(f"{action_type} action missing 'url' field")
            return False
    elif action_type in ["click", "click_element", "input", "input_text"]:  # Legacy names for compatibility
        if "index" not in action:
            logger.warning(f"{action_type} action missing 'index' field")
            return False
    elif action_type in ["input", "input_text"]:
        if "text" not in action:
            logger.warning(f"{action_type} action missing 'text' field")
            return False
    elif action_type in ["search", "search_google"]:  # search_google is legacy
        if "query" not in action:
            logger.warning(f"{action_type} action missing 'query' field")
            return False

    # Other actions are valid
    return True

