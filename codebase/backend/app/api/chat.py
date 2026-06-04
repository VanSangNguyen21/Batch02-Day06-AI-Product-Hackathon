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
import re
import asyncio
import logging
from collections import defaultdict, deque
import json
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, ConfigDict

from app.llm_client import LLMError, generate_chat_response, get_model_name, get_provider, is_local_model
from app.trace import AgentTrace
from middleware.cost_logger import log_cost, is_user_rate_limited
from middleware.data_masking import mask_sensitive_data
from middleware.guardrails import guardrail_manager
from middleware.auth import Role, get_role_limits
from app.api.auth import get_current_session, require_session_role, _Session
from app.llm_providers import resolve_config, chat_ollama, LLMProvider
import requests
import base64
from openai import OpenAI, AsyncOpenAI

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from middleware.cost_logger import log_cost, is_user_rate_limited
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
    """Yêu cầu chat / Chat request payload."""
    model_config = {"protected_namespaces": ()}

    user_id:          str  = Field(..., description="ID người dùng / User identifier")
    message:          str  = Field(..., min_length=1, max_length=2000, description="Tin nhắn người dùng / User message")
    session_id:       str  = Field(..., description="ID phiên hội thoại / Session identifier")
    quiz_completed:   bool = Field(False, description="Người dùng đã hoàn thành quiz chưa / Whether quiz is complete")
    questions_answered: int = Field(0, ge=0, description="Số câu quiz đã trả lời / Number of quiz questions answered")
    model_override:  Optional[str] = Field(None, description="Ghi đè mô hình / Override model")


class ChatResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    response:     str
    session_id:   str
    tokens_used:  Dict[str, int]
    cost:         Dict[str, Any]
    blocked:      bool = False
    block_reason: Optional[str] = None
    model_info:   Optional[Dict[str, Any]] = None
    trace:        Optional[Dict[str, Any]] = None   # Thought→Action→Observation trace


# ── Rate limiter ───────────────────────────────────────────────────────────────

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
            logger.warning(f" Guardrail triggered for pattern: {pattern.pattern}")
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


