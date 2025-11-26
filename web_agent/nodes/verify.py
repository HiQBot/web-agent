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
from web_agent.state import QAAgentState
from web_agent.config import settings

logger = logging.getLogger(__name__)


async def verify_node(state: QAAgentState) -> Dict[str, Any]:
    """
    Verify node: Legacy minimal verification

    SIMPLIFIED: Tab switching is now handled by ACT node for efficiency.
    This node is kept for backward compatibility but mainly verifies action results.

    Args:
        state: Current QA agent state

    Returns:
        Updated state with verification results
    """
    try:
        logger.info(f"Verify node - Step {state.get('step_count', 0)}")
        logger.info("ℹ️  Note: Tab switching now handled in ACT node for efficiency")

        action_results = state.get("action_results", [])

        verification_results = []

        # Verify actions based on action results
        # NOTE: ACT node already verified these via success/failure fields
        # This is a simple pass-through verification for backward compatibility
        for result in action_results:
            success = result.get("success", False)
            error = result.get("error")
            extracted_content = result.get("extracted_content", "")

            # Check if extracted_content contains error-like messages
            content_looks_like_error = False
            if extracted_content:
                error_indicators = [
                    "not available",
                    "page may have changed",
                    "Try refreshing",
                    "failed",
                    "error",
                    "not found",
                    "invalid",
                ]
                content_lower = extracted_content.lower()
                content_looks_like_error = any(indicator in content_lower for indicator in error_indicators)

            # Action status
            if success and not error and not content_looks_like_error:
                verification_results.append({
                    "status": "pass",
                    "reason": f"Action completed: {extracted_content[:50] if extracted_content else 'Success'}",
                })
            else:
                failure_reason = error or extracted_content or "Action returned success=False"
                verification_results.append({
                    "status": "fail",
                    "reason": failure_reason[:200],
                })

        # Determine overall status
        all_passed = all(
            r.get("status") == "pass"
            for r in verification_results
        )

        verification_status = "pass" if all_passed else "fail"

        # NOTE: Todo.md update is now handled in ACT node for efficiency
        # See act_wrapper.py lines 473-533 for todo update logic

        file_system_state = state.get("file_system_state")
        
        # Update history - create new list (LangGraph best practice: don't mutate state)
        new_history_entry = {
            "step": state.get("step_count", 0),
            "node": "verify",
            "verification_status": verification_status,
            "verification_results": verification_results,
        }

        # Return minimal state updates (ACT node handles tab switching and todo updates)
        return {
            "verification_status": verification_status,
            "verification_results": verification_results,
            "file_system_state": file_system_state,
            "history": [new_history_entry],  # operator.add will append to existing
        }
    except Exception as e:
        logger.error(f"Error in verify node: {e}")
        return {
            "error": f"Verify node error: {str(e)}",
            "verification_status": "fail",
            "verification_results": [{"status": "fail", "reason": str(e)}],
        }

