"""
LangGraph Nodes for QA Automation Workflow

HYBRID Architecture (Computer-Use + Enhanced Features):
- init: Initialize browser session and create todo.md (LLM-driven, structured)
- plan: Decompose complex tasks into sequential goals (LLM-driven)
- think: Full computer-use THINK - sees DOM, generates actions directly
- act: Pure executor - executes actions, returns fresh state
- report: Generate final report
- verify: (Legacy) Kept for backward compatibility, not used in main workflow

THINK Node (Computer-Use Pattern):
  - Input: Full browser state with DOM tree + todo.md + history
  - Uses: AgentMessagePrompt (like browser-use main branch)
  - Sees: Complete accessibility tree, form values, interactive elements
  - Generates: actions directly (list of normalized tool calls)
  - Updates: todo.md with completed steps (NEW enhancement)
  - Output: actions for ACT to execute

ACT Node (Pure Executor):
  - Input: actions from THINK
  - Executes: Actions via Tools.act()
  - Waits: Adaptive DOM stability detection (NEW enhancement)
  - Returns: Fresh browser state, action results
  - NO LLM CALLS: Just execution

Key Design Principles:
  - Full computer-use: THINK sees complete page state like human QA tester
  - Single LLM call: THINK generates actions directly (efficient)
  - Fresh DOM always: ACT returns fresh state for next THINK cycle
  - Smart updates: Auto-updates todo.md progress (NEW)
  - Adaptive waiting: Waits for actual DOM changes (NEW)
  - Dynamic & robust: Works on any website, any language
"""
from .init import init_node
from .plan import plan_node
from .think import think_node
from .act import act_node  # Simple executor, no wrapper needed
from .verify import verify_node
from .report import report_node

__all__ = [
    "init_node",
    "plan_node",
    "think_node",
    "act_node",
    "verify_node",
    "report_node",
]

