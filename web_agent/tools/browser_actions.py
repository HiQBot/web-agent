from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterable

from langchain_core.tools import tool

from web_agent.agent.views import ActionResult
from web_agent.browser import BrowserSession
from web_agent.filesystem.file_system import FileSystem
from web_agent.llm.base import BaseChatModel
from web_agent.tools.service import Tools

logger = logging.getLogger(__name__)


class BrowserToolExecutionError(RuntimeError):
	"""Raised when a browser tool cannot be executed due to missing context or dependencies."""


@dataclass
class BrowserToolContext:
	"""Execution context injected before running LangChain tools."""

	browser_session: BrowserSession
	tools: Tools
	file_system: FileSystem | None = None
	page_extraction_llm: BaseChatModel | None = None
	available_file_paths: list[str] | None = None
	sensitive_data: dict[str, str | dict[str, str]] | None = None


_CONTEXT: ContextVar[BrowserToolContext | None] = ContextVar('browser_tool_context', default=None)

# Mapping between tool names exposed to the LLM and Tools service method names
ACTION_NAME_MAP = {
	'select_dropdown': 'select_dropdown',
	'toggle_checkbox': 'checkbox',
	'extract_content': 'extract',
	'wait': 'wait',
	'scroll': 'scroll',
	'screenshot': 'screenshot',
	'switch_tab': 'switch',
	'close_tab': 'close',
	'upload_file': 'upload_file',
	'write_file': 'write_file',
	'read_file': 'read_file',
	'send_keys': 'send_keys',
	'evaluate_javascript': 'evaluate',
	'done': 'done',
	'go_back': 'go_back',
	'input_text': 'input',
	'search': 'search',
	'navigate': 'navigate',
	'click': 'click',
	'find_text': 'find_text',
}

FILE_SYSTEM_ACTIONS = {'extract', 'write_file', 'read_file', 'replace_file', 'done'}
AVAILABLE_FILE_ACTIONS = {'read_file', 'upload_file'}
PAGE_EXTRACTION_ACTIONS = {'extract'}


def set_browser_tool_context(ctx: BrowserToolContext) -> Token:
	"""Set the runtime context for tool execution."""
	return _CONTEXT.set(ctx)


def reset_browser_tool_context(token: Token) -> None:
	"""Reset the runtime context after tool execution."""
	_CONTEXT.reset(token)


def get_browser_tool_context() -> BrowserToolContext:
	ctx = _CONTEXT.get()
	if ctx is None:
		raise BrowserToolExecutionError('Browser tool context is not configured. Act node must set it before execution.')
	return ctx


async def _execute_action(action_key: str, **action_kwargs: Any) -> ActionResult:
	"""Execute the corresponding Tools action with the active context."""
	ctx = get_browser_tool_context()
	action_name = ACTION_NAME_MAP.get(action_key, action_key)

	if not hasattr(ctx.tools, action_name):
		raise BrowserToolExecutionError(f'Unsupported action: {action_name}')

	injected_kwargs: dict[str, Any] = {'browser_session': ctx.browser_session}

	if action_name in FILE_SYSTEM_ACTIONS:
		if ctx.file_system is None:
			raise BrowserToolExecutionError(f'Action "{action_name}" requires file system access.')
		injected_kwargs['file_system'] = ctx.file_system

	if action_name in AVAILABLE_FILE_ACTIONS:
		injected_kwargs['available_file_paths'] = ctx.available_file_paths or []

	if action_name in PAGE_EXTRACTION_ACTIONS:
		if ctx.page_extraction_llm is None:
			raise BrowserToolExecutionError('Extract actions require a page_extraction_llm.')
		injected_kwargs['page_extraction_llm'] = ctx.page_extraction_llm
		if 'file_system' not in injected_kwargs:
			if ctx.file_system is None:
				raise BrowserToolExecutionError('Extract actions require file system access.')
			injected_kwargs['file_system'] = ctx.file_system

	if action_name == 'input' and ctx.sensitive_data:
		injected_kwargs['has_sensitive_data'] = True
		injected_kwargs['sensitive_data'] = ctx.sensitive_data

	tool_callable = getattr(ctx.tools, action_name)
	result = await tool_callable(**action_kwargs, **injected_kwargs)

	if isinstance(result, ActionResult):
		return result
	if isinstance(result, str):
		return ActionResult(extracted_content=result)
	if isinstance(result, dict):
		return ActionResult(**result)

	raise BrowserToolExecutionError(f'Unexpected result type from action "{action_name}": {type(result)}')


def _ensure_positive_index(index: int, action: str) -> None:
	if index < 0:
		raise ValueError(f'{action} requires a non-negative element index.')


@tool
async def navigate(url: str, new_tab: bool = False) -> ActionResult:
	"""Navigate the browser to an absolute URL. Set new_tab=True to open in a separate tab."""
	return await _execute_action('navigate', url=url, new_tab=new_tab)


@tool
async def search(query: str, engine: str = 'duckduckgo') -> ActionResult:
	"""Run a search query using the configured search engine."""
	return await _execute_action('search', query=query, engine=engine)


@tool
async def go_back() -> ActionResult:
	"""Navigate back in browser history."""
	return await _execute_action('go_back')


@tool
async def wait(seconds: float = 3.0) -> ActionResult:
	"""Pause execution for a duration (0.1–30s) to allow the page to settle."""
	clamped = max(0.1, min(seconds, 30.0))
	return await _execute_action('wait', seconds=clamped)


@tool
async def click(index: int) -> ActionResult:
	"""Click a DOM element referenced by its index in the DOM snapshot."""
	if index <= 0:
		raise ValueError('click requires an element index greater than 0.')
	return await _execute_action('click', index=index)


