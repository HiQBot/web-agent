# Multi-LLM Implementation: Tool Calling Architecture

**Date**: 2025-12-03
**Status**: Implementation Phase
**Architecture**: LangChain v1.0 Native with `bind_tools()`

---

## Executive Summary

Migrating from `with_structured_output()` to **`bind_tools()` pattern** for universal multi-LLM compatibility (OpenAI, Gemini, Claude, and future providers).

**Why**: LangChain v1.0 standardized tool calling interface works identically across all providers, eliminating provider-specific workarounds and schema complexity issues.

---

## Architecture Overview

### Current Problem
```python
# ❌ Current approach - Provider-specific, schema complexity issues
method = "json_schema" if provider == "gemini" else "function_calling"
structured_llm = llm.with_structured_output(ActionModel, method=method)
response = await structured_llm.ainvoke(messages)  # Fails with Gemini
```

**Issues**:
- Complex union schema (22+ optional fields) breaks Gemini
- Provider-specific method selection needed
- Not agent-ready architecture

### Target Solution
```python
# ✅ New approach - Universal, provider-agnostic
llm_with_tools = llm.bind_tools(BROWSER_TOOLS)
response = await llm_with_tools.ainvoke(messages)
actions = response.tool_calls  # Works with ALL providers
```

**Benefits**:
- ✅ Universal compatibility (OpenAI, Gemini, Claude)
- ✅ No schema complexity issues
- ✅ Agent-ready architecture
- ✅ Future-proof (LangChain v1.0 standard)
- ✅ Zero technical debt

---

## Implementation Plan

### Phase 1: Define Browser Actions as Tools

**File**: `web_agent/tools/browser_actions.py` (NEW)

