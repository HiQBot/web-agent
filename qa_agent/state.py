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
    browser_state_summary: Optional[Any]  # Browser state summary (dict or BrowserStateSummary object)
    dom_snapshot: Optional[Dict[str, Any]]  # Full DOM snapshot data
    dom_selector_map: Optional[Dict[int, Any]]  # Cached selector map for element lookups
    
    # State Communication Flags (for Act → Think communication)
    fresh_state_available: bool  # True if Act node fetched fresh state after actions
    page_changed: bool  # True if page changed (navigation, tab switch, etc.)
    previous_url: Optional[str]  # Previous URL for change detection
    previous_element_count: Optional[int]  # Previous element count for change detection
    
    # Tab Management
    new_tab_id: Optional[str]  # New tab ID if tab was opened
    new_tab_url: Optional[str]  # New tab URL
    just_switched_tab: bool  # True if tab was just switched
    tab_switch_url: Optional[str]  # URL after tab switch
    tab_switch_title: Optional[str]  # Title after tab switch
    previous_tabs: List[str]  # List of previous tab IDs for comparison
    tab_count: int  # Current number of tabs
    
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
        dom_selector_map=None,
        fresh_state_available=False,
        page_changed=False,
        previous_url=None,
        previous_element_count=None,
        new_tab_id=None,
        new_tab_url=None,
        just_switched_tab=False,
        tab_switch_url=None,
        tab_switch_title=None,
        previous_tabs=[],
        tab_count=1,
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

