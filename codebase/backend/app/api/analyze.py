"""
====================================================
  API Endpoint: /api/analyze
  Phân tích hồ sơ người học và tạo lộ trình cá nhân
  VinUni AI20k Batch 02 · Day 05
====================================================
"""

import os
import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from app.llm_client import LLMError, generate_roadmap, get_model_name, get_provider
from middleware.cost_logger import log_cost
from middleware.data_masking import mask_sensitive_data
from middleware.guardrails import guardrail_manager

logger = logging.getLogger(__name__)
router = APIRouter()

_BASE = os.path.dirname(__file__)

# Rich few-shot prompt — works for all providers (Ollama, Claude, OpenAI)
SYSTEM_PROMPT_PATH = os.path.normpath(os.path.join(_BASE, "..", "..", "..", "prompts", "system_prompt.txt"))
# Backup: simpler backend-local prompt
LOCAL_SYSTEM_PROMPT_PATH = os.path.normpath(os.path.join(_BASE, "..", "..", "prompts", "system_prompt.txt"))


def load_system_prompt(provider: str = "ollama") -> str:
    for path in (SYSTEM_PROMPT_PATH, LOCAL_SYSTEM_PROMPT_PATH):
        try:
            with open(path, "r", encoding="utf-8") as f:
                logger.info(f"📄 Loaded system prompt ({provider}): {path}")
                return f.read()
        except FileNotFoundError:
            continue
    logger.warning("⚠️ No system prompt file found, using minimal default")
    return "You are an AI learning path advisor. Return JSON with milestones."


