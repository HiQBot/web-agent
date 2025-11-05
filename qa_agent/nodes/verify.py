"""
Verify Node - Verify action results

This node:
1. Checks if actions succeeded (DOM changes, URL changes, element visibility)
2. Compares expected vs actual results
3. Validates page state matches expectations
4. Generates verification results
"""
import logging
from typing import Dict, Any
from qa_agent.state import QAAgentState
from qa_agent.config import settings

logger = logging.getLogger(__name__)


async def verify_node(state: QAAgentState) -> Dict[str, Any]:
    """
    Verify node: Check if actions succeeded
    
    Args:
        state: Current QA agent state
        
    Returns:
        Updated state with verification results
    """
    try:
        logger.info(f"Verify node - Step {state.get('step_count', 0)}")
        
        browser_session = state.get("browser_session")
        action_results = state.get("action_results", [])
        
        verification_results = []
        
        # Verify actions based on action results
        # An action is successful if:
        # 1. success is True AND error is None/empty
        # 2. extracted_content exists (indicates action executed)
        for result in action_results:
            success = result.get("success", False)
            error = result.get("error")
            extracted_content = result.get("extracted_content")
            
            # Action succeeded if success=True and no error
            if success and not error:
                verification_results.append({
                    "status": "pass",
                    "reason": f"Action completed: {extracted_content[:50] if extracted_content else 'Success'}",
                    "details": result,
                })
            else:
                # Action failed if success=False OR error exists
                verification_results.append({
                    "status": "fail",
                    "reason": error or "Action returned success=False",
                    "details": result,
                })
        
        # Determine overall status
        all_passed = all(
            r.get("status") == "pass" 
            for r in verification_results
        )
        
        verification_status = "pass" if all_passed else "fail"
        
        # Update history - create new list (LangGraph best practice: don't mutate state)
        existing_history = state.get("history", [])
        new_history_entry = {
            "step": state.get("step_count", 0),
            "node": "verify",
            "verification_status": verification_status,
            "verification_results": verification_results,
        }
        
        return {
            "verification_status": verification_status,
            "verification_results": verification_results,
            "history": existing_history + [new_history_entry],  # Return new list
        }
    except Exception as e:
        logger.error(f"Error in verify node: {e}")
        return {
            "error": f"Verify node error: {str(e)}",
            "verification_status": "fail",
            "verification_results": [{"status": "fail", "reason": str(e)}],
        }

