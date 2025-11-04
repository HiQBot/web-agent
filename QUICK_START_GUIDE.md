# Quick Start Guide - Browser-Use to LangGraph Integration

## 📋 File Mapping Reference

### **Phase 1: Browser Session**
| Browser-Use Source | Destination | Modification Level |
|-------------------|-------------|-------------------|
| `browser_use/browser/session.py` | `qa_agent/browser/session.py` | Minimal (ensure init works) |
| `browser_use/browser/profile.py` | `qa_agent/browser/profile.py` | None (copy as-is) |
| `browser_use/browser/views.py` | `qa_agent/browser/views.py` | None (copy as-is) |
| `browser_use/browser/events.py` | `qa_agent/browser/events.py` | Minimal (keep action events) |

### **Phase 2: DOM Service**
| Browser-Use Source | Destination | Modification Level |
|-------------------|-------------|-------------------|
| `browser_use/dom/service.py` | `qa_agent/dom/service.py` | Minimal (test with session) |
| `browser_use/dom/views.py` | `qa_agent/dom/views.py` | None (copy as-is) |
| `browser_use/dom/enhanced_snapshot.py` | `qa_agent/dom/enhanced_snapshot.py` | None (copy as-is) |
| `browser_use/dom/serializer/serializer.py` | `qa_agent/dom/serializer/serializer.py` | None (copy as-is) |
| `browser_use/dom/serializer/clickable_elements.py` | `qa_agent/dom/serializer/clickable_elements.py` | None (copy as-is) |
| `browser_use/dom/serializer/paint_order.py` | `qa_agent/dom/serializer/paint_order.py` | None (copy as-is) |

### **Phase 3: Tools**
| Browser-Use Source | Destination | Modification Level |
|-------------------|-------------|-------------------|
| `browser_use/tools/service.py` | `qa_agent/tools/service.py` | Moderate (ensure BrowserSession integration) |
| `browser_use/tools/views.py` | `qa_agent/tools/views.py` | None (copy as-is) |
| `browser_use/tools/utils.py` | `qa_agent/tools/utils.py` | None (copy as-is) |
| `browser_use/tools/registry/service.py` | `qa_agent/tools/registry/service.py` | Minimal (test filtering) |
| `browser_use/tools/registry/views.py` | `qa_agent/tools/registry/views.py` | None (copy as-is) |

### **Phase 4: LLM & Prompts**
| Browser-Use Source | Destination | Modification Level |
|-------------------|-------------|-------------------|
| `browser_use/llm/base.py` | `qa_agent/llm/base.py` | None (copy as-is) |
| `browser_use/llm/openai/` | `qa_agent/llm/openai/` | None (copy as-is) |
| `browser_use/llm/anthropic/` | `qa_agent/llm/anthropic/` | None (copy as-is) |
| `browser_use/llm/google/` | `qa_agent/llm/google/` | None (copy as-is) |
| `browser_use/agent/system_prompt.md` | `qa_agent/prompts/system_prompt.md` | Moderate (adapt for QA) |

---

## 🚀 Starter Code Structure

### **1. State Model** (`qa_agent/state.py`)

```python
from typing import TypedDict, List, Optional, Any
from langgraph.graph.message import add_messages

class QAAgentState(TypedDict):
    """State for QA Automation Agent"""
    # Task & Goal
    task: str  # Original user task
    current_goal: Optional[str]  # Current sub-goal
    
    # Browser State
    browser_session: Optional[Any]  # BrowserSession instance
    current_url: Optional[str]
    browser_state_summary: Optional[str]  # Serialized DOM state
    
    # Actions & Results
    planned_actions: List[dict]  # Actions from Think node
    executed_actions: List[dict]  # Actions executed in Act node
    action_results: List[dict]  # Results from action execution
    
    # Verification
    verification_status: Optional[str]  # "pass" | "fail" | "pending"
    verification_results: List[dict]
    
    # Workflow Control
    step_count: int
    max_steps: int
    completed: bool
    error: Optional[str]
    
    # History
    history: List[dict]  # Step-by-step history
```