@tool
async def input_text(index: int, text: str, clear: bool = True) -> ActionResult:
	"""Type text into an input, textarea, or contentEditable element."""
	_ensure_positive_index(index, 'input_text')
	return await _execute_action('input_text', index=index, text=text, clear=clear)


@tool
async def select_dropdown(index: int, option_text: str) -> ActionResult:
	"""Select an option from a dropdown/select element by its visible text."""
	_ensure_positive_index(index, 'select_dropdown')
	if not option_text:
		raise ValueError('select_dropdown requires a non-empty option_text value.')
	return await _execute_action('select_dropdown', index=index, text=option_text)


@tool
async def toggle_checkbox(index: int, checked: bool | None = True) -> ActionResult:
	"""Ensure a checkbox/radio element is checked, unchecked, or toggled (checked=None)."""
	_ensure_positive_index(index, 'toggle_checkbox')
	return await _execute_action('toggle_checkbox', index=index, checked=checked)


@tool
async def extract_content(
	query: str,
	extract_links: bool = False,
	start_from_char: int = 0,
) -> ActionResult:
	"""Extract structured content from the current page based on a natural-language query."""
	if not query.strip():
		raise ValueError('extract_content requires a non-empty query.')
	return await _execute_action(
		'extract_content',
		query=query.strip(),
		extract_links=extract_links,
		start_from_char=max(0, start_from_char),
	)


@tool
async def find_text(text: str) -> ActionResult:
	"""Scroll to and highlight the first visible occurrence of the provided text."""
	if not text.strip():
		raise ValueError('find_text requires non-empty text.')
	return await _execute_action('find_text', text=text)


@tool
async def screenshot() -> ActionResult:
	"""Request a screenshot in the next browser observation."""
	return await _execute_action('screenshot')


@tool
async def scroll(direction: str = 'down', pages: float = 1.0, element_index: int | None = None) -> ActionResult:
	"""Scroll the page (or a specific scrollable element) by a number of viewport heights."""
	dir_lower = direction.lower()
	if dir_lower not in {'down', 'up', 'top', 'bottom'}:
		raise ValueError('scroll direction must be one of: up, down, top, bottom.')

	down_flag = dir_lower in {'down', 'bottom'}
	scroll_pages = pages
	if dir_lower in {'top', 'bottom'}:
		scroll_pages = max(pages, 10.0)

	params: dict[str, Any] = {
		'down': down_flag,
		'pages': max(0.1, min(scroll_pages, 10.0)),
	}
	if element_index is not None and element_index != 0:
		params['index'] = element_index

	return await _execute_action('scroll', **params)


@tool
async def switch_tab(tab_id: str) -> ActionResult:
	"""Switch to an existing tab using its 4-character identifier (shown in browser state)."""
	if not tab_id:
		raise ValueError('switch_tab requires a tab_id (last 4 characters of the target id).')
	return await _execute_action('switch_tab', tab_id=tab_id[-4:])


@tool
async def close_tab(tab_id: str) -> ActionResult:
	"""Close a browser tab by its identifier."""
	if not tab_id:
		raise ValueError('close_tab requires a tab_id.')
	return await _execute_action('close_tab', tab_id=tab_id[-4:])


@tool
async def upload_file(index: int, file_path: str) -> ActionResult:
	"""Upload a local file through the file input near the specified element index."""
	_ensure_positive_index(index, 'upload_file')
	if not file_path:
		raise ValueError('upload_file requires file_path to be provided.')
	return await _execute_action('upload_file', index=index, path=file_path)


@tool
async def write_file(
	file_name: str,
	content: str,
	append: bool = False,
	trailing_newline: bool = True,
) -> ActionResult:
	"""Write text content to a workspace file. Set append=True to append instead of overwrite."""
	if not file_name:
		raise ValueError('write_file requires a file_name.')
	return await _execute_action(
		'write_file',
		file_name=file_name,
		content=content,
		append=append,
		trailing_newline=trailing_newline,
	)


@tool
async def read_file(file_name: str) -> ActionResult:
	"""Read the contents of a workspace or downloaded file."""
	if not file_name:
		raise ValueError('read_file requires a file_name.')
	return await _execute_action('read_file', file_name=file_name)


@tool
async def send_keys(keys: str) -> ActionResult:
	"""Send raw keyboard input to the active page (e.g., 'Enter', 'Escape')."""
	if not keys:
		raise ValueError('send_keys requires a non-empty keys string.')
	return await _execute_action('send_keys', keys=keys)


@tool
async def evaluate_javascript(script: str) -> ActionResult:
	"""Execute JavaScript inside the page context and return the evaluated result."""
	if not script.strip():
		raise ValueError('evaluate_javascript requires JavaScript code to execute.')
	return await _execute_action('evaluate_javascript', code=script)


@tool
async def done(result: str, success: bool = True, files_to_display: Iterable[str] | None = None) -> ActionResult:
	"""Mark the task as complete and optionally attach file outputs."""
	return await _execute_action(
		'done',
		text=result,
		success=success,
		files_to_display=list(files_to_display or []),
	)


BROWSER_TOOLS = [
	navigate,
	search,
	go_back,
	wait,
	click,
	input_text,
	select_dropdown,
	toggle_checkbox,
	extract_content,
	find_text,
	screenshot,
	scroll,
	switch_tab,
	close_tab,
	upload_file,
	write_file,
	read_file,
	send_keys,
	evaluate_javascript,
	done,
]

__all__ = [
	'BROWSER_TOOLS',
	'BrowserToolContext',
	'BrowserToolExecutionError',
	'get_browser_tool_context',
	'reset_browser_tool_context',
	'set_browser_tool_context',
]

