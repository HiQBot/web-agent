"""
Configuration settings for QA Agent
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
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

    # Google/Gemini Settings
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None

    # Browser Settings (CDP & browser)
    headless: bool = False  # Set to False for headful browser (kernel-docker container)
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

    # browser compatibility settings (used by profile.py)
    IN_DOCKER: bool = False
    BROWSER_USE_CONFIG_DIR: Path = Path.home() / ".browser"
    BROWSER_USE_DEFAULT_USER_DATA_DIR: Path = Path.home() / ".browser" / "user-data"
    BROWSER_USE_EXTENSIONS_DIR: Path = Path.home() / ".browser" / "extensions"
    ANONYMIZED_TELEMETRY: bool = False  # Disable telemetry
    BROWSER_USE_LOGGING_LEVEL: str = "INFO"  # browser logging level

    # GIF generation settings (cross-platform)
    # Windows: C:/Windows/Fonts, Linux: /usr/share/fonts, macOS: /Library/Fonts
    # The GIF module will auto-detect the correct path based on platform

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields from env vars that aren't defined
    )


settings = Settings()

# Backward compatibility alias for browser code
CONFIG = settings


def is_running_in_docker() -> bool:
	"""
	Check if running inside Docker container

	Returns:
		True if running in Docker, False otherwise
	"""
	return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv') or settings.IN_DOCKER

