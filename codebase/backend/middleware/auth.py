"""
auth.py - Phân quyền chi tiết cho hệ thống AI Path
Detailed permission system with roles and rate limits.

Roles (least -> most privilege):
  GUEST     - Read-only, no LLM calls, no DB writes
  STUDENT   - Full chat + analyze + feedback
  PREMIUM   - Higher rate limits, all student features
  REVIEWER  - Read review queue + cost reports
  ADMIN     - Full access including resolve reviews
"""
import os
import logging
from enum import Enum
from typing import Optional, Dict, Set
from fastapi import Header, HTTPException, Depends

logger = logging.getLogger(__name__)


class Role(str, Enum):
    GUEST = "guest"
    STUDENT = "student"
    PREMIUM = "premium"
    REVIEWER = "reviewer"
    ADMIN = "admin"


# Permission matrix: endpoint prefix -> required roles
# '*' = all roles can access; [] = no access
ENDPOINT_PERMISSIONS: Dict[str, Set[Role]] = {
    "/health":               {Role.GUEST, Role.STUDENT, Role.PREMIUM, Role.REVIEWER, Role.ADMIN},
    "/api/analyze":          {Role.STUDENT, Role.PREMIUM, Role.ADMIN},
    "/api/chat":             {Role.STUDENT, Role.PREMIUM, Role.ADMIN},
    "/api/feedback":         {Role.STUDENT, Role.PREMIUM, Role.ADMIN},
    "/api/admin/review-queue":   {Role.REVIEWER, Role.ADMIN},
    "/api/admin/resolve":        {Role.ADMIN},
    "/api/admin/cost-report":    {Role.REVIEWER, Role.ADMIN},
    "/api/admin/user-cost":      {Role.REVIEWER, Role.ADMIN},
    "/":                     {Role.GUEST, Role.STUDENT, Role.PREMIUM, Role.REVIEWER, Role.ADMIN},
}


# Per-role rate limits (requests/minute)
RATE_LIMITS: Dict[Role, int] = {
    Role.GUEST:    2,
    Role.STUDENT:  5,
    Role.PREMIUM:  20,
    Role.REVIEWER: 30,
    Role.ADMIN:    60,
}


# Per-role daily cost limits (USD)
COST_LIMITS: Dict[Role, float] = {
    Role.GUEST:    0.0,    # Guests cannot call LLMs
    Role.STUDENT:  1.0,
    Role.PREMIUM:  5.0,
    Role.REVIEWER: 1.0,
    Role.ADMIN:    100.0,  # Effectively unlimited for admin
}


# Revoked/blocked user IDs (for abuse control)
_BLOCKED_USERS: Set[str] = set()


def get_role_limits(role: Role) -> Dict[str, float]:
    """Return rate/cost limits for a given role."""
    return {
        "rate_per_minute": float(RATE_LIMITS.get(role, 5)),
        "daily_cost_usd":  float(COST_LIMITS.get(role, 0.0)),
    }


def block_user(user_id: str) -> None:
    """Block a user (admin operation)."""
    _BLOCKED_USERS.add(user_id)
    logger.warning(f"User blocked: {user_id}")


def unblock_user(user_id: str) -> None:
    """Unblock a previously blocked user."""
    _BLOCKED_USERS.discard(user_id)
    logger.info(f"User unblocked: {user_id}")
