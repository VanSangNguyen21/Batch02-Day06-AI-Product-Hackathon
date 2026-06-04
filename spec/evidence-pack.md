# Evidence Pack — Dự án Cá nhân hóa lộ trình học AI cơ bản

## 1. Nhóm và track

* **Tên nhóm:** Nhóm 02 - Batch 02 (AI Product Labs)
* **Track:** AI Education / EdTech
* **Product/app đã chọn:** AI Learning Path Personalizer
* **Build slice đang nghĩ:** Khai báo mục tiêu và làm quiz đầu vào 10 câu để AI phân loại trình độ và xuất lộ trình học dạng cây trực quan (Visual Tree Roadmap).

## 2. Self-use evidence

Nhóm tự dùng một số chatbot AI (như ChatGPT, Gemini) để hỏi về lộ trình học AI và ghi nhận các điểm gãy.

| Observation | Screenshot/link | Path liên quan | Điều học được |
|---|---|---|---|
| AI đưa ra lộ trình quá dài, chung chung và chứa nhiều kiến thức nâng cao ngay từ đầu cho một người làm Business. | - | Low-confidence | Cần phải phân loại rõ luồng học ngay từ đầu thông qua câu hỏi trắc nghiệm và mục tiêu công việc. |
| AI đưa ra các tài liệu học tập không tồn tại hoặc link liên kết bị hỏng (hallucination). | - | Failure | Cần dùng cấu trúc JSON cố định và cung cấp liên kết tài liệu từ các nguồn chính thống (Coursera, Kaggle, DeepLearning.AI). |
| Người dùng cố tình spam các từ khóa độc hại hoặc hỏi về việc bẻ khóa/hack hệ thống trong ô chat lộ trình. | - | Failure (Security) | Cần bộ lọc Guardrail ở cả Frontend và Backend để chặn đứng các câu hỏi ngoài luồng trước khi gửi lên API. |

## 3. User / review / social evidence

* **Quote / review / observation:**
  * *"Tôi muốn học AI để ứng dụng vào công việc quản lý sản phẩm (Product Management), nhưng khi lên mạng tìm lộ trình thì toàn thấy yêu cầu học giải tích, đại số tuyến tính và code Python từ đầu. Quá nản!"* (Học viên chuyển ngành).
  * *"Học được vài bữa rồi bỏ vì không biết cái gì nên học trước cái gì học sau, tài liệu thì nhiều vô kể."* (Sinh viên kỹ thuật).
* **Nguồn:** Khảo sát học viên VinUni AI20k và các cộng đồng tự học AI trên Facebook/Discord.
* **User là ai:** Người đi làm thuộc khối ngành phi kỹ thuật (Non-tech) và sinh viên muốn tìm hiểu AI nhưng thiếu nền tảng.
* **Pain/failure mode:** Học sai định hướng, lãng phí thời gian vào toán và code sâu trong khi chỉ cần hiểu khái niệm ứng dụng.

## 4. Competitor / analog evidence

| App / mô hình tham khảo | Họ xử lý task này thế nào? | Pattern học được | Có áp dụng trong 1 ngày không? |
|---|---|---|---|
| **Roadmap.sh** | Cung cấp cây lộ trình tĩnh cực kỳ chi tiết cho kỹ sư phần mềm. | Sơ đồ dạng cây (Tree visual) giúp người học dễ hình dung cấu trúc tri thức. | Có, nhóm vẽ cây lộ trình tĩnh/động ở Frontend bằng CSS và JS. |
| **Duolingo** | Cho làm bài test đầu vào ngắn để xếp lớp ngay lập tức thay vì hỏi quá nhiều. | Tích hợp Quiz trắc nghiệm đánh giá năng lực nhanh trước khi mở khóa lộ trình. | Có, tích hợp form 10 câu trắc nghiệm kiến thức cơ bản về AI/Toán/Lập trình. |

## 5. Evidence -> Insight

```text
Evidence nổi bật nhất:
Học viên phi kỹ thuật bị ép học các môn toán chuyên sâu và lập trình phức tạp khi hỏi lộ trình học AI, dẫn đến bỏ cuộc nhanh chóng.

Insight:
User không chỉ gặp khó khăn ở việc thiếu tài liệu (họ thực ra có quá nhiều tài liệu).
Thật ra họ cần một bộ lọc thông tin thông minh và cá nhân hóa cao độ để hỗ trợ ra quyết định xem "cái gì thực sự cần thiết cho mục tiêu của họ" và "được bắt đầu ở trình độ vừa sức".

Opportunity:
AI có thể giúp bằng cách phân tích hồ sơ và chấm điểm bài kiểm tra năng lực đầu vào để cắt tỉa lộ trình, chỉ giữ lại các milestone phù hợp với mục tiêu cụ thể của user.
```

## 6. Evidence đổi SPEC như thế nào?

* [x] Đổi build slice (Thêm bài test 10 câu để đánh giá khách quan thay vì chỉ dựa trên mô tả chủ quan của user).
* [x] Đổi 4 paths (Xác định rõ ràng 3 phân loại lộ trình: Happy Path cho độ tự tin cao, Low-confidence Fallback cho trường hợp thông tin trái ngược, và Failure Mode khi AI sinh lỗi).

**Ghi rõ 1-2 thay đổi quan trọng:**
```text
Trước evidence, nhóm định: Chỉ cho user nhập mục tiêu học tập bằng chữ (text), sau đó AI sinh lộ trình dạng chat text thông thường.
Sau evidence, nhóm đổi thành: Cho user nhập mục tiêu, trả lời 10 câu trắc nghiệm đầu vào để chấm điểm năng lực thực tế. Kết quả hiển thị thành 2 Tab: Tab 1 là Chatbot tư vấn chuyên sâu, Tab 2 là Lộ trình học dạng sơ đồ cây tương tác (milestones, link tài liệu, nút hoàn thành).
Lý do: Đảm bảo tính khách quan của việc đánh giá năng lực (tránh trường hợp user tự đánh giá quá cao hoặc quá thấp) và tăng trải nghiệm học trực quan (người học cần sơ đồ cây hơn là đọc đống text dài).
```
