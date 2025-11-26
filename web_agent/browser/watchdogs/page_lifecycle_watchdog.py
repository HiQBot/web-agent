"""
Page Lifecycle Watchdog - Track page loading states

Eliminates arbitrary waits by tracking actual page lifecycle:
- init: Initial state
- loading: Page is loading
- DOMContentLoaded: DOM is ready
- load: Page fully loaded
- networkIdle: Network is idle (no requests for 500ms)
"""

import asyncio
import logging
from typing import ClassVar

from bubus import BaseEvent
from web_agent.browser.events import BrowserConnectedEvent
from web_agent.browser.watchdog_base import BaseWatchdog

logger = logging.getLogger(__name__)


class PageLifecycleWatchdog(BaseWatchdog):
	"""Track page lifecycle events for better wait conditions."""

	LISTENS_TO: ClassVar[list[type[BaseEvent]]] = [BrowserConnectedEvent]
	EMITS: ClassVar[list[type[BaseEvent]]] = []

	async def on_BrowserConnectedEvent(self, event: BrowserConnectedEvent) -> None:
		"""Enable lifecycle events when browser connects."""
		try:
			cdp_session = await self.browser_session.get_or_create_cdp_session()

			# Enable lifecycle events
			await cdp_session.cdp_client.send.Page.setLifecycleEventsEnabled(
				params={'enabled': True},
				session_id=cdp_session.session_id
			)

			logger.debug('📄 Page lifecycle events enabled')

			# Register lifecycle event handlers
			cdp_session.cdp_client.register.Page.lifecycleEvent(self._on_lifecycle_event)
			cdp_session.cdp_client.register.Page.loadEventFired(self._on_load_event)
			cdp_session.cdp_client.register.Page.domContentEventFired(self._on_dom_content_event)

		except Exception as e:
			logger.warning(f'Failed to enable page lifecycle events: {e}')

	def _on_lifecycle_event(self, event, session_id: str | None) -> None:
		"""Handle lifecycle state changes."""
		name = event.get('name')
		frame_id = event.get('frameId')

		logger.debug(f'📄 Page lifecycle: {name} (frame={frame_id[-4:] if frame_id else "unknown"})')

		# Store current state for wait conditions
		if not hasattr(self.browser_session, '_lifecycle_states'):
			self.browser_session._lifecycle_states = {}

		self.browser_session._lifecycle_states[frame_id] = name

		# Trigger waiters
		if hasattr(self.browser_session, '_lifecycle_waiters'):
			for target_state, future in list(self.browser_session._lifecycle_waiters.items()):
				if name == target_state and not future.done():
					future.set_result(True)

	def _on_load_event(self, event, session_id: str | None) -> None:
		"""Handle page load completion."""
		timestamp = event.get('timestamp')
		logger.debug(f'✅ Page load event fired (timestamp={timestamp})')

		# Mark page as loaded
		self.browser_session._page_loaded = True

	def _on_dom_content_event(self, event, session_id: str | None) -> None:
		"""Handle DOMContentLoaded event."""
		timestamp = event.get('timestamp')
		logger.debug(f'✅ DOMContentLoaded event fired (timestamp={timestamp})')

		# Mark DOM as ready
		self.browser_session._dom_content_loaded = True
