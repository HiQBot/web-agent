"""
Utility functions for QA Agent
"""
from .response_parser import validate_action  # parse_llm_action_plan removed - using structured output
from .session_registry import (
	register_session,
	unregister_session,
	get_session,
	list_sessions,
	session_count,
)
from .browser_utils import _log_pretty_path, _log_pretty_url, is_new_tab_page, time_execution_sync, time_execution_async, logger, match_url_with_domain_pattern
from .singleton import singleton

# Note: browser_manager is NOT imported here to avoid circular imports
# Import it directly: from web_agent.utils.browser_manager import create_browser_session

__all__ = [
	"validate_action",  # parse_llm_action_plan removed - using LangChain structured output
	"register_session",
	"unregister_session",
	"get_session",
	"list_sessions",
	"session_count",
	"_log_pretty_path",
	"_log_pretty_url",
	"is_new_tab_page",
	"time_execution_sync",
	"time_execution_async",
	"logger",
	"singleton",
	"match_url_with_domain_pattern",
]

