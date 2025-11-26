"""
QA Agent State Definition - LangGraph v1 Compatible

Uses TypedDict with Annotated reducers for state management following LangGraph v1 best practices.
No hardcoded values - all configurable via settings or state initialization.
"""
from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Annotated
import operator

from qa_agent.filesystem.file_system import FileSystemState
from qa_agent.config import settings


class QAAgentState(TypedDict):
    """
    QA Agent State Schema - LangGraph v1 TypedDict Pattern
    
    Fields with Annotated use reducers for automatic accumulation.
    Fields without Annotated are replaced each step.
    
    Reference: https://docs.langchain.com/oss/python/langgraph/
    """
    
    # ========== Core Task Fields ==========
    task: str  # Original user task - never changes
    start_url: Optional[str]  # Optional initial URL
    
    # ========== Browser Session ==========
    browser_session_id: Optional[str]  # Browser session identifier
    screenshot_service: Optional[Any]  # Screenshot service for judge/GIF (not serialized)
    
    # ========== Step Tracking ==========
    step_count: int  # Current step number (incremented each step)
    max_steps: int  # Maximum steps allowed (from config, not hardcoded)
    
    # ========== Current Page State ==========
    current_url: Optional[str]  # Current page URL
    previous_url: Optional[str]  # Previous URL for change detection
    current_title: Optional[str]  # Current page title
    previous_element_count: Optional[int]  # Previous element count for change detection
    previous_element_ids: Optional[List[int]]  # Phase 1 & 2: Previous element IDs for adaptive detection
    action_context: Optional[Dict[str, Any]]  # Phase 1: Action → element relationship context
    new_element_ids: Optional[List[int]]  # Phase 1: New elements that appeared after last action
    
    # ========== Tab Management ==========
    tab_count: int  # Number of open tabs
    previous_tabs: List[str]  # List of tab IDs for comparison
    new_tab_id: Optional[str]  # New tab ID if one was opened
    new_tab_url: Optional[str]  # New tab URL if one was opened
    just_switched_tab: bool  # Flag indicating tab switch occurred
    
    # ========== Task Progression Tracking (LLM-Driven) ==========
    # NO hardcoded goals - LLM manages via todo.md
    # These fields kept for backward compatibility but should be phased out
    goals: List[Dict[str, Any]]  # High-level goals (optional, LLM-driven via todo.md)
    completed_goals: Annotated[List[str], operator.add]  # Accumulated completed goal IDs
    current_goal_index: int  # Current goal index
    current_goal: Optional[str]  # Current goal description
    
    # ========== FileSystem State (CRITICAL for todo.md persistence) ==========
    file_system_state: Optional[FileSystemState]  # Persisted FileSystem state
    
    # ========== Action Planning & Execution ==========
    # Note: planned_actions are ActionModel objects from LLM, but stored as Any for state flexibility
    # think.py returns list[ActionModel], act.py receives them directly
    planned_actions: List[Any]  # Actions planned by think node (ActionModel objects)
    executed_actions: List[Dict[str, Any]]  # Actions executed by act node (as dicts for history)
    action_results: List[Dict[str, Any]]  # Results from executed actions
    
    # ========== History (Accumulated) ==========
    # LangGraph v1 pattern: Use Annotated with operator.add for accumulation
    history: Annotated[List[Dict[str, Any]], operator.add]  # Accumulated execution history
    
    # ========== Browser State Cache ==========
    browser_state_summary: Optional[Dict[str, Any]]  # Cached browser state summary
    dom_selector_map: Optional[Dict[int, Any]]  # Cached DOM selector map
    fresh_state_available: bool  # Flag indicating fresh state is available
    page_changed: bool  # Flag indicating page changed
    
    # ========== Tab Switch Context ==========
    tab_switch_url: Optional[str]  # URL after tab switch
    tab_switch_title: Optional[str]  # Title after tab switch
    
    # ========== Verification ==========
    verification_status: Optional[str]  # "pass", "fail", or None
    verification_results: List[Dict[str, Any]]  # Detailed verification results
    
    # ========== Error Handling & Loop Prevention ==========
    error: Optional[str]  # Error message if any
    consecutive_failures: int  # Consecutive failure count (browser pattern)
    max_failures: int  # Max failures before stopping (from config, not hardcoded)
    final_response_after_failure: bool  # Allow final attempt after max failures
    action_repetition_count: int  # Count of repeated actions
    
    # ========== Completion ==========
    completed: bool  # Task completion flag
    report: Optional[Dict[str, Any]]  # Final report

    # ========== Judge & GIF Settings ==========
    use_judge: bool  # Enable LLM judge evaluation (default: True)
    generate_gif: bool | str  # Enable GIF generation or specify output path (default: False)

    # ========== Read State (Extract Results) ==========
    read_state_description: Optional[str]  # Extract() results (one-time display)
    read_state_images: Optional[List[Dict[str, Any]]]  # Images from read_file

    # ========== Hierarchical THINK → ACT Flow ==========
    think_output: Optional[str]  # Strategic decision from THINK node (e.g., "Click login button")
    think_reasoning: Optional[str]  # THINK's reasoning (optional, for debugging)
    act_feedback: Optional[Dict[str, Any]]  # ACT's result: success, action_taken, result_summary, error
    act_error_context: Optional[str]  # Human-readable error message for THINK's retry decision
    last_act_result_success: bool  # Quick flag: did last ACT execution succeed?
    think_retries: int  # How many times current step was rethought (for retry loop prevention)


