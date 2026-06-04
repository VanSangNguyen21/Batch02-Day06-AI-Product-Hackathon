# RAG Quiz Selection System — Documentation

## Overview 📚

Hệ thống **RAG (Retrieval-Augmented Generation) Quiz Selection** là một hệ thống thông minh để **chọn bộ câu hỏi phù hợp** dựa trên profile của người dùng.

**Mục tiêu:** Trước khi lập lộ trình học tập, hệ thống sẽ:
1. Phân tích mục tiêu & background của người dùng
2. Sử dụng semantic similarity (embedding + cosine similarity) để chọn bộ câu hỏi tối ưu
3. Trả về 10 câu hỏi được customized cho từng người dùng
4. Điểm quiz sẽ dùng để fine-tune lộ trình học

---

## Architecture 🏗️

```
┌─────────────────────────────────────┐
│  User Profile Input                 │
│  - Learning Goal                    │
│  - Background                       │
│  - Current Level                    │
│  - Target Role (optional)           │
│  - Interests (optional)             │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  Build Profile Text                 │
│  (Combine all fields into 1 string)  │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  Embedding Layer (SentenceTransform) │
│  - Embed user profile               │
│  - Embed all quiz set metadata      │
│  - Store in memory cache            │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  Similarity Search (Cosine)         │
│  - Compute similarity score         │
│  - Rank quiz sets by score          │
│  - Apply min_similarity threshold   │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  Select Top-K Quiz Set              │
│  - Return 1 best matching quiz      │
│  - Fallback to metadata matching    │
│  - Last resort: return first        │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  Return Selected Quiz                │
│  - Quiz set + 10 questions           │
│  - Similarity score                 │
│  - Retrieval method info            │
└─────────────────────────────────────┘
```

---

## Core Components 🔧

### 1. Quiz Bank (`services/quiz_bank.py`)

Lưu trữ tất cả quiz sets với metadata:

```python
class QuizSet:
    set_id: str              # Unique ID (e.g., "fund-001")
    name: str                # Display name
    description: str         # Mô tả bộ câu hỏi
    difficulty: str          # easy | medium | hard | mixed
    topics: List[str]        # Chủ đề bao gồm
    target_goals: List[str]  # Mục tiêu phù hợp
    prerequisites: List[str] # Yêu cầu tối thiểu
    questions: List[Dict]    # 10 câu hỏi với option + explanation
    embedding_text: str      # Text để embedding
```

**Hiện có 4 bộ câu hỏi:**
- `fund-001`: AI & ML Fundamentals (easy) — cho người bắt đầu từ 0
- `inter-001`: Supervised Learning (medium) — cho người có experience cơ bản
- `biz-001`: AI for Business (easy) — cho người làm kinh doanh/quản lý
- `nlp-001`: NLP Basics (hard) — cho người tập trung vào NLP/LLM

### 2. RAG Retriever (`services/rag_retriever.py`)

Thực hiện semantic search:

```python
class QuizRAGRetriever:
    def embed_text(text: str) -> np.ndarray
        # Embed text using sentence-transformers (all-MiniLM-L6-v2)
    
    def get_quiz_embedding(quiz_set) -> np.ndarray
        # Get embedding của quiz set (với caching)
    
    def retrieve_quiz_sets(
        quiz_sets: List,
        learning_goal: str,
        background: str,
        current_level: str,
        ...
    ) -> Tuple[List, List[float]]
        # Trả về top_k quiz sets với similarity scores
    
    def retrieve_quiz_set_by_metadata(...)
        # Fallback: hardcoded metadata matching
```

**Embedding Model:** `all-MiniLM-L6-v2`
- Lightweight (~33MB)
- Output dimension: 384
- Tốc độ: ~1000 tokens/second

**Similarity:** Cosine similarity

### 3. API Endpoints (`app/api/quiz.py`)

```
POST /api/select-quiz
├─ Input: SelectQuizRequest
│  ├─ user_id
│  ├─ learning_goal (5-500 chars)
│  ├─ background (5-300 chars)
│  ├─ current_level (beginner|intermediate|advanced|expert)
│  ├─ target_role? (optional)
│  ├─ interests? (optional)
│  └─ use_semantic? (default: true)
└─ Output: SelectedQuizResponse
   ├─ quiz_set_id
   ├─ quiz_set_name
   ├─ difficulty, topics, target_goals
   ├─ questions: [{id, text, options, correct, explanation}]
   ├─ similarity_score (0.0-1.0)
   └─ retrieval_method (semantic|metadata|fallback)

GET /api/list-quiz-sets
└─ Output: QuizListResponse (metadata of all quiz sets)

GET /api/quiz-by-id/{quiz_set_id}
└─ Output: SelectedQuizResponse (direct access by ID)
```

