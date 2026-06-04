"""
admin.py - Các endpoint quản trị hệ thống
Admin endpoints for managing review queue and cost reports

Tác giả / Author: AI VinUni Batch02-Day05

⚠️  LƯU Ý BẢO MẬT / SECURITY NOTE:
    Trong môi trường production, hãy thêm authentication (JWT/API Key)
    cho tất cả các endpoint admin trước khi deploy!
    In production, add JWT/API key authentication to all admin endpoints!
"""

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel, Field

from models.database import (
    get_review_queue,
    resolve_review_item,
    get_cost_report,
    get_user_daily_cost,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ──────────────────────────────────────────────────────────────────────────────
# Xác thực đơn giản bằng API Key / Simple API key auth
# ──────────────────────────────────────────────────────────────────────────────

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "dev-admin-key-change-in-production")


def verify_admin_key(x_admin_key: Optional[str] = Header(None)) -> None:
    """
    Xác minh API key admin / Verify admin API key.
    Nên thay bằng JWT trong production / Should be replaced with JWT in production.
    """
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing X-Admin-Key header",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────────────

class ReviewQueueItem(BaseModel):
    """Một mục trong hàng đợi xem xét / Single item in the review queue."""
    id:               int
    feedback_id:      Optional[int]
    user_id:          str
    session_id:       str
    reason:           str
    confidence_score: Optional[float]
    rating:           Optional[int]
    status:           str
    reviewer_notes:   Optional[str]
    created_at:       str
    resolved_at:      Optional[str]
    roadmap_data:     Optional[str]   # JSON string (chưa parse để tiết kiệm bộ nhớ)
    chat_history:     Optional[str]   # JSON string


class ReviewQueueResponse(BaseModel):
    """Danh sách hàng đợi xem xét / Review queue list response."""
    total:  int
    status: str
    items:  List[ReviewQueueItem]


class ResolveRequest(BaseModel):
    """Yêu cầu giải quyết mục xem xét / Request to resolve a review item."""
    item_id:        int   = Field(..., description="ID mục cần giải quyết / Review item ID")
    reviewer_notes: str   = Field(..., min_length=5, description="Ghi chú của người xem xét / Reviewer notes")
    updated_roadmap: Optional[Dict[str, Any]] = Field(
        None,
        description="Lộ trình học tập đã được cập nhật (tuỳ chọn) / Updated roadmap (optional)"
    )


class ResolveResponse(BaseModel):
    """Kết quả giải quyết mục / Resolution result."""
    success:        bool
    item_id:        int
    message:        str
    resolved_at:    str


class CostReportEntry(BaseModel):
    """Mục trong báo cáo chi phí / Cost report entry."""
    user_id:              str
    date:                 str
    request_count:        int
    total_input_tokens:   int
    total_output_tokens:  int
    total_cost:           float
    avg_cost_per_request: float
    model_name:           str


