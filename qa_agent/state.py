"""
LangGraph State Model for QA Automation Agent

Defines the state schema that flows through the LangGraph workflow.
Following LangGraph v1.0 best practices:
- TypedDict for state definition
- Optional fields for incremental updates
- Lists are replaced (not appended) - nodes return new lists
"""
from typing import TypedDict, List, Optional, Any, Dict


class QAAgentState(TypedDict):
    """
    State for QA Automation Agent
    
    This state is passed between nodes in the LangGraph workflow.
    All fields are optional except where noted to allow incremental updates.
    """
    
    # Task & Goal
    task: str  # Original user task/instruction
    current_goal: Optional[str]  # Current sub-goal being worked on
    start_url: Optional[str]  # Initial URL to navigate to

    # Browser State (Serializable)
    browser_session_id: Optional[str]  # Session ID for lookup in registry (serializable)
    current_url: Optional[str]  # Current page URL
    browser_state_summary: Optional[str]  # Serialized DOM state for LLM
    dom_snapshot: Optional[Dict[str, Any]]  # Full DOM snapshot data
    
    # Actions & Results
    planned_actions: List[dict]  # Actions planned by Think node
    executed_actions: List[dict]  # Actions executed in Act node
    action_results: List[dict]  # Results from action execution
    
    # Verification
    verification_status: Optional[str]  # "pass" | "fail" | "pending" | None
    verification_results: List[dict]  # Detailed verification results
    
    # Workflow Control
    step_count: int  # Current step number
    max_steps: int  # Maximum steps allowed
    completed: bool  # Whether task is completed
    error: Optional[str]  # Error message if any
    
    # History & Context
    history: List[dict]  # Step-by-step execution history
    messages: List[dict]  # LLM messages (reserved for future LangChain message history compatibility)
    
    # Report
    report: Optional[dict]  # Final test report


def create_initial_state(
    task: str,
    max_steps: int = 50,
    start_url: Optional[str] = None,
    browser_session_id: Optional[str] = None,
    **kwargs
) -> QAAgentState:
    """
    Create initial state for QA agent workflow

    Args:
        task: User task/instruction
        max_steps: Maximum steps allowed
        start_url: Initial URL to navigate to
        browser_session_id: Browser session ID (if session already created)
        **kwargs: Additional state fields

    Returns:
        Initial QAAgentState
    """
    return QAAgentState(
        task=task,
        current_goal=None,
        start_url=start_url,
        browser_session_id=browser_session_id,
        current_url=None,
        browser_state_summary=None,
        dom_snapshot=None,
        planned_actions=[],
        executed_actions=[],
        action_results=[],
        verification_status=None,
        verification_results=[],
        step_count=0,
        max_steps=max_steps,
        completed=False,
        error=None,
        history=[],
        messages=[],
        report=None,
        **kwargs
    )