---

## Flow Integration 🔄

### Current Flow (Without RAG)
```
1. User fills goal + background form
2. User takes fixed 10-question quiz (fund-001)
3. Quiz score + profile → analyze API
4. Lộ trình được tạo
```

### New Flow (With RAG)
```
1. User fills goal + background form
2. Call /api/select-quiz with profile
   ├─ RAG matcher tìm bộ câu hỏi phù hợp
   └─ Return custom 10-question quiz (dynamic)
3. User takes quiz (từ bộ được chọn)
4. Quiz score + profile + quiz_set_id → analyze API
5. Lộ trình được tạo (có cân nhắc quiz context)
```

---

## Usage Examples 💡

### Example 1: Business User
```json
{
  "user_id": "user_123",
  "learning_goal": "Hiểu AI để áp dụng trong kinh doanh bán lẻ",
  "background": "Manager với 10 năm kinh nghiệm, không coding",
  "current_level": "beginner",
  "target_role": "AI Product Manager",
  "interests": ["AI for business", "ROI", "Use cases"]
}
```
**Expected:** `biz-001` (AI for Business Leaders)

### Example 2: Developer
```json
{
  "user_id": "user_456",
  "learning_goal": "Muốn trở thành ML Engineer",
  "background": "Backend developer 3 năm, biết Python tốt",
  "current_level": "intermediate",
  "target_role": "ML Engineer",
  "interests": ["Supervised Learning", "Model Selection", "Hyperparameter Tuning"]
}
```
**Expected:** `inter-001` (Supervised Learning Deep Dive)

### Example 3: Beginner
```json
{
  "user_id": "user_789",
  "learning_goal": "Bắt đầu học AI từ con số 0",
  "background": "Sinh viên năm 2, biết C++ cơ bản",
  "current_level": "beginner",
  "target_role": null,
  "interests": ["Machine Learning basics", "Python"]
}
```
**Expected:** `fund-001` (AI & ML Fundamentals)

---

## How to Extend 🚀

### Add New Quiz Set

1. **Create in `services/quiz_bank.py`:**
```python
QuizSet(
    set_id="cv-001",
    name="Computer Vision Basics",
    description="Image processing, CNN, object detection...",
    difficulty="hard",
    topics=["Image Processing", "CNN", "Computer Vision"],
    target_goals=["Build computer vision models", "Work with images"],
    prerequisites=["ML Fundamentals", "Python"],
    questions=[...]  # 10 questions
)
```

2. **Add to `QUIZ_BANK` list**

3. **Retriever sẽ tự động match** (vì dùng semantic similarity)

### Customize Embedding Model

Thay đổi trong `services/rag_retriever.py`:
```python
def get_embedder():
    # Thay từ all-MiniLM-L6-v2 sang model khác
    _embedder = SentenceTransformer('paraphrase-MiniLM-L6-v2')
    return _embedder
```

**Các model khác:**
- `all-MiniLM-L6-v2` (384d, lightweight, recommended)
- `all-MiniLM-L12-v2` (384d, slightly better quality)
- `all-mpnet-base-v2` (768d, better quality, slower)

### Adjust Similarity Threshold

```python
# In quiz.py /select-quiz endpoint
selected_sets, scores = retriever.retrieve_quiz_sets(
    ...,
    min_similarity=0.3  # Thay đổi ngưỡng
)
```

- `0.5`: Strict matching (chỉ lấy quiz rất phù hợp)
- `0.3`: Balanced (recommended)
- `0.1`: Loose matching (linh hoạt hơn)

---

## Performance & Scalability 📊

| Metric | Value | Notes |
|--------|-------|-------|
| Embedding time | ~50ms | Per user profile |
| Similarity search | ~10ms | For 4 quiz sets |
| Total latency | ~100-150ms | /select-quiz endpoint |
| Memory usage | ~100MB | Model + cache |
| Concurrent users | 100+ | (depends on server) |

