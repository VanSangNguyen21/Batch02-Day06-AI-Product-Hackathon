"""
database.py - Thiết lập cơ sở dữ liệu SQLite
SQLite database setup with tables and CRUD helpers

Tác giả / Author: AI VinUni Batch02-Day05
"""

import sqlite3
import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

# ──────────────────────────────────────────────────────────────────────────────
# Đường dẫn tệp cơ sở dữ liệu / Database file paths
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "data")

COST_DB_PATH = os.path.join(DB_DIR, "cost_logs.db")
FEEDBACK_DB_PATH = os.path.join(DB_DIR, "feedback.db")

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Hàm tiện ích kết nối / Connection helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_cost_db_connection() -> sqlite3.Connection:
    """Tạo kết nối đến cost_logs.db / Connect to cost database."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(COST_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Cho phép truy cập theo tên cột / Column name access
    return conn


def get_feedback_db_connection() -> sqlite3.Connection:
    """Tạo kết nối đến feedback.db / Connect to feedback database."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(FEEDBACK_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# Khởi tạo bảng / Table initialization
# ──────────────────────────────────────────────────────────────────────────────

def init_cost_db():
    """
    Khởi tạo bảng cost_logs trong cost_logs.db
    Initialize cost_logs table in cost_logs.db
    """
    conn = get_cost_db_connection()
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS cost_logs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         TEXT NOT NULL,
                session_id      TEXT,
                timestamp       TEXT NOT NULL,
                model_name      TEXT NOT NULL,
                input_tokens    INTEGER NOT NULL DEFAULT 0,
                output_tokens   INTEGER NOT NULL DEFAULT 0,
                calculated_cost REAL NOT NULL DEFAULT 0.0,
                confidence_score REAL,
                endpoint        TEXT,           -- e.g. /api/analyze, /api/chat
                rate_limited    INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            -- Index để tìm kiếm theo user và ngày / Index for user + date queries
            CREATE INDEX IF NOT EXISTS idx_cost_user_id
                ON cost_logs(user_id);

            CREATE INDEX IF NOT EXISTS idx_cost_timestamp
                ON cost_logs(timestamp);
        """)
        conn.commit()
        logger.info("✅ cost_logs table initialized")
    except Exception as e:
        logger.error(f"❌ Failed to init cost_logs table: {e}")
        raise
    finally:
        conn.close()


def init_feedback_db():
    """
    Khởi tạo các bảng feedback trong feedback.db
    Initialize feedback-related tables in feedback.db
    """
    conn = get_feedback_db_connection()
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            -- Bảng lưu phản hồi người dùng / User feedback table
            CREATE TABLE IF NOT EXISTS feedback_logs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          TEXT NOT NULL,
                session_id       TEXT NOT NULL,
                rating           INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                roadmap_data     TEXT,           -- JSON string
                chat_history     TEXT,           -- JSON string
                confidence_score REAL,
                flagged          INTEGER DEFAULT 0,  -- 1 = cần xem xét / needs review
                created_at       TEXT DEFAULT (datetime('now'))
            );

            -- Hàng đợi xem xét thủ công / Human review queue
            CREATE TABLE IF NOT EXISTS human_review_queue (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_id      INTEGER,
                user_id          TEXT NOT NULL,
                session_id       TEXT NOT NULL,
                reason           TEXT,           -- Lý do gắn cờ / Reason for flagging
                roadmap_data     TEXT,           -- JSON string
                chat_history     TEXT,           -- JSON string
                confidence_score REAL,
                rating           INTEGER,
                status           TEXT DEFAULT 'pending',  -- pending / resolved
                reviewer_notes   TEXT,
                resolved_at      TEXT,
                created_at       TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (feedback_id) REFERENCES feedback_logs(id)
            );

            -- Bảng phiên hội thoại / Chat sessions table
            CREATE TABLE IF NOT EXISTS sessions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       TEXT UNIQUE NOT NULL,
                user_id          TEXT NOT NULL,
                quiz_completed   INTEGER DEFAULT 0,  -- 0 = chưa xong / not done
                questions_answered INTEGER DEFAULT 0,
                conversation_history TEXT,          -- JSON string
                created_at       TEXT DEFAULT (datetime('now')),
                updated_at       TEXT DEFAULT (datetime('now'))
            );

            -- Bảng bad_feedback_logs để Regression Test / Bad feedback logs for regression tests
            CREATE TABLE IF NOT EXISTS bad_feedback_logs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_id      INTEGER,
                user_id          TEXT NOT NULL,
                session_id       TEXT NOT NULL,
                rating           INTEGER NOT NULL,
                roadmap_data     TEXT,
                chat_history     TEXT,
                confidence_score REAL,
                comment          TEXT,
                created_at       TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (feedback_id) REFERENCES feedback_logs(id)
            );

            -- Index tối ưu / Optimized indexes
            CREATE INDEX IF NOT EXISTS idx_feedback_user_id
                ON feedback_logs(user_id);

            CREATE INDEX IF NOT EXISTS idx_review_status
                ON human_review_queue(status);

            CREATE INDEX IF NOT EXISTS idx_sessions_session_id
                ON sessions(session_id);

            CREATE INDEX IF NOT EXISTS idx_sessions_user_id
                ON sessions(user_id);
        """)
        conn.commit()
        logger.info("✅ Feedback database tables initialized")
    except Exception as e:
        logger.error(f"❌ Failed to init feedback tables: {e}")
        raise
    finally:
        conn.close()


