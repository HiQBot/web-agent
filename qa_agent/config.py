"""
Configuration settings for QA Agent
"""
import os
from pathlib import Path
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
    max_actions_per_step: int = 3  # Max actions LLM can generate per think cycle

    # LLM Settings
    llm_provider: str = "openai"  # openai, anthropic, google, etc.
    llm_model: str = "gpt-4.1-mini"  # Will be overridden by .env LLM_MODEL
    llm_temperature: float = 0.7
    max_input_tokens: int = 128000  # gpt-4o context limit
    max_output_tokens: int = 16000

    # OpenAI Settings
    openai_api_key: Optional[str] = None

    # Anthropic Settings
    anthropic_api_key: Optional[str] = None

    # Browser Settings (CDP & browser-use)
    headless: bool = True
    browser_timeout: int = 30000  # milliseconds
    navigation_timeout: int = 30000  # milliseconds
    action_timeout: int = 5000  # milliseconds
    cdp_timeout: int = 30000  # CDP websocket timeout

    # Kernel-Image CDP Connection
    kernel_cdp_host: str = "localhost"
    kernel_cdp_port: int = 9222

    # Retry Strategy
    retry_delay: float = 1.0  # seconds between retries
    retry_backoff: float = 2.0  # exponential backoff multiplier

    # Logging
    log_level: str = "INFO"

    # Browser-use compatibility settings (used by profile.py)
    IN_DOCKER: bool = False
    BROWSER_USE_CONFIG_DIR: Path = Path.home() / ".browser-use"
    BROWSER_USE_DEFAULT_USER_DATA_DIR: Path = Path.home() / ".browser-use" / "user-data"
    BROWSER_USE_EXTENSIONS_DIR: Path = Path.home() / ".browser-use" / "extensions"
    ANONYMIZED_TELEMETRY: bool = False  # Disable telemetry
    BROWSER_USE_LOGGING_LEVEL: str = "INFO"  # Browser-use logging level

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()

# Backward compatibility alias for browser-use code
CONFIG = settings


def is_running_in_docker() -> bool:
	"""
	Check if running inside Docker container

	Returns:
		True if running in Docker, False otherwise
	"""
	return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv') or settings.IN_DOCKER

