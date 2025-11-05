"""
Report Node - Generate final test report

This node:
1. Collects all step results
2. Generates test report (pass/fail)
3. Formats output (JSON, HTML, markdown)
4. Includes screenshots/videos if available
5. Cleans up browser session
"""
import logging
from typing import Dict, Any
from datetime import datetime
from qa_agent.state import QAAgentState
from qa_agent.config import settings
from qa_agent.utils.browser_manager import cleanup_browser_session

logger = logging.getLogger(__name__)


async def report_node(state: QAAgentState) -> Dict[str, Any]:
    """
    Report node: Generate final test report
    
    Args:
        state: Current QA agent state
        
    Returns:
        Updated state with final report
    """
    try:
        logger.info("Report node - Generating final report")
        
        # Collect all results
        report = {
            "task": state.get("task"),
            "completed": state.get("completed", False),
            "steps": state.get("step_count", 0),
            "max_steps": state.get("max_steps", 50),
            "final_status": state.get("verification_status"),
            "verification_results": state.get("verification_results", []),
            "history": state.get("history", []),
            "error": state.get("error"),
            "timestamp": datetime.now().isoformat(),
            "executed_actions_count": len(state.get("executed_actions", [])),
            "planned_actions_count": len(state.get("planned_actions", [])),
        }
        
        # TODO: Phase 6 - Add screenshot/video capture
        # TODO: Phase 6 - Format report (JSON, HTML, markdown)

        # Cleanup browser session
        browser_session_id = state.get("browser_session_id")
        if browser_session_id:
            try:
                logger.info(f"Cleaning up browser session: {browser_session_id}")
                await cleanup_browser_session(browser_session_id)
                logger.info("Browser session cleaned up successfully")
            except Exception as e:
                logger.warning(f"Error cleaning up browser session: {e}")

        logger.info(f"Report generated: {report.get('final_status')} - {report.get('steps')} steps")

        return {
            "report": report,
            "completed": True,
        }
    except Exception as e:
        logger.error(f"Error in report node: {e}")
        return {
            "error": f"Report node error: {str(e)}",
            "completed": True,
            "report": {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        }

