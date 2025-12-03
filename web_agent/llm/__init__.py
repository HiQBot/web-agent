"""
LLM Integration for QA Agent

Supports multiple LLM providers:
- OpenAI (ChatGPT, GPT-4.1)
- Google Gemini (gemini-2.5-flash, gemini-2.5-pro)
- Anthropic Claude (optional, for future)
"""
import logging
from typing import Optional, Union
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from web_agent.config import settings

logger = logging.getLogger(__name__)


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    api_key: Optional[str] = None,
) -> Union[ChatOpenAI, ChatGoogleGenerativeAI]:
    """
    Get an initialized LLM instance based on provider

    Supports multiple providers with automatic selection from settings.

    Args:
        provider: LLM provider ('openai', 'google', 'gemini').
                 Defaults to settings.llm_provider
        model: Model name (defaults to provider-specific default)
        temperature: Temperature setting (defaults to settings.llm_temperature)
        api_key: API key for the provider (defaults to provider-specific key from settings)

    Returns:
        Initialized LLM instance (ChatOpenAI or ChatGoogleGenerativeAI)

    Raises:
        ValueError: If provider is unsupported or API key is missing
    """
    # Determine provider (default to openai for backward compatibility)
    provider = (provider or settings.llm_provider or "openai").lower()
    temp = temperature if temperature is not None else settings.llm_temperature

    verbose_msg = f"[LLM] Provider={provider} | Model={model or 'default'} | Temperature={temp}"
    logger.info(f"Initializing LLM: {verbose_msg}")
    print(verbose_msg)

    # OpenAI Provider
    if provider == "openai":
        model_name = model or settings.llm_model
        key = api_key or settings.openai_api_key

        if not key:
            raise ValueError(
                "OpenAI API key not found. "
                "Set OPENAI_API_KEY environment variable or configure in settings."
            )

        logger.info(f"Initializing ChatOpenAI with model: {model_name}")

        return ChatOpenAI(
            model=model_name,
            temperature=temp,
            api_key=key,
        )

    # Google Gemini Provider
    elif provider in ["google", "gemini"]:
        model_name = model or settings.gemini_model
        # Support both GOOGLE_API_KEY and GEMINI_API_KEY
        key = api_key or settings.google_api_key or settings.gemini_api_key

        if not key:
            raise ValueError(
                "Google API key not found. "
                "Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable or configure in settings."
            )

        logger.info(f"Initializing ChatGoogleGenerativeAI with model: {model_name}")

        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temp,
            google_api_key=key,
            convert_system_message_to_human=True,  # Gemini compatibility
        )

    elif provider in ["anthropic", "claude"]:
        model_name = model or getattr(settings, "anthropic_model", "claude-3-5-sonnet-20241022")
        key = api_key or settings.anthropic_api_key

        if not key:
            raise ValueError(
                "Anthropic API key not found. "
                "Set ANTHROPIC_API_KEY environment variable or configure in settings."
            )

        logger.info(f"Initializing ChatAnthropic with model: {model_name}")

        return ChatAnthropic(
            model=model_name,
            temperature=temp,
            api_key=key,
        )

    # Unsupported provider
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: openai, google (gemini), anthropic (claude)"
        )

