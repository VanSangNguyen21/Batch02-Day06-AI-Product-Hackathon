"""
progress.py - Persist learner progress per authenticated account.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Cookie
from pydantic import BaseModel, Field

from app.api.auth import require_auth_user
from models.database import (
    delete_learning_progress,
    get_learning_progress,
    upsert_learning_progress,
)

router = APIRouter()


class ProgressRequest(BaseModel):
    progress: Dict[str, Any] = Field(default_factory=dict)


@router.get("/progress")
async def get_progress(ai_path_session: Optional[str] = Cookie(default=None)):
    user = require_auth_user(ai_path_session)
    record = get_learning_progress(user["user_id"])
    return {
        "has_progress": bool(record),
        "progress": record["progress_data"] if record else None,
        "updated_at": record["updated_at"] if record else None,
    }


@router.put("/progress")
async def save_progress(payload: ProgressRequest, ai_path_session: Optional[str] = Cookie(default=None)):
    user = require_auth_user(ai_path_session)
    upsert_learning_progress(user["user_id"], payload.progress)
    return {"success": True}


@router.delete("/progress")
async def clear_progress(ai_path_session: Optional[str] = Cookie(default=None)):
    user = require_auth_user(ai_path_session)
    delete_learning_progress(user["user_id"])
    return {"success": True}
