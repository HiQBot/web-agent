"""
Console Watchdog - Monitor console messages and JavaScript errors

Provides real-time feedback to LLM about:
- JavaScript errors during form interactions
- Framework validation errors (React, Vue, Angular)
- Console warnings and logs
- Runtime exceptions

This gives the LLM full visibility into what's happening during browser interactions.
"""

import asyncio
import logging
import time
from collections import deque
from typing import ClassVar

from bubus import BaseEvent
from web_agent.browser.events import BrowserConnectedEvent, BrowserStopEvent
from web_agent.browser.watchdog_base import BaseWatchdog

logger = logging.getLogger(__name__)


class ConsoleWatchdog(BaseWatchdog):
	"""Monitor console messages and JavaScript errors for better LLM visibility."""

	LISTENS_TO: ClassVar[list[type[BaseEvent]]] = [BrowserConnectedEvent, BrowserStopEvent]
	EMITS: ClassVar[list[type[BaseEvent]]] = []

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Store recent console messages (last 100)
		self._console_messages = deque(maxlen=100)
		self._error_count = 0
		self._warning_count = 0
		self._enabled = False

	async def on_BrowserConnectedEvent(self, event: BrowserConnectedEvent) -> None:
		"""Enable console monitoring when browser connects."""
		try:
			self._console_messages.clear()
			self._error_count = 0
			self._warning_count = 0

			cdp_session = await self.browser_session.get_or_create_cdp_session()

			# Enable Console domain
			await cdp_session.cdp_client.send.Console.enable(
				session_id=cdp_session.session_id
			)

			# Enable Runtime domain for exception tracking
			await cdp_session.cdp_client.send.Runtime.enable(
				session_id=cdp_session.session_id
			)

			# Register console message handler
			cdp_session.cdp_client.register.Console.messageAdded(
				self._on_console_message
			)

			# Register runtime exception handler
			cdp_session.cdp_client.register.Runtime.exceptionThrown(
				self._on_runtime_exception
			)

			self._enabled = True
			logger.debug('🎯 Console monitoring enabled (errors, warnings, validation)')

		except Exception as e:
			logger.warning(f'Failed to enable console monitoring: {e}')

	async def on_BrowserStopEvent(self, event: BrowserStopEvent) -> None:
		"""Disable console monitoring when browser stops."""
		try:
			cdp_session = await self.browser_session.get_or_create_cdp_session()
			await cdp_session.cdp_client.send.Console.disable(
				session_id=cdp_session.session_id
			)
			await cdp_session.cdp_client.send.Runtime.disable(
				session_id=cdp_session.session_id
			)
			self._enabled = False
		except Exception:
			pass  # Browser may already be closed

	def _on_console_message(self, event, session_id: str | None) -> None:
		"""Handle console message events."""
		message = event.get('message', {})
		message_type = message.get('level', 'log')
		text = message.get('text', '')
		source = message.get('source', '')
		url = message.get('url', '')
		line = message.get('line', 0)
		column = message.get('column', 0)

		# Store message
		console_msg = {
			'type': message_type,
			'text': text,
			'source': source,
			'url': url,
			'line': line,
			'column': column,
			'timestamp': time.time(),
			'is_validation_error': self._is_form_validation_error(text)
		}
		self._console_messages.append(console_msg)

		# Count and log errors and warnings
		if message_type == 'error':
			self._error_count += 1
			# Truncate long messages for logging
			short_text = text[:200] + ('...' if len(text) > 200 else '')
			logger.warning(f'🔴 Console error: {short_text}')
		elif message_type == 'warning':
			self._warning_count += 1
			short_text = text[:200] + ('...' if len(text) > 200 else '')
			logger.debug(f'⚠️ Console warning: {short_text}')

		# Special handling for form validation errors
		if console_msg['is_validation_error']:
			short_text = text[:200] + ('...' if len(text) > 200 else '')
			logger.warning(f'📝 Form validation error: {short_text}')

	def _on_runtime_exception(self, event, session_id: str | None) -> None:
		"""Handle Runtime exceptions."""
		exception_details = event.get('exceptionDetails', {})
		exception = exception_details.get('exception', {})

		error_text = exception.get('description', 'Unknown error')
		error_type = exception.get('type', 'Error')
		line_number = exception_details.get('lineNumber', 0)
		column_number = exception_details.get('columnNumber', 0)
		url = exception_details.get('url', '')

		# Store as console error
		console_msg = {
			'type': 'error',
			'text': f'{error_type}: {error_text}',
			'source': 'runtime',
			'url': url,
			'line': line_number,
			'column': column_number,
			'timestamp': time.time(),
			'is_validation_error': self._is_form_validation_error(error_text)
		}
		self._console_messages.append(console_msg)
		self._error_count += 1

		short_text = error_text[:200] + ('...' if len(error_text) > 200 else '')
		logger.error(f'🔴 Runtime exception: {error_type}: {short_text}')

		# Check if it's a form-related error
		if console_msg['is_validation_error']:
			logger.warning(f'📝 Form-related runtime error: {short_text}')

	def _is_form_validation_error(self, text: str) -> bool:
		"""Detect if console message is a form validation error."""
		validation_keywords = [
			'validation',
			'invalid',
			'required',
			'error',
			'failed',
			'yup',
			'zod',
			'joi',
			'formik',
			'react-hook-form',
			'vee-validate',
			'validator',
			'constraint',
			'must be',
			'should be',
			'expected',
			'format',
			'pattern'
		]
		text_lower = text.lower()
		return any(keyword in text_lower for keyword in validation_keywords)

	def get_recent_errors(self, count: int = 10) -> list[dict]:
		"""Get recent console errors."""
		errors = [
			msg for msg in self._console_messages
			if msg['type'] == 'error'
		]
		return list(errors)[-count:]

	def get_recent_warnings(self, count: int = 10) -> list[dict]:
		"""Get recent console warnings."""
		warnings = [
			msg for msg in self._console_messages
			if msg['type'] == 'warning'
		]
		return list(warnings)[-count:]

	def get_validation_errors(self) -> list[dict]:
		"""Get form validation errors from console."""
		return [
			msg for msg in self._console_messages
			if msg.get('is_validation_error', False)
		]

	def get_all_messages(self, since_timestamp: float | None = None) -> list[dict]:
		"""Get all console messages, optionally filtered by timestamp."""
		if since_timestamp is None:
			return list(self._console_messages)
		return [
			msg for msg in self._console_messages
			if msg['timestamp'] > since_timestamp
		]

	def clear_messages(self) -> None:
		"""Clear stored console messages."""
		self._console_messages.clear()
		self._error_count = 0
		self._warning_count = 0

	def get_error_summary(self) -> dict:
		"""Get summary of errors and warnings for LLM visibility."""
		recent_errors = self.get_recent_errors(count=5)
		validation_errors = self.get_validation_errors()

		return {
			'total_errors': self._error_count,
			'total_warnings': self._warning_count,
			'recent_errors': [
				{
					'text': e['text'][:150],  # Truncate for token efficiency
					'source': e['source'],
					'is_validation': e.get('is_validation_error', False)
				}
				for e in recent_errors
			],
			'validation_errors': [
				{
					'text': e['text'][:150],
					'source': e['source']
				}
				for e in validation_errors[-3:]  # Last 3 validation errors
			],
			'has_errors': len(recent_errors) > 0,
			'has_validation_errors': len(validation_errors) > 0
		}

	def format_errors_for_llm(self) -> str:
		"""Format errors as string for LLM consumption."""
		summary = self.get_error_summary()

		if not summary['has_errors']:
			return ''

		parts = []

		if summary['validation_errors']:
			parts.append('Validation errors:')
			for err in summary['validation_errors']:
				parts.append(f"  - {err['text']}")

		if summary['recent_errors']:
			# Only include non-validation errors
			non_validation_errors = [
				err for err in summary['recent_errors']
				if not err['is_validation']
			]
			if non_validation_errors:
				parts.append('JavaScript errors:')
				for err in non_validation_errors[:3]:  # Max 3
					parts.append(f"  - {err['text']}")

		return '\n'.join(parts) if parts else ''