### **2. Basic Workflow** (`qa_agent/workflow.py`)

```python
from langgraph.graph import StateGraph, END
from qa_agent.state import QAAgentState
from qa_agent.nodes.think import think_node
from qa_agent.nodes.act import act_node
from qa_agent.nodes.verify import verify_node
from qa_agent.nodes.report import report_node

def should_continue(state: QAAgentState) -> str:
    """Router function to determine next node"""
    if state.get("completed"):
        return "done"
    if state.get("error"):
        return "done"
    if state.get("step_count", 0) >= state.get("max_steps", 50):
        return "done"
    if state.get("verification_status") == "pass":
        return "continue"
    if state.get("verification_status") == "fail":
        # Check retry count
        return "retry" if state.get("step_count", 0) < 3 else "done"
    return "continue"

def create_qa_workflow():
    """Create the QA automation workflow"""
    workflow = StateGraph(QAAgentState)
    
    # Add nodes
    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("report", report_node)
    
    # Set entry point
    workflow.set_entry_point("think")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "think",
        should_continue,
        {
            "continue": "act",
            "done": "report"
        }
    )
    
    workflow.add_edge("act", "verify")
    
    workflow.add_conditional_edges(
        "verify",
        should_continue,
        {
            "continue": "think",  # Loop back to think
            "retry": "think",     # Retry from think
            "done": "report"
        }
    )
    
    workflow.add_edge("report", END)
    
    return workflow.compile()
```

### **3. Think Node** (`qa_agent/nodes/think.py`)

```python
from qa_agent.state import QAAgentState
from qa_agent.utils.browser_state import get_browser_state
from qa_agent.prompts.prompt_builder import build_think_prompt
from qa_agent.llm.openai.chat import ChatOpenAI  # or your LLM choice

async def think_node(state: QAAgentState) -> QAAgentState:
    """Think node: Analyze browser state and plan actions"""
    
    # Get browser state
    browser_session = state.get("browser_session")
    if browser_session:
        browser_state = await get_browser_state(browser_session)
        state["browser_state_summary"] = browser_state
    
    # Build prompt
    prompt = build_think_prompt(
        task=state["task"],
        current_goal=state.get("current_goal"),
        browser_state=state.get("browser_state_summary"),
        history=state.get("history", [])
    )
    
    # Call LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
    response = await llm.ainvoke(prompt)
    
    # Parse response (extract thinking + actions)
    # TODO: Parse LLM response into actions
    planned_actions = []  # Parse from response
    
    # Update state
    state["planned_actions"] = planned_actions
    state["step_count"] = state.get("step_count", 0) + 1
    
    return state
```

### **4. Act Node** (`qa_agent/nodes/act.py`)

```python
from qa_agent.state import QAAgentState
from qa_agent.tools.service import Tools

async def act_node(state: QAAgentState) -> QAAgentState:
    """Act node: Execute planned actions"""
    
    browser_session = state.get("browser_session")
    if not browser_session:
        state["error"] = "No browser session available"
        return state
    
    # Initialize Tools
    tools = Tools()
    # Note: Tools needs BrowserSession - may need to pass via context
    
    # Execute actions
    planned_actions = state.get("planned_actions", [])
    executed_actions = []
    action_results = []
    
    for action in planned_actions:
        try:
            # Execute action via Tools.act()
            result = await tools.act(
                action=action,
                browser_session=browser_session
            )
            executed_actions.append(action)
            action_results.append(result)
        except Exception as e:
            action_results.append({"error": str(e)})
    
    # Update state
    state["executed_actions"] = executed_actions
    state["action_results"] = action_results
    
    return state
```

### **5. Verify Node** (`qa_agent/nodes/verify.py`)

