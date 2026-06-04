"""
auth.py - Authentication & session management endpoints.
POST   /api/auth/login    -> {token, user_id, role, expires_at}
POST   /api/auth/logout   -> invalidate session
GET    /api/auth/me       -> current session info
GET    /api/auth/whoami   -> convenience wrapper

Sessions are stored in-memory (process-local). Tokens are opaque random
strings. For a production system, swap with JWT + Redis/Postgres.

Auth flow:
  1. Client POST /api/auth/login with {user_id, api_key?}
  2. Server resolves role via existing API_KEYS table (admin/premium) or
     issues a default STUDENT session for any user_id.
  3. Server returns a 32-byte token; client stores in localStorage.
  4. Subsequent requests send "Authorization: Bearer <token>".
  5. /api/auth/logout invalidates the token.

Demo accounts (use the matching api_key, or leave blank for STUDENT):
  - ADMIN    : api_key = ADMIN_API_KEY   (default "dev-admin-key-...")
  - REVIEWER : api_key = REVIEWER_API_KEY
  - PREMIUM  : api_key = PREMIUM_API_KEY
  - STUDENT  : any user_id, no api_key
"""
import os
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from threading import Lock

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from middleware.auth import (
    Role,
    RATE_LIMITS,
    COST_LIMITS,
    get_role_limits,
)
from models.database import (
    get_user_by_username,
    create_login_user,
    verify_password,
    hash_password,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Session TTL (default 8 hours)
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "8"))


# ──────────────────────────────────────────────────────────────────────────────
# In-memory session store: token -> {user_id, role, expires_at, created_at}
# ──────────────────────────────────────────────────────────────────────────────
class _Session:
    __slots__ = ("user_id", "role", "created_at", "expires_at", "label")

    def __init__(self, user_id: str, role: Role, ttl_hours: int = SESSION_TTL_HOURS, label: str = ""):
        now = datetime.now(timezone.utc)
        self.user_id    = user_id
        self.role       = role
        self.created_at = now
        self.expires_at = now + timedelta(hours=ttl_hours)
        self.label      = label

    def to_public(self) -> Dict[str, Any]:
        return {
            "user_id":    self.user_id,
            "role":       self.role.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "label":      self.label,
        }


_sessions: Dict[str, _Session] = {}
_sessions_lock = Lock()


def _new_token() -> str:
    """Generate a 32-byte URL-safe token."""
    return secrets.token_urlsafe(32)


