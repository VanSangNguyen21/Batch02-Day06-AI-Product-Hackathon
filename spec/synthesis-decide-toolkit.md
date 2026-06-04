# Toolkit — Từ Evidence Đến Build Slice

## 1. Gom evidence thành cụm

* **Cụm 1: "Ngợp thông tin & Hoang mang giữa ma trận tài liệu"**
  * Học viên mới không biết bắt đầu từ đâu.
  * Lộ trình chung chung từ internet gây nản chí.
* **Cụm 2: "Lộ trình học không khớp với vai trò thực tế (Mismatch)"**
  * Học viên Business/Manager bị ép học toán/code quá sâu.
  * Học viên Kỹ thuật muốn thực hành ngay nhưng lộ trình quá thiên về lý thuyết.
* **Cụm 3: "Sợ AI ảo giác (Hallucination) giới thiệu tài liệu rác/hỏng"**
  * Lộ trình tự sinh chứa link không tồn tại hoặc tài liệu chất lượng kém.
* **Cụm 4: "Tấn công đầu vào và lạm dụng chatbot (Abuse/Jailbreak)"**
  * User nhập các câu hỏi phá hoại hoặc hỏi lan man ngoài phạm vi AI Education.

## 2. Viết insight

```text
Học viên mới bắt đầu học AI không chỉ cần một danh sách các tài liệu hay các khóa học hay.
Họ thật ra cần hỗ trợ ra quyết định lộ trình tối ưu và cá nhân hóa sâu sắc theo công việc thực tế và năng lực hiện tại của mình,
vì các khảo sát và phản hồi cho thấy họ thường nản lòng và bỏ cuộc khi phải học những thứ quá khó hoặc quá xa vời với công việc thực tế của họ.
```

## 3. Viết opportunity

```text
Cơ hội là dùng AI để tự động phân loại trình độ học viên (thông qua điểm số quiz 10 câu) kết hợp với mục tiêu công việc của họ để thiết kế lộ trình tinh gọn (mở rộng nhánh cần thiết, ẩn nhánh không cần),
giúp học viên tiếp cận lộ trình học vừa sức, trực quan và đúng mục tiêu ứng dụng,
trong khi vẫn kiểm soát rủi ro thông qua bộ lọc Guardrails rules và cơ chế Fallback (khóa nhánh nâng cao nếu độ tự tin thấp).
```

## 4. Chọn build slice

Build slice của nhóm đã được kiểm thử qua 5 câu hỏi:

| Câu hỏi | Trạng thái đạt | Chi tiết thực tế |
|---|---|---|
| User cụ thể chưa? | ĐẠT | Học viên mới bắt đầu học AI (phân loại rõ luồng Tech vs Non-tech). |
| Task đủ hẹp chưa? | ĐẠT | Khai báo mục tiêu ngắn + làm quiz 10 câu -> nhận Roadmap visual & chat hỗ trợ. Demo xong trong 3 phút. |
| AI decision rõ chưa? | ĐẠT | AI chấm điểm, xác định độ tự tin (Confidence Score) và sinh cấu trúc lộ trình học (Happy Path hoặc Fallback). |
| Failure path rõ chưa? | ĐẠT | Thử nghiệm nhập prompt độc hại / jailbreak hoặc phá hoại hệ thống để kích hoạt block và log cost. |
| Có evidence không? | ĐẠT | Có bằng chứng từ trải nghiệm học thực tế của các thành viên lớp VinUni AI20k. |

## 5. Quyết định: giữ, giảm scope, hay đổi hướng?

* Nhóm chọn **Augmentation kết hợp Conditional Automation** cho prototype này.
* AI tự động xử lý và đề xuất lộ trình dựa trên điểm thi và mục tiêu (Automation), nhưng quyền quyết định cuối cùng và chỉnh sửa lộ trình vẫn thuộc về người dùng (Augmentation).
* Giới hạn phạm vi: Chỉ tập trung vào 2 luồng chính: Business/Product AI và Machine Learning/Data Science. Không làm dàn trải tất cả các ngành nghề.

## 6. Câu chốt cuối

```text
Dựa trên bằng chứng người học bị ngợp giữa tài liệu học AI và học sai định hướng công việc,
nhóm sẽ build prototype hệ thống cá nhân hóa lộ trình học AI cơ bản (AI Learning Path Personalizer),
cho học viên mới bắt đầu học AI,
để giải quyết nỗi đau mất định hướng và ngợp kiến thức,
bằng cách sử dụng AI kết hợp bài kiểm tra 10 câu để phân tích trình độ và đề xuất lộ trình dạng cây trực quan (2 Tab: Chatbot & Roadmap),
và sẽ test failure path bằng các kịch bản spam/jailbreak hệ thống hoặc khi AI chấm điểm tự tin thấp (<80%).
```

## 7. Backlog (Không build trong Day 06)

* Tính năng cho phép đăng nhập và đồng bộ tiến độ học qua nhiều thiết bị.
* Hệ thống tự động gợi ý video YouTube/bài viết mới nhất theo thời gian thực (Real-time Scraping).
* Tích hợp thanh toán học phí hoặc kết nối trực tiếp với giảng viên là người thật.
