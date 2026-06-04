"""
chat.py - Endpoint chat hội thoại với AI
POST /api/chat: Conversational AI chat with guardrails and rate limiting

Tác giả / Author: AI VinUni Batch02-Day05
"""

import os
import re
import time
import logging
import asyncio
from collections import defaultdict, deque
import json
from typing import List, Optional, Dict, Any

from app.llm_client import LLMError, generate_chat_response, get_model_name, get_provider, is_local_model
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from middleware.cost_logger import log_cost, is_user_rate_limited
from models.database import upsert_session, get_session
from middleware.data_masking import mask_sensitive_data
from middleware.guardrails import guardrail_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# ──────────────────────────────────────────────────────────────────────────────
# Cấu hình / Configuration
# ──────────────────────────────────────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))
MIN_QUIZ_QUESTIONS    = 3   # Số câu tối thiểu phải trả lời / Minimum questions to answer
MAX_HISTORY_TURNS     = 10  # Số lượt hội thoại tối đa lưu trữ / Max conversation turns kept

# ──────────────────────────────────────────────────────────────────────────────
# Bộ nhớ trong cho rate limiting / In-memory rate limiter store
# Cấu trúc: {user_id: deque of timestamps}
# ──────────────────────────────────────────────────────────────────────────────
_rate_limit_store: Dict[str, deque] = defaultdict(lambda: deque())
_rate_limit_lock = asyncio.Lock()


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Yêu cầu chat / Chat request payload."""
    user_id:          str  = Field(..., description="ID người dùng / User identifier")
    message:          str  = Field(..., min_length=1, max_length=2000, description="Tin nhắn người dùng / User message")
    session_id:       str  = Field(..., description="ID phiên hội thoại / Session identifier")
    quiz_completed:   bool = Field(False, description="Người dùng đã hoàn thành quiz chưa / Whether quiz is complete")
    questions_answered: int = Field(0, ge=0, description="Số câu quiz đã trả lời / Number of quiz questions answered")
    model_override:  Optional[str] = Field(None, description="Ghi đè mô hình / Override model")


class ChatResponse(BaseModel):
    """Phản hồi chat / Chat response."""
    response:     str
    session_id:   str
    tokens_used:  Dict[str, int]
    cost:         Dict[str, Any]
    blocked:      bool = False
    block_reason: Optional[str] = None
    model_info:   Optional[Dict[str, Any]] = None


# ──────────────────────────────────────────────────────────────────────────────
# Kiểm tra nội dung / Content guardrails
# ──────────────────────────────────────────────────────────────────────────────

# Danh sách từ khoá gây hại / Harmful keyword list
HARMFUL_KEYWORDS = [
    # Bạo lực / Violence
    r"\b(giết|tự tử|tự sát|chết chóc|vũ khí|bom|nổ)\b",
    # Nội dung người lớn / Adult content
    r"\b(sex|porn|khiêu dâm|18\+)\b",
    # Thông tin cá nhân nhạy cảm / Sensitive personal data
    r"\b(cccd|cmnd|passport|số thẻ tín dụng|credit card)\b",
    # Tấn công hệ thống / System attack attempts
    r"(ignore previous|jailbreak|bypass|as an ai you have no|forget your instructions)",
    # Ngôn từ thù hận / Hate speech
    r"\b(phân biệt chủng tộc|kỳ thị|kỳ thị người)\b",
]

HARMFUL_PATTERNS = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in HARMFUL_KEYWORDS]


def check_guardrails(message: str) -> Optional[str]:
    """
    Kiểm tra nội dung tin nhắn vi phạm
    Check message content against guardrail rules.

    Returns:
        Lý do chặn nếu vi phạm / Block reason string, or None if clean
    """
    for pattern in HARMFUL_PATTERNS:
        if pattern.search(message):
            logger.warning(f"🚫 Guardrail triggered for pattern: {pattern.pattern}")
            return "Tin nhắn chứa nội dung không phù hợp / Message contains inappropriate content"

    # Kiểm tra độ dài bất thường / Check for abnormally long repetitive content
    if len(message) > 1500 and len(set(message.split())) < 20:
        return "Tin nhắn lặp lại bất thường / Abnormally repetitive message"

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Rate limiter
# ──────────────────────────────────────────────────────────────────────────────

async def check_rate_limit(user_id: str) -> bool:
    """
    Kiểm tra giới hạn tốc độ gửi tin nhắn (5 tin/phút per user)
    Check in-memory rate limit (5 messages/minute per user).

    Returns:
        True nếu bị giới hạn / True if rate limited
    """
    async with _rate_limit_lock:
        now = time.time()
        window_start = now - 60.0  # 60 giây / 60 seconds

        timestamps = _rate_limit_store[user_id]

        # Xóa các timestamp cũ hơn 60 giây / Remove timestamps older than 60s
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
            return True  # Đang bị giới hạn / Currently rate limited

        # Thêm timestamp hiện tại / Record current timestamp
        timestamps.append(now)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Hàm gọi LLM / LLM caller (chat)
# ──────────────────────────────────────────────────────────────────────────────

CHAT_SYSTEM_PROMPT = """Bạn là trợ lý AI chuyên về học tập và phát triển kỹ năng. 
Bạn hỗ trợ người dùng trong hành trình học tập AI/ML của họ. 
Hãy trả lời ngắn gọn, thực tế và động viên người dùng.
Nếu người dùng hỏi ngoài chủ đề học tập, hãy nhẹ nhàng hướng họ về đúng hướng.

