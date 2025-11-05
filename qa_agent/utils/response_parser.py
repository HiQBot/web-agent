"""
Utility functions for parsing LLM responses
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_llm_action_plan(response_content: str) -> List[Dict[str, Any]]:
    """
    Parse LLM response to extract action plan
    
    Tries multiple parsing strategies:
    1. Direct JSON parsing
    2. Extract JSON from markdown code blocks
    3. Extract JSON from text
    
    Args:
        response_content: Raw LLM response content
        
    Returns:
        List of action dictionaries
    """
    if not response_content or not response_content.strip():
        logger.warning("Empty LLM response")
        return []
    
    # Strategy 1: Try direct JSON parsing
    try:
        actions = json.loads(response_content.strip())
        if isinstance(actions, list):
            return actions
        elif isinstance(actions, dict) and "actions" in actions:
            return actions["actions"]
        # Handle single "done" action (both "type" and "action" keys)
        elif isinstance(actions, dict) and (actions.get("type") == "done" or actions.get("action") == "done"):
            return [actions]
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract JSON from markdown code blocks
    json_pattern = r'```(?:json)?\s*(\[.*?\])\s*```'
    matches = re.findall(json_pattern, response_content, re.DOTALL)
    if matches:
        try:
            actions = json.loads(matches[0])
            if isinstance(actions, list):
                return actions
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

    # Valid browser-use action types
    VALID_ACTIONS = {
        "go_to_url", "click_element", "input_text",
        "extract_page_content", "scroll_down", "scroll_up",
        "go_back", "search_google", "select_dropdown_option",
        "get_dropdown_options", "send_keys", "upload_file",
        "switch_tab", "close_tab", "done"
    }

    if action_type not in VALID_ACTIONS:
        logger.warning(f"Invalid action type: {action_type}. Must be one of: {VALID_ACTIONS}")
        return False

    # "done" action only needs action type and optionally text/message
    if action_type == "done":
        return True

    # Validate required fields by action type
    if action_type == "go_to_url":
        if "url" not in action:
            logger.warning(f"go_to_url action missing 'url' field")
            return False
    elif action_type in ["click_element", "input_text", "select_dropdown_option"]:
        if "index" not in action:
            logger.warning(f"{action_type} action missing 'index' field")
            return False
    elif action_type == "input_text":
        if "text" not in action:
            logger.warning(f"input_text action missing 'text' field")
            return False
    elif action_type == "search_google":
        if "query" not in action:
            logger.warning(f"search_google action missing 'query' field")
            return False

    # Other actions are valid
    return True

