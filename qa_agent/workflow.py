"""
LangGraph Workflow Definition

Creates the QA automation workflow with nodes and conditional edges.
"""
import logging
from typing import Literal, Any
from langgraph.graph import StateGraph, START, END
from qa_agent.state import QAAgentState
from qa_agent.nodes import init_node, plan_node, think_node, act_node, verify_node, report_node
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

        # Check max consecutive failures (browser pattern: service.py:1755-1761)
        # If final_response_after_failure is True, allow one final attempt after max_failures
        consecutive_failures = state.get("consecutive_failures", 0)
        max_failures = state.get("max_failures", 3)
        final_response_after_failure = state.get("final_response_after_failure", True)

        if consecutive_failures >= max_failures + int(final_response_after_failure):
            logger.error(f"❌ Stopping due to {max_failures} consecutive failures")
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


def should_continue_after_think(state: QAAgentState) -> Literal["continue", "done", "replan"]:
    """
    Router function to determine next node after think

    Args:
        state: Current QA agent state

    Returns:
        Next node to execute: "continue", "replan", or "done"
    """
    try:
        if state.get("completed"):
            return "done"

        if state.get("error"):
            return "done"

        # Check max consecutive failures (browser pattern)
        consecutive_failures = state.get("consecutive_failures", 0)
        max_failures = state.get("max_failures", 3)
        final_response_after_failure = state.get("final_response_after_failure", True)

        if consecutive_failures >= max_failures + int(final_response_after_failure):
            logger.error(f"❌ Stopping in think router due to {max_failures} consecutive failures")
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

        # Check if this is a goal transition (empty actions but more goals to do)
        goals = state.get("goals", [])
        current_goal_index = state.get("current_goal_index", 0)
        if goals and current_goal_index < len(goals):
            # Goal transition - loop back to think for next goal
            logger.info("Goal transition detected, looping back to THINK for next goal")
            return "replan"

        # No actions planned and no more goals, go to report
        return "done"
    except Exception as e:
        logger.error(f"Error in think router function: {e}")
        return "done"  # Fail safe: go to report on error


def create_qa_workflow() -> Any:
    """
    Create the QA automation workflow

    Architecture:
    - START → INIT → PLAN → THINK ⟷ ACT → THINK (optimized loop)
    - VERIFY only used for tab switching, not in main loop
    - Goals tracked in state, LLM adapts task context based on progress

    Returns:
        Compiled LangGraph workflow
    """
    logger.info("Creating QA automation workflow")

    # Create workflow graph
    workflow = StateGraph(QAAgentState)

    # Add nodes
    workflow.add_node("init", init_node)
    workflow.add_node("plan", plan_node)  # NEW: LLM-driven task decomposition
    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("verify", verify_node)  # Kept for tab switching
    workflow.add_node("report", report_node)

    # Set entry point using START constant (LangGraph v1.0 pattern)
    # START → INIT → PLAN → THINK (INIT creates browser, PLAN decomposes task)
    workflow.add_edge(START, "init")
    workflow.add_edge("init", "plan")  # NEW: Plan after init
    workflow.add_edge("plan", "think")  # NEW: Think after planning

    # Add conditional edges from think
    workflow.add_conditional_edges(
        "think",
        should_continue_after_think,
        {
            "continue": "act",
            "replan": "think",  # NEW: Loop back to think on goal transitions
            "done": "report",
        }
    )

    # CRITICAL OPTIMIZATION: ACT → THINK directly (bypassing VERIFY)
    # ACT already fetches fresh state and detects tab switches
    # VERIFY is only invoked when needed (see conditional edge below)
    workflow.add_edge("act", "think")  # CHANGED: Direct ACT→THINK loop

    # NOTE: We keep verify node for special cases (tab switching)
    # But it's not in the main loop anymore - this solves the efficiency issue
    # If needed, we can add conditional logic in ACT to route to VERIFY for tab switches

    # Add conditional edges from verify (for special cases if needed)
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
    logger.info("Architecture: INIT → PLAN → THINK ⟷ ACT (optimized loop)")

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

