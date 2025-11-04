"""
LangGraph Workflow Definition

Creates the QA automation workflow with nodes and conditional edges.
"""
import logging
from typing import Literal, Any
from langgraph.graph import StateGraph, START, END
from qa_agent.state import QAAgentState
from qa_agent.nodes import think_node, act_node, verify_node, report_node
from qa_agent.config import settings

logger = logging.getLogger(__name__)


def should_continue(state: QAAgentState) -> Literal["continue", "retry", "done"]:
    """
    Router function to determine next node after verify
    
    Args:
        state: Current QA agent state
        
    Returns:
        Next node to execute: "continue", "retry", or "done"
    """
    try:
        # Check if completed or error
        if state.get("completed"):
            logger.info("Workflow completed")
            return "done"
        
        if state.get("error"):
            logger.error(f"Workflow error: {state.get('error')}")
            return "done"
        
        # Check max steps (infinite loop prevention)
        step_count = state.get("step_count", 0)
        max_steps = state.get("max_steps", settings.max_steps)
        
        if step_count >= max_steps:
            logger.warning(f"Max steps reached: {step_count}/{max_steps}")
            return "done"
        
        # Check verification status
        verification_status = state.get("verification_status")
        
        if verification_status == "pass":
            logger.info("Verification passed, continuing")
            return "continue"
        
        if verification_status == "fail":
            # Check retry count
            history = state.get("history", [])
            retry_count = len([
                h for h in history
                if isinstance(h, dict) and h.get("node") == "verify" and h.get("verification_status") == "fail"
            ])
            
            if retry_count < settings.max_retries:
                logger.info(f"Verification failed, retrying ({retry_count}/{settings.max_retries})")
                return "retry"
            else:
                logger.warning("Max retries reached")
                return "done"
        
        # Default: continue
        return "continue"
    except Exception as e:
        logger.error(f"Error in router function: {e}")
        return "done"  # Fail safe: go to report on error


def should_continue_after_think(state: QAAgentState) -> Literal["continue", "done"]:
    """
    Router function to determine next node after think
    
    Args:
        state: Current QA agent state
        
    Returns:
        Next node to execute: "continue" or "done"
    """
    try:
        if state.get("completed"):
            return "done"
        
        if state.get("error"):
            return "done"
        
        # Infinite loop prevention
        step_count = state.get("step_count", 0)
        max_steps = state.get("max_steps", settings.max_steps)
        
        if step_count >= max_steps:
            logger.warning(f"Max steps reached in think router: {step_count}/{max_steps}")
            return "done"
        
        # If we have planned actions, continue to act
        planned_actions = state.get("planned_actions", [])
        if planned_actions:
            return "continue"
        
        # No actions planned, go to report
        return "done"
    except Exception as e:
        logger.error(f"Error in think router function: {e}")
        return "done"  # Fail safe: go to report on error


def create_qa_workflow() -> Any:
    """
    Create the QA automation workflow
    
    Returns:
        Compiled LangGraph workflow
    """
    logger.info("Creating QA automation workflow")
    
    # Create workflow graph
    workflow = StateGraph(QAAgentState)
    
    # Add nodes
    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("report", report_node)
    
    # Set entry point using START constant (LangGraph v1.0 pattern)
    workflow.add_edge(START, "think")
    
    # Add conditional edges from think
    workflow.add_conditional_edges(
        "think",
        should_continue_after_think,
        {
            "continue": "act",
            "done": "report",
        }
    )
    
    # Add edge from act to verify
    workflow.add_edge("act", "verify")
    
    # Add conditional edges from verify
    workflow.add_conditional_edges(
        "verify",
        should_continue,
        {
            "continue": "think",  # Loop back to think
            "retry": "think",     # Retry from think
            "done": "report",      # Go to report
        }
    )
    
    # Add edge from report to end
    workflow.add_edge("report", END)
    
    # Compile workflow
    compiled_workflow = workflow.compile()
    
    logger.info("Workflow created successfully")
    
    return compiled_workflow

