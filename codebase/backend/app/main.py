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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from app.api import analyze, chat, feedback, admin
from models.database import init_db

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup và shutdown events"""
    # Khởi tạo database khi start
    logger.info("🚀 Khởi động AI Path Backend...")
    init_db()
    logger.info("✅ Database đã được khởi tạo thành công")
    yield
    # Cleanup khi shutdown
    logger.info("👋 AI Path Backend đang dừng...")


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
#         "message": "🧠 Chào mừng đến với AI Path API!",
#         "docs": "/docs",
#         "health": "/health"
#     }

# Mount frontend static files
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
frontend_dir = os.path.join(project_root, "frontend")
if os.path.exists(frontend_dir):
    logger.info(f"📁 Mounting frontend static files from: {frontend_dir}")
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    logger.warning(f"⚠️ Frontend directory not found at: {frontend_dir}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Tự động reload khi code thay đổi (development)
        log_level="info"
    )
