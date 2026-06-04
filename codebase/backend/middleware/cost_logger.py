"""
====================================================
  Middleware: Cost Logger
  Theo dõi chi phí token và ghi log mọi API call
  VinUni AI20k Batch 02 · Day 05
====================================================
"""

import sqlite3
import logging
from datetime import datetime, date
from typing import Optional
import os

logger = logging.getLogger(__name__)

# Bảng giá token theo model (tính theo USD / 1 token)
PRICE_TABLE = {
    "gpt-4o": {
        "input":  2.50 / 1_000_000,   # $2.50 per 1M input tokens
        "output": 10.00 / 1_000_000,  # $10.00 per 1M output tokens
    },
    "gpt-4o-mini": {
        "input":  0.15 / 1_000_000,
        "output": 0.60 / 1_000_000,
    },
    "gpt-3.5-turbo": {
        "input":  0.50 / 1_000_000,
        "output": 1.50 / 1_000_000,
    },
    "gemini-1.5-flash": {
        "input":  0.075 / 1_000_000,
        "output": 0.30 / 1_000_000,
    },
    "gemini-1.5-pro": {
        "input":  3.50 / 1_000_000,
        "output": 10.50 / 1_000_000,
    },
}

# Ngưỡng chi phí tối đa mỗi ngày ($1 USD)
MAX_DAILY_COST_USD = float(os.getenv("MAX_DAILY_COST_USD", "1.0"))

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cost_logs.db")


