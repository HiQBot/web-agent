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

    # Browser Provider Selection
    browser_provider: str = "onkernal"  # "onkernal" or "chrome"
    
    # Chrome Settings (only used when BROWSER_PROVIDER=chrome)
    chrome_executable_path: Optional[str] = None  # Auto-detect if None
    
    # Port Settings (shared by both providers)
    cdp_port: int = 9222  # CDP port (will auto-detect conflicts)
    streaming_port: int = 8080  # Streaming port (will auto-detect conflicts)
    
    # Kernel-Image CDP Connection (for OnKernal provider)
    kernel_cdp_host: str = "localhost"
    kernel_cdp_port: int = 9222  # Deprecated: use cdp_port instead

    # Retry Strategy                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
    retry_delay: float = 1.0  # seconds between retries
    retry_backoff: float = 2.0  # exponential backoff multiplier

    # Logging
    log_level: str = "INFO"

    # browser compatibility settings (used by profile.py)
    IN_DOCKER: bool = False
    browser_CONFIG_DIR: Path = Path.home() / ".browser"
    browser_DEFAULT_USER_DATA_DIR: Path = Path.home() / ".browser" / "user-data"
    browser_EXTENSIONS_DIR: Path = Path.home() / ".browser" / "extensions"
    ANONYMIZED_TELEMETRY: bool = False  # Disable telemetry
    browser_LOGGING_LEVEL: str = "INFO"  # browser logging level

    # GIF generation settings (cross-platform)
    # Windows: C:/Windows/Fonts, Linux: /usr/share/fonts, macOS: /Library/Fonts
    # The GIF module will auto-detect the correct path based on platform

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),  # Look for .env in project root
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from env vars that aren't defined
        env_ignore_empty=True,  # Ignore empty env vars
        # Note: Environment variables take precedence over .env file
        # If BROWSER_PROVIDER is set in shell, it will override .env file
    )


# Determine .env file path relative to this config file
_config_dir = Path(__file__).parent
_project_root = _config_dir.parent
_env_file_path = _project_root / ".env"

# Log .env file detection
import logging
_logger = logging.getLogger(__name__)
_logger.info(f"Looking for .env file at: {_env_file_path}")
_logger.info(f".env file exists: {_env_file_path.exists()}")

if _env_file_path.exists():
    _env_content = _env_file_path.read_text()
    _browser_provider_lines = [l for l in _env_content.split('\n') 
                               if 'BROWSER_PROVIDER' in l.upper() 
                               and not l.strip().startswith('#')]
    if _browser_provider_lines:
        _logger.info(f"Found BROWSER_PROVIDER in .env: {_browser_provider_lines}")

# Create settings instance
settings = Settings()

# Debug: Log the browser provider setting at startup
_logger.info(f"Browser provider configuration loaded: '{settings.browser_provider}'")
_logger.info(f"Settings env_file path: {settings.model_config.get('env_file')}")

# Check if environment variable is overriding .env
import os
env_browser_provider = os.getenv('BROWSER_PROVIDER')
if env_browser_provider:
    _logger.warning(f"⚠️  BROWSER_PROVIDER environment variable is set to '{env_browser_provider}' - this overrides .env file!")
    _logger.warning(f"   To use .env file value, unset the environment variable: unset BROWSER_PROVIDER")
else:
    _logger.info("✓ No BROWSER_PROVIDER environment variable found - using .env file value")

# Backward compatibility alias for browser code
CONFIG = settings


def is_running_in_docker() -> bool:
	"""
	Check if running inside Docker container

	Returns:
		True if running in Docker, False otherwise
	"""
	return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv') or settings.IN_DOCKER

