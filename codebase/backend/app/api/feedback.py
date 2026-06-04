"""
feedback.py - Endpoint nhận phản hồi từ người dùng
POST /api/feedback: Collect user ratings and flag for human review when needed

Tác giả / Author: AI VinUni Batch02-Day05
"""

import logging
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator

from models.database import insert_feedback, insert_human_review, insert_bad_feedback

logger = logging.getLogger(__name__)

router = APIRouter()

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    """
    Dữ liệu phản hồi từ người dùng
    User feedback submission payload
    """
    user_id:          str   = Field(..., description="ID người dùng / User identifier")
    session_id:       str   = Field(..., description="ID phiên hội thoại / Session identifier")
    rating:           int   = Field(..., ge=1, le=5, description="Đánh giá 1-5 sao / Rating 1-5 stars")
    roadmap_data:     Optional[Dict[str, Any]] = Field(None, description="Dữ liệu lộ trình học tập / Roadmap JSON")
    chat_history:     Optional[List[Dict[str, str]]] = Field(None, description="Lịch sử hội thoại / Chat history")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Điểm tin cậy từ LLM / LLM confidence score")
    report:           bool  = Field(False, description="Người dùng chủ động báo cáo vấn đề / User actively reports an issue")
    comment:          Optional[str] = Field(None, max_length=1000, description="Nhận xét thêm / Additional comment")

    @validator("rating")
    def validate_rating(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


class FeedbackResponse(BaseModel):
    """
    Phản hồi sau khi lưu feedback
    Response after saving feedback
    """
    success:          bool
    feedback_id:      int
    flagged_for_review: bool
    flag_reason:      Optional[str] = None
    message:          str


# ──────────────────────────────────────────────────────────────────────────────
# Hàm kiểm tra cần gắn cờ / Flag decision logic
# ──────────────────────────────────────────────────────────────────────────────

def should_flag_for_review(
    rating: int,
    confidence_score: Optional[float],
    report: bool,
) -> tuple[bool, Optional[str]]:
    """
    Quyết định xem có cần gắn cờ để xem xét thủ công không
    Determine if this feedback should be flagged for human review.

    Điều kiện gắn cờ / Flag conditions:
    1. Đánh giá thấp: rating <= 2
    2. Điểm tin cậy cao + người dùng báo cáo: confidence_score > 0.8 AND report=True
    3. Người dùng chủ động báo cáo khi đánh giá thấp

    Returns:
        (should_flag: bool, reason: Optional[str])
    """
    reasons = []

    # Điều kiện 1: Đánh giá thấp / Low rating
    if rating <= 2:
        reasons.append(f"Đánh giá thấp: {rating}/5 sao")

    # Điều kiện 2: Tin cậy cao + báo cáo / High confidence + user report
    if confidence_score is not None and confidence_score > 0.8 and report:
        reasons.append(
            f"AI tự tin cao ({confidence_score:.0%}) nhưng người dùng báo cáo vấn đề"
        )

    # Điều kiện 3: Chỉ báo cáo (không cần điều kiện khác) / Pure report flag
    if report and not reasons:
        reasons.append("Người dùng chủ động báo cáo vấn đề")

    if reasons:
        return True, " | ".join(reasons)
    return False, None


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint chính / Main endpoint
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/feedback", response_model=FeedbackResponse, summary="Submit user feedback")
async def submit_feedback(payload: FeedbackRequest):
    """
    ## Nhận và lưu phản hồi người dùng, tự động gắn cờ khi cần
    ## Accept and save user feedback, auto-flag for human review when needed

    **Điều kiện gắn cờ xem xét thủ công / Human review flag conditions:**
    - rating ≤ 2  →  Đánh giá quá thấp / Very low rating
    - confidence_score > 0.8 AND report=True  →  AI quá tự tin nhưng sai / Overconfident AI
    - report=True  →  Người dùng chủ động báo cáo / User actively reports issue
    """
    user_id          = payload.user_id
    session_id       = payload.session_id
    rating           = payload.rating
    confidence_score = payload.confidence_score

    # ── Bước 1: Kiểm tra có cần gắn cờ không / Step 1: Check flag condition ──
    flagged, flag_reason = should_flag_for_review(
        rating=rating,
        confidence_score=confidence_score,
        report=payload.report,
    )

    if flagged:
        logger.info(
            f"🚩 Feedback flagged for review | user='{user_id}' | "
            f"rating={rating} | reason='{flag_reason}'"
        )

    # ── Bước 2: Lưu feedback vào DB / Step 2: Save feedback to DB ─────────────
    try:
        feedback_id = insert_feedback(
            user_id=user_id,
            session_id=session_id,
            rating=rating,
            roadmap_data=payload.roadmap_data,
            chat_history=payload.chat_history,
            confidence_score=confidence_score,
            flagged=flagged,
        )
        logger.info(f"✅ Feedback saved | id={feedback_id} | user='{user_id}' | rating={rating}")
        
        # If low rating (<= 2), also insert into bad_feedback_logs for Regression Test dataset
        if rating <= 2:
            try:
                bad_id = insert_bad_feedback(
                    feedback_id=feedback_id,
                    user_id=user_id,
                    session_id=session_id,
                    rating=rating,
                    roadmap_data=payload.roadmap_data,
                    chat_history=payload.chat_history,
                    confidence_score=confidence_score,
                    comment=payload.comment
                )
                logger.info(f"📉 low rating feedback copied to bad_feedback_logs | bad_id={bad_id}")
            except Exception as ex:
                logger.error(f"❌ Failed to save copy to bad_feedback_logs: {ex}")
    except Exception as e:
        logger.error(f"❌ Failed to save feedback: {e}")
        raise HTTPException(
            status_code=500,
            detail="Không thể lưu phản hồi. Vui lòng thử lại. / Could not save feedback. Please try again."
        )

    # ── Bước 3: Thêm vào hàng đợi xem xét nếu cần / Step 3: Add to review queue ──
    if flagged:
        try:
            review_id = insert_human_review(
                user_id=user_id,
                session_id=session_id,
                reason=flag_reason or "Unknown",
                feedback_id=feedback_id,
                roadmap_data=payload.roadmap_data,
                chat_history=payload.chat_history,
                confidence_score=confidence_score,
                rating=rating,
            )
            logger.info(f"🔍 Added to review queue | review_id={review_id} | feedback_id={feedback_id}")
        except Exception as e:
            # Không để lỗi DB review queue phá vỡ flow chính / Don't let review queue error break main flow
            logger.error(f"❌ Failed to add to review queue: {e}")

    # ── Bước 4: Tạo thông điệp phản hồi / Step 4: Build response message ─────
    if rating >= 4:
        message = "🎉 Cảm ơn bạn đã phản hồi tích cực! Chúng tôi sẽ tiếp tục cải thiện."
    elif rating == 3:
        message = "Cảm ơn phản hồi của bạn! Chúng tôi đang nỗ lực cải thiện hệ thống."
    else:
        message = (
            "Cảm ơn bạn đã phản hồi. Chúng tôi đã ghi nhận và sẽ cải thiện sớm nhất có thể. "
            "Phản hồi của bạn đã được chuyển đến đội ngũ chuyên gia để xem xét."
        )

    return FeedbackResponse(
        success=True,
        feedback_id=feedback_id,
        flagged_for_review=flagged,
        flag_reason=flag_reason,
        message=message,
    )
