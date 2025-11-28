"""
Browser Session Registry

Manages browser session instances to keep state serializable for LangGraph.
State stores session_id (string), this registry maps IDs to actual BrowserSession objects.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Global session registry - maps session_id -> BrowserSession
_SESSION_REGISTRY: Dict[str, any] = {}


def register_session(session_id: str, session: any) -> None:
	"""
	Register a browser session instance

	Args:
		session_id: Unique session identifier
		session: BrowserSession instance
	"""
	_SESSION_REGISTRY[session_id] = session
	logger.info(f"Registered browser session: {session_id}")


def get_session(session_id: str) -> Optional[any]:
	"""
	Retrieve a browser session by ID

	Args:
		session_id: Session identifier

	Returns:
		BrowserSession instance or None if not found
	"""
	session = _SESSION_REGISTRY.get(session_id)
	if session is None:
		logger.warning(f"Browser session not found: {session_id}")
	return session


def unregister_session(session_id: str) -> None:
	"""
	Unregister and remove a browser session

	Args:
		session_id: Session identifier to remove
	"""
	if session_id in _SESSION_REGISTRY:
		del _SESSION_REGISTRY[session_id]
		logger.info(f"Unregistered browser session: {session_id}")
	else:
		logger.warning(f"Attempted to unregister non-existent session: {session_id}")


def list_sessions() -> list[str]:
	"""Get list of all registered session IDs"""
	return list(_SESSION_REGISTRY.keys())


def session_count() -> int:
	"""Get count of active sessions"""
	return len(_SESSION_REGISTRY)
