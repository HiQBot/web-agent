"""
Run script for QA Automation Agent API

Usage:
    python run.py
    
Or with uvicorn directly:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""
import uvicorn
from web_agent.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )

