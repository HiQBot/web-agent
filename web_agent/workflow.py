"""
LangGraph Workflow Definition

Creates the QA automation workflow with nodes and conditional edges.
"""
import logging
from typing import Literal, Any
from langgraph.graph import StateGraph, START, END
from web_agent.state import QAAgentState
from web_agent.nodes import init_node, plan_node, think_node, act_node, report_node
from web_agent.config import settings

logger = logging.getLogger(__name__)


def should_continue_after_think(state: QAAgentState) -> Literal["continue", "done", "replan"]:
    """
    Router function to determine next node after think.

    Computer-Use Architecture:
    - THINK outputs: planned_actions (direct action list from full DOM analysis)
    - If planned_actions exist → continue to ACT for execution
    - If goal transition (no actions but more goals) → replan (loop to THINK)
    - If task completed or no more actions/goals → done (go to report)
    - Error handling with max failures

    Args:
        state: Current QA agent state

    Returns:
        Next node to execute: "continue", "replan", or "done"
    """
    try:
        # Check if task is completed
        if state.get("completed"):
            logger.info("✅ Task marked as completed in THINK node")
            return "done"

        if state.get("error"):
            logger.error(f"❌ THINK error: {state.get('error')}")
            return "done"

        # Check max failures
        consecutive_failures = state.get("consecutive_failures", 0)
        max_failures = state.get("max_failures", 3)
        final_response_after_failure = state.get("final_response_after_failure", True)

        if consecutive_failures >= max_failures + int(final_response_after_failure):
            logger.error(f"❌ Max consecutive failures reached ({consecutive_failures}/{max_failures})")
            return "done"

        # Check max steps (infinite loop prevention)
        step_count = state.get("step_count", 0)
        max_steps = state.get("max_steps", settings.max_steps)

        if step_count >= max_steps:
            logger.warning(f"⏸️  Max steps reached: {step_count}/{max_steps}")
            return "done"

        # Computer-use flow: Check if THINK generated planned actions
        planned_actions = state.get("planned_actions", [])
        if planned_actions:
            logger.info(f"📋 THINK generated {len(planned_actions)} planned actions → routing to ACT")
            return "continue"  # Go to ACT for execution

        # Check if this is a goal transition (empty actions but more goals to do)
        goals = state.get("goals", [])
        current_goal_index = state.get("current_goal_index", 0)
        if goals and current_goal_index < len(goals):
            # Goal transition - loop back to think for next goal
            logger.info("Goal transition detected, looping back to THINK for next goal")
            return "replan"

        # No actions planned and no more goals = done
        logger.warning("⚠️  No planned actions and no more goals")
        return "done"

    except Exception as e:
        logger.error(f"❌ Router error: {e}")
        return "done"


def create_qa_workflow() -> Any:
    """
    Create the QA automation workflow

    Architecture:
    - START → INIT → PLAN → THINK ⟷ ACT (optimized hierarchical loop)
    - THINK: Strategic planning + todo.md updates
    - ACT: Tactical execution + error detection
    - Verify node removed (functionality moved to ACT/THINK)

    Returns:
        Compiled LangGraph workflow
    """
    logger.info("Creating QA automation workflow")

    # Create workflow graph
    workflow = StateGraph(QAAgentState)

    # Add nodes
    workflow.add_node("init", init_node)
    workflow.add_node("plan", plan_node)  # LLM-driven task decomposition
    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
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

    # CRITICAL OPTIMIZATION: ACT → THINK directly (efficient single-node loop)
    # Architecture improvements:
    # - ACT: Focused execution (page validation + action generation + execution + error detection)
    # - THINK: Strategic planning + todo.md updates (reads executed_actions from ACT)
    # - Tab switching handled inline in ACT
    # Result: Clean separation of concerns, fast feedback loop
    workflow.add_edge("act", "think")  # Direct ACT→THINK loop (optimized)

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

