"""
====================================================
  API Endpoint: /api/chat
  Conversational AI with Thought→Action→Observation trace
  VinUni AI20k Batch 02 · Day 06
====================================================

Every request runs through 7 traced steps:
  Step 1 — check_rate_limit
  Step 2 — check_guardrails
  Step 3 — check_quiz_gate
  Step 4 — check_daily_cost
  Step 5 — load_conversation_history
  Step 6 — call_llm
  Step 7 — save_session
"""

import os
import time
import logging
import asyncio
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.llm_client import LLMError, generate_chat_response, get_model_name, get_provider, is_local_model
from app.trace import AgentTrace
from middleware.cost_logger import log_cost, is_user_rate_limited
from middleware.data_masking import mask_sensitive_data
from middleware.guardrails import guardrail_manager
from models.database import upsert_session, get_session

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Configuration ──────────────────────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))
MIN_QUIZ_QUESTIONS    = 3
MAX_HISTORY_TURNS     = 10

# In-memory rate limit store: {user_id: deque of timestamps}
_rate_limit_store: Dict[str, deque] = defaultdict(lambda: deque())
_rate_limit_lock = asyncio.Lock()

# ── Pydantic models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id:            str  = Field(..., description="User identifier")
    message:            str  = Field(..., min_length=1, max_length=2000)
    session_id:         str  = Field(..., description="Session identifier")
    quiz_completed:     bool = Field(False)
    questions_answered: int  = Field(0, ge=0)
    model_override:     Optional[str] = Field(None)


class ChatResponse(BaseModel):
    response:     str
    session_id:   str
    tokens_used:  Dict[str, int]
    cost:         Dict[str, Any]
    blocked:      bool = False
    block_reason: Optional[str] = None
    model_info:   Optional[Dict[str, Any]] = None
    trace:        Optional[Dict[str, Any]] = None   # Thought→Action→Observation trace


# ── Rate limiter ───────────────────────────────────────────────────────────────

async def _check_rate_limit(user_id: str) -> bool:
    """Return True if user is rate-limited (too many messages)."""
    async with _rate_limit_lock:
        now = time.time()
        window_start = now - 60.0
        timestamps = _rate_limit_store[user_id]
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()
        if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
            return True
        timestamps.append(now)
        return False


def _messages_used(user_id: str) -> int:
    """How many messages used in current 60-second window (without adding a new one)."""
    now = time.time()
    window_start = now - 60.0
    q = _rate_limit_store[user_id]
    return sum(1 for t in q if t >= window_start)


# ── Chat system prompt ─────────────────────────────────────────────────────────

CHAT_SYSTEM_PROMPT = (
    "Bạn là trợ lý AI chuyên về học tập và phát triển kỹ năng AI/ML tại VinUni. "
    "Hãy trả lời ngắn gọn, thực tế và động viên người dùng. "
    "Nếu người dùng hỏi ngoài chủ đề học tập AI, nhẹ nhàng hướng họ về đúng hướng.\n\n"
    "You are an AI learning assistant. Be concise, practical, and encouraging."
)


async def _call_chat_llm(messages: List[Dict[str, str]], model_name: str) -> Dict[str, Any]:
    full_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + messages
    try:
        return await generate_chat_response(full_messages, model_name)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unexpected LLM error: {exc}") from exc


