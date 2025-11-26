"""
Browser Session Lifecycle Manager

Manages browser session creation and cleanup for kernel-image CDP connection.
"""
import logging
from typing import Optional
import httpx
from uuid_extensions import uuid7str

from web_agent.browser.session import BrowserSession
from web_agent.browser.profile import BrowserProfile
from web_agent.config import settings
from web_agent.utils.session_registry import register_session, unregister_session

logger = logging.getLogger(__name__)


async def create_browser_session(start_url: Optional[str] = None) -> tuple[str, BrowserSession]:
	"""
	Create and initialize browser session connected to kernel-image CDP

	Args:
		start_url: Optional initial URL to navigate to

	Returns:
		Tuple of (session_id, BrowserSession instance)
	"""
	logger.info("Creating browser session for kernel-image CDP connection")

	# Generate unique session ID
	session_id = uuid7str()

	# Get WebSocket debugger URL from kernel-image HTTP endpoint
	http_url = f"http://{settings.kernel_cdp_host}:{settings.kernel_cdp_port}"
	logger.info(f"Querying CDP endpoint at: {http_url}")

	async with httpx.AsyncClient() as client:
		response = await client.get(f"{http_url}/json/version")
		version_data = response.json()
		cdp_url = version_data["webSocketDebuggerUrl"]
		logger.info(f"Got WebSocket URL: {cdp_url}")

	# Create browser profile configured for kernel-image (remote CDP)
	profile = BrowserProfile(
		cdp_url=cdp_url,  # Connect to kernel-image
		is_local=False,  # Remote browser (kernel-image container)
		headless=settings.headless,  # Kernel-image handles headful/headless
		minimum_wait_page_load_time=0.5,
		wait_for_network_idle_page_load_time=1.0,
		wait_between_actions=0.5,
		auto_download_pdfs=True,
		highlight_elements=True,
		dom_highlight_elements=True,
		paint_order_filtering=True,
	)

	# Create browser session
	session = BrowserSession(
		id=session_id,
		browser_profile=profile,
	)

	# Start session (connects to kernel-image CDP)
	await session.start()
	logger.info(f"Browser session {session_id} connected to kernel-image successfully")

	# Register session in registry for state serializability
	register_session(session_id, session)

	# Navigate to start URL if provided
	if start_url:
		logger.info(f"Navigating to start URL: {start_url}")
		await session.navigate_to(start_url)
		logger.info(f"Successfully navigated to: {start_url}")

	return session_id, session


async def cleanup_browser_session(session_id: Optional[str]) -> None:
	"""
	Safely cleanup browser session

	Args:
		session_id: Session ID to cleanup
	"""
	if not session_id:
		return

	from web_agent.utils.session_registry import get_session

	session = get_session(session_id)
	if session:
		try:
			logger.info(f"Cleaning up browser session: {session_id}")
			await session.stop()
			unregister_session(session_id)
			logger.info(f"Browser session {session_id} cleaned up successfully")
		except Exception as e:
			logger.error(f"Error cleaning up browser session {session_id}: {e}", exc_info=True)
	else:
		logger.warning(f"Browser session {session_id} not found in registry")
