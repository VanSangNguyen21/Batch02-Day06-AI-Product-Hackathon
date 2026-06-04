"""
Shared LLM client helpers for roadmap generation and chat.

Supports:
- Ollama local models via the native /api/chat endpoint
- OpenAI-compatible APIs via /v1/chat/completions
- Gemini via google-generativeai
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3.2"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


class LLMError(RuntimeError):
    """Raised when a configured LLM provider cannot complete a request."""


def get_model_name(model_override: Optional[str] = None) -> str:
    return model_override or os.getenv("MODEL_NAME", DEFAULT_MODEL)


def get_provider(model_name: Optional[str] = None) -> str:
    model_lower = (model_name or get_model_name()).lower()
    if model_lower.startswith("ollama/"):
        return "ollama"
    if "gemini" in model_lower:
        return "gemini"
    if any(token in model_lower for token in ("gpt", "deepseek", "nvidia", "nemotron", "openai")):
        return "openai"

    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider in {"ollama", "openai", "gemini"}:
        return provider

    if os.getenv("OLLAMA_BASE_URL"):
        return "ollama"
    return "ollama"


def is_local_model(model_name: Optional[str] = None) -> bool:
    return get_provider(model_name) == "ollama"


def normalize_model_name(model_name: str, provider: Optional[str] = None) -> str:
    if (provider or get_provider(model_name)) == "ollama" and model_name.startswith("ollama/"):
        return model_name.split("/", 1)[1]
    return model_name


def estimate_tokens(text: str) -> int:
    # Lightweight estimate for local providers that do not report usage.
    return max(1, len(text) // 4)


def extract_json_object(raw_content: str) -> Dict[str, Any]:
    content = (raw_content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise
        return json.loads(match.group(0))


def normalize_roadmap_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    milestones = data.get("milestones")
    if not isinstance(milestones, list):
        milestones = []

    normalized_milestones = []
    for item in milestones:
        if not isinstance(item, dict):
            continue
        normalized_milestones.append({
            "milestone_title": str(item.get("milestone_title") or item.get("title") or "Milestone"),
            "duration": str(item.get("duration") or item.get("time") or "1-2 tuần"),
            "resource_links": item.get("resource_links") if isinstance(item.get("resource_links"), list) else [],
            "difficulty": _normalize_difficulty(item.get("difficulty")),
            "description": str(item.get("description") or item.get("desc") or "Cột mốc học tập được cá nhân hóa."),
        })

    confidence = data.get("confidence_score", 0.55)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.55
    confidence = max(0.0, min(confidence, 1.0))

    path_type = str(data.get("path_type") or "").lower()
    if path_type not in {"happy", "low_conf", "failure"}:
        if confidence > 0.80:
            path_type = "happy"
        elif confidence >= 0.50:
            path_type = "low_conf"
        else:
            path_type = "failure"

    return {
        "milestones": normalized_milestones,
        "confidence_score": confidence,
        "path_type": path_type,
        "reasoning": str(data.get("reasoning") or "Phân tích tự động."),
        "personalization_notes": str(data.get("personalization_notes") or ""),
    }


def _normalize_difficulty(value: Any) -> str:
    difficulty = str(value or "beginner").strip().lower()
    if difficulty not in {"beginner", "intermediate", "advanced"}:
        return "beginner"
    return difficulty


async def generate_roadmap(system_prompt: str, user_prompt: str, model_name: Optional[str] = None) -> Dict[str, Any]:
    model = get_model_name(model_name)
    provider = get_provider(model)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if provider == "ollama":
        result = await _call_ollama(messages, model, temperature=0.1, max_tokens=2000, json_mode=True)
    elif provider == "gemini":
        result = await _call_gemini(messages, model, temperature=0.1, max_tokens=2048, json_mode=True)
    else:
        result = await _call_openai_compatible(messages, model, temperature=0.1, max_tokens=2000, json_mode=True)

    data = normalize_roadmap_payload(extract_json_object(result["content"]))
    data["_usage"] = {
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
    }
    return data


async def generate_chat_response(messages: List[Dict[str, str]], model_name: Optional[str] = None) -> Dict[str, Any]:
    model = get_model_name(model_name)
    provider = get_provider(model)

    if provider == "ollama":
        return await _call_ollama(messages, model, temperature=0.7, max_tokens=1024, json_mode=False)
    if provider == "gemini":
        return await _call_gemini(messages, model, temperature=0.7, max_tokens=1024, json_mode=False)
    return await _call_openai_compatible(messages, model, temperature=0.7, max_tokens=1024, json_mode=False)


async def _call_ollama(
    messages: List[Dict[str, str]],
    model_name: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> Dict[str, Any]:
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = normalize_model_name(model_name, "ollama")
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if json_mode:
        payload["format"] = "json"

    try:
        async with httpx.AsyncClient(timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))) as client:
            response = await client.post(f"{base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.ConnectError as exc:
        raise LLMError(
            f"Ollama is not reachable at {base_url}. Start it with `ollama serve` and pull `{model}`."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise LLMError(f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}") from exc
    except Exception as exc:
        raise LLMError(f"Ollama request failed: {exc}") from exc

    content = data.get("message", {}).get("content", "")
    if not content:
        raise LLMError("Ollama returned an empty response.")

    return {
        "content": content,
        "input_tokens": int(data.get("prompt_eval_count") or estimate_tokens(json.dumps(messages, ensure_ascii=False))),
        "output_tokens": int(data.get("eval_count") or estimate_tokens(content)),
    }


async def _call_openai_compatible(
    messages: List[Dict[str, str]],
    model_name: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    if not api_key:
        raise LLMError("OPENAI_API_KEY is not configured.")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        usage = response.usage
        return {
            "content": content,
            "input_tokens": usage.prompt_tokens if usage else estimate_tokens(json.dumps(messages, ensure_ascii=False)),
            "output_tokens": usage.completion_tokens if usage else estimate_tokens(content),
        }
    except Exception as exc:
        raise LLMError(f"OpenAI-compatible request failed: {exc}") from exc


async def _call_gemini(
    messages: List[Dict[str, str]],
    model_name: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("GEMINI_API_KEY is not configured.")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise LLMError("google-generativeai package is not installed.") from exc

    system_prompt = "\n".join(m["content"] for m in messages if m.get("role") == "system")
    user_messages = [m for m in messages if m.get("role") != "system"]
    latest_prompt = user_messages[-1]["content"] if user_messages else ""

    def _generate():
        genai.configure(api_key=api_key)
        generation_config: Dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if json_mode:
            generation_config["response_mime_type"] = "application/json"

        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt or None,
            generation_config=genai.GenerationConfig(**generation_config),
        )

        if len(user_messages) <= 1:
            return model.generate_content(latest_prompt)

        history = []
        for msg in user_messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})
        chat = model.start_chat(history=history)
        return chat.send_message(latest_prompt)

    try:
        response = await asyncio.to_thread(_generate)
    except Exception as exc:
        raise LLMError(f"Gemini request failed: {exc}") from exc

    content = response.text or ""
    usage = getattr(response, "usage_metadata", None)
    return {
        "content": content,
        "input_tokens": getattr(usage, "prompt_token_count", None) or estimate_tokens(json.dumps(messages, ensure_ascii=False)),
        "output_tokens": getattr(usage, "candidates_token_count", None) or estimate_tokens(content),
    }