def _create_session(user_id: str, role: Any, label: str = "") -> Dict[str, Any]:
    if not isinstance(role, Role):
        try:
            role = Role(str(role).lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    token = _new_token()
    sess  = _Session(user_id, role, label=label)
    with _sessions_lock:
        _sessions[token] = sess
    logger.info(f"Session created: user={user_id} role={role.value} label='{label}'")
    return {
        "token":      token,
        "user_id":    sess.user_id,
        "role":       sess.role.value,
        "expires_at": sess.expires_at.isoformat(),
        "limits":     get_role_limits(role),
    }


def _revoke_session(token: str) -> bool:
    with _sessions_lock:
        sess = _sessions.pop(token, None)
    if sess:
        logger.info(f"Session revoked: user={sess.user_id} role={sess.role.value}")
        return True
    return False


def _get_session(token: str) -> Optional[_Session]:
    sess = _sessions.get(token)
    if not sess:
        return None
    if datetime.now(timezone.utc) >= sess.expires_at:
        _revoke_session(token)
        return None
    return sess


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    """Login payload."""
    username: str = Field(..., min_length=1, max_length=64, description="User identifier")
    password: str = Field(..., min_length=1, max_length=256, description="Password")

class RegisterRequest(BaseModel):
    """Register payload."""
    username: str = Field(..., min_length=1, max_length=64, description="User identifier")
    password: str = Field(..., min_length=6, max_length=256, description="Password")


class LoginResponse(BaseModel):
    token:      str
    user_id:    str
    role:       str
    expires_at: str
    limits:     Dict[str, float]


class MeResponse(BaseModel):
    user_id:    str
    role:       str
    created_at: str
    expires_at: str
    limits:     Dict[str, float]


class LogoutResponse(BaseModel):
    revoked: bool
    message: str


# ──────────────────────────────────────────────────────────────────────────────
# Dependencies
# ──────────────────────────────────────────────────────────────────────────────
def get_current_session(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key:     Optional[str] = Header(None, alias="X-API-Key"),
    x_role:        Optional[str] = Header(None, alias="X-Role"),
    x_user_id:     Optional[str] = Header(None, alias="X-User-Id"),
) -> _Session:
    """
    Resolve the current user/session.
    Priority:
      1. Authorization: Bearer <token>  -> look up session
      2. X-API-Key + X-User-Id         -> ephemeral role (no session)
      3. X-Role + X-User-Id            -> dev mode
    Returns the session object so handlers can read user_id and role.
    """
    # 1. Bearer token (the proper flow)
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Invalid Authorization header (expected 'Bearer <token>')")
        sess = _get_session(token)
        if not sess:
            raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
        return sess

    raise HTTPException(status_code=401, detail="Missing Authorization header")


def require_session_role(*allowed: Role):
    """Dependency factory: requires an active session whose role is in `allowed`."""
    allowed_set = set(allowed)

    def _checker(
        authorization: Optional[str] = Header(None, alias="Authorization"),
        x_api_key:     Optional[str] = Header(None, alias="X-API-Key"),
        x_role:        Optional[str] = Header(None, alias="X-Role"),
        x_user_id:     Optional[str] = Header(None, alias="X-User-Id"),
    ) -> _Session:
        sess = get_current_session(authorization, x_api_key, x_role, x_user_id)
        if sess.role not in allowed_set:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{sess.role.value}' is not authorized. Required: {[r.value for r in allowed_set]}",
            )
        return sess

    return _checker


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    """
    Authenticate a user using username and password.
    """
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")

    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    if not verify_password(user["password_hash"], payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    try:
        role = Role(user.get("role", "student").lower())
    except ValueError:
        role = Role.STUDENT
        
    return _create_session(user_id=username, role=role, label="db_auth")

@router.post("/register", response_model=LoginResponse)
def register(payload: RegisterRequest):
    """
    Register a new user account.
    """
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
        
    existing = get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
        
    hashed = hash_password(payload.password)
    try:
        create_login_user(username, hashed, role="student")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")
        
    return _create_session(user_id=username, role=Role.STUDENT, label="db_auth")


@router.post("/logout", response_model=LogoutResponse)
def logout(authorization: Optional[str] = Header(None, alias="Authorization")):
    """Revoke the bearer token from the Authorization header."""
    if not authorization:
        return LogoutResponse(revoked=False, message="No session to revoke (missing Authorization header)")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return LogoutResponse(revoked=False, message="Invalid Authorization header")
    ok = _revoke_session(token)
    return LogoutResponse(
        revoked=ok,
        message="Session revoked" if ok else "Token not found or already expired",
    )


@router.get("/me", response_model=MeResponse)
def me(sess: _Session = Depends(get_current_session)):
    """Return information about the current session."""
    return MeResponse(
        user_id    = sess.user_id,
        role       = sess.role.value,
        created_at = sess.created_at.isoformat(),
        expires_at = sess.expires_at.isoformat(),
        limits     = get_role_limits(sess.role),
    )


@router.get("/whoami")
def whoami(sess: _Session = Depends(get_current_session)):
    """Lightweight identity check used by the frontend on page load."""
    return {
        "authenticated": True,
        "user_id":       sess.user_id,
        "role":          sess.role.value,
        "rate_limit":    RATE_LIMITS.get(sess.role, 5),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Admin helpers (optional)
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/sessions")
def list_sessions(sess: _Session = Depends(require_session_role(Role.ADMIN))):
    """List all active sessions. Admin only."""
    now = datetime.now(timezone.utc)
    with _sessions_lock:
        items = [
            {"token_prefix": tok[:8] + "…", **s.to_public()}
            for tok, s in _sessions.items()
            if s.expires_at > now
        ]
    return {"active_sessions": len(items), "sessions": items}
