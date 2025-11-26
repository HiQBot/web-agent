"""
LLM Integration for QA Agent

Uses LangChain's ChatOpenAI for OpenAI integration.
"""
import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from web_agent.config import settings

logger = logging.getLogger(__name__)


def get_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    api_key: Optional[str] = None,
) -> ChatOpenAI:
    """
    Get an initialized ChatOpenAI instance
    
    Args:
        model: Model name (defaults to settings.llm_model)
        temperature: Temperature setting (defaults to settings.llm_temperature)
        api_key: OpenAI API key (defaults to settings.openai_api_key or env var)
        
    Returns:
        Initialized ChatOpenAI instance
    """
    model_name = model or settings.llm_model
    temp = temperature if temperature is not None else settings.llm_temperature
    key = api_key or settings.openai_api_key
    
    if not key:
        raise ValueError(
            "OpenAI API key not found. "
            "Set OPENAI_API_KEY environment variable or configure in settings."
        )
    
    logger.info(f"Initializing ChatOpenAI with model: {model_name}, temperature: {temp}")
    
    return ChatOpenAI(
        model=model_name,
        temperature=temp,
        api_key=key,
    )