```python
from qa_agent.state import QAAgentState
from qa_agent.verifiers.text_verifier import verify_text
from qa_agent.verifiers.element_verifier import verify_element
from qa_agent.verifiers.url_verifier import verify_url

async def verify_node(state: QAAgentState) -> QAAgentState:
    """Verify node: Check if actions succeeded"""
    
    browser_session = state.get("browser_session")
    action_results = state.get("action_results", [])
    
    verification_results = []
    
    # Verify each action result
    for result in action_results:
        if "error" in result:
            verification_results.append({
                "status": "fail",
                "reason": result["error"]
            })
        else:
            # Perform verification based on action type
            # Example: verify text appeared, element visible, URL changed, etc.
            verification_results.append({
                "status": "pass",
                "details": "Action completed successfully"
            })
    
    # Determine overall status
    all_passed = all(r.get("status") == "pass" for r in verification_results)
    state["verification_status"] = "pass" if all_passed else "fail"
    state["verification_results"] = verification_results
    
    return state
```

### **6. Report Node** (`qa_agent/nodes/report.py`)

```python
from qa_agent.state import QAAgentState

async def report_node(state: QAAgentState) -> QAAgentState:
    """Report node: Generate final test report"""
    
    # Collect all results
    report = {
        "task": state["task"],
        "completed": state.get("completed", False),
        "steps": state.get("step_count", 0),
        "history": state.get("history", []),
        "final_status": state.get("verification_status"),
        "errors": state.get("error")
    }
    
    # Generate report (JSON, HTML, etc.)
    # TODO: Format report
    
    state["report"] = report
    state["completed"] = True
    
    return state
```

---

## 🔧 Integration Checklist

### **Phase 1 Setup**
- [ ] Create project structure
- [ ] Copy browser-use browser files
- [ ] Create LangGraph state model
- [ ] Create basic workflow
- [ ] Test browser session initialization

### **Phase 2 DOM**
- [ ] Copy DOM service files
- [ ] Create browser state extractor
- [ ] Test DOM serialization
- [ ] Update Think node with browser state

### **Phase 3 Tools**
- [ ] Copy tools files
- [ ] Integrate Tools with BrowserSession
- [ ] Update Act node with tool execution
- [ ] Test action execution

### **Phase 4 LLM**
- [ ] Copy LLM adapters
- [ ] Adapt system prompt
- [ ] Integrate LLM in Think node
- [ ] Test LLM action generation

### **Phase 5 Verification**
- [ ] Create verification logic
- [ ] Update Verify node
- [ ] Test verification flow
- [ ] Add conditional routing

### **Phase 6 Reporting**
- [ ] Create report generation
- [ ] Update Report node
- [ ] Test report output

### **Phase 7 Testing**
- [ ] End-to-end testing
- [ ] Error handling
- [ ] Performance optimization
- [ ] Documentation

---

## 📝 Quick Copy Commands

```bash
# Phase 1: Browser Session
cp -r browser-use-main/browser_use/browser qa_agent/

# Phase 2: DOM Service
cp -r browser-use-main/browser_use/dom qa_agent/

# Phase 3: Tools
cp -r browser-use-main/browser_use/tools qa_agent/

# Phase 4: LLM
cp -r browser-use-main/browser_use/llm qa_agent/

# Phase 5: Prompts
mkdir -p qa_agent/prompts
cp browser-use-main/browser_use/agent/system_prompt.md qa_agent/prompts/
```

---

## 🎯 First Steps

1. **Set up project structure**
   ```bash
   mkdir -p qa_agent/{nodes,browser,dom,tools,llm,prompts,verifiers,utils}
   ```

2. **Copy browser-use files** (start with browser session)
   ```bash
   cp browser-use-main/browser_use/browser/*.py qa_agent/browser/
   ```

3. **Create state model** (`qa_agent/state.py`)

4. **Create basic workflow** (`qa_agent/workflow.py`)

5. **Test initialization**
   ```python
   from qa_agent.workflow import create_qa_workflow
   workflow = create_qa_workflow()
   ```

---

## ⚠️ Important Notes

1. **Dependencies**: Ensure all browser-use dependencies are installed
2. **Imports**: Update import paths after copying files
3. **Testing**: Test each component after integration
4. **Modifications**: Keep modifications minimal, use adapters if needed