def save_to_sandbox_storage(data: dict):
    """
    Đẩy dữ liệu của các phiên có độ tự tin AI thấp (< 50%) vào Kho dữ liệu Hộp cát (Sandbox Storage).
    """
    try:
        sandbox_dir = os.path.join(os.path.dirname(SYSTEM_PROMPT_PATH), "..", "backend", "data")
        os.makedirs(sandbox_dir, exist_ok=True)
        sandbox_file = os.path.join(sandbox_dir, "sandbox_storage.jsonl")
        with open(sandbox_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        logger.info(f"📥 Saved low confidence case to Sandbox Storage: {sandbox_file}")
    except Exception as e:
        logger.error(f"❌ Failed to save to Sandbox Storage: {e}")


# ==================== REQUEST/RESPONSE MODELS ====================

class AnalyzeRequest(BaseModel):
    user_id: str
    session_id: str
    goal_description: str = Field(..., min_length=10, max_length=2000)
    quiz_answers: List[Optional[int]] = Field(..., min_length=1, max_length=10)
    time_per_week: str
    current_job: str
    background: Optional[str] = "none"
    quiz_score: Optional[int] = 0


class Milestone(BaseModel):
    milestone_title: str
    duration: str
    resource_links: List[str]
    difficulty: str  # beginner | intermediate | advanced
    description: str


class AnalyzeResponse(BaseModel):
    milestones: List[Milestone]
    confidence_score: float
    path_type: str          # happy | low_conf | failure
    reasoning: str
    personalization_notes: str
    cost_info: dict


# ==================== ENDPOINT ====================

@router.post("/analyze", response_model=AnalyzeResponse, summary="Phân tích hồ sơ và tạo lộ trình học")
async def analyze_profile(req: AnalyzeRequest):
    """
    Nhận thông tin người học từ Form + Quiz, gọi LLM API,
    trả về lộ trình học cá nhân hóa dạng JSON.
    
    Luồng xử lý:
    1. Validate input
    2. Build prompt từ user data
    3. Gọi OpenAI / Gemini API (temperature=0.2, JSON mode)
    4. Parse và validate JSON response
    5. Ghi log chi phí
    6. Xác định path_type dựa trên confidence_score
    7. Return kết quả
    """
    
    # Mask PII data
    req.goal_description = mask_sensitive_data(req.goal_description)
    req.current_job = mask_sensitive_data(req.current_job)
    if req.background:
        req.background = mask_sensitive_data(req.background)
        
    # Guardrail check
    for text_to_check, field_name in [(req.goal_description, "goal_description"), (req.current_job, "current_job")]:
        if text_to_check:
            guard_result = guardrail_manager.check_message(text_to_check)
            if guard_result and guard_result.get("blocked"):
                reason = guard_result.get("reason", "blocked")
                response_text = guard_result.get("response", "Yêu cầu vi phạm quy tắc an toàn.")
                logger.warning(f"🚫 Analyze request blocked due to {field_name}: {reason}")
                raise HTTPException(status_code=400, detail=response_text)

    logger.info(f"📊 Analyze request | user={req.user_id} | job={req.current_job} | score={req.quiz_score}/10")
    
    # Build user context prompt
    quiz_summary = f"Điểm quiz: {req.quiz_score}/10"
    if req.quiz_answers:
        correct_topics = []
        quiz_topics = [
            "Python (Cấu trúc dữ liệu & Immutability)",
            "Python (List comprehension)",
            "Python (Xử lý ngoại lệ try/except)",
            "Lập trình Pandas (Tabular Data)",
            "Thống kê (Mean)",
            "Đại số tuyến tính (Nhân ma trận)",
            "Xác suất có điều kiện (Bayes)",
            "Kiến trúc LLM (Attention/Transformer)",
            "Lý thuyết LLM (Hallucination)",
            "Prompt Engineering"
        ]
        for i, ans in enumerate(req.quiz_answers):
            if ans is not None and i < len(quiz_topics):
                correct_topics.append(quiz_topics[i])
        quiz_summary += f"\nCác topic đã trả lời: {', '.join(correct_topics) if correct_topics else 'Chưa có'}"

    user_prompt = f"""
Hãy phân tích hồ sơ người học SAU ĐÂY và thiết kế lộ trình học AI CÁ NHÂN HÓA RIÊNG BIỆT cho họ.
QUAN TRỌNG: Tạo lộ trình HOÀN TOÀN MỚI dựa trên thông tin cụ thể bên dưới. KHÔNG sao chép các ví dụ mẫu.

THÔNG TIN NGƯỜI HỌC:
- Mục tiêu: {req.goal_description}
- Công việc hiện tại: {req.current_job}
- Thời gian học mỗi tuần: {req.time_per_week}
- Nền tảng kỹ thuật: {req.background}
- {quiz_summary}

Trả về JSON theo đúng schema đã định nghĩa. KHÔNG thêm text ngoài JSON.
"""

    # Gọi LLM API
    model = get_model_name()
    provider = get_provider(model)
    roadmap_data = None
    input_tokens = 0
    output_tokens = 0

    try:
        logger.info(f"🤖 Generating roadmap with model {model} (provider={provider})")
        roadmap_data = await generate_roadmap(load_system_prompt(provider), user_prompt, model)
        usage = roadmap_data.pop("_usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
    except (json.JSONDecodeError, LLMError) as e:
        logger.error(f"❌ LLM roadmap generation failed: {e}")
        roadmap_data = None
    except Exception as e:
        logger.error(f"❌ Unexpected roadmap generation error: {e}")
        roadmap_data = None
    
    # Fallback nếu API không hoạt động hoặc không có key
    if roadmap_data is None:
        logger.warning("⚠️ Dùng fallback roadmap")
        roadmap_data = _get_fallback_roadmap(req.quiz_score, req.background, req.goal_description)
        input_tokens = 0
        output_tokens = 0
    
    # Ghi log chi phí
    confidence_score = float(roadmap_data.get("confidence_score", 0.5))
    cost_info = log_cost(
        user_id=req.user_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_name=model,
        session_id=req.session_id,
        confidence_score=confidence_score,
        endpoint="/api/analyze",
        quiz_score=f"{req.quiz_score}/10" if req.quiz_score is not None else "0/10",
        intent_detected=req.current_job or "none"
    )
    
    # Nếu confidence_score < 50%, lưu vào Sandbox Storage
    if confidence_score < 0.5:
        from datetime import datetime
        try:
            sandbox_data = {
                "user_id": req.user_id,
                "session_id": req.session_id,
                "goal_description": req.goal_description,
                "quiz_answers": req.quiz_answers,
                "quiz_score": req.quiz_score,
                "time_per_week": req.time_per_week,
                "current_job": req.current_job,
                "background": req.background,
                "confidence_score": confidence_score,
                "generated_roadmap": roadmap_data,
                "model_name": model,
                "timestamp": datetime.utcnow().isoformat()
            }
            save_to_sandbox_storage(sandbox_data)
        except Exception as ex:
            logger.error(f"❌ Failed to process sandbox storage save: {ex}")

    # Phân loại path_type dựa trên confidence_score theo đúng quy tắc SPEC:
    # > 0.80 -> "happy"
    # 0.50 - 0.80 -> "low_conf"
    # < 0.50 -> "failure"
    if confidence_score > 0.80:
        path_type = "happy"
    elif confidence_score >= 0.50:
        path_type = "low_conf"
    else:
        path_type = "failure"

    # Validate và trả về kết quả
    try:
        return AnalyzeResponse(
            milestones=[Milestone(**m) for m in roadmap_data.get("milestones", [])],
            confidence_score=confidence_score,
            path_type=path_type,
            reasoning=roadmap_data.get("reasoning", "Phân tích tự động"),
            personalization_notes=roadmap_data.get("personalization_notes", ""),
            cost_info=cost_info
        )
    except Exception as e:
        logger.error(f"❌ Response validation error: {e}")
        raise HTTPException(status_code=500, detail="Lỗi xử lý kết quả AI. Vui lòng thử lại.")


def _get_fallback_roadmap(quiz_score: int, background: str, goal: str) -> dict:
    """Lộ trình mặc định khi API không hoạt động"""
    return {
        "milestones": [
            {
                "milestone_title": "🌱 Nền tảng AI cho người mới",
                "duration": "Tuần 1-2 (4-6 giờ)",
                "resource_links": ["https://www.elementsofai.com", "https://kaggle.com/learn"],
                "difficulty": "beginner",
                "description": "Hiểu AI là gì, ứng dụng thực tế, và bắt đầu hành trình học AI đúng hướng."
            },
            {
                "milestone_title": "📊 Data & Thống kê cơ bản",
                "duration": "Tuần 3-4 (5-8 giờ)",
                "resource_links": ["https://www.khanacademy.org/math/statistics-probability"],
                "difficulty": "beginner",
                "description": "Thống kê mô tả, xác suất cơ bản, biểu đồ dữ liệu. Nền tảng không thể thiếu cho ML."
            },
            {
                "milestone_title": "🛠️ Công cụ AI thực hành",
                "duration": "Tuần 5-6 (5-7 giờ)",
                "resource_links": ["https://openai.com/chatgpt", "https://claude.ai"],
                "difficulty": "intermediate",
                "description": "Thực hành với các AI tools phổ biến, Prompt Engineering cơ bản, ứng dụng vào công việc."
            }
        ],
        "confidence_score": 0.55,
        "path_type": "low_conf",
        "reasoning": "API không khả dụng, hiển thị lộ trình cơ bản chuẩn VinUni.",
        "personalization_notes": "Lộ trình mặc định - chưa được cá nhân hóa."
    }
