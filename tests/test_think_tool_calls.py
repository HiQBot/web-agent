import types

import pytest

from web_agent.nodes.think import _tool_call_to_action


def test_tool_call_to_action_from_dict():
    tool_call = {
        "name": "click",
        "args": {"index": 5},
        "id": "call-1",
    }
    normalized = _tool_call_to_action(tool_call)
    assert normalized == {
        "action_type": "click",
        "params": {"index": 5},
        "tool_call_id": "call-1",
    }


def test_tool_call_to_action_from_object():
    tool_call = types.SimpleNamespace(
        name="navigate",
        args={"url": "https://example.com"},
        id="call-42",
    )
    normalized = _tool_call_to_action(tool_call)
    assert normalized["action_type"] == "navigate"
    assert normalized["params"]["url"] == "https://example.com"
    assert normalized["tool_call_id"] == "call-42"


def test_tool_call_to_action_handles_missing_values():
    empty_call = {"args": None}
    normalized = _tool_call_to_action(empty_call)
    assert normalized == {}

