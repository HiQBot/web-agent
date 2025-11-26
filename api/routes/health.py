"""
Health Check Routes

Simple health check endpoints for monitoring.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from web_agent.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    version: str
    service: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns:
        Health status
    """
    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        service="qa-automation-agent",
    )


@router.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint
    
    Returns:
        Readiness status
    """
    # TODO: Add checks for required services (browser, LLM, etc.)
    return {
        "ready": True,
        "checks": {
            "api": True,
            # "browser": False,  # Will be added in Phase 1
            # "llm": False,      # Will be added in Phase 4
        }
    }

