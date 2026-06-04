"""
progress.py - Persist learner progress per authenticated account.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_session, _Session
from models.database import (
    delete_learning_progress,
    get_learning_progress,
    upsert_learning_progress,
)

router = APIRouter()

class ProgressRequest(BaseModel):
    progress: Dict[str, Any] = Field(default_factory=dict)

def _get_user_id(sess: _Session = Depends(get_current_session)) -> str:
    if not sess:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return sess.user_id

@router.get("/progress")
async def get_progress(user_id: str = Depends(_get_user_id)):
    record = get_learning_progress(user_id)
    return {
        "has_progress": bool(record),
        "progress": record["progress_data"] if record else None,
        "updated_at": record["updated_at"] if record else None,
    }

@router.put("/progress")
async def save_progress(payload: ProgressRequest, user_id: str = Depends(_get_user_id)):
    upsert_learning_progress(user_id, payload.progress)
    return {"success": True}

@router.delete("/progress")
async def clear_progress(user_id: str = Depends(_get_user_id)):
    delete_learning_progress(user_id)
    return {"success": True}
