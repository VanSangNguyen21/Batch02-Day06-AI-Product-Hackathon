"""
Unified LLM client for roadmap JSON generation and chat responses.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMProviderError(RuntimeError):
    """Raised when the configured LLM provider cannot produce a response."""


@dataclass
class LLMJsonResult:
    data: Dict[str, Any]
    input_tokens: int
    output_tokens: int
    model_name: str
    provider_name: str


@dataclass
class LLMTextResult:
    content: str
    input_tokens: int
    output_tokens: int
    model_name: str
    provider_name: str


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def parse_json_object(text: str) -> Dict[str, Any]:
    cleaned = _strip_code_fence(text)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        parsed = json.loads(cleaned[start : end + 1])
        if isinstance(parsed, dict):
            return parsed

    raise LLMProviderError("LLM did not return a valid JSON object")


def _usage_from_openai_response(response: Any, prompt_text: str, content: str) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    output_tokens = getattr(usage, "completion_tokens", None) if usage else None
    return (
        int(input_tokens) if input_tokens is not None else _estimate_tokens(prompt_text),
        int(output_tokens) if output_tokens is not None else _estimate_tokens(content),
    )


def _usage_from_gemini_response(response: Any, prompt_text: str, content: str) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    return (
        int(input_tokens) if input_tokens is not None else _estimate_tokens(prompt_text),
        int(output_tokens) if output_tokens is not None else _estimate_tokens(content),
    )


def _is_retryable_error(err: Exception) -> bool:
    status_code = getattr(err, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True
    text = str(err).lower()
    return any(token in text for token in ("429", "rate limit", "timeout", "temporarily unavailable"))


async def _with_retries(label: str, func, settings: Settings) -> Any:
    last_error: Optional[Exception] = None
    for attempt in range(settings.retry_attempts):
        try:
            return await func()
        except Exception as err:
            last_error = err
            if attempt >= settings.retry_attempts - 1 or not _is_retryable_error(err):
                break
            delay = min(2 ** attempt, 8)
            logger.warning("%s failed with retryable error; retrying in %ss: %s", label, delay, err)
            await asyncio.sleep(delay)
    raise LLMProviderError(f"{label} failed: {last_error}") from last_error


async def generate_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model_name: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> LLMJsonResult:
    settings = get_settings()
    model = model_name or settings.analyze_model

    if not settings.api_key:
        raise LLMProviderError(f"{settings.provider.api_key_env} is not configured")

    if settings.llm_provider == "gemini":
        return await _generate_json_gemini(settings, system_prompt, user_prompt, model, temperature, max_tokens)

    return await _generate_json_openai_compatible(settings, system_prompt, user_prompt, model, temperature, max_tokens)


async def chat(
    messages: List[Dict[str, str]],
    *,
    system_prompt: str,
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> LLMTextResult:
    settings = get_settings()
    model = model_name or settings.chat_model

    if not settings.api_key:
        raise LLMProviderError(f"{settings.provider.api_key_env} is not configured")

    if settings.llm_provider == "gemini":
        return await _chat_gemini(settings, system_prompt, messages, model, temperature, max_tokens)

    return await _chat_openai_compatible(settings, system_prompt, messages, model, temperature, max_tokens)


async def _generate_json_openai_compatible(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> LLMJsonResult:
    from openai import AsyncOpenAI

    default_headers = {}
    if settings.llm_provider == "openrouter":
        default_headers = {
            "HTTP-Referer": "http://127.0.0.1:8000",
            "X-Title": "AI Learning Path Personalizer",
        }

    client = AsyncOpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=settings.request_timeout_seconds,
        default_headers=default_headers or None,
    )

    prompt = user_prompt
    if not settings.provider.supports_json_mode:
        prompt = (
            f"{user_prompt}\n\n"
            "Return only one valid JSON object. Do not wrap it in Markdown. "
            "Do not include explanations outside the JSON object."
        )

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if settings.provider.supports_json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    async def _call():
        return await client.chat.completions.create(**kwargs)

    response = await _with_retries("LLM JSON call", _call, settings)
    content = response.choices[0].message.content or ""
    input_tokens, output_tokens = _usage_from_openai_response(response, system_prompt + prompt, content)
    return LLMJsonResult(
        data=parse_json_object(content),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_name=model,
        provider_name=settings.llm_provider,
    )


async def _chat_openai_compatible(
    settings: Settings,
    system_prompt: str,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> LLMTextResult:
    from openai import AsyncOpenAI

    default_headers = {}
    if settings.llm_provider == "openrouter":
        default_headers = {
            "HTTP-Referer": "http://127.0.0.1:8000",
            "X-Title": "AI Learning Path Personalizer",
        }

    client = AsyncOpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=settings.request_timeout_seconds,
        default_headers=default_headers or None,
    )
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    async def _call():
        return await client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    response = await _with_retries("LLM chat call", _call, settings)
    content = response.choices[0].message.content or ""
    input_tokens, output_tokens = _usage_from_openai_response(response, json.dumps(full_messages), content)
    return LLMTextResult(
        content=content.strip(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_name=model,
        provider_name=settings.llm_provider,
    )


async def _generate_json_gemini(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> LLMJsonResult:
    try:
        import google.generativeai as genai
    except ImportError as err:
        raise LLMProviderError("google-generativeai package is not installed") from err

    def _call_sync():
        genai.configure(api_key=settings.api_key)
        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json",
                max_output_tokens=max_tokens,
            ),
        )
        return gemini_model.generate_content(user_prompt)

    response = await _with_retries("Gemini JSON call", lambda: asyncio.to_thread(_call_sync), settings)
    content = getattr(response, "text", "") or ""
    input_tokens, output_tokens = _usage_from_gemini_response(response, system_prompt + user_prompt, content)
    return LLMJsonResult(
        data=parse_json_object(content),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_name=model,
        provider_name=settings.llm_provider,
    )


async def _chat_gemini(
    settings: Settings,
    system_prompt: str,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> LLMTextResult:
    try:
        import google.generativeai as genai
    except ImportError as err:
        raise LLMProviderError("google-generativeai package is not installed") from err

    def _call_sync():
        genai.configure(api_key=settings.api_key)
        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        history = []
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})

        chat_session = gemini_model.start_chat(history=history)
        last_message = messages[-1]["content"] if messages else ""
        return chat_session.send_message(last_message)

    response = await _with_retries("Gemini chat call", lambda: asyncio.to_thread(_call_sync), settings)
    content = getattr(response, "text", "") or ""
    input_tokens, output_tokens = _usage_from_gemini_response(response, json.dumps(messages), content)
    return LLMTextResult(
        content=content.strip(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_name=model,
        provider_name=settings.llm_provider,
    )
