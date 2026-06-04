# Day06 — AI Product Hackathon 🧠✨
## AI Learning Path Personalizer

> SPEC → Prototype → Demo. Hôm nay không có bài giảng mới — hôm nay chứng minh: SPEC là giả thuyết, prototype là bằng chứng, demo là thuyết phục.

---

## 👥 Thành viên nhóm

| Tên tài khoản | Họ và tên | Vai trò |
|---|---|---|
| **VanSangNguyen21** (sangthon2003@gmail.com) | Nguyễn Văn Sáng | Product Manager / Lead |
| **phammaianh11102005@gmail.com** | Phạm Mai Anh | Prompt / AI Engineer |
| **Shiner-2** | Phạm Ngọc Hải Dương | Backend Core Developer |
| **letho1608** | Lê Quang Thọ | Backend Data & Ops |
| **DoTrungDuc1908** | Đỗ Trung Đức | Frontend UI/UX Developer |
| **nguyetbinh** | Vương Nguyệt Bình | QA / Test & Pitching |

---

## 🎯 Mô tả sản phẩm

**AI Learning Path Personalizer** — Hệ thống cá nhân hóa lộ trình học AI dành cho người mới bắt đầu.

**Track:** Learning OS (Vin AI Thực Chiến)

**User:** Người mới bắt đầu học AI (sinh viên, người chuyển ngành, người làm kinh doanh/quản lý) đang bị ngợp giữa ma trận tài liệu học tập.

**Build slice:**
> Cho người mới bắt đầu học AI đang khai báo mục tiêu học tập, prototype dùng AI để phân tích mục tiêu & điểm số quiz đầu vào (10 câu) nhằm đề xuất lộ trình học dạng cây trực quan, tạo ra lộ trình học cá nhân hóa với Confidence Score tương ứng, và xử lý Low-confidence bằng cách kích hoạt Fallback hiển thị lộ trình cơ bản kèm khóa các nhánh nâng cao.

---

## 🚀 Tính năng chính

1. **Quiz & Goal Selection** — Form đăng ký mục tiêu + bài test 10 câu đánh giá trình độ
2. **Interactive Visual Tree Roadmap** — Lộ trình học dạng sơ đồ cây, có milestone, thời lượng và link tài liệu
3. **Conversational AI Companion** — Chatbot tích hợp giải thích milestone và tư vấn học tập
4. **4 Paths Protection** — Happy (>80%), Low-conf (50-80%), Failure, Correction/Feedback Loop
5. **AI Guardrails** — Chặn Prompt Injection, Rate Limit 5 tin/phút, khóa chat nếu chưa làm quiz
6. **Cost & Token Monitoring** — Theo dõi chi phí API theo từng phiên

---

## 📁 Cấu trúc repo

```text
Day06-AI-Product-Hackathon/
├── README.md                   ← File này (thành viên + mô tả sản phẩm)
├── spec/                       ← SPEC sản phẩm
│   ├── README.md               ← Hướng dẫn viết SPEC
│   ├── spec.md                 ← SPEC chính (thin-spec từ Day 5)
│   ├── evidence-pack.md        ← Bằng chứng / evidence
│   ├── thin-spec-template.md   ← Template thin SPEC
│   └── synthesis-decide-toolkit.md
└── codebase/                   ← Mã nguồn prototype
    ├── README.md               ← Hướng dẫn cài đặt & chạy
    ├── backend/                ← FastAPI backend
    │   ├── app/api/            ← API endpoints (analyze, chat, feedback, admin)
    │   ├── middleware/         ← Guardrails, Cost Logger, Data Masking
    │   ├── models/             ← SQLite Database & CRUD
    │   └── requirements.txt
    ├── frontend/               ← Giao diện web
    │   ├── index.html
    │   └── src/ (app.js, styles.css)
    ├── prompts/                ← System prompt & guardrail rules
    ├── evals/                  ← Test dataset & evaluation report
    ├── docs/                   ← Architecture & demo script
    └── cloudflare-demo/        ← Phiên bản deploy trên Cloudflare Workers
```

---

## ⚙️ Cách chạy prototype

### 1. Cài đặt dependencies

```bash
cd codebase/backend
pip install -r requirements.txt
```

### 2. Cấu hình môi trường

```bash
copy .env.example .env
```

Mặc định project chạy với Ollama local:
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
MODEL_NAME=llama3.2
MAX_DAILY_COST_USD=1.0
RATE_LIMIT_PER_MINUTE=5
```

Trước khi chạy backend, mở Ollama và tải model nếu cần:
```bash
ollama serve
ollama pull llama3.2
```

### 3. Chạy backend server

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 4. Chạy frontend

Mở file `codebase/frontend/index.html` trực tiếp bằng trình duyệt hoặc dùng **Live Server** trong VS Code.

---

## 🛠️ Tech Stack

| Layer | Công nghệ |
|-------|-----------|
| Frontend | HTML5, Vanilla CSS3 (Glassmorphism, Dark theme), Vanilla JavaScript |
| Backend | FastAPI (Python), Uvicorn, Pydantic, SQLite3 |
| AI Model | Ollama local mặc định — `llama3.2`; tùy chọn OpenAI-compatible / Gemini |
| Guardrails | Custom regex + keyword filter (guardrail_rules.json) |
| Cost tracking | SQLite cost_logs table + in-memory rate limiter |

---

## 👤 Phân công chi tiết

| Thành viên | Phần đã làm | File chứng minh |
|---|---|---|
| **VanSangNguyen21** | Product Lead — Quản lý Spec, định nghĩa Pain & Opportunity, tổng hợp tài liệu nhóm, tích hợp guardrails & evals pipeline | `spec/spec.md`, `spec/evidence-pack.md`, `codebase/evals/run_evals.py`, `codebase/backend/middleware/guardrails.py` |
| **phammaianh11102005** | Prompt Engineer — Thiết kế System Prompt, JSON Schema, Guardrail rules chống Injection | `codebase/prompts/system_prompt.txt`, `codebase/prompts/guardrail_rules.json` |
| **Shiner-2** | Backend Core — API `/api/analyze`, `/api/chat`, routing chính | `codebase/backend/app/api/analyze.py`, `codebase/backend/app/api/chat.py`, `codebase/backend/app/main.py` |
| **letho1608** | Backend Data & Ops — SQLite database, Cost Logger, Rate limits, Feedback log | `codebase/backend/models/database.py`, `codebase/backend/middleware/cost_logger.py`, `codebase/backend/app/api/feedback.py` |
| **DoTrungDuc1908** | Frontend UI/UX — Giao diện Web HTML/CSS/JS, Form khảo sát, Quiz 10 câu, Visual Tree Roadmap | `codebase/frontend/index.html`, `codebase/frontend/src/app.js`, `codebase/frontend/src/styles.css` |
| **nguyetbinh** | QA / Test & Pitching — Dataset 10 user profiles, evaluation report, demo script, architecture docs | `codebase/evals/test_dataset.json`, `codebase/evals/evaluation_report.md`, `codebase/docs/demo_script.md` |

---

*Batch 02 · Ngày 06 — VinUni AI20k · AI Thực Chiến · 2026*