```python
"""
Browser action tools for LangChain multi-LLM compatibility.
Each action is a standalone tool with simple, focused schema.
"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ===== Navigation Actions =====

@tool
def navigate(url: str) -> str:
    """Navigate to a URL in the browser.

    Args:
        url: The URL to navigate to (e.g., 'https://example.com')

    Returns:
        Status message confirming navigation
    """
    # Implementation will be added
    return f"Navigated to {url}"


@tool
def go_back() -> str:
    """Go back to the previous page in browser history.

    Returns:
        Status message confirming navigation
    """
    return "Went back one page"


@tool
def search(query: str) -> str:
    """Search using the default search engine.

    Args:
        query: Search query text

    Returns:
        Status message confirming search
    """
    return f"Searched for: {query}"


# ===== DOM Interaction Actions =====

@tool
def click(index: int) -> str:
    """Click an element on the page.

    Args:
        index: Element index from the DOM representation

    Returns:
        Status message confirming click
    """
    return f"Clicked element at index {index}"


@tool
def input_text(index: int, text: str) -> str:
    """Input text into a form field.

    Args:
        index: Element index of the input field
        text: Text to input

    Returns:
        Status message confirming input
    """
    return f"Input '{text}' into element {index}"


@tool
def select_dropdown(index: int, value: str) -> str:
    """Select an option from a dropdown menu.

    Args:
        index: Element index of the dropdown
        value: Value of the option to select

    Returns:
        Status message confirming selection
    """
    return f"Selected '{value}' in dropdown at index {index}"


@tool
def toggle_checkbox(index: int, checked: bool) -> str:
    """Check or uncheck a checkbox.

    Args:
        index: Element index of the checkbox
        checked: True to check, False to uncheck

    Returns:
        Status message confirming toggle
    """
    action = "Checked" if checked else "Unchecked"
    return f"{action} checkbox at index {index}"


# ===== Content Extraction Actions =====

@tool
def extract_content(content_type: str = "text") -> str:
    """Extract content from the current page.

    Args:
        content_type: Type of content ('text', 'html', 'markdown')

    Returns:
        Extracted content
    """
    return f"Extracted {content_type} content from page"


@tool
def find_text(text: str) -> str:
    """Find text on the current page.

    Args:
        text: Text to search for

    Returns:
        Status message with search results
    """
    return f"Found text: '{text}'"


@tool
def screenshot(filename: str = None) -> str:
    """Take a screenshot of the current page.

    Args:
        filename: Optional filename for the screenshot

    Returns:
        Path to the saved screenshot
    """
    return f"Screenshot saved: {filename or 'screenshot.png'}"


# ===== Scrolling & Waiting Actions =====

@tool
def scroll(direction: str = "down", amount: int = None) -> str:
    """Scroll the page.

    Args:
        direction: Direction to scroll ('up', 'down', 'top', 'bottom')
        amount: Optional pixel amount to scroll

    Returns:
        Status message confirming scroll
    """
    return f"Scrolled {direction}" + (f" by {amount}px" if amount else "")


@tool
def wait(seconds: float) -> str:
    """Wait for a specified duration.

    Args:
        seconds: Number of seconds to wait (0.1 to 30.0)

    Returns:
        Status message confirming wait
    """
    return f"Waited {seconds} seconds"


# ===== Tab/Window Management =====

@tool
def switch_tab(index: int) -> str:
    """Switch to a different browser tab.

    Args:
        index: Index of the tab to switch to

    Returns:
        Status message confirming tab switch
    """
    return f"Switched to tab {index}"


@tool
def close_tab() -> str:
    """Close the current browser tab.

    Returns:
        Status message confirming close
    """
    return "Closed current tab"


# ===== File Actions =====

@tool
def upload_file(index: int, file_path: str) -> str:
    """Upload a file to a file input element.

    Args:
        index: Element index of the file input
        file_path: Path to the file to upload

    Returns:
        Status message confirming upload
    """
    return f"Uploaded {file_path} to element {index}"


@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file.

    Args:
        file_path: Path where to save the file
        content: Content to write

    Returns:
        Status message confirming write
    """
    return f"Wrote content to {file_path}"


@tool
def read_file(file_path: str) -> str:
    """Read content from a file.

    Args:
        file_path: Path to the file to read

    Returns:
        File content
    """
    return f"Content of {file_path}"


# ===== Advanced Actions =====

@tool
def send_keys(keys: str) -> str:
    """Send keyboard keys to the browser.

    Args:
        keys: Keys to send (e.g., 'Enter', 'Tab', 'Escape')

    Returns:
        Status message confirming key press
    """
    return f"Sent keys: {keys}"


@tool
def evaluate_javascript(script: str) -> str:
    """Execute JavaScript in the browser context.

    Args:
        script: JavaScript code to execute

    Returns:
        Result of the JavaScript execution
    """
    return f"Executed JavaScript: {script[:50]}..."


# ===== Task Completion =====

@tool
def done(result: str) -> str:
    """Mark the task as complete with a final result.

    Args:
        result: The final result or extracted information

    Returns:
        Completion message with result
    """
    return f"Task completed: {result}"


# ===== Tool Registry =====

BROWSER_TOOLS = [
    # Navigation
    navigate,
    go_back,
    search,
    # DOM Interaction
    click,
    input_text,
    select_dropdown,
    toggle_checkbox,
    # Content
    extract_content,
    find_text,
    screenshot,
    # Scrolling
    scroll,
    wait,
    # Tabs
    switch_tab,
    close_tab,
    # Files
    upload_file,
    write_file,
    read_file,
    # Advanced
    send_keys,
    evaluate_javascript,
    # Completion
    done,
]
```

---

### Phase 2: Update Think Node

**File**: `web_agent/nodes/think.py`

