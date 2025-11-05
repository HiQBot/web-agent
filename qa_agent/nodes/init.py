"""
INIT Node: Initialize browser session at workflow start

This node creates the BrowserSession connected to kernel-image CDP
and prepares it for use by THINK and ACT nodes.
"""
import logging
from typing import Any, Dict

from qa_agent.state import QAAgentState
from qa_agent.utils.browser_manager import create_browser_session

logger = logging.getLogger(__name__)


async def init_node(state: QAAgentState) -> Dict[str, Any]:
	"""Initialize browser session for the workflow.

	Args:
		state: Current workflow state (may contain start_url)

	Returns:
		Dict with browser_session_id and current_url
	"""
	logger.info("INIT: Starting browser session initialization")

	# Get start URL from state if provided
	start_url = state.get("start_url")

	# Create browser session (this connects to kernel-image CDP)
	logger.info(f"INIT: Creating browser session{' with start_url=' + start_url if start_url else ''}")
	session_id, session = await create_browser_session(start_url=start_url)

	logger.info(f"INIT: Browser session created successfully: {session_id}")

	# Get current URL after navigation
	current_url = None
	if start_url:
		try:
			current_url = await session.get_current_page_url()
			logger.info(f"INIT: Navigated to {current_url}")
		except Exception as e:
			logger.warning(f"INIT: Could not get current page URL: {e}")
			current_url = start_url  # Fallback to requested URL

	return {
		"browser_session_id": session_id,
		"current_url": current_url,
	}