def create_initial_state(
    task: str,
    start_url: Optional[str] = None,
    max_steps: Optional[int] = None,
    max_failures: Optional[int] = None,
    use_judge: bool = True,
    generate_gif: bool | str = False,
) -> QAAgentState:
    """
    Create initial QA agent state

    Args:
        task: User task description
        start_url: Optional initial URL to navigate to
        max_steps: Maximum steps allowed (defaults to settings.max_steps)
        max_failures: Maximum consecutive failures (defaults to settings.max_failures)
        use_judge: Enable LLM judge evaluation (default: True)
        generate_gif: Enable GIF generation or specify output path (default: False)

    Returns:
        Initial QAAgentState dictionary

    Note:
        - No hardcoded values - all come from parameters or settings
        - LangGraph reducers handle accumulation automatically
        - FileSystem state initialized as None (created in think_node)
        - Judge and GIF features are opt-in/opt-out via parameters
    """
    # Use settings defaults if not provided (no hardcoded values)
    max_steps = max_steps if max_steps is not None else settings.max_steps
    max_failures = max_failures if max_failures is not None else getattr(settings, 'max_failures', 3)
    
    return {
        # Core task
        "task": task,
        "start_url": start_url,
        
        # Browser session
        "browser_session_id": None,
        "screenshot_service": None,  # Initialized in init_node
        
        # Step tracking
        "step_count": 0,
        "max_steps": max_steps,  # From config, not hardcoded
        
        # Current page state
        "current_url": None,
        "previous_url": None,
        "current_title": None,
        "previous_element_count": None,
        "previous_element_ids": None,  # Phase 1 & 2: Track element IDs for adaptive detection
        "action_context": None,  # Phase 1: Action → element relationship
        "new_element_ids": None,  # Phase 1: New elements after actions
        
        # Tab management
        "tab_count": 1,  # Start with 1 tab
        "previous_tabs": [],
        "new_tab_id": None,
        "new_tab_url": None,
        "just_switched_tab": False,
        
        # Task progression (LLM-driven via todo.md)
        "goals": [],  # Empty - LLM creates todo.md
        "completed_goals": [],  # Reducer will accumulate
        "current_goal_index": 0,
        "current_goal": None,
        
        # FileSystem state (CRITICAL for todo.md persistence)
        "file_system_state": None,  # Created in think_node, persisted across steps
        
        # Action planning & execution
        "planned_actions": [],
        "executed_actions": [],
        "action_results": [],
        
        # History (accumulated via reducer)
        "history": [],  # Reducer will accumulate
        
        # Browser state cache
        "browser_state_summary": None,
        "dom_selector_map": None,
        "fresh_state_available": False,
        "page_changed": False,
        
        # Tab switch context
        "tab_switch_url": None,
        "tab_switch_title": None,
        
        # Verification
        "verification_status": None,
        "verification_results": [],
        
        # Error handling & loop prevention
        "error": None,
        "consecutive_failures": 0,
        "max_failures": max_failures,  # From config, not hardcoded
        "final_response_after_failure": True,  # browser default
        "action_repetition_count": 0,
        
        # Completion
        "completed": False,
        "report": None,

        # Judge & GIF
        "use_judge": use_judge,  # Enable judge evaluation
        "generate_gif": generate_gif,  # Enable GIF or specify path

        # Read state
        "read_state_description": None,
        "read_state_images": None,

        # Hierarchical THINK → ACT Flow
        "think_output": None,  # Strategic decision from THINK
        "think_reasoning": None,  # THINK's reasoning (debug)
        "act_feedback": None,  # ACT's execution result
        "act_error_context": None,  # Error message for THINK's retry
        "last_act_result_success": False,  # Did last ACT succeed?
        "think_retries": 0,  # Retry counter for current step
    }

