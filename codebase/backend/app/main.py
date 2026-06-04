"""
====================================================
  AI Path - Backend API Main Entry Point
  FastAPI Application
  VinUni AI20k Batch 02 · Day 05
====================================================
"""

from dotenv import load_dotenv
import os
# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path)

import sys
import subprocess
# ──────────────────────────────────────────────────────────────────────────────
# Kill any process already bound to our target port (avoids "address in use"
# errors when restarting the server). Windows + POSIX compatible.
# ──────────────────────────────────────────────────────────────────────────────
def _kill_processes_on_port(port: int) -> int:
    """Kill all processes bound to the given TCP port. Returns number killed."""
    current_pid = os.getpid()
    killed = 0
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                f'netstat -ano | findstr :{port}',
                shell=True, text=True, stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            return 0
        seen = set()
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            pid = int(parts[-1])
            if pid == current_pid or pid in seen:
                continue
            seen.add(pid)
            try:
                subprocess.run(
                    f'taskkill /F /PID {pid}',
                    shell=True, capture_output=True, text=True,
                )
                killed += 1
            except Exception:
                pass
    else:
        try:
            out = subprocess.check_output(
                ["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
                stderr=subprocess.DEVNULL, text=True,
            )
            for pid in out.strip().split():
                pid = int(pid)
                if pid == current_pid:
                    continue
                try:
                    os.kill(pid, 9)
                    killed += 1
                except Exception:
                    pass
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return killed


_SERVER_PORT = int(os.getenv("PORT", "8000"))
_n_killed = _kill_processes_on_port(_SERVER_PORT)
if _n_killed:
    print(f"[main] Killed {_n_killed} existing process(es) on port {_SERVER_PORT}", flush=True)
    import time as _t; _t.sleep(0.5)  # let the OS release the socket

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import io

# ──────────────────────────────────────────────────────────────────────────────
# Force UTF-8 on stdout/stderr so Vietnamese log messages render correctly
# on Windows consoles (default codepage = cp1252 → would mangle diacritics).
# Must run BEFORE logging.basicConfig.
# ──────────────────────────────────────────────────────────────────────────────
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass

from app.api import analyze, chat, feedback, admin, auth
from models.database import init_db

# Cấu hình logging / Logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup và shutdown events"""
    # Khởi tạo database khi start
    logger.info(" Khởi động AI Path Backend...")
    init_db()
    logger.info(" Database đã được khởi tạo thành công")
    yield
    # Cleanup khi shutdown
    logger.info(" AI Path Backend đang dừng...")


# Khởi tạo FastAPI app
app = FastAPI(
    title="AI Path API",
    description="Backend API cho hệ thống cá nhân hóa lộ trình học AI - VinUni AI20k Batch 02",
    version="1.0.0",
    lifespan=lifespan
)

# ==================== CORS MIDDLEWARE ====================
# Cho phép frontend connect (trong production, giới hạn origins cụ thể)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong production: ["https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ROUTES ====================
app.include_router(auth.router,    prefix="/api/auth", tags=["Authentication"])
app.include_router(analyze.router, prefix="/api", tags=["Phân tích & Lộ trình"])
app.include_router(chat.router,    prefix="/api", tags=["Chatbot"])
app.include_router(feedback.router, prefix="/api", tags=["Feedback"])
app.include_router(admin.router,   prefix="/api/admin", tags=["Admin"])


# ==================== HEALTH CHECK ====================
@app.get("/health", tags=["System"])
async def health_check():
    """Kiểm tra trạng thái hệ thống"""
    return {
        "status": "healthy",
        "service": "AI Path Backend",
        "version": "1.0.0",
        "batch": "VinUni AI20k Batch 02"
    }


# @app.get("/", tags=["System"])
# async def root():
#     """Root endpoint"""
#     return {
#         "message": " Chào mừng đến với AI Path API!",
#         "docs": "/docs",
#         "health": "/health"
#     }

# Mount frontend static files
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
frontend_dir = os.path.join(project_root, "frontend")
if os.path.exists(frontend_dir):
    logger.info(f" Mounting frontend static files from: {frontend_dir}")
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    logger.warning(f" Frontend directory not found at: {frontend_dir}")


# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint — hardcoded localhost:8000, reload=False (port-killer handles restart)
# Usage:  python app/main.py
#      or python -m app.main
# ──────────────────────────────────────────────────────────────────────────────
def run(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Start uvicorn with hardcoded defaults. Override via kwargs if needed."""
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run()
