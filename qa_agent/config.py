"""
Configuration settings for QA Agent
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    api_title: str = "QA Automation Agent API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    
    # LangGraph Settings
    max_steps: int = 50
    max_retries: int = 3
    
    # LLM Settings
    llm_provider: str = "openai"  # openai, anthropic, google, etc.
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.7
    
    # OpenAI Settings
    openai_api_key: Optional[str] = None
    
    # Anthropic Settings
    anthropic_api_key: Optional[str] = None
    
    # Browser Settings
    headless: bool = True
    browser_timeout: int = 30
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()

