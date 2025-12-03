"""
Chrome Browser Provider

Uses existing LocalBrowserWatchdog mechanism to launch local Chrome/Chromium browser.
This follows the industry-standard pattern (same as browser-use).

Chrome runs headful on the desktop and streams via CDP screencast to Live Preview.
"""
import logging
from typing import Optional, Tuple
from uuid_extensions import uuid7str

from web_agent.browser.session import BrowserSession
from web_agent.browser.profile import BrowserProfile
from web_agent.browser.providers import BrowserProvider
from web_agent.config import settings
from web_agent.utils.session_registry import register_session

logger = logging.getLogger(__name__)


class ChromeProvider(BrowserProvider):
	"""
	Provider for local Chrome/Chromium browser.
	
	Uses existing LocalBrowserWatchdog mechanism for Chrome launch.
	When BrowserSession.start() is called with is_local=True and cdp_url=None,
	it automatically dispatches BrowserLaunchEvent which LocalBrowserWatchdog handles.
	"""
	
	def __init__(self):
		self._viewer_url: str = "http://localhost:8080"
		self._session: Optional[BrowserSession] = None
	
	async def create_session(self, start_url: Optional[str] = None) -> Tuple[str, BrowserSession]:
		"""
		Create and initialize browser session with local Chrome.
		
		Uses existing LocalBrowserWatchdog mechanism:
		1. Create BrowserProfile with is_local=True, cdp_url=None
		2. Set executable_path from config if provided
		3. Create BrowserSession with that profile
		4. Call session.start() → automatically dispatches BrowserLaunchEvent
		5. LocalBrowserWatchdog handles Chrome launch with proper args
		6. Returns CDP URL → BrowserSession connects via CDP
		
		Args:
			start_url: Optional initial URL to navigate to
			
		Returns:
			Tuple of (session_id, BrowserSession instance)
		"""
		logger.info("Creating browser session for local Chrome using LocalBrowserWatchdog")

		# Generate unique session ID
		session_id = uuid7str()

		# Create browser profile configured for local Chrome launch
		# Key: is_local=True, cdp_url=None triggers automatic launch via LocalBrowserWatchdog
		# Chrome runs headful (visible window) and streams via CDP screencast to Live Preview
		profile = BrowserProfile(
			cdp_url=None,  # None triggers automatic launch via LocalBrowserWatchdog
			is_local=True,  # Local browser - triggers BrowserLaunchEvent
			executable_path=settings.chrome_executable_path if settings.chrome_executable_path else None,
			headless=False,  # Headful mode - Chrome runs with UI, captured via screencast for Live Preview
			args=[
				'--window-size=1920,1080',  # Set window size for consistent screenshots
			],
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
		
		# Store session reference for cleanup
		self._session = session
		
		# Start session - this will automatically:
		# 1. Dispatch BrowserLaunchEvent (because is_local=True, cdp_url=None)
		# 2. LocalBrowserWatchdog handles the event and launches Chrome
		# 3. Returns CDP URL from LocalBrowserWatchdog
		# 4. BrowserSession connects via CDP
		await session.start()
		logger.info(f"Browser session {session_id} connected to Chrome successfully")
		
		# Register session in registry
		register_session(session_id, session)
		
		# Navigate to start URL if provided
		if start_url:
			logger.info(f"Navigating to start URL: {start_url}")
			await session.navigate_to(start_url)
			logger.info(f"Successfully navigated to: {start_url}")
		
		return session_id, session
	
	async def cleanup(self) -> None:
		"""
		Cleanup Chrome browser resources.

		LocalBrowserWatchdog manages Chrome process lifecycle automatically.
		We just need to stop the browser session.
		"""
		if self._session:
			try:
				logger.info("Stopping Chrome browser session")
				await self._session.stop()  # This dispatches BrowserStopEvent → LocalBrowserWatchdog handles cleanup
				logger.info("Chrome browser session stopped")
			except Exception as e:
				logger.error(f"Error stopping Chrome browser session: {e}")
			finally:
				self._session = None
	
	def get_cdp_url(self) -> str:
		"""Get CDP WebSocket URL from the session."""
		if self._session and self._session.cdp_url:
			return self._session.cdp_url
		return f"ws://localhost:{settings.cdp_port}/devtools/browser"
	
	def get_viewer_url(self) -> str:
		"""Get URL for frontend iframe (Chrome streaming interface)."""
		return self._viewer_url

