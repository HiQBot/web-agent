# QA Automation Agent - Implementation Plan
## LangGraph + Browser-Use Integration Strategy

---

## 🎯 **CORE GOAL**

Build a robust QA Automation Agent using LangGraph/LangChain for orchestration while leveraging browser-use's battle-tested components (browser session, DOM handling, tools) with minimal modifications.

**Architecture Philosophy:**
- **LangGraph**: Agentic workflow orchestration (think → act → verify → report)
- **Browser-Use Components**: Reuse CDP browser automation, DOM serialization, and tool execution
- **Minimal Changes**: Adapt browser-use components to LangGraph context, not rewrite

---

## 🏗️ **ARCHITECTURE OVERVIEW**

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                        │
│  ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐│
│  │  Think  │───▶│   Act   │───▶│  Verify  │───▶│ Report  ││
│  └─────────┘    └─────────┘    └──────────┘    └─────────┘│
│       │              │               │               │      │
│       └──────────────┴───────────────┴───────────────┘      │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Browser-Use Components Layer                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ BrowserSession│  │  DomService  │  │ Tools/Registry│    │
│  │   (CDP)      │  │  (Serializer)│  │  (Actions)    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Chrome DevTools Protocol (CDP)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 **PHASE BREAKDOWN**

### **PHASE 1: Foundation Setup** 
**Goal**: Set up LangGraph structure and integrate browser-use browser session

**Duration**: 2-3 days

#### Tasks:
1. **Create LangGraph State Model**
   - File: `qa_agent/state.py`
   - Define state schema (task, browser_state, history, results, step_count)

2. **Integrate BrowserSession**
   - Copy: `browser_use/browser/session.py` → `qa_agent/browser/session.py`
   - Copy: `browser_use/browser/profile.py` → `qa_agent/browser/profile.py`
   - Copy: `browser_use/browser/views.py` → `qa_agent/browser/views.py`
   - Copy: `browser_use/browser/events.py` → `qa_agent/browser/events.py`
   - **Modifications**:
     - Remove agent-specific event handlers (if any)
     - Ensure session can be initialized from LangGraph context
     - Keep CDP connection logic intact

3. **Create Basic LangGraph Nodes**
   - File: `qa_agent/nodes/__init__.py`
   - File: `qa_agent/nodes/think.py` (placeholder)
   - File: `qa_agent/nodes/act.py` (placeholder)
   - File: `qa_agent/nodes/verify.py` (placeholder)
   - File: `qa_agent/nodes/report.py` (placeholder)

4. **Create Workflow Structure**
   - File: `qa_agent/workflow.py`
   - Define basic node structure with conditional edges
   - Test basic state flow

**Deliverable**: Browser session initializes, LangGraph workflow compiles and runs

---

### **PHASE 2: DOM & Browser State Integration**
**Goal**: Integrate DOM serialization and browser state management

**Duration**: 3-4 days

#### Tasks:
1. **Integrate DomService**
   - Copy: `browser_use/dom/service.py` → `qa_agent/dom/service.py`
   - Copy: `browser_use/dom/views.py` → `qa_agent/dom/views.py`
   - Copy: `browser_use/dom/enhanced_snapshot.py` → `qa_agent/dom/enhanced_snapshot.py`
   - Copy: `browser_use/dom/serializer/` → `qa_agent/dom/serializer/`
     - `serializer.py`
     - `clickable_elements.py`
     - `paint_order.py`
   - **Modifications**:
     - Ensure DomService works with our BrowserSession
     - Test DOM serialization in LangGraph context

2. **Create Browser State Extractor**
   - File: `qa_agent/utils/browser_state.py`
   - Function: `get_browser_state()` - calls DomService and formats for LLM
   - Function: `get_interactive_elements()` - extract clickable elements

3. **Update Think Node**
   - File: `qa_agent/nodes/think.py`
   - **Functionality**:
     - Get current browser state (URL, DOM, interactive elements)
     - Format prompt with browser state
     - Call LLM for thinking + next actions
     - Parse LLM response into actions