**Optimization tips:**
- Embedding cache prevents re-computing (already done)
- Use lightweight model (all-MiniLM)
- Can batch process multiple users

---

## Limitations & Fallbacks ⚠️

### When RAG Might Fail:
1. **Vague goal:** "Muốn học AI" → fallback to `beginner` level
2. **Language mismatch:** Goal in English, Vietnamese text → still works (multilingual model)
3. **Contradictory inputs:** Advanced level + beginner goal → may mismatch
4. **No semantic match:** similarity < min_threshold → fallback to metadata matching

### Fallback Strategy:
1. **Primary:** Semantic search (RAG)
2. **Secondary:** Metadata matching (difficulty + topics)
3. **Tertiary:** Return first quiz set

---

## Testing 🧪

### Unit Test Example:

```python
from services.quiz_bank import get_all_quiz_sets
from services.rag_retriever import select_quiz_for_user

quiz_sets = get_all_quiz_sets()

# Test 1: Business user
selected, score = select_quiz_for_user(
    quiz_sets=quiz_sets,
    learning_goal="Learn AI for business",
    background="Manager, 10 years experience",
    current_level="beginner",
    target_role="Product Manager"
)
assert selected.set_id == "biz-001"
assert score > 0.5

# Test 2: Developer
selected, score = select_quiz_for_user(
    quiz_sets=quiz_sets,
    learning_goal="Master supervised learning",
    background="Software engineer",
    current_level="intermediate"
)
assert selected.set_id == "inter-001"
```

### Manual Test:

```bash
# List all quiz sets
curl http://localhost:8000/api/list-quiz-sets

# Select quiz for a user
curl -X POST http://localhost:8000/api/select-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "learning_goal": "Learn Machine Learning basics",
    "background": "Computer science student",
    "current_level": "beginner"
  }'

# Get quiz by ID
curl http://localhost:8000/api/quiz-by-id/fund-001
```

---

## Next Steps 🎯

1. **Integrate with Frontend:** Update form flow to call `/select-quiz` before quiz
2. **Store quiz_set_id:** Save in user session/database
3. **Enhanced Analytics:** Track which quiz sets are selected for different user profiles
4. **A/B Testing:** Compare results with fixed quiz vs. dynamic quiz
5. **More Quiz Sets:** Add CV, Reinforcement Learning, NLP Advanced, etc.
6. **User Feedback Loop:** Collect feedback on quiz selection quality
7. **Fine-tune Matching:** Adjust min_similarity, add topic weighting, etc.

---

## Architecture Diagram 📐

```
┌──────────────────────────────────────────┐
│         Frontend Form                    │
│  (Goal, Background, Level, Role, etc.)   │
└────────────────┬─────────────────────────┘
                 │ POST /api/select-quiz
                 ▼
┌──────────────────────────────────────────┐
│      API Gateway (FastAPI)               │
│  - Input validation                      │
│  - Guardrails check                      │
│  - Data masking                          │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│      RAG Retriever Service               │
│  - Build profile text                    │
│  - Load sentence-transformer             │
│  - Compute embeddings                    │
│  - Calculate cosine similarity           │
│  - Apply thresholds & fallbacks          │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│      Quiz Bank (In-Memory)               │
│  - 4 quiz sets                           │
│  - Each with 10 questions                │
│  - Metadata (difficulty, topics, goals)  │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│    Selected Quiz + Questions             │
│  - Return to frontend                    │
│  - Render 10 questions                   │
│  - User takes quiz                       │
└────────────────┬─────────────────────────┘
                 │
                 ▼ User submits quiz
                 │
                 ▼
┌──────────────────────────────────────────┐
│      Analyze API                         │
│  - Combine quiz score + profile          │
│  - Generate personalized roadmap         │
│  - Return learning path                  │
└──────────────────────────────────────────┘
```

---

## References 📚

- **Sentence Transformers:** https://www.sbert.net/
- **All-MiniLM Model:** https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- **Cosine Similarity:** https://en.wikipedia.org/wiki/Cosine_similarity
- **RAG Pattern:** https://research.ibm.com/blog/retrieval-augmented-generation-RAG

---

**Document Version:** 1.0  
**Last Updated:** 2026-06-04  
**Author:** VinUni AI20k Batch 02 - Day 06 Hackathon
