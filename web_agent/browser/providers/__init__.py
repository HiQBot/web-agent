"""
Browser Provider Abstraction

Factory pattern for creating browser sessions from different providers
(OnKernal, Chrome, etc.). All providers expose CDP interface.
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from web_agent.browser.session import BrowserSession
from web_agent.config import settings

logger = logging.getLogger(__name__)


class BrowserProvider(ABC):
	"""Abstract base class for browser providers."""
	
	@abstractmethod
	async def create_session(self, start_url: Optional[str] = None) -> Tuple[str, BrowserSession]:
		"""
		Create and initialize a browser session.
		
		Args:
			start_url: Optional initial URL to navigate to
			
		Returns:
			Tuple of (session_id, BrowserSession instance)
		"""
		pass
	
	@abstractmethod
	async def cleanup(self) -> None:
		"""Cleanup browser instance and resources."""
		pass
	
	@abstractmethod
	def get_cdp_url(self) -> str:
		"""Get CDP WebSocket URL for connecting to browser."""
		pass
	
	@abstractmethod
	def get_viewer_url(self) -> str:
		"""Get URL for frontend iframe/viewer."""
		pass


def get_browser_provider() -> BrowserProvider:
	"""
	Factory function to get the appropriate browser provider based on configuration.
	
	Returns:
		BrowserProvider instance (OnKernalProvider or ChromeProvider)
	"""
	provider_name = settings.browser_provider.lower()
	logger.info(f"Browser provider setting: '{settings.browser_provider}' (normalized: '{provider_name}')")
	
	if provider_name == "onkernal":
		from web_agent.browser.providers.onkernal_provider import OnKernalProvider
		logger.info("Creating OnKernalProvider instance")
		return OnKernalProvider()
	elif provider_name == "chrome":
		from web_agent.browser.providers.chrome_provider import ChromeProvider
		logger.info("Creating ChromeProvider instance")
		return ChromeProvider()
	else:
		raise ValueError(
			f"Unknown browser provider: {provider_name}. "
			f"Supported providers: 'onkernal', 'chrome'"
		)

