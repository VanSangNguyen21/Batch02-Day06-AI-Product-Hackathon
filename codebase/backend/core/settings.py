"""
Centralized runtime settings and LLM provider registry.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key_env: str
    default_base_url: Optional[str]
    analyze_model: str
    chat_model: str
    supports_json_mode: bool
    free_tier_default: bool
    openai_compatible: bool


PROVIDER_REGISTRY: Dict[str, ProviderConfig] = {
    "gemini": ProviderConfig(
        name="gemini",
        api_key_env="GEMINI_API_KEY",
        default_base_url=None,
        analyze_model="gemini-2.5-flash-lite",
        chat_model="gemini-2.5-flash-lite",
        supports_json_mode=True,
        free_tier_default=True,
        openai_compatible=False,
    ),
    "openai": ProviderConfig(
        name="openai",
        api_key_env="OPENAI_API_KEY",
        default_base_url="https://api.openai.com/v1",
        analyze_model="gpt-4o-mini",
        chat_model="gpt-4o-mini",
        supports_json_mode=True,
        free_tier_default=False,
        openai_compatible=True,
    ),
    "nvidia": ProviderConfig(
        name="nvidia",
        api_key_env="NVIDIA_API_KEY",
        default_base_url="https://integrate.api.nvidia.com/v1",
        analyze_model="deepseek-ai/deepseek-v4-flash",
        chat_model="deepseek-ai/deepseek-v4-flash",
        supports_json_mode=False,
        free_tier_default=False,
        openai_compatible=True,
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        default_base_url="https://openrouter.ai/api/v1",
        analyze_model="google/gemini-2.0-flash-exp:free",
        chat_model="google/gemini-2.0-flash-exp:free",
        supports_json_mode=False,
        free_tier_default=True,
        openai_compatible=True,
    ),
    "groq": ProviderConfig(
        name="groq",
        api_key_env="GROQ_API_KEY",
        default_base_url="https://api.groq.com/openai/v1",
        analyze_model="llama-3.1-8b-instant",
        chat_model="llama-3.1-8b-instant",
        supports_json_mode=False,
        free_tier_default=True,
        openai_compatible=True,
    ),
    "huggingface": ProviderConfig(
        name="huggingface",
        api_key_env="HF_TOKEN",
        default_base_url="https://router.huggingface.co/v1",
        analyze_model="zai-org/GLM-4.7:cerebras",
        chat_model="zai-org/GLM-4.7:cerebras",
        supports_json_mode=False,
        free_tier_default=True,
        openai_compatible=True,
    ),
}


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    analyze_model: str
    chat_model: str
    provider: ProviderConfig
    api_key: Optional[str]
    base_url: Optional[str]
    llm_free_tier: bool
    allow_model_override: bool
    request_timeout_seconds: float
    retry_attempts: int
    allowed_origins: List[str]
    admin_api_key: str


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _provider_name() -> str:
    raw = (_env("LLM_PROVIDER", "gemini") or "gemini").strip().lower()
    if raw in PROVIDER_REGISTRY:
        return raw
    return "gemini"


def _base_url_for(provider_name: str, provider: ProviderConfig) -> Optional[str]:
    env_names = {
        "openai": ("OPENAI_BASE_URL", "OPENAI_API_BASE"),
        "nvidia": ("NVIDIA_BASE_URL",),
        "openrouter": ("OPENROUTER_BASE_URL",),
        "groq": ("GROQ_BASE_URL",),
        "huggingface": ("HF_BASE_URL",),
    }.get(provider_name, ())

    for env_name in env_names:
        value = _env(env_name)
        if value:
            return value.rstrip("/")
    return provider.default_base_url


def _model_for(kind: str, provider: ProviderConfig) -> str:
    explicit_name = "ANALYZE_MODEL" if kind == "analyze" else "CHAT_MODEL"
    explicit = _env(explicit_name)
    if explicit:
        return explicit

    legacy = _env("MODEL_NAME")
    if legacy:
        return legacy

    return provider.analyze_model if kind == "analyze" else provider.chat_model


def _allowed_origins() -> List[str]:
    raw = _env(
        "ALLOWED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,null",
    )
    return [origin.strip() for origin in (raw or "").split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    provider_name = _provider_name()
    provider = PROVIDER_REGISTRY[provider_name]
    api_key = _env(provider.api_key_env)

    free_default = provider.free_tier_default or (
        provider_name == "openrouter"
        and (
            (_env("ANALYZE_MODEL") or provider.analyze_model).endswith(":free")
            or (_env("CHAT_MODEL") or provider.chat_model).endswith(":free")
        )
    )

    return Settings(
        llm_provider=provider_name,
        analyze_model=_model_for("analyze", provider),
        chat_model=_model_for("chat", provider),
        provider=provider,
        api_key=api_key,
        base_url=_base_url_for(provider_name, provider),
        llm_free_tier=_bool_env("LLM_FREE_TIER", free_default),
        allow_model_override=_bool_env("ALLOW_MODEL_OVERRIDE", False),
        request_timeout_seconds=float(_env("LLM_TIMEOUT_SECONDS", "45")),
        retry_attempts=max(1, int(_env("LLM_RETRY_ATTEMPTS", "3") or "3")),
        allowed_origins=_allowed_origins(),
        admin_api_key=_env("ADMIN_API_KEY", "dev-admin-key-change-in-production") or "dev-admin-key-change-in-production",
    )


def clear_settings_cache() -> None:
    get_settings.cache_clear()