You are an AI assistant specializing in learning and skill development.
Always be encouraging, practical, and concise."""


async def call_chat_llm(
    messages: List[Dict[str, str]],
    model_name: str,
) -> Dict[str, Any]:
    """
    Gọi LLM cho hội thoại chat
    Call LLM API with conversation history.
    """
    try:
        full_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + messages
        return await generate_chat_response(full_messages, model_name)
    except LLMError as e:
        logger.error(f"Chat LLM error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected chat LLM error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint chính / Main endpoint
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, summary="Conversational AI chat")
async def chat(payload: ChatRequest):
    """
    ## Hội thoại AI với kiểm tra bảo vệ nội dung và giới hạn tốc độ
    ## AI chat with content guardrails and rate limiting

    **Quy trình / Flow:**
    1. Rate limit check: 5 tin nhắn/phút per user_id
    2. Guardrail check: từ khóa & regex
    3. Quiz gate: nếu chưa trả lời đủ 3 câu → chặn thân thiện
    4. Daily cost check
    5. Tải lịch sử hội thoại từ DB / Load conversation history from DB
    6. Gọi LLM / Call LLM
    7. Lưu lịch sử + ghi chi phí / Save history + log cost
    """
    user_id    = payload.user_id
    session_id = payload.session_id
    message    = mask_sensitive_data(payload.message.strip())
    model_name = get_model_name(payload.model_override)
    model_provider = get_provider(model_name)
    uses_local_model = is_local_model(model_name)

    # ── Bước 1: Rate limit / Step 1: Rate limit ──────────────────────────────
    if not uses_local_model and await check_rate_limit(user_id):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": (
                    f"Bạn đã gửi quá {RATE_LIMIT_PER_MINUTE} tin nhắn trong 1 phút. "
                    "Vui lòng chờ một chút trước khi tiếp tục."
                ),
            }
        )

    # ── Bước 2: Guardrail / Step 2: Content guardrail ────────────────────────
    guard_result = guardrail_manager.check_message(message)
    if guard_result and guard_result.get("blocked"):
        reason = guard_result.get("reason", "blocked")
        response_text = guard_result.get("response", "[Yêu cầu truy cập thông tin hệ thống bị từ chối do vi phạm quy tắc an toàn quốc tế]")
        logger.info(f"🚫 Message blocked for user '{user_id}': {reason}")
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            tokens_used={"input": 0, "output": 0, "total": 0},
            cost={"request_cost_usd": 0.0, "daily_cost_usd": 0.0, "rate_limited": False},
            blocked=True,
            block_reason=reason,
            model_info={
                "model": model_name,
                "provider": model_provider,
                "is_local": uses_local_model,
                "question_limit": None if uses_local_model else RATE_LIMIT_PER_MINUTE,
            },
        )

    # ── Bước 3: Quiz gate / Step 3: Quiz completion gate ─────────────────────
    questions_answered = payload.questions_answered
    quiz_completed     = payload.quiz_completed

    # Ưu tiên dữ liệu từ DB nếu có / Prefer DB data if available
    session_data = get_session(session_id)
    if session_data:
        questions_answered = max(questions_answered, session_data.get("questions_answered", 0))
        quiz_completed     = quiz_completed or bool(session_data.get("quiz_completed", False))

    if not quiz_completed and questions_answered < MIN_QUIZ_QUESTIONS:
        friendly_block = (
            f"👋 Chào bạn! Để tôi có thể hỗ trợ tốt hơn, "
            f"bạn cần hoàn thành ít nhất {MIN_QUIZ_QUESTIONS} câu hỏi khảo sát trước nhé.\n"
            f"Bạn đã trả lời {questions_answered}/{MIN_QUIZ_QUESTIONS} câu. "
            f"Hãy quay lại phần khảo sát để tiếp tục! 📝\n\n"
            f"Hi there! To provide you with better support, please complete at least "
            f"{MIN_QUIZ_QUESTIONS} quiz questions first. "
            f"You've answered {questions_answered}/{MIN_QUIZ_QUESTIONS}. "
            f"Please go back to the quiz section to continue!"
        )
        return ChatResponse(
            response=friendly_block,
            session_id=session_id,
            tokens_used={"input": 0, "output": 0, "total": 0},
            cost={"request_cost_usd": 0.0, "daily_cost_usd": 0.0, "rate_limited": False},
            blocked=True,
            block_reason="quiz_not_completed",
            model_info={
                "model": model_name,
                "provider": model_provider,
                "is_local": uses_local_model,
                "question_limit": None if uses_local_model else RATE_LIMIT_PER_MINUTE,
            },
        )

    # ── Bước 4: Kiểm tra chi phí ngày / Step 4: Daily cost limit ─────────────
    if not uses_local_model and is_user_rate_limited(user_id):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_cost_limit_exceeded",
                "message": "Bạn đã vượt giới hạn chi phí ngày hôm nay. Vui lòng thử lại vào ngày mai.",
            }
        )

    # ── Bước 5: Tải lịch sử / Step 5: Load conversation history ──────────────
    conversation_history: List[Dict[str, str]] = []
    if session_data and session_data.get("conversation_history"):
        conversation_history = session_data["conversation_history"]

    # Giữ lại MAX_HISTORY_TURNS lượt gần nhất / Keep only recent turns
    if len(conversation_history) > MAX_HISTORY_TURNS * 2:
        conversation_history = conversation_history[-(MAX_HISTORY_TURNS * 2):]

    # Thêm tin nhắn mới / Add new user message
    conversation_history.append({"role": "user", "content": message})

    # ── Bước 6: Gọi LLM / Step 6: Call LLM ──────────────────────────────────
    logger.info(f"💬 Chat LLM call for user '{user_id}' | session='{session_id}' | model='{model_name}'")
    llm_result = await call_chat_llm(conversation_history, model_name)

    ai_response   = llm_result["content"]
    input_tokens  = llm_result["input_tokens"]
    output_tokens = llm_result["output_tokens"]

    # Phản hồi fallback khi không chắc chắn câu trả lời / Fallback response if AI is uncertain
    uncertainty_keywords = [
        "tôi không biết", "tôi không chắc", "nằm ngoài phạm vi", 
        "không thể trả lời", "không thuộc chuyên môn", "không rõ", 
        "chưa có câu trả lời", "không thể hỗ trợ", "sorry, i don't know", 
        "i'm not sure", "out of scope", "i cannot answer"
    ]
    
    ai_response_lower = ai_response.lower()
    is_uncertain = any(uk in ai_response_lower for uk in uncertainty_keywords)
    
    if is_uncertain:
        logger.info(f"⚠️ Detected low-confidence/uncertain AI chat response for user '{user_id}'. Appending human fallback information.")
        ai_response += (
            "\n\n---"
            "\n💡 *Chú ý: Câu hỏi này có vẻ nằm ngoài phạm vi học tập thông thường của tôi hoặc tôi chưa hoàn toàn chắc chắn. "
            "Nếu bạn cần thêm thông tin chính xác, bạn có thể liên hệ trực tiếp với Cố vấn học tập VinUni qua email: "
            "[ai-support@vinuni.edu.vn](mailto:ai-support@vinuni.edu.vn) hoặc bấm nút Trợ giúp (biểu tượng 🛠️ ở góc trên bên phải) để được hỗ trợ.*"
        )

    # ── Bước 7: Lưu lịch sử & ghi chi phí / Step 7: Save history & log cost ─
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
        intent_detected="chat_conversation"
    )

    logger.info(f"✅ Chat response sent | user='{user_id}' | cost=${cost_info['calculated_cost']:.6f}")

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
        model_info={
            "model": model_name,
            "provider": model_provider,
            "is_local": uses_local_model,
            "question_limit": None if uses_local_model else RATE_LIMIT_PER_MINUTE,
        },
    )


@router.get("/model-config", summary="Current LLM model and question limit policy")
async def model_config(model_override: Optional[str] = None):
    model_name = get_model_name(model_override)
    provider = get_provider(model_name)
    local = is_local_model(model_name)
    return {
        "model": model_name,
        "provider": provider,
        "is_local": local,
        "question_limit": None if local else RATE_LIMIT_PER_MINUTE,
        "unlimited_questions": local,
    }