def init_db():
    """
    Hàm khởi tạo tất cả cơ sở dữ liệu
    Initialize all databases - called on app startup
    """
    logger.info("🗄️  Initializing databases...")
    init_cost_db()
    init_feedback_db()
    logger.info("✅ All databases initialized successfully")


# ──────────────────────────────────────────────────────────────────────────────
# CRUD Helpers - cost_logs
# ──────────────────────────────────────────────────────────────────────────────

def insert_cost_log(
    user_id: str,
    input_tokens: int,
    output_tokens: int,
    calculated_cost: float,
    model_name: str,
    confidence_score: Optional[float] = None,
    endpoint: Optional[str] = None,
) -> int:
    """
    Thêm bản ghi chi phí vào database
    Insert a cost log record into cost_logs.db

    Returns: id của bản ghi vừa tạo / id of the inserted record
    """
    conn = get_cost_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cost_logs
                (user_id, timestamp, input_tokens, output_tokens,
                 calculated_cost, confidence_score, model_name, endpoint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            datetime.utcnow().isoformat(),
            input_tokens,
            output_tokens,
            calculated_cost,
            confidence_score,
            model_name,
            endpoint,
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_daily_cost(user_id: str, date_str: Optional[str] = None) -> float:
    """
    Lấy tổng chi phí trong ngày của người dùng
    Get total cost for a user on a given day (default: today UTC)

    Returns: tổng chi phí (USD) / total cost in USD
    """
    if date_str is None:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    conn = get_cost_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(calculated_cost), 0.0) as daily_cost
            FROM cost_logs
            WHERE user_id = ?
              AND DATE(timestamp) = ?
        """, (user_id, date_str))
        row = cursor.fetchone()
        return float(row["daily_cost"]) if row else 0.0
    finally:
        conn.close()


def get_cost_report(date_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lấy báo cáo chi phí theo ngày và người dùng
    Get daily cost summary grouped by user
    """
    if date_str is None:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    conn = get_cost_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                user_id,
                DATE(timestamp) as date,
                COUNT(*) as request_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(calculated_cost) as total_cost,
                AVG(calculated_cost) as avg_cost_per_request,
                model_name
            FROM cost_logs
            WHERE DATE(timestamp) = ?
            GROUP BY user_id, DATE(timestamp), model_name
            ORDER BY total_cost DESC
        """, (date_str,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# CRUD Helpers - feedback_logs
# ──────────────────────────────────────────────────────────────────────────────

def insert_feedback(
    user_id: str,
    session_id: str,
    rating: int,
    roadmap_data: Optional[dict] = None,
    chat_history: Optional[list] = None,
    confidence_score: Optional[float] = None,
    flagged: bool = False,
) -> int:
    """
    Thêm bản ghi phản hồi vào database
    Insert a feedback record. Returns the new feedback id.
    """
    conn = get_feedback_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO feedback_logs
                (user_id, session_id, rating, roadmap_data,
                 chat_history, confidence_score, flagged)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            session_id,
            rating,
            json.dumps(roadmap_data) if roadmap_data else None,
            json.dumps(chat_history) if chat_history else None,
            confidence_score,
            1 if flagged else 0,
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_human_review(
    user_id: str,
    session_id: str,
    reason: str,
    feedback_id: Optional[int] = None,
    roadmap_data: Optional[dict] = None,
    chat_history: Optional[list] = None,
    confidence_score: Optional[float] = None,
    rating: Optional[int] = None,
) -> int:
    """
    Thêm mục vào hàng đợi xem xét thủ công
    Add an item to the human review queue
    """
    conn = get_feedback_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO human_review_queue
                (feedback_id, user_id, session_id, reason, roadmap_data,
                 chat_history, confidence_score, rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback_id,
            user_id,
            session_id,
            reason,
            json.dumps(roadmap_data) if roadmap_data else None,
            json.dumps(chat_history) if chat_history else None,
            confidence_score,
            rating,
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_review_queue(status: str = "pending") -> List[Dict[str, Any]]:
    """
    Lấy danh sách các mục cần xem xét
    Get items from the human review queue filtered by status
    """
    conn = get_feedback_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM human_review_queue
            WHERE status = ?
            ORDER BY created_at DESC
        """, (status,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def resolve_review_item(item_id: int, reviewer_notes: str) -> bool:
    """
    Đánh dấu mục đã được giải quyết
    Mark a review queue item as resolved
    """
    conn = get_feedback_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE human_review_queue
            SET status = 'resolved',
                reviewer_notes = ?,
                resolved_at = ?
            WHERE id = ?
        """, (reviewer_notes, datetime.utcnow().isoformat(), item_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# CRUD Helpers - sessions
# ──────────────────────────────────────────────────────────────────────────────

def upsert_session(
    session_id: str,
    user_id: str,
    quiz_completed: bool = False,
    questions_answered: int = 0,
    conversation_history: Optional[list] = None,
) -> None:
    """
    Tạo hoặc cập nhật phiên hội thoại
    Create or update a chat session record
    """
    conn = get_feedback_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions
                (session_id, user_id, quiz_completed, questions_answered, conversation_history, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                quiz_completed = excluded.quiz_completed,
                questions_answered = excluded.questions_answered,
                conversation_history = excluded.conversation_history,
                updated_at = excluded.updated_at
        """, (
            session_id,
            user_id,
            1 if quiz_completed else 0,
            questions_answered,
            json.dumps(conversation_history) if conversation_history else "[]",
            datetime.utcnow().isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Lấy thông tin phiên hội thoại
    Get a session record by session_id
    """
    conn = get_feedback_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            # Parse JSON fields
            data["conversation_history"] = json.loads(data.get("conversation_history") or "[]")
            return data
        return None
    finally:
        conn.close()


def insert_bad_feedback(
    feedback_id: int,
    user_id: str,
    session_id: str,
    rating: int,
    roadmap_data: Optional[dict] = None,
    chat_history: Optional[list] = None,
    confidence_score: Optional[float] = None,
    comment: Optional[str] = None
) -> int:
    """
    Lưu phản hồi đánh giá thấp (1-2 sao) vào bảng bad_feedback_logs để chạy Regression Test.
    """
    conn = get_feedback_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bad_feedback_logs
                (feedback_id, user_id, session_id, rating, roadmap_data,
                 chat_history, confidence_score, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback_id,
            user_id,
            session_id,
            rating,
            json.dumps(roadmap_data) if roadmap_data else None,
            json.dumps(chat_history) if chat_history else None,
            confidence_score,
            comment
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
