# Thin SPEC — Dự án Cá nhân hóa lộ trình học AI cơ bản

## 1. Track, product/app và user

* **Track:** AI Education / Công nghệ Giáo dục (EdTech).
* **Product/app thật:** AI Learning Path Personalizer (Cá nhân hóa lộ trình học AI).
* **User cụ thể:** Người mới bắt đầu học AI (sinh viên, người chuyển ngành, người làm kinh doanh/quản lý) đang bị ngợp giữa ma trận tài liệu học tập.
* **Nhóm có phải user thật không? Nếu không, khác ở đâu?** Có, các thành viên trong nhóm cũng từng là những người mới bắt đầu học AI và trải qua cảm giác ngợp thông tin, do đó thấu hiểu sâu sắc nỗi đau của người dùng.

## 2. Evidence summary

| Evidence | Nguồn | User/pain nói lên điều gì? | SPEC phải đổi gì? |
|---|---|---|---|
| Người học ngợp giữa tài liệu (Coursera, YouTube, Kaggle) | Phỏng vấn học viên & Self-use | Không biết bắt đầu từ đâu, học trước quên sau | Cần có quiz đánh giá đầu vào thay vì chỉ khai báo mục tiêu bằng lời nói |
| Người học kinh doanh bị bắt học toán tuyến tính | Phản hồi cộng đồng | Lộ trình quá xa rời thực tế công việc | Phân loại rõ ràng luồng người dùng (Business vs Technical) |
| AI sinh lộ trình ảo hoặc tài liệu hỏng | Test prompt ban đầu | Người học mất lòng tin | Thêm cấu trúc JSON Mode cố định tài liệu và link nguồn uy tín |

## 3. Pain statement

```text
Người mới học AI đang gặp khó ở bước chọn lộ trình và tài liệu học phù hợp,
vì họ bị ngợp bởi quá nhiều nguồn tài liệu (YouTube, Kaggle, Coursera) mà không biết cái nào phù hợp với năng lực và mục tiêu của mình,
dẫn tới mất định hướng, học trước quên sau, bỏ cuộc giữa chừng.
Bằng chứng chính là các phản hồi: "Học kinh doanh AI nhưng bị ép code toán tuyến tính", "không biết bắt đầu từ đâu sau khi xem 10 video khác nhau".
```

## 4. Build slice

```text
Cho người mới bắt đầu học AI đang khai báo mục tiêu học tập,
prototype sẽ dùng AI để phân tích mục tiêu & điểm số quiz đầu vào (10 câu) nhằm đề xuất một lộ trình học dạng cây trực quan (Visual Tree Roadmap),
tạo ra lộ trình học cá nhân hóa với độ tự tin (Confidence Score) tương ứng,
và xử lý tình trạng Low-confidence bằng cách kích hoạt chế độ Fallback hiển thị lộ trình cơ bản kèm khóa các nhánh nâng cao.
```

## 5. Auto/Aug decision

* [x] **Augmentation:** AI gợi ý/đề xuất lộ trình học, người dùng giữ quyền chỉnh sửa, tích chọn hoàn thành milestone hoặc chat với AI để yêu cầu giải thích thêm hoặc điều chỉnh lộ trình.
* **Lý do chọn:** Lộ trình học là vấn đề mang tính cá nhân cao. AI chỉ đóng vai trò tư vấn định hướng, người học phải là người chủ động quyết định học cái gì và khi nào.
* **Human role:** **reviewer / decider** (Người dùng xem và quyết định lộ trình của mình).

## 6. Four paths

| Path | Prototype phải thể hiện gì? |
|---|---|
| **Happy Path** (Conf > 80%) | Hiển thị lộ trình cá nhân hóa hoàn chỉnh dưới dạng cây visual tương tác, có các milestone rõ ràng, thời lượng học và link tài liệu đính kèm. |
| **Low-confidence** (Conf 50% - 80%) | Kích hoạt chế độ **Fallback**: Hiển thị cảnh báo màu vàng, khóa các nhánh nâng cao, đề xuất lộ trình cơ bản chuẩn hóa để học viên tích lũy thêm kiến thức nền tảng trước. |
| **Failure** | Khi AI lỗi hệ thống hoặc sinh ra dữ liệu rỗng/hỏng. Hệ thống hiển thị Alert lỗi màu đỏ và nút **"Reset & Yêu cầu hỗ trợ"**, rollback tài khoản về lộ trình mặc định. |
| **Correction** | Khi người dùng chấm điểm feedback thấp (1-2 sao) hoặc sửa lộ trình. Hệ thống kích hoạt **Feedback Loop**, tự động lưu lịch sử phiên làm việc vào cơ sở dữ liệu SQLite để làm tập kiểm thử. |

## 7. Failure mode nguy hiểm nhất

```text
Nếu user nhập mục tiêu độc hại, spam ký tự hoặc hỏi ngoài luồng khi chưa làm quiz,
AI có thể sinh câu trả lời vô nghĩa hoặc bị jailbreak lộ system prompt,
hậu quả là tốn chi phí API, làm hỏng giao diện hoặc rò rỉ dữ liệu hệ thống.
Prototype sẽ xử lý bằng bộ lọc Guardrail rules (Regex & Keyword), giới hạn Rate Limit (5 câu/phút) và chặn cổng chat nếu chưa hoàn thành quiz.
Owner kiểm thử path này là Thành viên D (QA/Test).
```

## 8. Owner plan cho sáng Day 06 (Team 6 Thành Viên)

| Thành viên | Vai trò | Việc phụ trách | Bằng chứng cần có trong repo |
|---|---|---|---|
| **VanSangNguyen21** (sangthon2003@gmail.com) | **Product Manager / Lead** | Quản lý Spec, định nghĩa Pain & Opportunity, tổng hợp tài liệu nhóm | `/02-group-spec/thin-spec.md`, `/02-group-spec/evidence-pack.md` |
| **phammaianh11102005@gmail.com** | **Prompt / AI Engineer** | Thiết kế System Prompt, JSON Output, Few-shot Prompting và Guardrail chống Injection | `/prompts/system_prompt.txt`, `/prompts/guardrail_rules.json` |
| **Shiner-2** | **Backend Core Developer** | Phát triển API Endpoint phân tích (`/api/analyze`), chat (`/api/chat`) và cấu hình định tuyến chính | `/backend/app/api/analyze.py`, `/backend/app/api/chat.py`, `/backend/app/main.py` |
| **letho1608** | **Backend Data & Ops** | Thiết kế SQLite database, Cost Logger middleware đo lường token, xử lý Rate limits và lưu Feedback log | `/backend/models/database.py`, `/backend/middleware/cost_logger.py`, `/backend/app/api/feedback.py` |
| **DoTrungDuc1908** | **Frontend UI/UX Developer** | Phát triển giao diện Web HTML/CSS/JS chia Tab, Form khảo sát, Quiz 10 câu và kết xuất sơ đồ cây | `/frontend/index.html`, `/frontend/src/app.js`, `/frontend/src/styles.css` |
| **nguyetbinh** | **QA / Test & Pitching** | Xây dựng bộ dataset test 10 người dùng, viết báo cáo đánh giá chất lượng prompt, soạn kịch bản Demo | `/evals/test_dataset.json`, `/evals/evaluation_report.md`, `/docs/demo_script.md`, `/docs/architecture.md` |

