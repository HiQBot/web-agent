"""
LangGraph Nodes for QA Automation Workflow

Hierarchical Architecture (Phase 3 - THINK → ACT):
- init: Initialize browser session and create todo.md
- plan: Decompose complex tasks into sequential goals (LLM-driven)
- think: Minimal THINK node - strategic decision only + todo.md updates (~300 tokens)
- act: ACT wrapper with page validation - executes THINK output with fresh DOM (~1500 tokens)
- report: Generate final report
- verify: (Legacy) Kept for backward compatibility, not used in main workflow

THINK Characteristics:
  - Input: task + todo.md + previous ACT feedback
  - Output: think_output (strategic decision string, NOT actions)
  - Responsibility: What should we do next?
  - Page Mismatch Handling: Detects and suggests recovery if ACT reports page validation failure
  - Retry Logic: Tracks think_retries counter (max 3) for recovery attempts

ACT Wrapper Characteristics:
  - Input: think_output from THINK + fresh browser state
  - Process:
    1. Fetches fresh browser state with cached=False (always current DOM)
    2. Validates page context using PageContextAnalyzer (semantic, no hardcoding)
    3. If page invalid → returns error with recovery suggestion
    4. If page valid → generates specific actions from THINK output + fresh DOM
    5. Executes actions via original act_node logic
    6. Returns structured act_feedback with page_validation info
  - Output: executed_actions, action_results, act_feedback (with page validation info)
  - Responsibility: How do we execute the THINK decision?

Feedback Loop:
  - act_feedback → THINK (includes page_validation info)
  - page_validation_info → used by THINK to detect mismatches
  - If mismatch detected → THINK generates recovery navigation action
  - If valid → THINK calls LLM for next strategic decision

Key Design Principles:
  - Separation of concerns: THINK is strategic (~300 tokens), ACT is tactical (~1500 tokens)
  - Fresh DOM always: ACT fetches cached=False every time for current element indices
  - Dynamic detection: PageContextAnalyzer uses semantic analysis, not hardcoded keywords
  - Industry-agnostic: Works on any website structure, any language
  - Intelligent recovery: Detects wrong page + suggests navigation without hardcoding
"""
from .init import init_node
from .plan import plan_node
from .think import think_node
from .act_wrapper import act_wrapper_node as act_node  # ACT wrapper bridges THINK→ACT hierarchical flow
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

