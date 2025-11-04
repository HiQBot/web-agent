"""
Workflow Routes

Endpoints for running QA automation workflows.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from qa_agent.workflow import create_qa_workflow
from qa_agent.state import create_initial_state
from qa_agent.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Create workflow instance (will be initialized once)
_workflow = None


def get_workflow():
    """Get or create workflow instance"""
    global _workflow
    if _workflow is None:
        _workflow = create_qa_workflow()
    return _workflow


class TaskRequest(BaseModel):
    """Request model for running a task"""
    task: str = Field(..., description="Task description or instruction")
    max_steps: Optional[int] = Field(default=settings.max_steps, description="Maximum steps allowed")


class TaskResponse(BaseModel):
    """Response model for task execution"""
    task: str
    completed: bool
    step_count: int
    verification_status: Optional[str]
    report: Optional[dict]
    error: Optional[str]


@router.post("/workflow/run", response_model=TaskResponse)
async def run_task(request: TaskRequest):
    """
    Run a QA automation task
    
    Phase 1: Executes workflow with placeholder actions (no browser session yet).
    The workflow will flow through: think → act → verify → report nodes.
    
    Args:
        request: Task request with task description
        
    Returns:
        Task execution result with workflow state
    """
    logger.info(f"Received task request: {request.task}")
    
    try:
        # Create initial state
        initial_state = create_initial_state(
            task=request.task,
            max_steps=request.max_steps or settings.max_steps,
        )
        
        # Get workflow
        workflow = get_workflow()
        
        # Run workflow (async)
        result = await workflow.ainvoke(initial_state)
        
        # Return result
        return TaskResponse(
            task=result.get("task", request.task),
            completed=result.get("completed", False),
            step_count=result.get("step_count", 0),
            verification_status=result.get("verification_status"),
            report=result.get("report"),
            error=result.get("error"),
        )
        
    except Exception as e:
        logger.error(f"Error running task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