class CostReportResponse(BaseModel):
    """Báo cáo chi phí tổng hợp / Aggregated cost report."""
    date:         str
    total_cost:   float
    total_users:  int
    entries:      List[CostReportEntry]
    generated_at: str


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint: Xem hàng đợi xem xét / Review queue
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/admin/review-queue",
    response_model=ReviewQueueResponse,
    summary="List items flagged for human review",
)
async def get_human_review_queue(
    status: str = Query("pending", description="Lọc theo trạng thái: pending | resolved | all"),
    x_admin_key: Optional[str] = Header(None),
):
    """
    ## Lấy danh sách các mục cần xem xét thủ công
    ## Get list of items flagged for human review

    **Các trạng thái / Status options:**
    - `pending`: Chưa giải quyết / Not yet resolved (default)
    - `resolved`: Đã giải quyết / Already resolved
    - `all`: Tất cả / All items
    """
    verify_admin_key(x_admin_key)

    # Xác thực giá trị status / Validate status value
    valid_statuses = {"pending", "resolved", "all"}
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    try:
        if status == "all":
            # Lấy cả pending và resolved / Get both pending and resolved
            pending_items  = get_review_queue("pending")
            resolved_items = get_review_queue("resolved")
            items = pending_items + resolved_items
        else:
            items = get_review_queue(status)

        logger.info(f"📋 Admin fetched review queue | status='{status}' | count={len(items)}")

        return ReviewQueueResponse(
            total=len(items),
            status=status,
            items=[ReviewQueueItem(**item) for item in items],
        )
    except Exception as e:
        logger.error(f"❌ Failed to fetch review queue: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint: Giải quyết mục xem xét / Resolve review item
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/admin/resolve",
    response_model=ResolveResponse,
    summary="Resolve a human review queue item",
)
async def resolve_review(
    payload: ResolveRequest,
    x_admin_key: Optional[str] = Header(None),
):
    """
    ## Đánh dấu một mục trong hàng đợi xem xét là đã giải quyết
    ## Mark a human review queue item as resolved

    Người xem xét cần cung cấp ghi chú về quyết định của mình.
    The reviewer must provide notes explaining their decision.
    """
    verify_admin_key(x_admin_key)

    try:
        success = resolve_review_item(
            item_id=payload.item_id,
            reviewer_notes=payload.reviewer_notes,
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Review item with id={payload.item_id} not found"
            )

        resolved_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"✅ Review item resolved | id={payload.item_id} | "
            f"notes='{payload.reviewer_notes[:50]}...'"
        )

        return ResolveResponse(
            success=True,
            item_id=payload.item_id,
            message=f"Mục #{payload.item_id} đã được giải quyết thành công / Item #{payload.item_id} resolved successfully",
            resolved_at=resolved_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to resolve review item {payload.item_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint: Báo cáo chi phí / Cost report
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/admin/cost-report",
    response_model=CostReportResponse,
    summary="Daily cost summary per user",
)
async def get_daily_cost_report(
    date: Optional[str] = Query(
        None,
        description="Ngày báo cáo (YYYY-MM-DD), mặc định hôm nay UTC / Report date (YYYY-MM-DD), defaults to today UTC"
    ),
    x_admin_key: Optional[str] = Header(None),
):
    """
    ## Báo cáo chi phí LLM theo ngày, phân theo từng người dùng
    ## Daily LLM cost report, broken down by user

    Hữu ích để theo dõi sử dụng và phát hiện chi phí bất thường.
    Useful for monitoring usage and detecting abnormal spending.
    """
    verify_admin_key(x_admin_key)

    # Xác thực định dạng ngày / Validate date format
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD (e.g. 2024-01-15)"
            )
    else:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        entries = get_cost_report(date_str=date)

        # Tính tổng chi phí / Calculate grand total
        total_cost = sum(e.get("total_cost", 0.0) for e in entries)

        logger.info(
            f"📊 Admin fetched cost report | date='{date}' | "
            f"users={len(entries)} | total=${total_cost:.4f}"
        )

        return CostReportResponse(
            date=date,
            total_cost=round(total_cost, 6),
            total_users=len(entries),
            entries=[CostReportEntry(**e) for e in entries],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.error(f"❌ Failed to fetch cost report for date '{date}': {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint: Chi phí người dùng cụ thể / Single user cost
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/admin/user-cost/{user_id}",
    summary="Get daily cost for a specific user",
)
async def get_user_cost(
    user_id: str,
    date: Optional[str] = Query(None, description="Ngày (YYYY-MM-DD), mặc định hôm nay"),
    x_admin_key: Optional[str] = Header(None),
):
    """
    ## Xem chi phí trong ngày của một người dùng cụ thể
    ## View the daily cost for a specific user
    """
    verify_admin_key(x_admin_key)

    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    daily_cost = get_user_daily_cost(user_id)
    max_limit  = float(os.getenv("MAX_DAILY_COST_USD", "1.00"))

    return {
        "user_id":     user_id,
        "date":        date,
        "daily_cost":  round(daily_cost, 6),
        "limit_usd":   max_limit,
        "usage_pct":   round((daily_cost / max_limit) * 100, 2) if max_limit > 0 else 0.0,
        "rate_limited": daily_cost > max_limit,
    }
