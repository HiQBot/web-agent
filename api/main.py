"""
FastAPI Main Application

Entry point for the QA Automation Agent API.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import workflow, health, websocket, browser_stream, tests
from web_agent.config import settings

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
    description="QA Automation Agent API - LangGraph + browser Integration with WebSocket Streaming",
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
app.include_router(tests.router, prefix=settings.api_prefix, tags=["Tests"])
app.include_router(workflow.router, prefix=settings.api_prefix, tags=["Workflow"])
app.include_router(websocket.router, prefix=settings.api_prefix, tags=["WebSocket"])
app.include_router(browser_stream.router, prefix=settings.api_prefix, tags=["Browser Stream"])


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    import os
    logger.info("QA Automation Agent API starting up")
    logger.info(f"API Version: {settings.api_version}")
    logger.info(f"Max Steps: {settings.max_steps}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    
    # Debug: Check browser provider configuration
    logger.info(f"Browser Provider: {settings.browser_provider}")
    logger.info(f"Headless: {settings.headless}")
    logger.info(f"LLM Model: {settings.llm_model}")
    
    # Check for environment variable override
    env_browser_provider = os.getenv('BROWSER_PROVIDER')
    if env_browser_provider:
        logger.warning(f"⚠️  BROWSER_PROVIDER environment variable is set to '{env_browser_provider}' - this overrides .env file!")
        logger.warning(f"   Current settings.browser_provider = '{settings.browser_provider}'")
    else:
        logger.info(f"✓ No BROWSER_PROVIDER environment variable - using .env file value: '{settings.browser_provider}'")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("QA Automation Agent API shutting down")
    
    # Cleanup browser provider (e.g., stop Chrome process)
    try:
        from web_agent.utils.browser_manager import cleanup_browser_provider
        await cleanup_browser_provider()
    except Exception as e:
        logger.error(f"Error during browser provider cleanup: {e}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "QA Automation Agent API",
        "version": settings.api_version,
        "status": "running",
    }