async def call_chat_llm(
    messages: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Gọi LLM cho hội thoại chat.
    Dispatch theo LLM_PROVIDER env (openai | ollama | gemini | nvidia | deepseek).
    """
    cfg = resolve_config()
    full_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + messages

    if cfg.provider == LLMProvider.OLLAMA:
        try:
            logger.info(f"Ollama chat at {cfg.base_url} with model {cfg.model}")
            return await chat_ollama(full_messages, cfg, temperature=0.7, max_tokens=1024)
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")

    if cfg.provider == LLMProvider.GEMINI:
        return await _call_gemini_chat(full_messages, cfg.model)

    # OpenAI / NVIDIA / DeepSeek
    return await _call_openai_chat(full_messages, cfg.model)


async def _call_chat_llm(messages: List[Dict[str, str]], model_name: str) -> Dict[str, Any]:
    full_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + messages
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        
        # Override API key for Nvidia models or if using Nvidia base URL
        if "nvidia" in model_name.lower() or "nemotron" in model_name.lower() or "nvidia" in base_url.lower():
            api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1")

        if not api_key:
            raise HTTPException(status_code=500, detail="API key not configured")

        # Chèn system message / Prepend system message
        full_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + messages

        try:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            kwargs = {
                "model": model_name,
                "messages": full_messages,
                "temperature": 0.7,
                "max_tokens": 1024,
            }

            # Handle DeepSeek specific prompt kwargs
            if "deepseek" in model_name.lower():
                kwargs["extra_body"] = {"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}}

            response = await client.chat.completions.create(**kwargs)
            
            # Check for reasoning/thinking block if any
            reasoning = getattr(response.choices[0].message, "reasoning", None) or getattr(response.choices[0].message, "reasoning_content", None)
            content = response.choices[0].message.content
            if reasoning:
                content = f"> **Thinking:**\n> {reasoning.strip()}\n\n{content}"

            return {
                "content":       content,
                "input_tokens":  response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            }
        except Exception as api_err:
            logger.warning(f"AsyncOpenAI failed, trying requests fallback: {api_err}")
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "model": model_name,
                "messages": full_messages,
                "temperature": 0.7,
                "max_tokens": 1024,
            }
            if "deepseek" in model_name.lower():
                payload["extra_body"] = {"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}}
                
            loop = asyncio.get_event_loop()
            
            def _post():
                url = f"{base_url.rstrip('/')}/chat/completions"
                return requests.post(url, headers=headers, json=payload, timeout=30)
                
            res = await loop.run_in_executor(None, _post)
            if res.status_code != 200:
                raise Exception(f"HTTP {res.status_code}: {res.text}")
                
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            
            reasoning = data["choices"][0]["message"].get("reasoning_content") or data["choices"][0]["message"].get("reasoning")
            if reasoning:
                content = f"> **Thinking:**\n> {reasoning.strip()}\n\n{content}"
                
            usage = data.get("usage", {})
            return {
                "content": content,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0)
            }

    except Exception as e:
        logger.error(f"OpenAI/Nvidia chat error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")


# ── Main endpoint ──────────────────────────────────────────────────────────────

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=CHAT_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1024,
            ),
        )

        # Chuyển đổi định dạng messages cho Gemini / Convert message format for Gemini
        gemini_history = []
        for msg in messages[:-1]:  # Tất cả trừ tin nhắn cuối / All except last
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        chat = model.start_chat(history=gemini_history)
        # Gửi tin nhắn cuối cùng / Send the last message
        last_message = messages[-1]["content"] if messages else ""
        response = chat.send_message(last_message)

        input_tokens  = response.usage_metadata.prompt_token_count     if response.usage_metadata else 100
        output_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 50

        return {
            "content":       response.text,
            "input_tokens":  input_tokens,
            "output_tokens": output_tokens,
        }
    except ImportError:
        raise HTTPException(status_code=500, detail="google-generativeai package not installed")
    except Exception as e:
        logger.error(f"Gemini chat error: {e}")
        raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# Offline fallback khi LLM không khả dụng
# ──────────────────────────────────────────────────────────────────────────────

def _offline_chat_fallback(conversation_history: List[Dict[str, str]]) -> str:
    """
    Trả lời offline dựa trên từ khoá khi LLM API không hoạt động.
    Used when Ollama/OpenAI/Gemini endpoints fail or are not configured.
    """
    last_user_msg = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    msg_lower = last_user_msg.lower()

    if any(kw in msg_lower for kw in ["python", "lap trinh", "code", "coding"]):
        return (
            "Python cho AI/ML — lo trinh goi y:\n\n"
            "1. Python co ban: bien, vong lap, ham, OOP\n"
            "2. NumPy — tinh toan ma tran hieu qua\n"
            "3. Pandas — xu ly du lieu bang\n"
            "4. Matplotlib / Seaborn — truc quan hoa\n\n"
            "Tai nguyen mien phi: Kaggle Learn, CS50P Harvard."
        )
    if any(kw in msg_lower for kw in ["deep learning", "neural", "dl", "mang noron"]):
        return (
            "Deep Learning nam o Giai doan 3 trong lo trinh cua ban. "
            "Bat dau voi MLP / Backpropagation, sau do toi CNN (thi giac) "
            "va Transformer (NLP/LLM). Tai nguyen: fast.ai, DeepLearning.AI."
        )
    if any(kw in msg_lower for kw in ["tai lieu", "sach", "course", "khoa hoc", "hoc o dau"]):
        return (
            "Tai nguyen hoc AI goi y:\n\n"
            "- Coursera — Machine Learning Specialization (Andrew Ng)\n"
            "- fast.ai — Practical Deep Learning\n"
            "- Google ML Crash Course\n"
            "- Kaggle Learn (mien phi)\n"
            "- 'Hands-On ML' — Aurelien Geron (sach)"
        )
    if any(kw in msg_lower for kw in ["bao lau", "thoi gian", "how long"]):
        return (
            "Voi lich hoc deu dan (4–10 gio/tuan), lo trinh 4 giai doan "
            "thuong mat khoang 6–9 thang de hoan thanh. Ban co the di nhanh hon "
            "neu da co nen tang toan/lap trinh vung."
        )
    if any(kw in msg_lower for kw in ["lo trinh", "roadmap", "ke hoach", "buoc"]):
        return (
            "Lo trinh cua ban gom 4 giai doan:\n"
            "1. Nen tang Toan & Python\n"
            "2. Machine Learning co ban\n"
            "3. Deep Learning & Neural Networks\n"
            "4. Du an thuc te & Trien khai\n\n"
            "Ban co the xem chi tiet trong tab Lo trinh hoc."
        )
    return (
        "Xin chao! Hien tai may chu AI dang ban (che do offline). "
        "Duoi day la vai goi y chung:\n\n"
        "- Tap trung vao milestone dang active trong lo trinh\n"
        "- Thuc hanh code moi ngay, du chi 30 phut\n"
        "- Hoi cu the ve Python / ML / Deep Learning / tai lieu de nhan cau tra loi chinh xac hon."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint chính / Main endpoint
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, summary="Conversational AI chat")
async def chat(payload: ChatRequest, sess: _Session = Depends(require_session_role(Role.STUDENT, Role.PREMIUM, Role.ADMIN))):
    """
    7-step traced chat endpoint.

    **Quy trình / Flow:**
    1. Role check: STUDENT / PREMIUM / ADMIN
    2. Rate limit check: per-role (STUDENT=5, PREMIUM=20, ADMIN=60 msg/min)
    3. Guardrail check: từ khóa & regex
    4. Quiz gate: nếu chưa trả lời đủ 3 câu → chặn thân thiện
    5. Daily cost check
    6. Tải lịch sử hội thoại từ DB / Load conversation history from DB
    7. Gọi LLM / Call LLM
    8. Lưu lịch sử + ghi chi phí / Save history + log cost
    """
    user_id    = payload.user_id
    session_id = payload.session_id
    message    = mask_sensitive_data(payload.message.strip())
    model_name = payload.model_override or os.getenv("MODEL_NAME", "gpt-4o")
    role       = sess.role
    limits     = get_role_limits(role)
    logger.info(f"Chat request | user={user_id} role={role.value} rate_limit={limits['rate_per_minute']}/min cost_limit=${limits['daily_cost_usd']}/day")

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
        reason = guard_result.get("reason", "blocked")
        response_text = guard_result.get("response", "[Yêu cầu truy cập thông tin hệ thống bị từ chối do vi phạm quy tắc an toàn quốc tế]")
        logger.info(f" Message blocked for user '{user_id}': {reason}")
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

    if not quiz_completed and questions_answered < MIN_QUIZ_QUESTIONS:
        friendly_block = (
            f" Chào bạn! Để tôi có thể hỗ trợ tốt hơn, "
            f"bạn cần hoàn thành ít nhất {MIN_QUIZ_QUESTIONS} câu hỏi khảo sát trước nhé.\n"
            f"Bạn đã trả lời {questions_answered}/{MIN_QUIZ_QUESTIONS} câu. "
            f"Hãy quay lại phần khảo sát để tiếp tục! \n\n"
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
        )

    # ── Bước 4: Kiểm tra chi phí ngày / Step 4: Daily cost limit ─────────────
    if is_user_rate_limited(user_id):
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
    logger.info(f"Chat LLM call for user '{user_id}' | session='{session_id}' | model='{model_name}'")
    try:
        llm_result   = await call_chat_llm(conversation_history)
        ai_response  = llm_result["content"]
        input_tokens = llm_result["input_tokens"]
        output_tokens = llm_result["output_tokens"]
    except HTTPException as http_err:
        logger.warning(f"LLM API failed for chat ({http_err.detail}); using offline fallback")
        ai_response = _offline_chat_fallback(conversation_history)
        input_tokens  = sum(len(str(m.get("content", ""))) for m in conversation_history) // 4
        output_tokens = len(ai_response) // 4
    except Exception as e:
        logger.error(f"Unexpected chat LLM error: {e}; using offline fallback")
        ai_response = _offline_chat_fallback(conversation_history)
        input_tokens  = sum(len(str(m.get("content", ""))) for m in conversation_history) // 4
        output_tokens = len(ai_response) // 4

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
        logger.info(f" Detected low-confidence/uncertain AI chat response for user '{user_id}'. Appending human fallback information.")
        ai_response += (
            "\n\n---"
            "\n *Chú ý: Câu hỏi này có vẻ nằm ngoài phạm vi học tập thông thường của tôi hoặc tôi chưa hoàn toàn chắc chắn. "
            "Nếu bạn cần thêm thông tin chính xác, bạn có thể liên hệ trực tiếp với Cố vấn học tập VinUni qua email: "
            "[ai-support@vinuni.edu.vn](mailto:ai-support@vinuni.edu.vn) hoặc bấm nút Trợ giúp (biểu tượng  ở góc trên bên phải) để được hỗ trợ.*"
        )

    # ── Bước 7: Lưu lịch sử & ghi chi phí / Step 7: Save history & log cost ─
    conversation_history.append({"role": "assistant", "content": ai_response})

    upsert_session(
        session_id=session_id,
        user_id=user_id,
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

    logger.info(f" Chat response sent | user='{user_id}' | cost=${cost_info['calculated_cost']:.6f}")

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
