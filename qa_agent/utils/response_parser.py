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
            elif action_type == "switch" or action_type == "switch_tab":
                # Shorthand switch: {"switch": "E33D"}
                converted.append({
                    "action": "switch",  # Browser-use function name
                    "tab_id": str(action_params),
                    "reasoning": "Browser-use shorthand switch tab"
                })
            elif action_type == "navigate" or action_type == "go_to_url":
                # Shorthand navigate: {"navigate": "https://..."}
                converted.append({
                    "action": "navigate",
                    "url": str(action_params),
                    "reasoning": "Browser-use shorthand navigate"
                })
            elif action_type == "input" or action_type == "input_text":
                # Shorthand input: {"input": "text"} - but this needs an index, so warn
                logger.warning(f"Shorthand input without index, skipping: {action_params}")
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
            # {"click": {"selector": 6438}} - LLM sometimes uses "selector"
            index = action_params.get("index") or action_params.get("element_index") or action_params.get("element") or action_params.get("selector")
            if index is None:
                logger.warning(f"No index found in click action params: {action_params}")
                continue
            converted.append({
                "action": "click",  # Browser-use function name
                "index": int(index),
                "reasoning": "Browser-use action"
            })
        elif action_type == "input_text" or action_type == "input":
            # Input can have index, element_index, element, or id (browser-use supports id lookup)
            # LLM sometimes uses "element" instead of "index" or "element_index"
            index = action_params.get("index") or action_params.get("element_index") or action_params.get("element")
            # If no index but has id, we need to find it in DOM (but for now, warn)
            if index is None and action_params.get("id"):
                logger.warning(f"Input action has 'id' ({action_params.get('id')}) but no index - LLM should provide index from browser_state")
            # Default to None if no index provided (let act node handle error)
            converted.append({
                "action": "input",  # Browser-use function name
                "index": int(index) if index is not None else None,  # Convert to int if provided
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
                "index": action_params.get("index"),  # Optional index for element-specific scrolling
                "reasoning": "Browser-use action"
            })
        elif action_type == "switch_tab" or action_type == "switch":
            # Browser-use uses "switch" as the action name
            # LLM sometimes uses "tab" instead of "tab_id"
            tab_id = action_params.get("tab_id") or action_params.get("tab", "")
            # Ensure tab_id is 4 characters (last 4 of target_id)
            if tab_id and len(tab_id) > 4:
                tab_id = tab_id[-4:]
            converted.append({
                "action": "switch",  # Browser-use function name is "switch"
                "tab_id": tab_id,
                "reasoning": "Browser-use switch tab action"
            })
        elif action_type == "close_tab":
            converted.append({
                "action": "close_tab",
                "tab_id": action_params.get("tab_id", ""),
                "reasoning": "Browser-use close tab action"
            })
        elif action_type == "extract":
            # Handle different extract formats from LLM
            # LLM sometimes uses "attributes", "info", or "elements"
            query = action_params.get("query", "")
            elements = action_params.get("elements") or action_params.get("attributes", []) or action_params.get("info", [])
            text = action_params.get("text", False)
            url = action_params.get("url", False)

            # Handle when LLM outputs query as a dict: {"query": {"title": "...", "url": "..."}}
            if isinstance(query, dict):
                # Extract what the LLM wants
                query_keys = list(query.keys())
                if "title" in query_keys and "url" in query_keys:
                    query = "extract the page title and URL"
                elif "title" in query_keys:
                    query = "extract the page title"
                elif "url" in query_keys:
                    query = "extract the page URL"
                else:
                    query = f"extract {', '.join(query_keys)}"

            # If LLM wants title/URL, these are already in browser state - convert to appropriate query
            if elements and isinstance(elements, list):
                if "title" in elements and "url" in elements:
                    query = "extract the page title and URL"
                elif "title" in elements:
                    query = "extract the page title"
                elif "url" in elements:
                    query = "extract the page URL"
                else:
                    query = f"extract {', '.join(elements)}"
            elif text and url:
                query = "extract the page title and URL"
            elif text:
                query = "extract the page title"
            elif url:
                query = "extract the page URL"
            elif not query:
                # Default query if none provided
                query = "extract relevant information from the page"
            
            converted.append({
                "action": "extract",
                "query": query,
                "extract_links": action_params.get("extract_links", False) or url or (elements and "url" in elements if isinstance(elements, list) else False),
                "start_from_char": action_params.get("start_from_char", 0),
                "reasoning": "Browser-use extract action"
            })
        elif action_type == "search":
            converted.append({
                "action": "search",
                "query": action_params.get("query", ""),
                "engine": action_params.get("engine", "duckduckgo"),
                "reasoning": "Browser-use search action"
            })
        elif action_type == "send_keys":
            converted.append({
                "action": "send_keys",
                "keys": action_params.get("keys", ""),
                "reasoning": "Browser-use send keys action"
            })
        elif action_type == "wait":
            converted.append({
                "action": "wait",
                "seconds": action_params.get("seconds", 3),
                "reasoning": "Browser-use wait action"
            })
        elif action_type == "screenshot":
            converted.append({
                "action": "screenshot",
                "reasoning": "Browser-use screenshot action"
            })
        elif action_type == "go_back":
            converted.append({
                "action": "go_back",
                "reasoning": "Browser-use go back action"
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

    # Strategy 1: Strip JSON comments before parsing (JSON doesn't support comments)
    # Remove single-line comments (// ...) and multi-line comments (/* ... */)
    cleaned_content = response_content.strip()
    # Remove single-line comments
    cleaned_content = re.sub(r'//.*?$', '', cleaned_content, flags=re.MULTILINE)
    # Remove multi-line comments
    cleaned_content = re.sub(r'/\*.*?\*/', '', cleaned_content, flags=re.DOTALL)
    
    # Strategy 1: Try direct JSON parsing (on cleaned content)
    try:
        parsed = json.loads(cleaned_content)

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
            # Strip comments from extracted JSON
            json_str = matches[0]
            json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
            json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
            parsed = json.loads(json_str)

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
        "send_keys", "switch", "switch_tab", "close_tab", "wait", "screenshot", "go_back",
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

