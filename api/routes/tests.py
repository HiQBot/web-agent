"""
Test Plans Routes

Endpoints for managing test plans and test execution.
"""
import logging
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory storage for test plans (in production, use a database)
test_plans_db: dict[str, dict] = {}


class TestPlanCreate(BaseModel):
    """Request model for creating a test plan"""
    description: str = Field(..., description="Test description/task")
    url: str = Field(..., description="Target URL for testing")
    name: Optional[str] = Field(None, description="Optional test name")


class TestPlan(BaseModel):
    """Test plan model"""
    id: str
    name: str
    description: str
    url: str
    website_name: Optional[str] = None
    status: str  # pending, running, completed, failed
    created_at: str
    updated_at: str
    step_count: Optional[int] = 0
    verification_status: Optional[str] = None
    report: Optional[dict] = None


class TestPlansResponse(BaseModel):
    """Response model for listing test plans"""
    test_plans: List[TestPlan]


@router.get("/tests/test-plans", response_model=TestPlansResponse)
async def get_test_plans():
    """
    Get all test plans

    Returns a list of all test plans with their current status.
    """
    try:
        plans = [TestPlan(**plan) for plan in test_plans_db.values()]
        # Sort by created_at descending (newest first)
        plans.sort(key=lambda x: x.created_at, reverse=True)
        return TestPlansResponse(test_plans=plans)
    except Exception as e:
        logger.error(f"Error fetching test plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tests/test-plans", response_model=TestPlan)
async def create_test_plan(request: TestPlanCreate):
    """
    Create a new test plan

    Creates a test plan and returns it with status 'pending'.
    The test will be executed automatically via WebSocket.

    Args:
        request: Test plan creation request

    Returns:
        Created test plan
    """
    try:
        # Generate unique ID
        test_id = str(uuid.uuid4())

        # Extract website name from URL
        website_name = None
        try:
            from urllib.parse import urlparse
            parsed = urlparse(request.url)
            website_name = parsed.netloc or parsed.path
        except:
            pass

        # Generate name if not provided
        name = request.name or f"Test: {request.description[:50]}"

        # Create test plan
        now = datetime.utcnow().isoformat()
        test_plan = {
            "id": test_id,
            "name": name,
            "description": request.description,
            "url": request.url,
            "website_name": website_name,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "step_count": 0,
            "verification_status": None,
            "report": None
        }

        # Store in database
        test_plans_db[test_id] = test_plan

        logger.info(f"Created test plan {test_id}: {name}")

        return TestPlan(**test_plan)

    except Exception as e:
        logger.error(f"Error creating test plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/test-plans/{test_id}", response_model=TestPlan)
async def get_test_plan(test_id: str):
    """
    Get a specific test plan by ID

    Args:
        test_id: Test plan ID

    Returns:
        Test plan details
    """
    if test_id not in test_plans_db:
        raise HTTPException(status_code=404, detail=f"Test plan {test_id} not found")

    return TestPlan(**test_plans_db[test_id])


@router.put("/tests/test-plans/{test_id}/status")
async def update_test_plan_status(
    test_id: str,
    status: str,
    step_count: Optional[int] = None,
    verification_status: Optional[str] = None,
    report: Optional[dict] = None
):
    """
    Update test plan status

    Called by WebSocket workflow to update test execution status.

    Args:
        test_id: Test plan ID
        status: New status (pending, running, completed, failed)
        step_count: Number of steps executed
        verification_status: Verification result
        report: Test execution report

    Returns:
        Updated test plan
    """
    if test_id not in test_plans_db:
        raise HTTPException(status_code=404, detail=f"Test plan {test_id} not found")

    test_plan = test_plans_db[test_id]
    test_plan["status"] = status
    test_plan["updated_at"] = datetime.utcnow().isoformat()

    if step_count is not None:
        test_plan["step_count"] = step_count
    if verification_status is not None:
        test_plan["verification_status"] = verification_status
    if report is not None:
        test_plan["report"] = report

    logger.info(f"Updated test plan {test_id} status to {status}")

    return TestPlan(**test_plan)


@router.delete("/tests/test-plans/{test_id}")
async def delete_test_plan(test_id: str):
    """
    Delete a test plan

    Args:
        test_id: Test plan ID

    Returns:
        Success message
    """
    if test_id not in test_plans_db:
        raise HTTPException(status_code=404, detail=f"Test plan {test_id} not found")

    del test_plans_db[test_id]
    logger.info(f"Deleted test plan {test_id}")

    return {"message": f"Test plan {test_id} deleted successfully"}


@router.get("/tests/stats")
async def get_test_stats():
    """
    Get test execution statistics

    Returns:
        Statistics about test executions
    """
    total = len(test_plans_db)
    pending = sum(1 for p in test_plans_db.values() if p["status"] == "pending")
    running = sum(1 for p in test_plans_db.values() if p["status"] == "running")
    completed = sum(1 for p in test_plans_db.values() if p["status"] == "completed")
    failed = sum(1 for p in test_plans_db.values() if p["status"] == "failed")

    pass_rate = round((completed / total * 100) if total > 0 else 0, 1)

    return {
        "total_tests": total,
        "pending": pending,
        "running": running,
        "completed": completed,
        "failed": failed,
        "pass_rate": pass_rate
    }
