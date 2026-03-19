"""
OpenAI-compatible API client that respects LLM_PROVIDER and EMBEDDING_PROVIDER.

Supports flexible provider/model selection: options are enabled from .env
(which API keys are set). UI can show provider and model dropdowns and get
client for the selected combination.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI

# Default model lists for sidebar (can override via .env LLM_MODELS_OPENAI, etc.)
_DEFAULT_MODELS_OPENAI = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
_DEFAULT_MODELS_OPENROUTER = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "anthropic/claude-3-5-sonnet",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemini-2.0-flash-001",
]


def get_available_llm_providers() -> list[str]:
    """
    Return list of LLM provider names that are configured in .env (have API key or URL).
    Used to populate sidebar: only these options are shown and enabled.
    """
    available = []
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"):
        available.append("openai")
    if os.environ.get("OPENROUTER_API_KEY"):
        available.append("openrouter")
    # Ollama: always offer if OLLAMA_URL is set (local); no key required
    if os.environ.get("OLLAMA_URL", "http://localhost:11434").strip():
        available.append("ollama")
    return available if available else ["openai"]  # fallback so UI doesn't break


def get_default_llm_models(provider: str) -> list[str]:
    """
    Return list of model choices for the given provider, from .env when possible.
    .env can set: LLM_CHOICE (default), LLM_MODELS_OPENAI, LLM_MODELS_OPENROUTER (comma-sep), OLLAMA_MODEL.
    """
    provider = (provider or "").strip().lower()
    default_choice = os.environ.get("LLM_CHOICE", "").strip()
    if provider == "openai":
        from_env = os.environ.get("LLM_MODELS_OPENAI", "").strip()
        models = [m.strip() for m in from_env.split(",") if m.strip()] if from_env else _DEFAULT_MODELS_OPENAI.copy()
        if default_choice and default_choice not in models:
            models.insert(0, default_choice)
        return models or _DEFAULT_MODELS_OPENAI
    if provider == "openrouter":
        from_env = os.environ.get("LLM_MODELS_OPENROUTER", "").strip()
        models = [m.strip() for m in from_env.split(",") if m.strip()] if from_env else _DEFAULT_MODELS_OPENROUTER.copy()
        if default_choice and default_choice not in models:
            models.insert(0, default_choice)
        return models or _DEFAULT_MODELS_OPENROUTER
    if provider == "ollama":
        default = os.environ.get("OLLAMA_MODEL", "llama3.2:3b").strip()
        from_env = os.environ.get("OLLAMA_MODELS", "").strip()
        models = [m.strip() for m in from_env.split(",") if m.strip()] if from_env else [default, "llama3.2:3b", "llama3.1:8b", "qwen2.5:7b-instruct"]
        if default and default not in models:
            models.insert(0, default)
        return models or [default]
    return []


def get_llm_client(provider_override: str | None = None) -> "OpenAI":
    """
    Return an OpenAI-compatible client for chat.
    If provider_override is set (openai, openrouter), use that provider's key and base URL from .env.
    Otherwise use LLM_PROVIDER from .env.
    (Ollama is not an OpenAI client; callers must use Ollama URL when provider is ollama.)
    """
    provider = (provider_override or os.environ.get("LLM_PROVIDER") or "openai").strip().lower()
    if provider == "ollama":
        raise RuntimeError("Ollama does not use OpenAI client; use Ollama URL and /api/chat in the app.")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    if provider == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
        if not key:
            raise RuntimeError("OpenRouter requires OPENROUTER_API_KEY or LLM_API_KEY in .env")
        return _client(base_url or "https://openrouter.ai/api/v1", key)
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    if not key:
        raise RuntimeError("OpenAI requires OPENAI_API_KEY or LLM_API_KEY in .env")
    return _client(base_url if provider == "openai" else None, key)


def _client(base_url: str | None, api_key: str) -> "OpenAI":
    """Return OpenAI-compatible client; use Langfuse-wrapped client when LANGFUSE keys are set for tracing."""
    use_langfuse = (
        os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    )
    if use_langfuse:
        try:
            from langfuse.openai import OpenAI as LangfuseOpenAI
            if base_url:
                return LangfuseOpenAI(base_url=base_url.rstrip("/"), api_key=api_key)
            return LangfuseOpenAI(api_key=api_key)
        except Exception:
            pass
    from openai import OpenAI
    if base_url:
        return OpenAI(base_url=base_url.rstrip("/"), api_key=api_key)
    return OpenAI(api_key=api_key)


def get_embedding_client() -> "OpenAI":
    """
    Return an OpenAI-compatible client for embeddings.
    Uses EMBEDDING_PROVIDER: openrouter -> OpenRouter URL + key; openai -> OpenAI.
    """
    provider = (os.environ.get("EMBEDDING_PROVIDER") or "openai").strip().lower()
    base_url = os.environ.get("EMBEDDING_BASE_URL", "https://api.openai.com/v1").strip()
    if provider == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("EMBEDDING_API_KEY")
        if not key:
            raise RuntimeError("EMBEDDING_PROVIDER=openrouter requires OPENROUTER_API_KEY or EMBEDDING_API_KEY in .env")
        return _client(base_url or "https://openrouter.ai/api/v1", key)
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMBEDDING_API_KEY")
    if not key:
        raise RuntimeError("Set OPENAI_API_KEY or EMBEDDING_API_KEY in .env for embeddings")
    return _client(base_url if provider == "openai" else None, key)
