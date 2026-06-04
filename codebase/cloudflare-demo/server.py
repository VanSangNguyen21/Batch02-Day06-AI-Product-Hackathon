# ============================================================
# CLOUDFLARE SHIELD & AI HUB — FASTAPI BACKEND
# Provides static hosting, Turnstile backend verification,
# and mock/live proxying to Cloudflare Workers AI.
# ============================================================

import os
import time
import httpx
import logging
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cloudflare-server")

app = FastAPI(
    title="Cloudflare Developer Shield Backend",
    description="FastAPI Backend for verifying Turnstile tokens and communicating with Cloudflare Workers AI",
    version="1.0.0"
)

# CORS configurations (allow frontend to call from any local port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class TurnstileRequest(BaseModel):
    token: str
    username: str
    action: str

class AIRequest(BaseModel):
    prompt: str

# Cloudflare Turnstile Testing Secret Keys mapping
SECRET_KEYS_MAP = {
    # Site Key -> Secret Key
    "1x00000000000000000000AA": "1x00000000000000000000000000000000AA", # Always Pass
    "2x00000000000000000000AB": "2x00000000000000000000000000000000AB", # Always Fail
    "3x00000000000000000000FF": "3x00000000000000000000000000000000FF", # Force Interactive
}

# ─── TURNSTILE VERIFICATION ENDPOINT ──────────────────────────
@app.post("/api/verify-turnstile")
async def verify_turnstile(req: TurnstileRequest, request: Request):
    logger.info(f"Received verification request from user: {req.username} for action: {req.action}")
    
    # 1. Determine site key type from token prefix to map the correct secret key
    # (Cloudflare's Turnstile tokens carry sitekey details inside them)
    # For simplicity, we can inspect the token or default to the Always Pass secret.
    secret_key = "1x00000000000000000000000000000000AA"
    
    # Look for signatures of failure/pass test keys
    if "2x00000000000000000000AB" in req.token or req.token.startswith("XXXX.dummy.token.fail"):
        secret_key = SECRET_KEYS_MAP["2x00000000000000000000AB"]
    elif "3x00000000000000000000FF" in req.token:
        secret_key = SECRET_KEYS_MAP["3x00000000000000000000FF"]

    # 2. Get client remote IP
    client_ip = request.client.host
    
    # 3. Call Cloudflare siteverify API
    cf_verify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    payload = {
        "secret": secret_key,
        "response": req.token,
        "remoteip": client_ip
    }
    
    start_time = time.time()
    try:
        async with httpx.AsyncClient() as client:
            cf_response = await client.post(cf_verify_url, data=payload, timeout=5.0)
            cf_data = cf_response.json()
            
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Cloudflare Turnstile verification took {elapsed_ms}ms. Response: {cf_data}")
        
        if cf_data.get("success"):
            return {
                "success": True,
                "message": "Token verification passed successfully",
                "cf_response_time": elapsed_ms,
                "country": request.headers.get("cf-ipcountry", "VN"),
                "action": req.action
            }
        else:
            error_codes = cf_data.get("error-codes", [])
            logger.warning(f"Verification failed on Cloudflare end: {error_codes}")
            raise HTTPException(
                status_code=400,
                detail=f"Turnstile token verification failed. Error codes: {error_codes}"
            )
            
    except httpx.RequestError as e:
        logger.error(f"Failed to communicate with Cloudflare siteverify: {e}")
        # Fallback for offline / network errors
        if secret_key == SECRET_KEYS_MAP["2x00000000000000000000AB"]:
            raise HTTPException(
                status_code=400,
                detail="Simulated Verification Failure (Network Offline / Always Fail Mode)"
            )
        return {
            "success": True,
            "message": "Token verification simulated (Cloudflare network unreachable)",
            "cf_response_time": 0,
            "country": "VN",
            "action": req.action
        }

# ─── WORKERS AI TEXT PROXY ────────────────────────────────────
@app.post("/api/workers-ai/text")
async def run_ai_text(req: AIRequest):
    # Try fetching Cloudflare credentials from environment (if set by user)
    cf_account_id = os.environ.get("CF_ACCOUNT_ID")
    cf_api_token = os.environ.get("CF_API_TOKEN")

    if cf_account_id and cf_api_token:
        logger.info("Real Cloudflare credentials detected! Proxying request to Workers AI...")
        url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/ai/run/@cf/meta/llama-3.1-8b-instruct"
        headers = {"Authorization": f"Bearer {cf_api_token}"}
        body = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant running on Cloudflare Workers AI."},
                {"role": "user", "content": req.prompt}
            ]
        }
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers, json=body, timeout=15.0)
                return res.json()
        except Exception as e:
            logger.error(f"Error calling real Cloudflare API: {e}")
            raise HTTPException(status_code=502, detail=f"Cloudflare Workers AI Gateway Error: {e}")
    else:
        # Simulate text generation response
        logger.info("No Cloudflare credentials found. Returning high-fidelity mock response.")
        time.sleep(1.0)
        return {
            "model": "@cf/meta/llama-3.1-8b-instruct",
            "success": True,
            "result": {
                "response": f"Xin chào! Đây là phản hồi giả lập từ Meta Llama 3.1 chạy trên Cloudflare Edge Network. Bạn đã nhập prompt: '{req.prompt}'. Để kích hoạt API thật, hãy cấu hình CF_ACCOUNT_ID và CF_API_TOKEN trong file .env hoặc biến môi trường hệ thống."
            },
            "tokens_used": 156,
            "cost_usd": 0.000015
        }

# ─── WORKERS AI IMAGE PROXY ───────────────────────────────────
@app.post("/api/workers-ai/image")
async def run_ai_image(req: AIRequest):
    cf_account_id = os.environ.get("CF_ACCOUNT_ID")
    cf_api_token = os.environ.get("CF_API_TOKEN")

    if cf_account_id and cf_api_token:
        logger.info("Real Cloudflare credentials detected! Generating image via Workers AI...")
        url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell"
        headers = {"Authorization": f"Bearer {cf_api_token}"}
        body = {"prompt": req.prompt}
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers, json=body, timeout=25.0)
                # Cloudflare returns raw image bytes for Flux model
                if res.status_code == 200:
                    import base64
                    encoded_img = base64.b64encode(res.content).decode("utf-8")
                    return {
                        "model": "@cf/black-forest-labs/flux-1-schnell",
                        "success": True,
                        "image_url": f"data:image/jpeg;base64,{encoded_img}"
                    }
                else:
                    raise HTTPException(status_code=res.status_code, detail="Failed generating image on Cloudflare")
        except Exception as e:
            logger.error(f"Error calling real Cloudflare API: {e}")
            raise HTTPException(status_code=502, detail=f"Cloudflare Workers AI Gateway Error: {e}")
    else:
        # Mock image trigger (app.js will catch and fall back to unsplash image display)
        time.sleep(1.5)
        raise HTTPException(
            status_code=501,
            detail="Cloudflare credentials not configured. Falling back to frontend sandbox simulation."
        )

# Mount static files to serve the frontend directly at http://localhost:8080/
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting local server...")
    uvicorn.run(app, host="127.0.0.1", port=8080)