# ── Main endpoint ──────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, summary="Conversational AI chat with trace")
async def chat(payload: ChatRequest):
    """
    7-step traced chat endpoint.

    Thought → Action → Observation for each step:
      1. check_rate_limit
      2. check_guardrails
      3. check_quiz_gate
      4. check_daily_cost   (skipped for local models)
      5. load_conversation_history
      6. call_llm
      7. save_session
    """
    user_id    = payload.user_id
    session_id = payload.session_id
    message    = mask_sensitive_data(payload.message.strip())
    model_name = get_model_name(payload.model_override)
    provider   = get_provider(model_name)
    is_local   = is_local_model(model_name)

    trace = AgentTrace(session_id=session_id, user_id=user_id, user_message=message)

    def _model_info() -> Dict[str, Any]:
        return {
            "model": model_name,
            "provider": provider,
            "is_local": is_local,
            "question_limit": None if is_local else RATE_LIMIT_PER_MINUTE,
        }

    def _empty_cost() -> Dict[str, Any]:
        return {"request_cost_usd": 0.0, "daily_cost_usd": 0.0, "rate_limited": False}

    # ── Step 1: Rate limit ────────────────────────────────────────────────────
    step1 = trace.begin(
        thought=(
            f"Kiểm tra rate limit cho user '{user_id}'. "
            f"Giới hạn: {RATE_LIMIT_PER_MINUTE} msg/phút. "
            f"Local model → bỏ qua giới hạn."
            if is_local else
            f"Kiểm tra rate limit cho user '{user_id}'. "
            f"Giới hạn: {RATE_LIMIT_PER_MINUTE} msg/phút."
        ),
        action="check_rate_limit",
        user_id=user_id,
        limit_per_minute=RATE_LIMIT_PER_MINUTE,
        is_local_model=is_local,
    )

    if is_local:
        trace.ok(step1, f"Rate limit SKIPPED — local model '{model_name}' has no message cap.")
    elif await _check_rate_limit(user_id):
        used = _messages_used(user_id)
        trace.block(step1, f"Rate limit EXCEEDED: {used}/{RATE_LIMIT_PER_MINUTE} messages in last 60s.")
        trace.finish("blocked", "rate_limit_exceeded")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": (
                    f"Bạn đã gửi quá {RATE_LIMIT_PER_MINUTE} tin nhắn trong 1 phút. "
                    "Vui lòng chờ một chút trước khi tiếp tục."
                ),
                "trace": trace.to_dict(),
            },
        )
    else:
        used = _messages_used(user_id)
        trace.ok(step1, f"Rate limit OK — {used}/{RATE_LIMIT_PER_MINUTE} messages used in last 60s.")

    # ── Step 2: Guardrails ────────────────────────────────────────────────────
    step2 = trace.begin(
        thought=(
            "Kiểm tra nội dung tin nhắn qua bộ lọc guardrail: "
            "banned keywords, jailbreak patterns, spam, out-of-scope."
        ),
        action="check_guardrails",
        message_preview=message[:80],
        rules="banned_keywords + jailbreak_patterns + spam_detection",
    )

    guard_result = guardrail_manager.check_message(message)
    if guard_result and guard_result.get("blocked"):
        reason       = guard_result.get("reason", "blocked")
        block_resp   = guard_result.get("response", "[Yêu cầu bị từ chối]")
        trace.block(step2, f"Guardrail TRIGGERED — reason: {reason}")
        trace.finish("blocked", reason)
        logger.warning("[%s] 🚫 Guardrail blocked user '%s': %s", session_id, user_id, reason)
        return ChatResponse(
            response=block_resp,
            session_id=session_id,
            tokens_used={"input": 0, "output": 0, "total": 0},
            cost=_empty_cost(),
            blocked=True,
            block_reason=reason,
            model_info=_model_info(),
            trace=trace.to_dict(),
        )
    trace.ok(step2, "Guardrail PASSED — no violations detected.")

    # ── Step 3: Quiz gate ─────────────────────────────────────────────────────
    questions_answered = payload.questions_answered
    quiz_completed     = payload.quiz_completed

    session_data = get_session(session_id)
    if session_data:
        questions_answered = max(questions_answered, session_data.get("questions_answered", 0))
        quiz_completed     = quiz_completed or bool(session_data.get("quiz_completed", False))

    step3 = trace.begin(
        thought=(
            f"Kiểm tra quiz gate — user phải trả lời ít nhất {MIN_QUIZ_QUESTIONS} câu "
            "trước khi chat để AI có đủ ngữ cảnh cá nhân hóa phản hồi."
        ),
        action="check_quiz_gate",
        quiz_completed=quiz_completed,
        questions_answered=questions_answered,
        min_required=MIN_QUIZ_QUESTIONS,
    )

    if not quiz_completed and questions_answered < MIN_QUIZ_QUESTIONS:
        obs = (
            f"Quiz gate BLOCKED — {questions_answered}/{MIN_QUIZ_QUESTIONS} "
            "questions answered. Chưa đủ ngữ cảnh để chat."
        )
        trace.block(step3, obs)
        trace.finish("blocked", "quiz_not_completed")
        return ChatResponse(
            response=(
                f"👋 Chào bạn! Để tôi có thể hỗ trợ tốt hơn, "
                f"bạn cần hoàn thành ít nhất {MIN_QUIZ_QUESTIONS} câu hỏi khảo sát trước nhé.\n"
                f"Bạn đã trả lời {questions_answered}/{MIN_QUIZ_QUESTIONS} câu. "
                f"Hãy quay lại phần khảo sát để tiếp tục! 📝"
            ),
            session_id=session_id,
            tokens_used={"input": 0, "output": 0, "total": 0},
            cost=_empty_cost(),
            blocked=True,
            block_reason="quiz_not_completed",
            model_info=_model_info(),
            trace=trace.to_dict(),
        )
    trace.ok(
        step3,
        f"Quiz gate PASSED — {questions_answered} questions answered, completed={quiz_completed}."
    )

    # ── Step 4: Daily cost limit (cloud models only) ──────────────────────────
    if not is_local:
        max_usd = os.getenv("MAX_DAILY_COST_USD", "1.00")
        step4 = trace.begin(
            thought=(
                f"Kiểm tra giới hạn chi phí ngày (tối đa ${max_usd}/ngày/user) "
                "để kiểm soát API costs. Bỏ qua cho local model."
            ),
            action="check_daily_cost",
            user_id=user_id,
            max_daily_cost_usd=max_usd,
            model=model_name,
        )
        if is_user_rate_limited(user_id):
            trace.block(step4, f"Daily cost EXCEEDED — user '{user_id}' reached ${max_usd} limit today.")
            trace.finish("blocked", "daily_cost_limit_exceeded")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "daily_cost_limit_exceeded",
                    "message": "Bạn đã vượt giới hạn chi phí ngày hôm nay. Vui lòng thử lại vào ngày mai.",
                    "trace": trace.to_dict(),
                },
            )
        trace.ok(step4, f"Daily cost OK — within ${max_usd} daily limit.")

    # ── Step 5: Load conversation history ─────────────────────────────────────
    conversation_history: List[Dict[str, str]] = []

    step5 = trace.begin(
        thought=(
            "Tải lịch sử hội thoại từ database để duy trì ngữ cảnh. "
            f"Giữ tối đa {MAX_HISTORY_TURNS} lượt gần nhất."
        ),
        action="load_conversation_history",
        session_id=session_id,
        max_turns=MAX_HISTORY_TURNS,
    )
    try:
        if session_data and session_data.get("conversation_history"):
            history = session_data["conversation_history"]
            # Keep only the most recent turns to avoid context overflow
            if len(history) > MAX_HISTORY_TURNS * 2:
                history = history[-(MAX_HISTORY_TURNS * 2):]
            conversation_history = history
        turns_loaded = len(conversation_history) // 2  # pairs of user+assistant
        trace.ok(step5, f"Loaded {len(conversation_history)} messages ({turns_loaded} turns) from session history.")
    except Exception as exc:
        trace.error(step5, f"History load failed: {exc}", "Continuing with empty history.")
        logger.error("[%s] Failed to load conversation history: %s", session_id, exc)
        conversation_history = []

    conversation_history.append({"role": "user", "content": message})

    # ── Step 6: Call LLM ──────────────────────────────────────────────────────
    step6 = trace.begin(
        thought=(
            f"Gọi LLM '{model_name}' (provider={provider}) để tạo phản hồi. "
            f"Context: {len(conversation_history)} messages. Temperature=0.7."
        ),
        action="call_llm",
        model=model_name,
        provider=provider,
        is_local=is_local,
        messages_in_context=len(conversation_history),
        temperature=0.7,
    )

    logger.info("[%s] 💬 LLM call — user='%s' model='%s'", session_id, user_id, model_name)

    try:
        llm_result    = await _call_chat_llm(conversation_history, model_name)
        ai_response   = llm_result["content"]
        input_tokens  = llm_result.get("input_tokens", 0)
        output_tokens = llm_result.get("output_tokens", 0)

        if not ai_response:
            raise LLMError("LLM returned an empty response.")

        trace.ok(
            step6,
            f"LLM responded — {input_tokens} input + {output_tokens} output tokens. "
            f"Response length: {len(ai_response)} chars."
        )

    except HTTPException as exc:
        # Already wrapped by _call_chat_llm — re-raise with trace attached
        raw_detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        trace.error(step6, raw_detail)
        trace.finish("error", raw_detail)
        logger.error("[%s] ❌ LLM call failed: %s", session_id, raw_detail)
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": "llm_call_failed",
                "provider": provider,
                "model": model_name,
                "message": raw_detail,
                "hint": (
                    "Ollama không phản hồi. Chạy `ollama serve` rồi thử lại."
                    if provider == "ollama" else
                    "Kiểm tra API key và kết nối mạng."
                ),
                "trace": trace.to_dict(),
            },
        ) from exc

    except LLMError as exc:
        trace.error(step6, str(exc))
        trace.finish("error", str(exc))
        logger.error("[%s] ❌ LLMError: %s", session_id, exc)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "llm_error",
                "provider": provider,
                "model": model_name,
                "message": str(exc),
                "hint": (
                    "Ollama không phản hồi. Kiểm tra `ollama serve`."
                    if provider == "ollama" else
                    "Kiểm tra API key."
                ),
                "trace": trace.to_dict(),
            },
        ) from exc

    except Exception as exc:
        error_msg = f"Unexpected error during LLM call: {type(exc).__name__}: {exc}"
        trace.error(step6, error_msg)
        trace.finish("error", error_msg)
        logger.error("[%s] ❌ Unexpected LLM error: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "llm_unexpected_error",
                "provider": provider,
                "model": model_name,
                "message": error_msg,
                "trace": trace.to_dict(),
            },
        ) from exc

    # Low-confidence fallback note
    _uncertainty_kw = [
        "tôi không biết", "tôi không chắc", "nằm ngoài phạm vi",
        "không thể trả lời", "không thuộc chuyên môn", "không rõ",
        "chưa có câu trả lời", "sorry, i don't know",
        "i'm not sure", "out of scope", "i cannot answer",
    ]
    if any(kw in ai_response.lower() for kw in _uncertainty_kw):
        ai_response += (
            "\n\n---"
            "\n💡 *Câu hỏi này có vẻ nằm ngoài phạm vi học tập của tôi. "
            "Liên hệ Cố vấn VinUni: "
            "[ai-support@vinuni.edu.vn](mailto:ai-support@vinuni.edu.vn) "
            "hoặc bấm nút 🛠️ để được hỗ trợ.*"
        )

    # ── Step 7: Save session ──────────────────────────────────────────────────
    step7 = trace.begin(
        thought=(
            "Lưu lịch sử hội thoại cập nhật vào database và ghi log chi phí token."
        ),
        action="save_session",
        session_id=session_id,
        total_messages=len(conversation_history) + 1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    try:
        conversation_history.append({"role": "assistant", "content": ai_response})
        upsert_session(
            session_id=session_id,
            user_id=user_id,
            quiz_completed=quiz_completed,
            questions_answered=questions_answered,
            conversation_history=conversation_history,
        )
        cost_info = log_cost(
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=model_name,
            endpoint="/api/chat",
            quiz_score=f"{questions_answered}/10",
            intent_detected="chat_conversation",
        )
        trace.ok(
            step7,
            f"Session saved — {len(conversation_history)} messages persisted. "
            f"Cost: ${cost_info['calculated_cost']:.6f} | Daily: ${cost_info['daily_cost_total']:.4f}."
        )
    except Exception as exc:
        trace.error(step7, f"Save failed: {exc}", "Response still returned to user.")
        logger.error("[%s] Failed to save session or log cost: %s", session_id, exc, exc_info=True)
        cost_info = {"calculated_cost": 0.0, "daily_cost_total": 0.0, "rate_limited": False}

    trace.finish("success")
    logger.info("[%s] ✅ Chat complete — cost=$%.6f", session_id, cost_info["calculated_cost"])

    return ChatResponse(
        response=ai_response,
        session_id=session_id,
        tokens_used={
            "input":  input_tokens,
            "output": output_tokens,
            "total":  input_tokens + output_tokens,
        },
        cost={
            "request_cost_usd": cost_info["calculated_cost"],
            "daily_cost_usd":   cost_info["daily_cost_total"],
            "rate_limited":     cost_info["rate_limited"],
        },
        model_info=_model_info(),
        trace=trace.to_dict(),
    )


# ── Model config endpoint ──────────────────────────────────────────────────────

@router.get("/model-config", summary="Current LLM model and rate limit policy")
async def model_config(model_override: Optional[str] = None):
    name     = get_model_name(model_override)
    prov     = get_provider(name)
    local    = is_local_model(name)
    return {
        "model":               name,
        "provider":            prov,
        "is_local":            local,
        "question_limit":      None if local else RATE_LIMIT_PER_MINUTE,
        "unlimited_questions": local,
    }
