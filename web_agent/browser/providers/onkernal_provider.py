"""
OnKernal Browser Provider

Connects to remote OnKernal Browser via CDP.
"""
import logging
from typing import Optional, Tuple
import httpx
from uuid_extensions import uuid7str

from web_agent.browser.session import BrowserSession
from web_agent.browser.profile import BrowserProfile
from web_agent.browser.providers import BrowserProvider
from web_agent.config import settings
from web_agent.utils.session_registry import register_session, unregister_session

logger = logging.getLogger(__name__)


class OnKernalProvider(BrowserProvider):
	"""Provider for OnKernal Browser (remote CDP)."""
	
	def __init__(self):
		self._cdp_port: Optional[int] = None
		self._viewer_url: str = "http://localhost:8080"
	
	async def create_session(self, start_url: Optional[str] = None) -> Tuple[str, BrowserSession]:
		"""
		Create and initialize browser session connected to OnKernal Browser CDP.
		
		Args:
			start_url: Optional initial URL to navigate to
			
		Returns:
			Tuple of (session_id, BrowserSession instance)
		"""
		logger.info("Creating browser session for OnKernal Browser CDP connection")
		
		# Generate unique session ID
		session_id = uuid7str()
		
		# Use the configured OnKernal CDP port directly (the service already binds to it)
		self._cdp_port = getattr(settings, 'kernel_cdp_port', None) or getattr(settings, 'cdp_port', 9222)
		
		# Get WebSocket debugger URL from OnKernal HTTP endpoint
		http_url = f"http://{settings.kernel_cdp_host}:{self._cdp_port}"
		logger.info(f"Querying CDP endpoint at: {http_url}")
		
		try:
			async with httpx.AsyncClient() as client:
				response = await client.get(f"{http_url}/json/version", timeout=5.0)
				response.raise_for_status()
				version_data = response.json()
				cdp_url = version_data["webSocketDebuggerUrl"]
				logger.info(f"Got WebSocket URL: {cdp_url}")
		except httpx.RequestError as e:
			raise RuntimeError(
				f"Failed to connect to OnKernal Browser at {http_url}. "
				f"Make sure OnKernal Browser is running. Error: {e}"
			)
		
		# Create browser profile configured for OnKernal (remote CDP)
		profile = BrowserProfile(
			cdp_url=cdp_url,  # Connect to OnKernal
			is_local=False,  # Remote browser (OnKernal container)
			headless=settings.headless,  # OnKernal handles headful/headless
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
		
		# Start session (connects to OnKernal CDP)
		await session.start()
		logger.info(f"Browser session {session_id} connected to OnKernal Browser successfully")
		
		# Register session in registry for state serializability
		register_session(session_id, session)
		
		# Navigate to start URL if provided
		if start_url:
			logger.info(f"Navigating to start URL: {start_url}")
			await session.navigate_to(start_url)
			logger.info(f"Successfully navigated to: {start_url}")
		
		return session_id, session
	
	async def cleanup(self) -> None:
		"""Cleanup OnKernal browser resources."""
		# OnKernal is managed externally, nothing to cleanup here
		logger.debug("OnKernal provider cleanup (no action needed)")
	
	def get_cdp_url(self) -> str:
		"""Get CDP WebSocket URL."""
		if self._cdp_port:
			return f"ws://{settings.kernel_cdp_host}:{self._cdp_port}/devtools/browser"
		return f"ws://{settings.kernel_cdp_host}:{settings.kernel_cdp_port}/devtools/browser"
	
	def get_viewer_url(self) -> str:
		"""Get URL for frontend iframe (OnKernal WebRTC interface)."""
		return self._viewer_url

