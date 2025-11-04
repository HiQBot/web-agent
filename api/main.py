"""
FastAPI Main Application

Entry point for the QA Automation Agent API.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import workflow, health
from qa_agent.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="QA Automation Agent API - LangGraph + Browser-Use Integration",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix=settings.api_prefix, tags=["Health"])
app.include_router(workflow.router, prefix=settings.api_prefix, tags=["Workflow"])


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("QA Automation Agent API starting up")
    logger.info(f"API Version: {settings.api_version}")
    logger.info(f"Max Steps: {settings.max_steps}")
    logger.info(f"LLM Provider: {settings.llm_provider}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("QA Automation Agent API shutting down")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "QA Automation Agent API",
        "version": settings.api_version,
        "status": "running",
    }

