# AI Learning Path Personalizer 🧠✨

Hệ thống cá nhân hóa lộ trình học AI cơ bản dành cho người mới bắt đầu (học viên VinUni AI20k Batch 02 · Day 05). Hệ thống tự động phân loại năng lực người học thông qua mục tiêu và bài thi trắc nghiệm đầu vào, từ đó đề xuất lộ trình dạng cây tương tác và hỗ trợ chatbot tư vấn chuyên sâu.

## 🚀 Tính Năng Chính (Features)

1. **Khảo Sát & Trắc Nghiệm Đầu Vào (Quiz & Goal Selection):** Form đăng ký mục tiêu cùng bài test 10 câu trắc nghiệm kiến thức nền tảng AI/Toán/Python để đánh giá trình độ khách quan.
2. **Lộ Trình Tương Tác Dạng Cây (Interactive Visual Tree Roadmap):** Hiển thị sơ đồ lộ trình học dạng nhánh cây trực quan, có các milestone chi tiết, thời lượng học dự kiến và liên kết tài liệu chất lượng cao từ Coursera/Kaggle/DeepLearning.AI.
3. **Chatbot Tư Vấn Đồng Hành (Conversational AI Companion):** Chatbot tích hợp giúp giải thích các milestone trong lộ trình hoặc trả lời các thắc mắc chuyên sâu của học viên.
4. **Cơ Chế Bảo Vệ 4 Paths & Fallback:**
   * **Happy Path (Conf > 80%):** Lộ trình cá nhân hóa hoàn toàn.
   * **Low-Confidence Fallback (Conf 50% - 80%):** Khóa nhánh nâng cao và đề xuất lộ trình nền tảng chuẩn để tránh người học bị ngợp.
   * **Failure Mode:** Gặp sự cố hoặc dữ liệu rỗng sẽ kích hoạt chế độ Rollback về lộ trình mặc định và hiện nút cứu trợ.
   * **Correction / Feedback Loop:** Đánh giá thấp (1-2 sao) sẽ lưu vết toàn bộ phiên chat + quiz vào DatabaseSQLite để cải tiến mô hình.
5. **Bộ Lọc Bảo Vệ (AI Guardrails):**
   * Chặn Prompt Injection, chống rò rỉ prompt hệ thống.
   * Giới hạn tần suất chat (Rate Limit): tối đa 5 câu/phút để chống spam và cạn kiệt tài nguyên.
   * Chặn cổng chat nếu chưa làm đủ 3 câu quiz khảo sát để đảm bảo thông tin nền tảng.
6. **Giám Sát Chi Phí (Cost & Token Monitoring):** Tính toán và lưu chi phí API gọi LLM thực tế vào database, tự động khóa tài khoản tạm thời nếu tổng chi phí vượt quá $1.00 USD/ngày.

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack)

* **Frontend:** HTML5, Vanilla CSS3 (Custom Design System, Glassmorphism, animations), Vanilla JavaScript.
* **Backend:** FastAPI (Python), Uvicorn, Pydantic, HTTPX, SQLite3.
* **Mô hình AI:** OpenAI API (GPT-4o, GPT-4o-mini) hoặc Gemini API (Gemini 1.5 Flash).

---

## 📁 Cấu Trúc Thư Mục Dự Án (Project Structure)

```text
project/
├── backend/
│   ├── app/
│   │   ├── api/             # API Endpoints (analyze, chat, feedback, admin)
│   │   └── main.py          # Điểm khởi chạy FastAPI
│   ├── middleware/          # Cost & Rate Limiting Middleware
│   ├── models/              # SQLite Database & CRUD
│   ├── .env.example         # Mẫu file cấu hình môi trường
│   └── requirements.txt     # Các thư viện Python cần thiết
├── frontend/
│   ├── index.html           # File giao diện chính
│   └── src/
│       ├── app.js           # Xử lý logic và API Call ở Client
│       └── styles.css       # File style chính của dự án (Dark theme, Glass)
├── prompts/
│   ├── system_prompt.txt    # System prompt hướng dẫn AI xuất JSON lộ trình
│   └── guardrail_rules.json # Bộ quy tắc chặn từ khóa cấm và rate limit
├── evals/
│   ├── test_dataset.json    # 10 hồ sơ người học thử nghiệm
│   └── evaluation_report.md # Mẫu báo cáo đánh giá chất lượng prompt
└── docs/
    ├── architecture.md      # Tài liệu kiến trúc hệ thống
    └── demo_script.md       # Kịch bản demo chạy thử nghiệm
```

---

## ⚙️ Hướng Dẫn Cài Đặt & Chạy Dự Án (Installation & Startup)

### 1. Chuẩn Bị Cấu Hình Môi Trường (Backend Environment Setup)
1. Di chuyển vào thư mục backend:
   ```bash
   cd project/backend
   ```
2. Tạo file `.env` từ file mẫu:
   ```bash
   copy .env.example .env
   ```
3. Mở file `.env` lên và điền các API Key cần thiết:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   MODEL_NAME=gpt-4o-mini
   MAX_DAILY_COST_USD=1.0
   ```

### 2. Cài Đặt Thư Viện Python
```bash
pip install -r requirements.txt
```

### 3. Chạy Backend Server
Chạy lệnh khởi động Uvicorn từ thư mục `project/backend`:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API docs sẽ khả dụng tại địa chỉ: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 4. Chạy Frontend
Bạn chỉ cần mở trực tiếp file `project/frontend/index.html` bằng trình duyệt web của mình hoặc sử dụng tiện ích Live Server trong VS Code để chạy.



