"""
====================================================
  API Endpoint: /api/quiz
  Dynamic Quiz Selection using RAG
  VinUni AI20k Batch 02 · Day 06
====================================================
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from services.quiz_bank import get_all_quiz_sets, QuizSet
from services.rag_retriever import select_quiz_for_user
from middleware.guardrails import guardrail_manager
from middleware.data_masking import mask_sensitive_data

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== REQUEST/RESPONSE MODELS ====================

class SelectQuizRequest(BaseModel):
    """Request để select quiz dựa trên user profile"""
    user_id: str
    learning_goal: str = Field(..., min_length=5, max_length=500, description="Mục tiêu học tập")
    background: str = Field(..., min_length=5, max_length=300, description="Background/kinh nghiệm")
    current_level: str = Field(..., description="beginner | intermediate | advanced | expert")
    target_role: Optional[str] = Field(None, description="Vai trò mục tiêu (vd: ML Engineer)")
    interests: Optional[List[str]] = Field(None, description="Danh sách topics quan tâm")
    use_semantic: bool = Field(True, description="Sử dụng semantic search (RAG) hay metadata matching")


class QuestionResponse(BaseModel):
    """Mô hình của một câu hỏi"""
    id: str
    text: str
    options: List[Dict[str, str]]
    correct: int
    explanation: str


class SelectedQuizResponse(BaseModel):
    """Response khi select quiz"""
    quiz_set_id: str
    quiz_set_name: str
    quiz_set_description: str
    difficulty: str
    topics: List[str]
    target_goals: List[str]
    questions: List[QuestionResponse]
    similarity_score: float
    retrieval_method: str  # "semantic" | "metadata" | "fallback"


class QuizListResponse(BaseModel):
    """Response khi list tất cả quiz sets"""
    total_sets: int
    quiz_sets: List[Dict[str, Any]]


# ==================== ENDPOINTS ====================

@router.post(
    "/select-quiz",
    response_model=SelectedQuizResponse,
    summary="Chọn quiz dựa trên user profile (RAG)"
)
async def select_quiz(req: SelectQuizRequest):
    """
    Chọn bộ câu hỏi phù hợp dựa trên profile người dùng.
    
    Flow:
    1. Validate input với guardrails
    2. Sử dụng RAG retriever để match profile với quiz sets
    3. Return câu hỏi được chọn
    
    Args:
        user_id: ID người dùng
        learning_goal: Mục tiêu học tập
        background: Background hiện tại
        current_level: Trình độ hiện tại
        target_role: (Optional) Vai trò mục tiêu
        interests: (Optional) Các topics quan tâm
        use_semantic: Có dùng semantic search không
    
    Returns:
        SelectedQuizResponse: Bộ câu hỏi được chọn + metadata
    """
    
    # Mask sensitive data
    learning_goal = mask_sensitive_data(req.learning_goal)
    background = mask_sensitive_data(req.background)
    
    # Guardrail check
    for text, field_name in [
        (learning_goal, "learning_goal"),
        (background, "background")
    ]:
        guard_result = guardrail_manager.check_message(text)
        if guard_result and guard_result.get("blocked"):
            reason = guard_result.get("reason", "blocked")
            response_text = guard_result.get("response", "Yêu cầu không hợp lệ")
            logger.warning(f"🚫 Select quiz blocked due to {field_name}: {reason}")
            raise HTTPException(status_code=400, detail=response_text)
    
    logger.info(
        f"🎯 Select quiz request | user={req.user_id} | level={req.current_level} | "
        f"goal={learning_goal[:50]}..."
    )
    
    try:
        # Get all quiz sets
        quiz_sets = get_all_quiz_sets()
        
        if not quiz_sets:
            logger.error("❌ No quiz sets available")
            raise HTTPException(
                status_code=500,
                detail="Không có bộ câu hỏi nào khả dụng"
            )
        
        # Select quiz using RAG
        selected_quiz, similarity_score = select_quiz_for_user(
            quiz_sets=quiz_sets,
            learning_goal=learning_goal,
            background=background,
            current_level=req.current_level,
            target_role=req.target_role,
            interests=req.interests,
            use_semantic=req.use_semantic,
            top_k=1
        )
        
        if not selected_quiz:
            logger.error("❌ Failed to select quiz")
            raise HTTPException(
                status_code=500,
                detail="Không thể chọn bộ câu hỏi phù hợp"
            )
        
        # Determine retrieval method
        if similarity_score >= 0.4:
            retrieval_method = "semantic"
        elif similarity_score >= 0.3:
            retrieval_method = "metadata"
        else:
            retrieval_method = "fallback"
        
        logger.info(
            f"✅ Quiz selected: {selected_quiz.name} "
            f"(method={retrieval_method}, score={similarity_score:.3f})"
        )
        
        # Build response
        questions = [
            QuestionResponse(
                id=q["id"],
                text=q["text"],
                options=q["options"],
                correct=q["correct"],
                explanation=q["explanation"]
            )
            for q in selected_quiz.questions
        ]
        
        response = SelectedQuizResponse(
            quiz_set_id=selected_quiz.set_id,
            quiz_set_name=selected_quiz.name,
            quiz_set_description=selected_quiz.description,
            difficulty=selected_quiz.difficulty,
            topics=selected_quiz.topics,
            target_goals=selected_quiz.target_goals,
            questions=questions,
            similarity_score=similarity_score,
            retrieval_method=retrieval_method
        )
        
        logger.info(f"📤 Returning {len(questions)} questions for quiz: {selected_quiz.name}")
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in select_quiz: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi chọn bộ câu hỏi: {str(e)}"
        )


@router.get(
    "/list-quiz-sets",
    response_model=QuizListResponse,
    summary="Liệt kê tất cả bộ câu hỏi"
)
async def list_quiz_sets():
    """
    Liệt kê tất cả quiz sets có sẵn với metadata.
    
    Returns:
        QuizListResponse: Danh sách quiz sets
    """
    try:
        quiz_sets = get_all_quiz_sets()
        
        quiz_list = [
            {
                "set_id": qs.set_id,
                "name": qs.name,
                "description": qs.description,
                "difficulty": qs.difficulty,
                "topics": qs.topics,
                "target_goals": qs.target_goals,
                "question_count": len(qs.questions)
            }
            for qs in quiz_sets
        ]
        
        logger.info(f"📋 Listing {len(quiz_sets)} quiz sets")
        
        return QuizListResponse(
            total_sets=len(quiz_sets),
            quiz_sets=quiz_list
        )
    
    except Exception as e:
        logger.error(f"❌ Error listing quiz sets: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi liệt kê bộ câu hỏi: {str(e)}"
        )


@router.get(
    "/quiz-by-id/{quiz_set_id}",
    response_model=SelectedQuizResponse,
    summary="Lấy quiz bằng ID"
)
async def get_quiz_by_id(quiz_set_id: str):
    """
    Lấy bộ câu hỏi theo ID.
    
    Args:
        quiz_set_id: ID của quiz set
    
    Returns:
        SelectedQuizResponse: Bộ câu hỏi được chọn
    """
    try:
        quiz_sets = get_all_quiz_sets()
        selected_quiz = None
        
        for qs in quiz_sets:
            if qs.set_id == quiz_set_id:
                selected_quiz = qs
                break
        
        if not selected_quiz:
            logger.warning(f"⚠️ Quiz set not found: {quiz_set_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Bộ câu hỏi không tìm thấy: {quiz_set_id}"
            )
        
        questions = [
            QuestionResponse(
                id=q["id"],
                text=q["text"],
                options=q["options"],
                correct=q["correct"],
                explanation=q["explanation"]
            )
            for q in selected_quiz.questions
        ]
        
        logger.info(f"✅ Retrieved quiz: {selected_quiz.name}")
        
        return SelectedQuizResponse(
            quiz_set_id=selected_quiz.set_id,
            quiz_set_name=selected_quiz.name,
            quiz_set_description=selected_quiz.description,
            difficulty=selected_quiz.difficulty,
            topics=selected_quiz.topics,
            target_goals=selected_quiz.target_goals,
            questions=questions,
            similarity_score=1.0,  # Direct access
            retrieval_method="direct"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting quiz by id: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi lấy bộ câu hỏi: {str(e)}"
        )
