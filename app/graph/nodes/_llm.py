from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq

from app.config import settings


def build_llm(max_tokens: int = 1024, temperature: float = 0) -> BaseChatModel:
    """Return a ChatGroq model configured from environment settings."""
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model_name,
        max_tokens=max_tokens,
        temperature=temperature,
    )
