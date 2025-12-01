"""
Browser Session Lifecycle Manager

Manages browser session creation and cleanup using browser providers.
Supports both OnKernal and Chrome browsers via provider pattern.
"""
import logging
from typing import Optional

from web_agent.browser.session import BrowserSession
from web_agent.browser.providers import get_browser_provider
from web_agent.utils.session_registry import unregister_session

logger = logging.getLogger(__name__)

# Global provider instance (created on first use)
_provider_instance = None


async def create_browser_session(start_url: Optional[str] = None) -> tuple[str, BrowserSession]:
	"""
	Create and initialize browser session using the configured browser provider.

	Args:
		start_url: Optional initial URL to navigate to

	Returns:
		Tuple of (session_id, BrowserSession instance)
	"""
	global _provider_instance
	
	# Always get fresh provider to respect config changes (don't cache)
	# This ensures BROWSER_PROVIDER env changes are picked up
	from web_agent.config import settings
	current_provider_name = settings.browser_provider.lower()
	
	# Reset provider if config changed or if None
	if _provider_instance is None:
		_provider_instance = get_browser_provider()
		logger.info(f"Using browser provider: {type(_provider_instance).__name__}")
	
	# Create session using provider
	return await _provider_instance.create_session(start_url)


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


async def cleanup_browser_provider() -> None:
	"""
	Cleanup browser provider resources (e.g., stop Chrome process).
	"""
	global _provider_instance
	
	if _provider_instance is not None:
		try:
			await _provider_instance.cleanup()
			logger.info("Browser provider cleaned up")
		except Exception as e:
			logger.error(f"Error cleaning up browser provider: {e}", exc_info=True)
		finally:
			_provider_instance = None
