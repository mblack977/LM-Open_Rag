import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderSettings:
    chat_provider: str = "lm_studio"
    chat_model: Optional[str] = None
    chat_api_key: Optional[str] = None
    chat_base_url: Optional[str] = None

    embedding_provider: str = "local"
    embedding_model: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None


def load_from_env() -> "ProviderSettings":
    # Detect embedding provider from env
    embedding_provider = (os.getenv("EMBEDDING_PROVIDER") or "").strip()
    if not embedding_provider:
        if os.getenv("OLLAMA_EMBEDDING_MODEL"):
            embedding_provider = "ollama"
        elif os.getenv("LM_STUDIO_EMBEDDING_MODEL"):
            embedding_provider = "lm_studio"
        elif os.getenv("OPENAI_EMBEDDING_MODEL"):
            embedding_provider = "openai"
        elif os.getenv("GEMINI_EMBEDDING_MODEL"):
            embedding_provider = "gemini"
        else:
            embedding_provider = "local"

    # Detect chat provider from env
    chat_provider = (os.getenv("CHAT_PROVIDER") or "").strip()
    if not chat_provider:
        lm_base = os.getenv("LM_STUDIO_BASE_URL") or ""
        if os.getenv("OPENAI_API_KEY") and not lm_base:
            chat_provider = "openai"
        elif os.getenv("GEMINI_API_KEY") and not lm_base and not os.getenv("OPENAI_API_KEY"):
            chat_provider = "gemini"
        else:
            chat_provider = "lm_studio"

    # Chat credentials per provider
    if chat_provider == "openai":
        chat_model = os.getenv("OPENAI_CHAT_MODEL") or os.getenv("LM_STUDIO_MODEL")
        chat_api_key = os.getenv("OPENAI_API_KEY")
        chat_base_url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    elif chat_provider == "gemini":
        chat_model = os.getenv("GEMINI_CHAT_MODEL")
        chat_api_key = os.getenv("GEMINI_API_KEY")
        chat_base_url = None
    elif chat_provider == "ollama":
        chat_model = os.getenv("LM_STUDIO_MODEL")
        chat_api_key = os.getenv("LM_STUDIO_API_KEY") or "ollama"
        chat_base_url = (
            os.getenv("OLLAMA_BASE_URL")
            or os.getenv("LM_STUDIO_BASE_URL")
            or "http://localhost:11434/v1"
        )
    else:  # lm_studio
        chat_model = os.getenv("LM_STUDIO_MODEL")
        chat_api_key = os.getenv("LM_STUDIO_API_KEY") or "lm-studio"
        chat_base_url = os.getenv("LM_STUDIO_BASE_URL") or "http://localhost:1234/v1"

    # Embedding credentials per provider
    if embedding_provider == "openai":
        embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small"
        embedding_api_key = os.getenv("OPENAI_API_KEY")
        embedding_base_url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    elif embedding_provider == "gemini":
        embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL") or "models/text-embedding-004"
        embedding_api_key = os.getenv("GEMINI_API_KEY")
        embedding_base_url = None
    elif embedding_provider == "ollama":
        embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL")
        embedding_api_key = None
        embedding_base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    elif embedding_provider == "lm_studio":
        embedding_model = os.getenv("LM_STUDIO_EMBEDDING_MODEL")
        embedding_api_key = os.getenv("LM_STUDIO_API_KEY") or "lm-studio"
        embedding_base_url = (os.getenv("LM_STUDIO_BASE_URL") or "http://localhost:1234/v1").rstrip("/")
    else:  # local
        embedding_model = None
        embedding_api_key = None
        embedding_base_url = None

    return ProviderSettings(
        chat_provider=chat_provider,
        chat_model=chat_model,
        chat_api_key=chat_api_key,
        chat_base_url=chat_base_url,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
    )


# Mutable global — reassign fields or call load_from_env() to reset from env
current_settings: ProviderSettings = load_from_env()