**Deliverable**: Think node can see browser state and generate actions

---

### **PHASE 3: Tools & Actions Integration**
**Goal**: Integrate browser-use tools/registry into LangGraph act node

**Duration**: 4-5 days

#### Tasks:
1. **Integrate Tools Registry**
   - Copy: `browser_use/tools/registry/service.py` → `qa_agent/tools/registry/service.py`
   - Copy: `browser_use/tools/registry/views.py` → `qa_agent/tools/registry/views.py`
   - Copy: `browser_use/tools/service.py` → `qa_agent/tools/service.py`
   - Copy: `browser_use/tools/views.py` → `qa_agent/tools/views.py`
   - Copy: `browser_use/tools/utils.py` → `qa_agent/tools/utils.py`
   - **Modifications**:
     - Ensure Tools class accepts BrowserSession
     - Verify all action models work with our setup

2. **Integrate Action Execution Events**
   - Copy: `browser_use/browser/events.py` (action events) → keep in `qa_agent/browser/events.py`
   - Ensure events work with BrowserSession

3. **Update Act Node**
   - File: `qa_agent/nodes/act.py`
   - **Functionality**:
     - Receive actions from Think node
     - Initialize Tools instance with BrowserSession
     - Execute actions via `Tools.act()` method
     - Capture action results
     - Update state with results

4. **Create Action Wrapper**
   - File: `qa_agent/utils/action_executor.py`
   - Wrapper around browser-use Tools to integrate with LangGraph state

**Deliverable**: Act node can execute browser actions (click, type, navigate, etc.)

---

### **PHASE 4: Prompt & LLM Integration**
**Goal**: Integrate browser-use prompts and LLM adapters

**Duration**: 3-4 days

#### Tasks:
1. **Integrate System Prompt**
   - Copy: `browser_use/agent/system_prompt.md` → `qa_agent/prompts/system_prompt.md`
   - File: `qa_agent/prompts/prompt_builder.py`
   - **Modifications**:
     - Adapt prompt for QA-specific workflow
     - Add LangGraph state context
     - Integrate browser state formatting

2. **Integrate LLM Adapters**
   - Copy: `browser_use/llm/` → `qa_agent/llm/`
   - Keep all LLM providers (OpenAI, Anthropic, Google, etc.)
   - **Modifications**:
     - Ensure LLM classes work with LangGraph
     - Test tool calling format compatibility

3. **Update Think Node with LLM**
   - File: `qa_agent/nodes/think.py` (enhance)
   - **Functionality**:
     - Build prompt with system message + browser state
     - Call LLM with tool definitions (from Tools registry)
     - Parse structured output (thinking + actions)

4. **Create Response Parser**
   - File: `qa_agent/utils/response_parser.py`
   - Parse LLM response into LangGraph state updates

**Deliverable**: Think node generates actions via LLM based on browser state

---

### **PHASE 5: Verification & Validation**
**Goal**: Implement verification logic for QA-specific checks

**Duration**: 3-4 days

#### Tasks:
1. **Create Verification Node**
   - File: `qa_agent/nodes/verify.py`
   - **Functionality**:
     - Check if action succeeded (DOM changes, URL changes, element visibility)
     - Compare expected vs actual results
     - Validate page state matches expectations
     - Generate verification results

2. **Create QA-Specific Verifiers**
   - File: `qa_agent/verifiers/__init__.py`
   - File: `qa_agent/verifiers/text_verifier.py` - verify text appears/doesn't appear
   - File: `qa_agent/verifiers/element_verifier.py` - verify element state
   - File: `qa_agent/verifiers/url_verifier.py` - verify navigation
   - File: `qa_agent/verifiers/form_verifier.py` - verify form submission

3. **Create Conditional Router**
   - File: `qa_agent/workflow.py` (enhance)
   - Router function: `should_continue(state)` → "continue" | "retry" | "done"
   - Logic:
     - If verification passes → continue to next think
     - If verification fails → retry (with max retries)
     - If task complete → done → report

**Deliverable**: Verify node validates actions and routes workflow accordingly