```python
from web_agent.tools.browser_actions import BROWSER_TOOLS
from web_agent.llm import get_llm

async def think_node(state: AgentState) -> AgentState:
    """
    Think node using LangChain tool calling (universal multi-LLM).
    Works identically with OpenAI, Gemini, Claude, and future providers.
    """
    logger.info("=== THINK NODE (Tool Calling) ===")

    # Get LLM (provider-agnostic)
    llm = get_llm()

    # Bind browser action tools
    llm_with_tools = llm.bind_tools(BROWSER_TOOLS)

    # Build messages
    messages = build_langchain_messages(state)

    # Invoke LLM - it decides which tool(s) to call
    response = await llm_with_tools.ainvoke(messages)

    # Extract tool calls (standardized across ALL providers)
    tool_calls = response.tool_calls

    logger.info(f"LLM wants to call {len(tool_calls)} tool(s)")

    # Convert tool calls to actions
    actions = []
    for tool_call in tool_calls:
        action = {
            "action_type": tool_call["name"],  # e.g., "click", "navigate"
            "params": tool_call["args"],  # e.g., {"index": 5}
            "tool_call_id": tool_call["id"]  # For tracking
        }
        actions.append(action)
        logger.info(f"  - {action['action_type']}: {action['params']}")

    # Update state
    state["actions"] = actions
    state["thoughts"] = response.content or "Executing browser actions"

    # Check if done
    done_actions = [a for a in actions if a["action_type"] == "done"]
    if done_actions:
        state["current_state_name"] = "done"
        state["result"] = done_actions[0]["params"].get("result", "Task completed")

    return state
```

---

### Phase 3: Update Action Execution

**File**: `web_agent/nodes/act.py`

```python
from web_agent.tools.browser_actions import BROWSER_TOOLS

# Create tool name to function mapping
TOOL_MAP = {tool.name: tool for tool in BROWSER_TOOLS}

async def act_node(state: AgentState) -> AgentState:
    """
    Execute browser actions returned by tool calling.
    """
    logger.info("=== ACT NODE ===")

    actions = state.get("actions", [])
    results = []

    for action in actions:
        action_type = action["action_type"]
        params = action["params"]

        logger.info(f"Executing: {action_type} with {params}")

        # Get the tool function
        tool_func = TOOL_MAP.get(action_type)

        if not tool_func:
            error_msg = f"Unknown action: {action_type}"
            logger.error(error_msg)
            results.append({"error": error_msg})
            continue

        try:
            # Execute the tool
            result = await tool_func.ainvoke(params)
            results.append({"success": True, "result": result})
            logger.info(f"  → {result}")
        except Exception as e:
            error_msg = f"Action {action_type} failed: {str(e)}"
            logger.error(error_msg)
            results.append({"error": error_msg})

    state["action_results"] = results
    return state
```

---

### Phase 4: Update LLM Factory

**File**: `web_agent/llm/__init__.py`

```python
"""
Multi-LLM support with LangChain v1.0 standardized interface.
All providers use the same bind_tools() interface.
"""
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from web_agent.config import settings

def get_llm(
    provider: str = None,
    model: str = None,
    temperature: float = None,
):
    """
    Get LLM instance with universal tool calling support.

    All returned LLMs support:
    - llm.bind_tools(tools) - Bind tools to LLM
    - response.tool_calls - Extract tool calls from response

    This works identically across OpenAI, Gemini, Claude.
    """
    provider = (provider or settings.llm_provider or "openai").lower()
    temp = temperature if temperature is not None else settings.llm_temperature

    if provider == "openai":
        model_name = model or settings.llm_model
        return ChatOpenAI(
            model=model_name,
            temperature=temp,
            api_key=settings.openai_api_key,
        )

    elif provider in ["google", "gemini"]:
        model_name = model or settings.gemini_model
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temp,
            google_api_key=settings.google_api_key or settings.gemini_api_key,
            convert_system_message_to_human=True,
        )

    elif provider in ["anthropic", "claude"]:
        model_name = model or "claude-3-5-sonnet-20241022"
        return ChatAnthropic(
            model=model_name,
            temperature=temp,
            api_key=settings.anthropic_api_key,
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")
```

