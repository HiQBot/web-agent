"""
LangGraph Workflow Definition

Creates the QA automation workflow with nodes and conditional edges.
"""
import logging
from typing import Literal, Any
from langgraph.graph import StateGraph, START, END
from qa_agent.state import QAAgentState
from qa_agent.nodes import init_node, think_node, act_node, verify_node, report_node
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
            # Count consecutive failures from most recent steps
            history = state.get("history", [])
            consecutive_failures = 0

            # Iterate backwards through history
            for entry in reversed(history):
                if not isinstance(entry, dict):
                    continue
                if entry.get("node") == "verify":
                    if entry.get("verification_status") == "fail":
                        consecutive_failures += 1
                    else:
                        # Stop at first non-failure
                        break

            if consecutive_failures < settings.max_retries:
                logger.info(f"Verification failed, retrying ({consecutive_failures}/{settings.max_retries})")
                return "retry"
            else:
                logger.warning(f"Max consecutive retries reached ({consecutive_failures}/{settings.max_retries})")
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
    workflow.add_node("init", init_node)
    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("report", report_node)

    # Set entry point using START constant (LangGraph v1.0 pattern)
    # START -> INIT -> THINK (INIT creates browser session)
    workflow.add_edge(START, "init")
    workflow.add_edge("init", "think")
    
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
    
    # Add graph visualization capability (LangGraph pattern)
    try:
        # Generate graph visualization
        graph = compiled_workflow.get_graph()
        logger.info("Graph visualization available - use workflow.get_graph().draw_mermaid_png() to visualize")
    except Exception as e:
        logger.debug(f"Could not get graph for visualization: {e}")
    
    return compiled_workflow


def visualize_workflow(workflow=None, output_file: str = "workflow_graph.png"):
    """
    Visualize the QA workflow graph.
    
    Args:
        workflow: Compiled workflow (if None, creates new one)
        output_file: Path to save PNG image
        
    Returns:
        Graph visualization (PNG bytes or file path)
    """
    if workflow is None:
        workflow = create_qa_workflow()
    
    try:
        graph = workflow.get_graph()
        
        # Generate Mermaid diagram
        mermaid_diagram = graph.draw_mermaid()
        logger.info(f"Generated Mermaid diagram ({len(mermaid_diagram)} chars)")
        
        # Generate PNG (requires graphviz or mermaid.ink)
        try:
            png_bytes = graph.draw_mermaid_png()
            if output_file:
                with open(output_file, "wb") as f:
                    f.write(png_bytes)
                logger.info(f"✅ Workflow graph saved to: {output_file}")
            return png_bytes
        except Exception as e:
            logger.warning(f"Could not generate PNG (install graphviz or use mermaid.ink): {e}")
            logger.info("Mermaid diagram:")
            print(mermaid_diagram)
            return mermaid_diagram
            
    except Exception as e:
        logger.error(f"Could not visualize workflow: {e}")
        return None

