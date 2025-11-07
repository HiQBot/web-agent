# LangChain Structured Output Documentation Analysis

## Official Documentation Sources

### 1. Structured Outputs Concept Page
**URL**: https://python.langchain.com/docs/concepts/structured_outputs/

**Key Points**:
- `with_structured_output()` method enables models to return outputs formatted according to a specified schema
- Accepts schemas in various forms:
  - OpenAI function/tool schema
  - JSON Schema
  - `TypedDict` class
  - **Pydantic class** (what we're using)
- If a Pydantic class is used, the model output will be an instance of that class
- Method parameter options:
  - `'json_schema'`: Utilizes OpenAI's Structured Output API (default)
  - `'function_calling'`: Employs OpenAI's tool-calling API
  - `'json_mode'`: Uses OpenAI's JSON mode

**Example**:
```python
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

class ResponseFormatter(BaseModel):
    answer: str
    followup_question: str

model = ChatOpenAI(model="gpt-4o").with_structured_output(ResponseFormatter)
structured_output = model.invoke("What is the powerhouse of the cell?")
print(structured_output)  # Direct Pydantic model instance
```

### 2. How-To Guide: Structured Output
**URL**: https://python.langchain.com/docs/how_to/structured_output/

**Key Points**:
- Detailed guide on implementing structured outputs
- Examples of different schema types
- Best practices for structured output

### 3. ChatOpenAI API Reference
**URL**: https://api.python.langchain.com/en/latest/langchain_openai/langchain_openai.chat_models.ChatOpenAI.html

**Key Points**:
- Official API reference for `ChatOpenAI` class
- Documentation for `with_structured_output()` method
- Method signatures and parameters

## Critical Finding: Usage Metadata Limitation

### Browser-Use's LangChain Integration Example

**Location**: `browser-use-main/examples/models/langchain/chat.py` (lines 146-148)

**Key Finding**:
```python
# For structured output, usage metadata is typically not available
# in the parsed object since it's a Pydantic model, not an AIMessage
usage = None
```

**This confirms**:
- ✅ `with_structured_output()` returns the Pydantic model **directly**
- ❌ Usage metadata is **NOT available** in the parsed object
- ❌ The result is a Pydantic model, not an `AIMessage` object
- ❌ No `.usage` or `.usage_metadata` property available

### Browser-Use's Workaround

**Location**: `browser-use-main/examples/models/langchain/chat.py` (lines 155-188)

**Fallback Strategy**:
1. Try `with_structured_output()` first
2. If it fails or usage is needed, fall back to regular `ainvoke()`
3. Parse the JSON response manually
4. Extract usage from the `AIMessage` response

**Code**:
```python
try:
    structured_chat = self.chat.with_structured_output(output_format)
    parsed_object = await structured_chat.ainvoke(langchain_messages)
    usage = None  # Not available with structured output
except AttributeError:
    # Fall back to manual parsing
    response = await self.chat.ainvoke(langchain_messages)
    usage = self._get_usage(response)  # Extract from AIMessage
    # Parse JSON manually
    parsed_object = output_format(**json.loads(response.content))
```

## Implications for Our Code

### 1. Usage Metadata Access

**Problem**: LangChain's `with_structured_output()` does NOT provide usage metadata directly.

**Possible Solutions**:

**Option A: Use Callbacks** (Recommended)
- LangChain supports callbacks for tracking usage
- Can register callbacks to capture token usage
- More complex but preserves telemetry

**Option B: Accept `usage=None`** (Simple)
- Accept that structured output doesn't provide usage
- Set `usage=None` in `ChatInvokeCompletion`
- Simple but loses token tracking

**Option C: Fallback to Regular `ainvoke()`** (Browser-use pattern)
- Use regular `ainvoke()` when usage is needed
- Parse JSON response manually
- Extract usage from `AIMessage`
- More complex but preserves usage tracking

**Option D: Use LangChain's Response Metadata** (Investigate)
- Check if LangChain provides response metadata
- May need to use callbacks or response wrappers
- Needs investigation

### 2. Response Structure

**Browser-use Pattern**:
```python
response = await llm.ainvoke(messages, output_format=AgentOutput)
parsed = response.completion  # Pydantic model
usage = response.usage  # ChatInvokeUsage
```

**LangChain Pattern**:
```python
structured_llm = llm.with_structured_output(AgentOutput)
parsed = await structured_llm.ainvoke(messages)  # Direct Pydantic model
# NO usage available directly!
```

### 3. Required Code Changes

**Files Affected**:
1. `qa_agent/nodes/think.py` - Already updated ✅
2. `qa_agent/actor/page.py` - Needs update ❌
3. `qa_agent/tokens/service.py` - Needs update ❌
4. `qa_agent/llm/__init__.py` - May need wrapper ❌

## Recommended Approach

### Create LangChain ChatOpenAI Wrapper

**Benefits**:
- Maintains browser-use compatible interface
- Handles usage extraction via callbacks
- Centralizes LangChain-specific logic
- Minimal changes to existing code

**Implementation Strategy**:
1. Create wrapper that implements `BaseChatModel` Protocol
2. Wrap LangChain's `ChatOpenAI`
3. Use callbacks to capture usage metadata
4. Return `ChatInvokeCompletion` with usage information
5. Handle both structured and non-structured outputs

## Documentation Links

### Primary Sources
1. **Structured Outputs Concept**: https://python.langchain.com/docs/concepts/structured_outputs/
2. **Structured Output How-To**: https://python.langchain.com/docs/how_to/structured_output/
3. **ChatOpenAI API Reference**: https://api.python.langchain.com/en/latest/langchain_openai/langchain_openai.chat_models.ChatOpenAI.html

### Related Documentation
4. **LangGraph v1 Migration Guide**: https://docs.langchain.com/oss/python/migrate/langgraph-v1
5. **LangChain v1 Release Notes**: https://docs.langchain.com/oss/python/releases-v1
6. **LangGraph Structured Output Guide**: https://langchain-ai.github.io/langgraph/how-tos/react-agent-structured-output/

## Key Takeaways

1. ✅ `with_structured_output()` is the correct method for LangChain
2. ✅ Returns Pydantic model directly (not wrapped)
3. ❌ Usage metadata is NOT available directly
4. ⚠️ Need to use callbacks or fallback strategy for usage tracking
5. ⚠️ Browser-use's example confirms this limitation

## Next Steps

1. Investigate LangChain callbacks for usage tracking
2. Create wrapper that implements browser-use compatible interface
3. Update all code that uses `output_format` parameter
4. Test usage tracking with structured output

