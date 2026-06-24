from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.config import settings


def build_llm(max_tokens: int = 1024, temperature: float = 0) -> BaseChatModel:
    """Return ChatAnthropic if the key is set, otherwise fall back to ChatGroq."""
    if settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    from langchain_groq import ChatGroq

    return ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=settings.groq_api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    )