def get_db_connection():
    """Tạo kết nối SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_cost_db():
    """Khởi tạo bảng cost_logs nếu chưa có"""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cost_logs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          TEXT    NOT NULL,
            session_id       TEXT,
            timestamp        TEXT    NOT NULL,
            model_name       TEXT    NOT NULL,
            input_tokens     INTEGER NOT NULL,
            output_tokens    INTEGER NOT NULL,
            calculated_cost  REAL    NOT NULL,
            confidence_score REAL,
            endpoint         TEXT,
            rate_limited     INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    logger.info("✅ Cost logs database initialized")


def calculate_cost(input_tokens: int, output_tokens: int, model_name: str) -> float:
    """
    Tính tổng chi phí cho một API call.
    
    Công thức:
    Total Cost = (Input Tokens × Price_In) + (Output Tokens × Price_Out)
    
    Args:
        input_tokens:  Số token đầu vào (prompt)
        output_tokens: Số token đầu ra (completion)
        model_name:    Tên model AI đang dùng
    
    Returns:
        total_cost: Tổng chi phí (USD)
    """
    prices = PRICE_TABLE.get(model_name, PRICE_TABLE["gpt-4o-mini"])
    
    total_cost = (input_tokens * prices["input"]) + (output_tokens * prices["output"])
    return round(total_cost, 8)


def get_user_daily_cost(user_id: str) -> float:
    """
    Lấy tổng chi phí trong ngày của user.
    
    Args:
        user_id: ID người dùng
    
    Returns:
        total_cost_today: Tổng chi phí hôm nay (USD)
    """
    try:
        conn = get_db_connection()
        today = date.today().isoformat()
        cursor = conn.execute("""
            SELECT COALESCE(SUM(calculated_cost), 0.0) as total
            FROM cost_logs
            WHERE user_id = ?
              AND DATE(timestamp) = ?
        """, (user_id, today))
        result = cursor.fetchone()
        conn.close()
        return float(result["total"]) if result else 0.0
    except Exception as e:
        logger.error(f"❌ Lỗi khi lấy daily cost của user {user_id}: {e}")
        return 0.0


def is_user_rate_limited(user_id: str) -> bool:
    """
    Kiểm tra xem user đã vượt giới hạn chi phí ngày hay chưa.
    
    Args:
        user_id: ID người dùng
        
    Returns:
        bool: True nếu vượt hạn mức, False nếu không
    """
    daily_cost = get_user_daily_cost(user_id)
    return daily_cost >= MAX_DAILY_COST_USD


def log_cost(
    user_id: str,
    input_tokens: int,
    output_tokens: int,
    model_name: str = "gpt-4o-mini",
    session_id: Optional[str] = None,
    confidence_score: Optional[float] = None,
    endpoint: Optional[str] = None,
    quiz_score: str = "0/10",
    intent_detected: str = "none"
) -> dict:
    """
    Ghi log chi phí API call vào database và file JSON.
    
    Args:
        user_id:          ID người dùng
        input_tokens:     Số token đầu vào
        output_tokens:    Số token đầu ra
        model_name:       Tên model
        session_id:       ID phiên làm việc
        confidence_score: Điểm tự tin của AI (0-1)
        endpoint:         Endpoint API được gọi
        quiz_score:       Điểm quiz của học viên
        intent_detected:  Mục tiêu học / Intent của học viên
    
    Returns:
        dict với thông tin cost và rate_limited flag
    """
    cost = calculate_cost(input_tokens, output_tokens, model_name)
    
    # Kiểm tra daily cost limit
    daily_cost = get_user_daily_cost(user_id)
    is_rate_limited = (daily_cost + cost) > MAX_DAILY_COST_USD
    
    if is_rate_limited:
        logger.warning(f"⚠️ User {user_id} đã vượt ngưỡng chi phí ngày: ${daily_cost:.4f} + ${cost:.6f} > ${MAX_DAILY_COST_USD}")
    
    try:
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO cost_logs 
            (user_id, session_id, timestamp, model_name, input_tokens, output_tokens, 
             calculated_cost, confidence_score, endpoint, rate_limited)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            session_id,
            datetime.utcnow().isoformat(),
            model_name,
            input_tokens,
            output_tokens,
            cost,
            confidence_score,
            endpoint,
            int(is_rate_limited)
        ))
        conn.commit()
        conn.close()
        
        logger.info(f"💰 Cost logged | user={user_id} | tokens={input_tokens}+{output_tokens} | cost=${cost:.6f} | daily=${daily_cost:.4f}")
    except Exception as e:
        logger.error(f"❌ Lỗi khi ghi cost log vào SQLite: {e}")

    # Ghi log JSON cấu trúc vào file cost_logs.jsonl
    import json
    import uuid
    log_id = f"log_req_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
    
    json_log = {
        "log_id": log_id,
        "user_id": user_id,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_metrics": {
            "quiz_score": quiz_score,
            "intent_detected": intent_detected
        },
        "llm_usage": {
            "model_name": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "confidence_score": confidence_score if confidence_score is not None else 0.0,
            "calculated_cost_usd": cost
        }
    }
    
    try:
        log_dir = os.path.dirname(DB_PATH)
        os.makedirs(log_dir, exist_ok=True)
        jsonl_path = os.path.join(log_dir, "cost_logs.jsonl")
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(json_log, ensure_ascii=False) + "\n")
        logger.info(f"📝 JSON Cost log saved to file: {jsonl_path}")
    except Exception as e:
        logger.error(f"❌ Lỗi khi ghi cost log vào file JSONL: {e}")
    
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "calculated_cost": cost,
        "daily_cost_total": daily_cost + cost,
        "rate_limited": is_rate_limited
    }


def get_cost_summary(date_str: Optional[str] = None) -> list:
    """
    Lấy báo cáo chi phí theo ngày cho admin.
    
    Args:
        date_str: Ngày cần lấy báo cáo (ISO format, mặc định hôm nay)
    
    Returns:
        list các dict chứa thống kê chi phí per user
    """
    if not date_str:
        date_str = date.today().isoformat()
    
    try:
        conn = get_db_connection()
        cursor = conn.execute("""
            SELECT 
                user_id,
                COUNT(*) as total_calls,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(calculated_cost) as total_cost,
                AVG(confidence_score) as avg_confidence,
                MAX(rate_limited) as was_rate_limited
            FROM cost_logs
            WHERE DATE(timestamp) = ?
            GROUP BY user_id
            ORDER BY total_cost DESC
        """, (date_str,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception as e:
        logger.error(f"❌ Lỗi khi lấy cost summary: {e}")
        return []
