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
        # Handle single "done" action
        elif isinstance(actions, dict) and actions.get("type") == "done":
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
    
    # Fallback: Return a generic action based on the response
    logger.warning(f"Could not parse LLM response as JSON. Raw response: {response_content[:200]}")
    
    # Try to infer at least one action from the text
    if 'navigate' in response_content.lower() or 'url' in response_content.lower():
        return [{
            "type": "navigate",
            "target": "https://example.com",
            "reasoning": "LLM suggested navigation but response format was unclear"
        }]
    
    return []


def validate_action(action: Dict[str, Any]) -> bool:
    """
    Validate that an action has required fields
    
    Args:
        action: Action dictionary to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(action, dict):
        return False
    
    if "type" not in action:
        return False
    
    action_type = action.get("type", "")
    
    # "done" action only needs type and optionally message
    if action_type == "done":
        return True
    
    # Required fields by action type
    if action_type == "navigate":
        return "target" in action or "url" in action
    elif action_type in ["click", "type", "select"]:
        return "target" in action
    elif action_type == "type":
        return "target" in action and ("value" in action or "text" in action)
    
    # Other actions might not need specific fields
    return True