---

### **PHASE 6: Reporting & Observability**
**Goal**: Implement reporting and result collection

**Duration**: 2-3 days

#### Tasks:
1. **Create Report Node**
   - File: `qa_agent/nodes/report.py`
   - **Functionality**:
     - Collect all step results
     - Generate test report (pass/fail)
     - Format output (JSON, HTML, markdown)
     - Include screenshots/videos if available

2. **Integrate Screenshot Service** (optional)
   - Copy: `browser_use/screenshots/service.py` → `qa_agent/screenshots/service.py`
   - Add screenshot capture to report

3. **Create Result Aggregator**
   - File: `qa_agent/utils/results.py`
   - Aggregate all step results into final report

**Deliverable**: Report node generates comprehensive test reports

---

### **PHASE 7: Integration & Testing**
**Goal**: Full integration testing and refinement

**Duration**: 4-5 days

#### Tasks:
1. **End-to-End Workflow Test**
   - Test: Login flow
   - Test: Form submission
   - Test: Multi-step navigation
   - Test: Error handling

2. **State Management Testing**
   - Verify state persists correctly across nodes
   - Test state cleanup

3. **Error Handling**
   - Handle browser crashes
   - Handle network errors
   - Handle invalid actions
   - Handle timeout scenarios

4. **Performance Optimization**
   - Optimize DOM serialization (if needed)
   - Cache browser state where possible
   - Optimize LLM calls

5. **Documentation**
   - Usage examples
   - API documentation
   - Configuration guide

**Deliverable**: Fully functional QA automation agent with comprehensive testing

---

## 📁 **PROJECT STRUCTURE**

```
onkernal/
├── qa_agent/
│   ├── __init__.py
│   ├── state.py                    # LangGraph state model
│   ├── workflow.py                 # LangGraph workflow definition
│   │
│   ├── nodes/                      # LangGraph nodes
│   │   ├── __init__.py
│   │   ├── think.py                # Thinking & planning node
│   │   ├── act.py                  # Action execution node
│   │   ├── verify.py               # Verification node
│   │   └── report.py               # Reporting node
│   │
│   ├── browser/                    # Browser-Use components (copied)
│   │   ├── session.py              # BrowserSession (from browser-use)
│   │   ├── profile.py              # BrowserProfile (from browser-use)
│   │   ├── views.py                # Browser views (from browser-use)
│   │   └── events.py               # Browser events (from browser-use)
│   │
│   ├── dom/                        # DOM-Use components (copied)
│   │   ├── service.py              # DomService (from browser-use)
│   │   ├── views.py                # DOM views (from browser-use)
│   │   ├── enhanced_snapshot.py    # Snapshot builder (from browser-use)
│   │   └── serializer/             # DOM serializers (from browser-use)
│   │       ├── serializer.py
│   │       ├── clickable_elements.py
│   │       └── paint_order.py
│   │
│   ├── tools/                      # Tools-Use components (copied)
│   │   ├── service.py              # Tools class (from browser-use)
│   │   ├── views.py                # Tool action models (from browser-use)
│   │   ├── utils.py                # Tool utilities (from browser-use)
│   │   └── registry/               # Tool registry (from browser-use)
│   │       ├── service.py
│   │       └── views.py
│   │
│   ├── llm/                        # LLM adapters (copied)
│   │   ├── base.py                 # Base LLM (from browser-use)
│   │   ├── openai/                 # OpenAI adapter (from browser-use)
│   │   ├── anthropic/              # Anthropic adapter (from browser-use)
│   │   └── ...                     # Other LLM providers
│   │
│   ├── prompts/                    # Prompt management
│   │   ├── system_prompt.md        # System prompt (adapted from browser-use)
│   │   └── prompt_builder.py      # Prompt construction
│   │
│   ├── verifiers/                  # QA verification logic
│   │   ├── __init__.py
│   │   ├── text_verifier.py
│   │   ├── element_verifier.py
│   │   ├── url_verifier.py
│   │   └── form_verifier.py
│   │
│   └── utils/                      # Utility functions
│       ├── browser_state.py        # Browser state extraction
│       ├── action_executor.py      # Action execution wrapper
│       ├── response_parser.py      # LLM response parsing
│       └── results.py              # Result aggregation
│
├── tests/                          # Test suite
│   ├── test_workflow.py
│   ├── test_nodes.py
│   └── test_integration.py
│
├── examples/                       # Usage examples
│   ├── basic_test.py
│   ├── login_test.py
│   └── form_test.py
│
└── IMPLEMENTATION_PLAN.md          # This file
```

