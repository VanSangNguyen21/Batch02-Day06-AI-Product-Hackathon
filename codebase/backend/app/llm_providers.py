"""
llm_providers.py - LLM provider abstraction

Single source of truth for which LLM provider to use.
Reads LLM_PROVIDER + per-provider config from .env / environment.

Supported providers:
  - openai    (OpenAI API or any OpenAI-compatible endpoint)
  - ollama    (local Ollama server, no API key required)
  - gemini    (Google Gemini)
  - nvidia    (NVIDIA integrate.api.nvidia.com)
  - deepseek  (DeepSeek API)

Environment variables (per provider):
  LLM_PROVIDER        - Provider name (default: openai)
  OPENAI_API_KEY      - OpenAI API key
  OPENAI_API_BASE     - OpenAI base URL (default: https://api.openai.com/v1)
  OPENAI_MODEL        - OpenAI model (default: gpt-4o-mini)

  OLLAMA_BASE_URL     - Ollama base URL (default: http://localhost:11434)
  OLLAMA_MODEL        - Ollama model (default: llama3.2)

  GEMINI_API_KEY      - Google Gemini API key
  GEMINI_MODEL        - Gemini model (default: gemini-1.5-flash)

  NVIDIA_API_KEY      - NVIDIA integrate API key
  NVIDIA_MODEL        - NVIDIA model (default: deepseek-ai/deepseek-v3.1)

  DEEPSEEK_API_KEY    - DeepSeek API key
  DEEPSEEK_API_BASE   - DeepSeek base URL (default: https://api.deepseek.com/v1)
  DEEPSEEK_MODEL      - DeepSeek model (default: deepseek-chat)
"""

import os
import logging
from enum import Enum
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    NVIDIA = "nvidia"
    DEEPSEEK = "deepseek"


class LLMConfig:
    """Resolved configuration for a single provider call."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        supports_json_mode: bool = True,
        supports_thinking_param: bool = False,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.supports_json_mode = supports_json_mode
        self.supports_thinking_param = supports_thinking_param

    def __repr__(self) -> str:
        return (
            f"LLMConfig(provider={self.provider.value}, model={self.model!r}, "
            f"base_url={self.base_url!r}, has_key={bool(self.api_key)})"
        )


def resolve_config(provider_override: Optional[str] = None) -> LLMConfig:
    """Resolve LLM config from environment."""
    provider_name = (provider_override or os.getenv("LLM_PROVIDER", "")).strip().lower()
    if not provider_name:
        provider_name = _infer_provider_from_model(os.getenv("MODEL_NAME", ""))
    if provider_name not in LLMProvider._value2member_map_:
        logger.warning(f"Unknown LLM_PROVIDER='{provider_name}', falling back to 'openai'")
        provider_name = "openai"
    provider = LLMProvider(provider_name)

    if provider == LLMProvider.OLLAMA:
        return LLMConfig(
            provider=provider,
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
            supports_json_mode=False,
        )
    if provider == LLMProvider.GEMINI:
        return LLMConfig(
            provider=provider,
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            api_key=os.getenv("GEMINI_API_KEY"),
            supports_json_mode=True,
        )
    if provider == LLMProvider.NVIDIA:
        return LLMConfig(
            provider=provider,
            model=os.getenv("NVIDIA_MODEL", "deepseek-ai/deepseek-v3.1"),
            api_key=os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1"),
            supports_json_mode=True,
            supports_thinking_param=True,
        )
    if provider == LLMProvider.DEEPSEEK:
        return LLMConfig(
            provider=provider,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
            supports_json_mode=True,
            supports_thinking_param=True,
        )
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        supports_json_mode=True,
    )


def _infer_provider_from_model(model: str) -> str:
    """Best-effort fallback when LLM_PROVIDER is not set."""
    m = model.lower()
    if m.startswith("ollama/") or "ollama" in m:
        return "ollama"
    if "gemini" in m:
        return "gemini"
    if "nvidia" in m or "nemotron" in m:
        return "nvidia"
    if "deepseek" in m:
        return "deepseek"
    return "openai"


def _format_messages_ollama(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [{"role": m["role"], "content": m["content"]} for m in messages]


async def chat_ollama(
    messages: List[Dict[str, str]],
    cfg: LLMConfig,
    *,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> Dict[str, Any]:
    """Call local Ollama server with fallback to OpenAI-compatible endpoint."""
    timeout = httpx.Timeout(120.0, connect=10.0)
    openai_url = f"{cfg.base_url}/v1/chat/completions"
    ollama_url = f"{cfg.base_url}/api/chat"

    payload = {
        "model": cfg.model,
        "messages": _format_messages_ollama(messages),
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if json_mode:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            res = await client.post(ollama_url, json=payload)
            if res.status_code == 404:
                logger.info("Ollama /api/chat 404, trying OpenAI-compatible /v1/chat/completions")
                openai_payload = {
                    "model": cfg.model,
                    "messages": _format_messages_ollama(messages),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if json_mode:
                    openai_payload["response_format"] = {"type": "json_object"}
                res = await client.post(openai_url, json=openai_payload)
            res.raise_for_status()
            data = res.json()
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Cannot connect to Ollama at {cfg.base_url}. "
                f"Is the server running? Start it with: ollama serve"
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama HTTP {e.response.status_code}: {e.response.text}") from e

    if "choices" in data:
        choice = data["choices"][0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return {
            "content": content,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }

    message = data.get("message", {}) or {}
    content = message.get("content", "")
    return {
        "content": content,
        "input_tokens": data.get("prompt_eval_count", 0) or 0,
        "output_tokens": data.get("eval_count", 0) or 0,
    }


def get_price_table() -> Dict[str, Dict[str, float]]:
    """Pricing table for cost calculation. Keys are model name substrings."""
    return {
        "gpt-4o":         {"input":  2.50 / 1_000_000, "output": 10.00 / 1_000_000},
        "gpt-4o-mini":    {"input":  0.15 / 1_000_000, "output":  0.60 / 1_000_000},
        "gpt-3.5-turbo":  {"input":  0.50 / 1_000_000, "output":  1.50 / 1_000_000},
        "gemini-1.5-flash": {"input": 0.075 / 1_000_000, "output":  0.30 / 1_000_000},
        "gemini-1.5-pro": {"input":  3.50 / 1_000_000, "output": 10.50 / 1_000_000},
        "ollama":         {"input":  0.0,              "output":  0.0},
    }


def is_local_model(model: str) -> bool:
    """True nếu model chạy local (Ollama / llama.cpp) - miễn phí."""
    m = (model or "").lower()
    if not m:
        return False
    return (
        "ollama" in m
        or m.startswith("llama")
        or m.startswith("mistral")
        or m.startswith("qwen")
        or ":" in m
    )


def estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Estimate cost in USD. Local models are free."""
    if is_local_model(model):
        return 0.0
    model_lower = model.lower()
    for key, prices in get_price_table().items():
        if key in model_lower:
            return (input_tokens * prices["input"]) + (output_tokens * prices["output"])
    return 0.0
