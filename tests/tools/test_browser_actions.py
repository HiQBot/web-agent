import types
from unittest.mock import AsyncMock

import pytest

from web_agent.agent.views import ActionResult
from web_agent.tools.browser_actions import (
	BrowserToolContext,
	BrowserToolExecutionError,
	extract_content,
	navigate,
	read_file,
	reset_browser_tool_context,
	send_keys,
	set_browser_tool_context,
	write_file,
)


def _make_session() -> types.SimpleNamespace:
	return types.SimpleNamespace(id='session-1')


def _make_context(tools, **kwargs) -> BrowserToolContext:
	return BrowserToolContext(
		browser_session=_make_session(),
		tools=tools,
		**kwargs,
	)


@pytest.mark.asyncio
async def test_navigate_invokes_underlying_tool():
	tools = types.SimpleNamespace(
		navigate=AsyncMock(return_value=ActionResult(extracted_content='navigated'))
	)
	ctx = _make_context(tools)
	token = set_browser_tool_context(ctx)

	try:
		result = await navigate.ainvoke({'url': 'https://example.com', 'new_tab': True})
	finally:
		reset_browser_tool_context(token)

	assert result.extracted_content == 'navigated'
	tools.navigate.assert_awaited_once_with(
		url='https://example.com', new_tab=True, browser_session=ctx.browser_session
	)


@pytest.mark.asyncio
async def test_extract_requires_llm_and_filesystem():
	tools = types.SimpleNamespace(
		extract=AsyncMock(return_value=ActionResult(extracted_content='extracted'))
	)
	ctx = _make_context(tools, file_system=types.SimpleNamespace())
	token = set_browser_tool_context(ctx)

	try:
		with pytest.raises(BrowserToolExecutionError):
			await extract_content.ainvoke({'query': 'product list'})
	finally:
		reset_browser_tool_context(token)


@pytest.mark.asyncio
async def test_write_file_requires_file_system():
	tools = types.SimpleNamespace(
		write_file=AsyncMock(return_value=ActionResult(extracted_content='written'))
	)
	ctx = _make_context(tools)
	token = set_browser_tool_context(ctx)

	try:
		with pytest.raises(BrowserToolExecutionError):
			await write_file.ainvoke({'file_name': 'notes.md', 'content': 'hello'})
	finally:
		reset_browser_tool_context(token)


@pytest.mark.asyncio
async def test_read_file_passes_available_paths():
	tools = types.SimpleNamespace(
		read_file=AsyncMock(return_value=ActionResult(extracted_content='content'))
	)
	ctx = _make_context(
		tools,
		file_system=types.SimpleNamespace(),
		available_file_paths=['/tmp/report.txt'],
	)
	token = set_browser_tool_context(ctx)

	try:
		result = await read_file.ainvoke({'file_name': '/tmp/report.txt'})
	finally:
		reset_browser_tool_context(token)

	assert result.extracted_content == 'content'
	tools.read_file.assert_awaited_once_with(
		file_name='/tmp/report.txt',
		browser_session=ctx.browser_session,
		file_system=ctx.file_system,
		available_file_paths=['/tmp/report.txt'],
	)


@pytest.mark.asyncio
async def test_send_keys_rejects_empty_input():
	tools = types.SimpleNamespace(
		send_keys=AsyncMock(return_value=ActionResult(extracted_content='sent'))
	)
	ctx = _make_context(tools)
	token = set_browser_tool_context(ctx)

	try:
		with pytest.raises(ValueError):
			await send_keys.ainvoke({'keys': ''})
	finally:
		reset_browser_tool_context(token)