---

## Implementation Checklist

### Week 1: Tool Definitions
- [ ] Create `web_agent/tools/browser_actions.py`
- [ ] Define all 22 browser actions as `@tool` functions
- [ ] Create `BROWSER_TOOLS` list
- [ ] Add docstrings and type hints
- [ ] Unit test each tool function

### Week 2: Node Updates
- [ ] Refactor `think.py` to use `bind_tools()`
- [ ] Update `act.py` to execute tools via `TOOL_MAP`
- [ ] Update `get_llm()` with provider comments
- [ ] Remove old `with_structured_output()` code
- [ ] Remove old `ActionModel` union schemas

### Week 3: Testing & Deployment
- [ ] Test with OpenAI (gpt-4o-mini, gpt-4.1)
- [ ] Test with Gemini (gemini-2.5-flash, gemini-2.5-pro)
- [ ] Test with Claude (claude-3-5-sonnet) when ready
- [ ] Integration tests across all providers
- [ ] Update API documentation
- [ ] Deploy to staging
- [ ] Deploy to production

---

## Key Benefits

### Universal Compatibility
```python
# Same code works for ALL providers - no special cases!
llm = get_llm(provider="openai")  # or "gemini" or "claude"
llm_with_tools = llm.bind_tools(BROWSER_TOOLS)
response = await llm_with_tools.ainvoke(messages)
tool_calls = response.tool_calls  # Always works!
```

### Simple Schemas
```python
# ✅ Each tool has simple, focused schema
@tool
def click(index: int) -> str:
    """Click an element"""
    pass

# ❌ Old way: Complex union with 22+ optional fields
class ActionModel(BaseModel):
    click: Union[ClickAction, None] = None
    navigate: Union[NavigateAction, None] = None
    # ... 20 more unions
```

### Agent-Ready Architecture
```python
# Future: Multi-step reasoning, tool composition
llm_with_tools = llm.bind_tools(BROWSER_TOOLS + API_TOOLS + DATABASE_TOOLS)

# Future: Human-in-the-loop
if needs_approval:
    await wait_for_human_approval(tool_calls)

# Future: Tool result feedback
for tool_call in tool_calls:
    result = execute_tool(tool_call)
    messages.append(ToolMessage(result, tool_call_id=tool_call.id))
```

---

## Comparison: Old vs New

| Aspect | Old (with_structured_output) | New (bind_tools) |
|--------|----------------------------|------------------|
| **Gemini Support** | ❌ Fails with empty dicts | ✅ Works perfectly |
| **Provider Code** | ⚠️ Different per provider | ✅ Identical for all |
| **Schema Complexity** | ❌ 22+ union fields | ✅ Simple per-tool schemas |
| **Agent-Ready** | ❌ Single-shot only | ✅ Multi-step, composable |
| **Maintainability** | ⚠️ Custom workarounds | ✅ LangChain handles it |
| **Future-Proof** | ⚠️ May deprecate | ✅ LangChain v1.0 standard |
| **Testing** | ⚠️ Provider-specific tests | ✅ Universal test suite |

---

## References

- [LangChain Tool Calling Guide](https://blog.langchain.com/tool-calling-with-langchain/)
- [LangChain v1.0 Release](https://blog.langchain.com/langchain-langgraph-1dot0/)
- [bind_tools() vs with_structured_output()](https://github.com/langchain-ai/langchain/discussions/25811)
- [LangGraph Structured Output](https://langchain-ai.github.io/langgraph/how-tos/react-agent-structured-output/)
- [Multi-Agent Systems 2025](https://blogs.infoservices.com/artificial-intelligence/langchain-multi-agent-ai-framework-2025/)

---

**Status**: Ready for Implementation
**Architecture**: LangChain v1.0 Native
**Estimated Timeline**: 2-3 weeks
**Technical Debt**: Zero ✅