---

## 🔧 **KEY MODIFICATIONS NEEDED**

### **1. BrowserSession Integration**
- **Location**: `qa_agent/browser/session.py`
- **Changes**:
  - Ensure it can be initialized from LangGraph state
  - Remove agent-specific event handlers (if any)
  - Keep CDP connection logic intact

### **2. Tools Integration**
- **Location**: `qa_agent/tools/service.py`
- **Changes**:
  - Ensure `Tools.__init__()` accepts `BrowserSession`
  - Verify action execution returns results compatible with LangGraph state
  - Test tool registry filtering works

### **3. Prompt Adaptation**
- **Location**: `qa_agent/prompts/system_prompt.md`
- **Changes**:
  - Adapt for QA-specific workflow
  - Reference LangGraph state structure
  - Add verification instructions

### **4. State Management**
- **Location**: `qa_agent/state.py`
- **Changes**:
  - Define state schema compatible with browser-use components
  - Include: task, browser_state, actions, results, step_count, verification_status

---

## 🚀 **INTEGRATION STRATEGY**

### **Approach: Minimal Modification**

1. **Copy First, Modify Later**
   - Copy browser-use files as-is
   - Test integration
   - Modify only where necessary

2. **Adapter Pattern**
   - Create thin wrappers if needed
   - Don't modify core browser-use logic
   - Keep modifications isolated

3. **Dependency Management**
   - Identify shared dependencies (cdp_use, pydantic, etc.)
   - Ensure version compatibility
   - Add to requirements.txt

---

## 📦 **DEPENDENCIES**

### **Core Dependencies** (from browser-use)
- `cdp_use` - Chrome DevTools Protocol client
- `pydantic` - Data validation
- `httpx` - HTTP client
- `bubus` - Event bus (if used)

### **LangGraph Dependencies**
- `langchain` - Core LangChain
- `langgraph` - LangGraph workflow
- `langchain-openai` (or other LLM providers)

### **Additional Dependencies**
- `asyncio` - Async support
- `logging` - Logging

---

## ✅ **SUCCESS CRITERIA**

### **Phase 1-2** (Foundation)
- ✅ Browser session initializes
- ✅ LangGraph workflow compiles
- ✅ DOM can be serialized

### **Phase 3-4** (Core Functionality)
- ✅ Actions can be executed
- ✅ LLM generates actions from browser state
- ✅ State flows correctly between nodes

### **Phase 5-6** (Complete Workflow)
- ✅ Verification logic works
- ✅ Reports are generated
- ✅ Multi-step tasks complete successfully

### **Phase 7** (Production Ready)
- ✅ Error handling robust
- ✅ Performance acceptable
- ✅ Documentation complete

---

## 🎯 **NEXT STEPS**

1. **Start with Phase 1**: Set up project structure and LangGraph workflow
2. **Copy browser-use components**: Begin with BrowserSession
3. **Test incrementally**: After each phase, test integration
4. **Iterate**: Refine based on testing results

---

## 📝 **NOTES**

- **Browser-Use License**: Ensure browser-use license allows code reuse
- **Dependencies**: Keep browser-use dependencies compatible
- **Testing**: Test each component integration before moving to next phase
- **Documentation**: Document any modifications made to browser-use code

---

**Estimated Total Duration**: 21-28 days (3-4 weeks)

**Risk Mitigation**:
- Start with smallest integration (browser session)
- Test each phase before proceeding
- Keep browser-use code as-is, create adapters if needed
- Have fallback plan if integration issues arise

