"""
====================================================
  Quiz Bank with RAG Support
  Dynamic Question Selection Based on User Profile
  VinUni AI20k Batch 02 · Day 06
====================================================
"""

from typing import List, Dict, Any
import json

class QuizSet:
    """Định nghĩa một bộ câu hỏi với metadata"""
    def __init__(
        self,
        set_id: str,
        name: str,
        description: str,
        difficulty: str,  # easy, medium, hard, mixed
        topics: List[str],  # Các chủ đề của bộ câu hỏi
        target_goals: List[str],  # Mục tiêu học tập phù hợp
        prerequisites: List[str],  # Yêu cầu tối thiểu
        questions: List[Dict[str, Any]],
        embedding_text: str = None  # Text để embedding
    ):
        self.set_id = set_id
        self.name = name
        self.description = description
        self.difficulty = difficulty
        self.topics = topics
        self.target_goals = target_goals
        self.prerequisites = prerequisites
        self.questions = questions
        # Tạo text embedding từ description + topics + goals
        self.embedding_text = embedding_text or f"{name} {description} {' '.join(topics)} {' '.join(target_goals)}"


# ================================================================
# QUIZ BANK: Bộ câu hỏi khác nhau cho các lộ trình khác nhau
# ================================================================

QUIZ_BANK = [
    # ── Quiz Set 1: Fundamentals (Cho người bắt đầu từ 0)
    QuizSet(
        set_id="fund-001",
        name="AI & ML Fundamentals",
        description="Đánh giá kiến thức nền tảng về AI, Machine Learning và Toán học cơ bản",
        difficulty="easy",
        topics=["AI Basics", "ML Definitions", "Math Foundation", "Python Basics"],
        target_goals=["Learn AI Basics", "Learn ML from scratch", "Prepare for advanced courses"],
        prerequisites=[],
        questions=[
            {
                "id": "ch1-1",
                "text": "Machine Learning là gì?",
                "options": [
                    {"label": "A", "text": "Một nhánh của thiết kế phần mềm truyền thống"},
                    {"label": "B", "text": "Hệ thống dựa trên luật được lập trình thủ công"},
                    {"label": "C", "text": "Một lĩnh vực nghiên cứu cho phép máy học từ dữ liệu mà không cần lập trình tường minh"},
                    {"label": "D", "text": "Một phương pháp mã hóa dữ liệu"}
                ],
                "correct": 2,
                "explanation": "Đáp án C đúng vì định nghĩa này phản ánh đặc điểm cốt lõi của Machine Learning"
            },
            {
                "id": "ch1-2",
                "text": "Ai là người đã định nghĩa ML là 'Field of study that gives computers the ability to learn without being explicitly programmed'?",
                "options": [
                    {"label": "A", "text": "Andrew Ng"},
                    {"label": "B", "text": "Arthur Samuel"},
                    {"label": "C", "text": "Tom Mitchell"},
                    {"label": "D", "text": "Alan Turing"}
                ],
                "correct": 1,
                "explanation": "Đáp án B đúng vì đây là định nghĩa kinh điển của Arthur Samuel từ 1959"
            },
            {
                "id": "ch1-3",
                "text": "Tom Mitchell định nghĩa ML như thế nào?",
                "options": [
                    {"label": "A", "text": "ML là quá trình phân tích dữ liệu bằng tay"},
                    {"label": "B", "text": "ML là mô hình hoá các lý thuyết thống kê"},
                    {"label": "C", "text": "Một chương trình học từ kinh nghiệm E với nhiệm vụ T và đo lường P nếu hiệu suất tăng theo kinh nghiệm"},
                    {"label": "D", "text": "ML là việc lập trình các thuật toán tối ưu"}
                ],
                "correct": 2,
                "explanation": "Đáp án C là định nghĩa chính thức từ Tom Mitchell trong sách 'Machine Learning'"
            },
            {
                "id": "ch1-4",
                "text": "Mục tiêu chính của Machine Learning là gì?",
                "options": [
                    {"label": "A", "text": "Viết càng nhiều dòng code càng tốt"},
                    {"label": "B", "text": "Tạo hệ thống dựa trên luật cứng"},
                    {"label": "C", "text": "Xây dựng mô hình tổng quát hoá tốt trên dữ liệu chưa thấy"},
                    {"label": "D", "text": "Tăng tốc độ xử lý máy tính"}
                ],
                "correct": 2,
                "explanation": "Đáp án C đúng vì generalization là mục tiêu cốt lõi của ML"
            },
            {
                "id": "ch1-5",
                "text": "Phân loại nào sau đây là đúng về Machine Learning?",
                "options": [
                    {"label": "A", "text": "Supervised Learning, Unsupervised Learning, Reinforcement Learning"},
                    {"label": "B", "text": "Fast Learning, Slow Learning, Medium Learning"},
                    {"label": "C", "text": "Online Learning, Offline Learning, Batch Learning"},
                    {"label": "D", "text": "Tất cả đều đúng"}
                ],
                "correct": 0,
                "explanation": "Đáp án A là các phân loại chính của ML dựa trên loại tín hiệu huấn luyện"
            },
            {
                "id": "ch1-6",
                "text": "Deep Learning khác với Machine Learning truyền thống ở điểm nào?",
                "options": [
                    {"label": "A", "text": "Deep Learning sử dụng neural networks với nhiều lớp"},
                    {"label": "B", "text": "Deep Learning tự động học feature thay vì thủ công"},
                    {"label": "C", "text": "Deep Learning có thể xử lý dữ liệu không cấu trúc"},
                    {"label": "D", "text": "Tất cả đều đúng"}
                ],
                "correct": 3,
                "explanation": "Đáp án D đúng vì tất cả các đặc điểm này phân biệt Deep Learning"
            },
            {
                "id": "ch1-7",
                "text": "Overfitting trong Machine Learning là gì?",
                "options": [
                    {"label": "A", "text": "Mô hình học tốt cả dữ liệu train và test"},
                    {"label": "B", "text": "Mô hình học quá kỹ dữ liệu train nhưng không tổng quát trên dữ liệu mới"},
                    {"label": "C", "text": "Mô hình sử dụng quá nhiều features"},
                    {"label": "D", "text": "Mô hình có quá ít tham số"}
                ],
                "correct": 1,
                "explanation": "Đáp án B là định nghĩa chính xác của overfitting"
            },
            {
                "id": "ch1-8",
                "text": "Ngôn ngữ lập trình nào được sử dụng nhiều nhất cho Machine Learning?",
                "options": [
                    {"label": "A", "text": "Java"},
                    {"label": "B", "text": "Python"},
                    {"label": "C", "text": "C++"},
                    {"label": "D", "text": "JavaScript"}
                ],
                "correct": 1,
                "explanation": "Đáp án B đúng vì Python có ecosystem ML phong phú (TensorFlow, PyTorch, scikit-learn)"
            },
            {
                "id": "ch1-9",
                "text": "Epoch trong Machine Learning có nghĩa là gì?",
                "options": [
                    {"label": "A", "text": "Một lần lặp qua toàn bộ tập dữ liệu huấn luyện"},
                    {"label": "B", "text": "Một cập nhật trọng số của mô hình"},
                    {"label": "C", "text": "Một phút thực thi"},
                    {"label": "D", "text": "Một lớp trong neural network"}
                ],
                "correct": 0,
                "explanation": "Đáp án A là định nghĩa chính xác của epoch"
            },
            {
                "id": "ch1-10",
                "text": "Mô hình nào sau đây thường được sử dụng cho phân loại?",
                "options": [
                    {"label": "A", "text": "Linear Regression"},
                    {"label": "B", "text": "Logistic Regression"},
                    {"label": "C", "text": "Decision Tree"},
                    {"label": "D", "text": "B và C đều đúng"}
                ],
                "correct": 3,
                "explanation": "Đáp án D đúng vì cả Logistic Regression và Decision Tree được dùng cho classification"
            }
        ]
    ),

    # ── Quiz Set 2: Intermediate (Cho người có experience cơ bản)
    QuizSet(
        set_id="inter-001",
        name="Supervised Learning Deep Dive",
        description="Kiểm tra kiến thức sâu về Supervised Learning, Regression, Classification và Model Evaluation",
        difficulty="medium",
        topics=["Supervised Learning", "Regression", "Classification", "Model Evaluation"],
        target_goals=["Build supervised learning models", "Improve model accuracy", "Master model selection"],
        prerequisites=["ML Basics", "Python Fundamentals"],
        questions=[
            {
                "id": "inter-1",
                "text": "Cross-validation có mục đích gì trong Machine Learning?",
                "options": [
                    {"label": "A", "text": "Tăng tốc độ huấn luyện mô hình"},
                    {"label": "B", "text": "Đánh giá hiệu suất mô hình một cách đáng tin cậy trên dữ liệu chưa thấy"},
                    {"label": "C", "text": "Giảm kích thước tập dữ liệu"},
                    {"label": "D", "text": "Tăng kích thước bộ bộ nhớ"}
                ],
                "correct": 1,
                "explanation": "Cross-validation giúp ước lượng hiệu suất thực tế của mô hình"
            },
            {
                "id": "inter-2",
                "text": "Precision và Recall khác nhau ở điểm nào?",
                "options": [
                    {"label": "A", "text": "Precision là tỷ lệ dự đoán đúng, Recall là tỷ lệ phát hiện đúng"},
                    {"label": "B", "text": "Chúng là một thứ"},
                    {"label": "C", "text": "Precision chỉ dùng cho regression, Recall cho classification"},
                    {"label": "D", "text": "Precision luôn cao hơn Recall"}
                ],
                "correct": 0,
                "explanation": "Precision = TP/(TP+FP), Recall = TP/(TP+FN) - hai metric khác nhau"
            },
            {
                "id": "inter-3",
                "text": "Khi nào bạn nên chọn Random Forest thay vì Decision Tree?",
                "options": [
                    {"label": "A", "text": "Khi dữ liệu nhỏ"},
                    {"label": "B", "text": "Khi muốn giảm overfitting và tăng sự ổn định"},
                    {"label": "C", "text": "Khi cần mô hình nhanh chóng"},
                    {"label": "D", "text": "Khi features ít"}
                ],
                "correct": 1,
                "explanation": "Random Forest là ensemble method giúp giảm variance so với Decision Tree"
            },
            {
                "id": "inter-4",
                "text": "Gradient Descent có tác dụng gì?",
                "options": [
                    {"label": "A", "text": "Tìm cực tiểu của hàm loss"},
                    {"label": "B", "text": "Tìm cực đại của hàm loss"},
                    {"label": "C", "text": "Kiểm tra xem mô hình fit hay không"},
                    {"label": "D", "text": "Chia dữ liệu thành train/test"}
                ],
                "correct": 0,
                "explanation": "Gradient Descent là thuật toán tối ưu hóa để minimize loss function"
            },
            {
                "id": "inter-5",
                "text": "Regularization trong Machine Learning có tác dụng gì?",
                "options": [
                    {"label": "A", "text": "Tăng độ phức tạp của mô hình"},
                    {"label": "B", "text": "Giảm overfitting bằng cách penalize các trọng số lớn"},
                    {"label": "C", "text": "Tăng tốc độ huấn luyện"},
                    {"label": "D", "text": "Giảm số lượng features"}
                ],
                "correct": 1,
                "explanation": "Regularization (L1/L2) giúp kiểm soát độ phức tạp mô hình"
            },
            {
                "id": "inter-6",
                "text": "SVM (Support Vector Machine) là gì?",
                "options": [
                    {"label": "A", "text": "Một mô hình chỉ dùng cho regression"},
                    {"label": "B", "text": "Một mô hình tìm hyperplane tối ưu để phân chia dữ liệu"},
                    {"label": "C", "text": "Một phương pháp xử lý dữ liệu thất thoát"},
                    {"label": "D", "text": "Một kiến trúc neural network"}
                ],
                "correct": 1,
                "explanation": "SVM tìm margin lớn nhất giữa các lớp dữ liệu"
            },
            {
                "id": "inter-7",
                "text": "Feature scaling tại sao quan trọng?",
                "options": [
                    {"label": "A", "text": "Để mô hình học nhanh hơn và tránh các vấn đề số học"},
                    {"label": "B", "text": "Để tăng kích thước dataset"},
                    {"label": "C", "text": "Để giảm số features"},
                    {"label": "D", "text": "Không có tác dụng gì"}
                ],
                "correct": 0,
                "explanation": "Feature scaling giúp các thuật toán gradient-based hội tụ nhanh hơn"
            },
            {
                "id": "inter-8",
                "text": "Hyperparameter tuning là gì?",
                "options": [
                    {"label": "A", "text": "Quá trình tìm các tham số tốt nhất của mô hình"},
                    {"label": "B", "text": "Quá trình lựa chọn training data"},
                    {"label": "C", "text": "Quá trình test model"},
                    {"label": "D", "text": "Quá trình xóa dữ liệu thất thoát"}
                ],
                "correct": 0,
                "explanation": "Hyperparameter tuning thường dùng Grid Search hoặc Random Search"
            },
            {
                "id": "inter-9",
                "text": "K-Fold Cross Validation với K=5 có nghĩa là gì?",
                "options": [
                    {"label": "A", "text": "Chia dữ liệu thành 5 phần, huấn luyện 5 lần"},
                    {"label": "B", "text": "Chia dữ liệu thành 5 phần, test trên mỗi phần"},
                    {"label": "C", "text": "Chia dữ liệu thành 5 phần, huấn luyện 5 lần, test 4 lần mỗi lần"},
                    {"label": "D", "text": "Tất cả đều đúng"}
                ],
                "correct": 2,
                "explanation": "5-Fold CV: train trên 4 fold, validate trên 1 fold, lặp 5 lần"
            },
            {
                "id": "inter-10",
                "text": "ROC Curve dùng để đánh giá cái gì?",
                "options": [
                    {"label": "A", "text": "Hiệu suất của mô hình regression"},
                    {"label": "B", "text": "Trade-off giữa True Positive Rate và False Positive Rate"},
                    {"label": "C", "text": "Tốc độ huấn luyện"},
                    {"label": "D", "text": "Kích thước model"}
                ],
                "correct": 1,
                "explanation": "ROC curve trực quan hóa hiệu suất classifier ở các ngưỡng khác nhau"
            }
        ]
    ),

    # ── Quiz Set 3: For Business Users (Cho người làm kinh doanh/quản lý)
    QuizSet(
        set_id="biz-001",
        name="AI for Business Leaders",
        description="Đánh giá hiểu biết về AI, ứng dụng trong kinh doanh và quản lý dự án AI",
        difficulty="easy",
        topics=["AI Applications", "Business Strategy", "AI ROI", "Project Management"],
        target_goals=["Learn AI for business", "Understand AI use cases", "Lead AI projects"],
        prerequisites=[],
        questions=[
            {
                "id": "biz-1",
                "text": "AI mang lại giá trị gì cho doanh nghiệp?",
                "options": [
                    {"label": "A", "text": "Chỉ giảm chi phí"},
                    {"label": "B", "text": "Tự động hóa, cải thiện quyết định, tạo sản phẩm mới"},
                    {"label": "C", "text": "Không mang lại giá trị gì"},
                    {"label": "D", "text": "Chỉ dùng cho tech companies"}
                ],
                "correct": 1,
                "explanation": "AI tạo giá trị qua tự động hóa, analytics và innovation"
            },
            {
                "id": "biz-2",
                "text": "Triệu chứng nào cho thấy dự án AI sẽ thất bại?",
                "options": [
                    {"label": "A", "text": "Không có dữ liệu chất lượng"},
                    {"label": "B", "text": "Không có support từ leadership"},
                    {"label": "C", "text": "Không định nghĩa rõ business problem"},
                    {"label": "D", "text": "Tất cả đều là triệu chứng"}
                ],
                "correct": 3,
                "explanation": "Ba yếu tố này đều là rủi ro lớn cho dự án AI"
            },
            {
                "id": "biz-3",
                "text": "ROI (Return on Investment) của AI project nên được đo lường thế nào?",
                "options": [
                    {"label": "A", "text": "Tính (Lợi nhuận tăng - Chi phí AI) / Chi phí AI"},
                    {"label": "B", "text": "Tính số lượng model được deploy"},
                    {"label": "C", "text": "Tính accuracy của model"},
                    {"label": "D", "text": "Không thể đo lường"}
                ],
                "correct": 0,
                "explanation": "ROI = (Benefits - Costs) / Costs, phải liên kết với business outcomes"
            },
            {
                "id": "biz-4",
                "text": "Use case AI nào phổ biến nhất trong bán lẻ?",
                "options": [
                    {"label": "A", "text": "Dự đoán nhu cầu hàng"},
                    {"label": "B", "text": "Gợi ý sản phẩm cá nhân"},
                    {"label": "C", "text": "Phát hiện gian lận"},
                    {"label": "D", "text": "Tất cả đều phổ biến"}
                ],
                "correct": 3,
                "explanation": "Tất cả ba use case đều được áp dụng rộng rãi"
            },
            {
                "id": "biz-5",
                "text": "Khi nào nên thuê AI consultants?",
                "options": [
                    {"label": "A", "text": "Luôn luôn"},
                    {"label": "B", "text": "Khi không có in-house expertise và quy mô dự án lớn"},
                    {"label": "C", "text": "Không bao giờ"},
                    {"label": "D", "text": "Chỉ khi mô hình thất bại"}
                ],
                "correct": 1,
                "explanation": "Consultants giúp xác định problem, strategy và tránh lầm lỗi"
            },
            {
                "id": "biz-6",
                "text": "Data Privacy và GDPR ảnh hưởng đến AI project như thế nào?",
                "options": [
                    {"label": "A", "text": "Không ảnh hưởng"},
                    {"label": "B", "text": "Ảnh hưởng nhỏ"},
                    {"label": "C", "text": "Ảnh hưởng lớn - phải tuân thủ, có thể hạn chế dữ liệu"},
                    {"label": "D", "text": "Chỉ áp dụng cho EU"}
                ],
                "correct": 2,
                "explanation": "GDPR và quy định địa phương ảnh hưởng lớn đến data collection và usage"
            },
            {
                "id": "biz-7",
                "text": "Bias trong AI model có nguy hiểm gì?",
                "options": [
                    {"label": "A", "text": "Không có nguy hiểm"},
                    {"label": "B", "text": "Có thể dẫn đến quyết định bất công, tổn hại brand"},
                    {"label": "C", "text": "Chỉ ảnh hưởng kỹ thuật"},
                    {"label": "D", "text": "Không thể kiểm soát"}
                ],
                "correct": 1,
                "explanation": "Bias trong AI có thể gây ra hậu quả pháp lý, đạo đức và kinh doanh"
            },
            {
                "id": "biz-8",
                "text": "Agile methodology có phù hợp với AI project không?",
                "options": [
                    {"label": "A", "text": "Không, AI cần waterfall"},
                    {"label": "B", "text": "Có, nhưng cần điều chỉnh để phù hợp với R&D nature"},
                    {"label": "C", "text": "Chỉ phù hợp với data engineering"},
                    {"label": "D", "text": "Không có methodology nào phù hợp"}
                ],
                "correct": 1,
                "explanation": "Agile phù hợp nhưng cần iterations nhanh và feedback loop từ business"
            },
            {
                "id": "biz-9",
                "text": "Model complexity và business value có mối quan hệ gì?",
                "options": [
                    {"label": "A", "text": "Phức tạp hơn = giá trị cao hơn"},
                    {"label": "B", "text": "Đơn giản hơn = giá trị cao hơn"},
                    {"label": "C", "text": "Cần balance: simple models có thể đủ tốt nhưng dễ deploy"},
                    {"label": "D", "text": "Không liên quan"}
                ],
                "correct": 2,
                "explanation": "Interpretability và maintainability thường quan trọng hơn complexity"
            },
            {
                "id": "biz-10",
                "text": "Tại sao nên start với pilot project cho AI?",
                "options": [
                    {"label": "A", "text": "Tiết kiệm chi phí, học hỏi, giảm rủi ro"},
                    {"label": "B", "text": "Không cần pilot nếu có kế hoạch tốt"},
                    {"label": "C", "text": "Chỉ cần pilot nếu budget hạn chế"},
                    {"label": "D", "text": "Pilot làm lãng phí thời gian"}
                ],
                "correct": 0,
                "explanation": "Pilot projects giúp validate hypothesis và build credibility"
            }
        ]
    ),

    # ── Quiz Set 4: Advanced / NLP (Cho người tập trung vào NLP)
    QuizSet(
        set_id="nlp-001",
        name="Natural Language Processing Basics",
        description="Kiểm tra kiến thức về NLP, embeddings, transformers và ứng dụng",
        difficulty="hard",
        topics=["NLP", "Text Preprocessing", "Word Embeddings", "Transformers", "LLM"],
        target_goals=["Master NLP techniques", "Build NLP applications", "Work with LLMs"],
        prerequisites=["ML Fundamentals", "Python programming"],
        questions=[
            {
                "id": "nlp-1",
                "text": "Tokenization trong NLP có mục đích gì?",
                "options": [
                    {"label": "A", "text": "Chia văn bản thành các đơn vị nhỏ (tokens)"},
                    {"label": "B", "text": "Dịch văn bản sang ngôn ngữ khác"},
                    {"label": "C", "text": "Xoá các từ không quan trọng"},
                    {"label": "D", "text": "Nén dữ liệu văn bản"}
                ],
                "correct": 0,
                "explanation": "Tokenization là bước đầu tiên trong NLP preprocessing"
            },
            {
                "id": "nlp-2",
                "text": "Word2Vec là gì?",
                "options": [
                    {"label": "A", "text": "Một cách chuyển từ thành vector có ý nghĩa"},
                    {"label": "B", "text": "Một bản dịch tự động"},
                    {"label": "C", "text": "Một công cụ để kiểm tra chính tả"},
                    {"label": "D", "text": "Một loại HTML"}
                ],
                "correct": 0,
                "explanation": "Word2Vec dùng Skip-gram hoặc CBOW để tạo embeddings"
            },
            {
                "id": "nlp-3",
                "text": "Transformer architecture khác gì so với RNN/LSTM?",
                "options": [
                    {"label": "A", "text": "Dùng Attention mechanism thay vì sequential processing"},
                    {"label": "B", "text": "Nhanh hơn và có thể xử lý sequences dài hơn"},
                    {"label": "C", "text": "Cho kết quả tốt hơn trên NLP tasks"},
                    {"label": "D", "text": "Tất cả đều đúng"}
                ],
                "correct": 3,
                "explanation": "Transformers có tất cả những ưu điểm trên"
            },
            {
                "id": "nlp-4",
                "text": "BERT là gì?",
                "options": [
                    {"label": "A", "text": "Một pre-trained language model dùng bidirectional context"},
                    {"label": "B", "text": "Một mô hình translation"},
                    {"label": "C", "text": "Một bộ từ điển"},
                    {"label": "D", "text": "Một phương pháp xoá dữ liệu thất thoát"}
                ],
                "correct": 0,
                "explanation": "BERT là mô hình pre-trained của Google, nền tảng cho nhiều ứng dụng"
            },
            {
                "id": "nlp-5",
                "text": "Fine-tuning một pre-trained model có ưu điểm gì?",
                "options": [
                    {"label": "A", "text": "Cần ít dữ liệu labeled hơn"},
                    {"label": "B", "text": "Huấn luyện nhanh hơn"},
                    {"label": "C", "text": "Kết quả tốt hơn trên task cụ thể"},
                    {"label": "D", "text": "Tất cả đều đúng"}
                ],
                "correct": 3,
                "explanation": "Transfer learning qua fine-tuning là phương pháp phổ biến"
            },
            {
                "id": "nlp-6",
                "text": "Attention mechanism giải quyết vấn đề nào của RNN?",
                "options": [
                    {"label": "A", "text": "Vanishing gradient problem"},
                    {"label": "B", "text": "Không thể xử lý dependencies dài"},
                    {"label": "C", "text": "Tốc độ xử lý chậm"},
                    {"label": "D", "text": "Tất cả đều đúng"}
                ],
                "correct": 3,
                "explanation": "Attention có thể focus vào relevant parts của sequence"
            },
            {
                "id": "nlp-7",
                "text": "Stop words trong NLP nên được xoá hay giữ?",
                "options": [
                    {"label": "A", "text": "Luôn luôn xoá"},
                    {"label": "B", "text": "Luôn luôn giữ"},
                    {"label": "C", "text": "Phụ thuộc vào task"},
                    {"label": "D", "text": "Không có stop words"}
                ],
                "correct": 2,
                "explanation": "Có tasks cần stop words (semantic), có tasks không cần"
            },
            {
                "id": "nlp-8",
                "text": "GPT khác gì so với BERT?",
                "options": [
                    {"label": "A", "text": "GPT dùng causal attention, BERT dùng bidirectional"},
                    {"label": "B", "text": "GPT là generative, BERT là feature extractor"},
                    {"label": "C", "text": "GPT có thể generate text, BERT dùng cho classification"},
                    {"label": "D", "text": "Tất cả đều đúng"}
                ],
                "correct": 3,
                "explanation": "GPT và BERT có kiến trúc khác nhau phục vụ mục đích khác"
            },
            {
                "id": "nlp-9",
                "text": "Embedding dimension (d_model) là gì?",
                "options": [
                    {"label": "A", "text": "Số chiều của vector biểu diễn từ"},
                    {"label": "B", "text": "Số từ trong vocabulary"},
                    {"label": "C", "text": "Số layer trong model"},
                    {"label": "D", "text": "Số parameter của model"}
                ],
                "correct": 0,
                "explanation": "Embedding dimension điều chỉnh complexity và quality của embeddings"
            },
            {
                "id": "nlp-10",
                "text": "Zero-shot learning trong NLP là gì?",
                "options": [
                    {"label": "A", "text": "Không huấn luyện model"},
                    {"label": "B", "text": "Model có thể thực hiện task mà chưa từng thấy dữ liệu training"},
                    {"label": "C", "text": "Model sinh output bằng 0"},
                    {"label": "D", "text": "Model không có accuracy"}
                ],
                "correct": 1,
                "explanation": "LLMs như GPT-3 có thể zero-shot thông qua prompt engineering"
            }
        ]
    ),
]


def get_all_quiz_sets() -> List[QuizSet]:
    """Lấy tất cả quiz sets"""
    return QUIZ_BANK


def get_quiz_set_by_id(set_id: str) -> QuizSet:
    """Lấy quiz set theo ID"""
    for quiz_set in QUIZ_BANK:
        if quiz_set.set_id == set_id:
            return quiz_set
    return None


def get_quiz_sets_by_difficulty(difficulty: str) -> List[QuizSet]:
    """Lấy quiz sets theo độ khó"""
    return [q for q in QUIZ_BANK if q.difficulty == difficulty]


def get_quiz_sets_by_topic(topic: str) -> List[QuizSet]:
    """Lấy quiz sets chứa một topic cụ thể"""
    return [q for q in QUIZ_BANK if topic in q.topics]


def get_quiz_sets_by_goal(goal: str) -> List[QuizSet]:
    """Lấy quiz sets phù hợp với một mục tiêu cụ thể"""
    return [q for q in QUIZ_BANK if goal in q.target_goals]
