# RAG Quiz Selection System — Quick Start Guide

> **AI Learning Path Personalizer — Enhanced with RAG** 🎯  
> Dynamic question selection based on user profile using semantic similarity
> 
> VinUni AI20k Batch 02 · Day 06

---

## 🚀 What's New?

Trước đây: Tất cả người dùng làm **cùng 1 bộ 10 câu hỏi cố định** (`fund-001`)

Bây giờ: Hệ thống sẽ **tự động chọn bộ câu hỏi phù hợp** dựa trên:
- 🎯 Mục tiêu học tập
- 💼 Background & kinh nghiệm
- 📊 Trình độ hiện tại
- 🎓 Target role
- 💡 Lĩnh vực quan tâm

**4 quiz sets khác nhau:**
1. **Fundamentals** (easy) — Người bắt đầu từ 0
2. **Supervised Learning** (medium) — Developer có ML basics
3. **AI for Business** (easy) — Manager/non-technical
4. **NLP Basics** (hard) — ML Engineer tập trung NLP/LLM

---

## 📋 System Architecture

```
User Profile Input
       ↓
/api/select-quiz (RAG)
       ↓
[Embedding + Semantic Search]
       ↓
Select Best Matching Quiz
       ↓
Return 10 Questions
       ↓
User Takes Quiz
       ↓
/api/analyze (Generate Roadmap)
```

---

## ⚡ Installation & Setup

### 1. Install Dependencies

```bash
cd codebase/backend
pip install -r requirements.txt
```

**New dependencies added:**
```
sentence-transformers==3.0.1  # For semantic embeddings
scikit-learn==1.5.0           # For cosine similarity
numpy==1.24.3                 # For vector operations
```

### 2. Start Backend

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs available at: http://127.0.0.1:8000/docs

### 3. (Optional) Update Frontend

Add script to HTML header:
```html
<script src="src/rag-quiz-selector.js"></script>
```

---

## 📖 Usage Examples

### Example 1: Beginner Without Coding Background

**User Input:**
```
Goal: "Muốn bắt đầu học AI từ con số 0"
Background: "Sinh viên năm 2, không có coding"
Level: "beginner"
```

**API Call:**
```bash
curl -X POST http://127.0.0.1:8000/api/select-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "learning_goal": "Muốn bắt đầu học AI từ con số 0",
    "background": "Sinh viên năm 2, không có coding",
    "current_level": "beginner"
  }'
```

**Result:** ✅ Selects `fund-001` (AI & ML Fundamentals)  
**Match Score:** 0.92 (very high)  
**Method:** `semantic`

---

### Example 2: Experienced Developer

**User Input:**
```
Goal: "Muốn master supervised learning models"
Background: "Backend developer 3 năm, biết Python tốt"
Level: "intermediate"
Interests: ["Regression", "Classification", "Model Selection"]
```

**API Call:**
```bash
curl -X POST http://127.0.0.1:8000/api/select-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_002",
    "learning_goal": "Muốn master supervised learning models",
    "background": "Backend developer 3 năm, biết Python tốt",
    "current_level": "intermediate",
    "interests": ["Regression", "Classification", "Model Selection"]
  }'
```

**Result:** ✅ Selects `inter-001` (Supervised Learning Deep Dive)  
**Match Score:** 0.87  
**Method:** `semantic`

---

### Example 3: Business User

**User Input:**
```
Goal: "Hiểu AI để áp dụng trong kinh doanh"
Background: "Manager với 10 năm kinh nghiệm, không coding"
Level: "beginner"
Target Role: "Product Manager"
```

**API Call:**
```bash
curl -X POST http://127.0.0.1:8000/api/select-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_003",
    "learning_goal": "Hiểu AI để áp dụng trong kinh doanh",
    "background": "Manager với 10 năm kinh nghiệm, không coding",
    "current_level": "beginner",
    "target_role": "Product Manager"
  }'
```

**Result:** ✅ Selects `biz-001` (AI for Business Leaders)  
**Match Score:** 0.85  
**Method:** `semantic`

---

## 🔧 API Endpoints

### Select Quiz (Dynamic RAG Selection)
```
POST /api/select-quiz
```
- **Input:** User profile (goal, background, level, etc.)
- **Output:** Best matching quiz set + 10 questions
- **Latency:** ~100-200ms

### List All Quiz Sets
```
GET /api/list-quiz-sets
```
- **Output:** Metadata of all 4 quiz sets

### Get Quiz by ID (Direct Access)
```
GET /api/quiz-by-id/{quiz_id}
```
- **Input:** Quiz ID (e.g., `fund-001`)
- **Output:** Quiz set + 10 questions

---

## 📚 Available Quiz Sets

| Quiz ID | Name | Difficulty | Best For | Topics |
|---------|------|------------|----------|--------|
| `fund-001` | AI & ML Fundamentals | Easy | Beginners, no prerequisites | AI basics, ML, Python, Math |
| `inter-001` | Supervised Learning | Medium | Developers with ML basics | Regression, Classification, Evaluation |
| `biz-001` | AI for Business Leaders | Easy | Business/non-technical users | AI applications, ROI, strategy |
| `nlp-001` | Natural Language Processing | Hard | ML engineers | NLP, Transformers, LLM |

---

## 🧠 How RAG Works

### Step 1: Embedding
- User profile (goal + background) → converted to vector (384 dimensions)
- Each quiz set metadata → converted to vector (384 dimensions)
- Using `all-MiniLM-L6-v2` model (lightweight, fast)

### Step 2: Similarity Search
- Compute cosine similarity between user profile & all quiz sets
- Range: 0 (no match) → 1 (perfect match)

### Step 3: Ranking
- Sort quiz sets by similarity score
- Apply threshold: only select if similarity ≥ 0.3

### Step 4: Selection
- Return top 1 quiz set
- If no match: fallback to metadata matching (difficulty-based)
- If still no match: return default `fund-001`

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| Model loading time | ~5 seconds (first load only, then cached) |
| Embedding generation | ~50ms per user |
| Similarity search | ~10ms for 4 quizzes |
| Total /select-quiz latency | ~100-200ms |
| Memory usage | ~100MB (model + cache) |

---

## 🛠️ Integration with Frontend

### Option 1: Simple Integration (No RAG)
Keep using fixed quiz:
```javascript
// Load default quiz directly
const quiz = await fetch('http://127.0.0.1:8000/api/quiz-by-id/fund-001')
  .then(r => r.json());
```

### Option 2: Smart Integration (With RAG) ⭐ Recommended
```javascript
// Step 1: User fills form
const userProfile = {
  goal_why: formData.goal,
  goal_job: formData.job,
  goal_level: formData.level
};

// Step 2: Call RAG selector
const selectedQuiz = await fetch('http://127.0.0.1:8000/api/select-quiz', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: 'user_' + Date.now(),
    learning_goal: userProfile.goal_why,
    background: userProfile.goal_job,
    current_level: userProfile.goal_level
  })
}).then(r => r.json());

// Step 3: Display selected quiz
console.log(`Quiz selected: ${selectedQuiz.quiz_set_name}`);
console.log(`Match score: ${selectedQuiz.similarity_score}`);
console.log(`Method: ${selectedQuiz.retrieval_method}`);

// Step 4: Display questions
displayQuizQuestions(selectedQuiz.questions);

// Step 5: After quiz, get score
const userAnswers = [2, 1, 2, ...]; // User's answers
const score = calculateScore(selectedQuiz.questions, userAnswers);

// Step 6: Call analyze API
const roadmap = await fetch('http://127.0.0.1:8000/api/analyze', {
  method: 'POST',
  body: JSON.stringify({
    user_id: 'user_' + Date.now(),
    goal_description: selectedQuiz.quiz_set_name,
    quiz_answers: userAnswers,
    quiz_score: score,
    current_job: userProfile.goal_job,
    background: userProfile.goal_job
  })
}).then(r => r.json());

displayRoadmap(roadmap);
```

---

## 🔍 Testing the System

### Test 1: List All Quiz Sets
```bash
curl http://127.0.0.1:8000/api/list-quiz-sets | jq '.quiz_sets[] | {id: .set_id, name: .name, difficulty: .difficulty}'
```

### Test 2: Select Quiz for Different User Types
```bash
# Beginner
curl -X POST http://127.0.0.1:8000/api/select-quiz \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test1", "learning_goal": "Learn AI basics", "background": "No experience", "current_level": "beginner"}' | jq

# Intermediate Developer
curl -X POST http://127.0.0.1:8000/api/select-quiz \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test2", "learning_goal": "Master machine learning", "background": "Python developer", "current_level": "intermediate"}' | jq

# Business User
curl -X POST http://127.0.0.1:8000/api/select-quiz \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test3", "learning_goal": "Understand AI for business", "background": "Business manager", "current_level": "beginner", "target_role": "Product Manager"}' | jq
```

### Test 3: Get Quiz by ID
```bash
curl http://127.0.0.1:8000/api/quiz-by-id/fund-001 | jq '.questions | length'
```

---

## 📝 Adding New Quiz Sets

### Step 1: Create New Quiz Set in `services/quiz_bank.py`

```python
QuizSet(
    set_id="cv-001",
    name="Computer Vision Basics",
    description="Image processing, CNN, object detection",
    difficulty="hard",
    topics=["Image Processing", "CNN", "Computer Vision"],
    target_goals=["Build CV models", "Master image processing"],
    prerequisites=["ML Fundamentals"],
    questions=[
        {
            "id": "cv-1",
            "text": "Convolution operation trong CNN có tác dụng gì?",
            "options": [...],
            "correct": 2,
            "explanation": "..."
        },
        # ... 9 more questions
    ]
)
```

### Step 2: Add to QUIZ_BANK List

```python
QUIZ_BANK = [
    # existing quizzes...
    QuizSet(...),  # New quiz set
]
```

### Step 3: That's it!
RAG system sẽ tự động match user profiles với quiz mới.

---

## 🚨 Troubleshooting

### Issue: Quiz selection returns same quiz every time
**Solution:** Check min_similarity threshold in `services/rag_retriever.py`. Try lowering to 0.25

### Issue: Embeddings not loading
**Solution:** Make sure `sentence-transformers` installed: `pip install sentence-transformers==3.0.1`

### Issue: Slow performance on first request
**Solution:** First load downloads model (~33MB). Subsequent requests are cached and fast.

### Issue: Wrong quiz selected
**Solution:** Try with more specific profile inputs. Add `target_role` and `interests` fields.

---

## 📊 Example Output

```json
{
  "quiz_set_id": "fund-001",
  "quiz_set_name": "AI & ML Fundamentals",
  "difficulty": "easy",
  "topics": ["AI Basics", "ML Definitions", "Math Foundation"],
  "questions": [
    {
      "id": "ch1-1",
      "text": "Machine Learning là gì?",
      "options": [
        { "label": "A", "text": "Nhánh thiết kế phần mềm" },
        { "label": "B", "text": "Hệ thống dựa trên luật cứng" },
        { "label": "C", "text": "Máy học từ dữ liệu tự động" },
        { "label": "D", "text": "Phương pháp mã hóa" }
      ],
      "correct": 2,
      "explanation": "ML cho phép máy học từ dữ liệu"
    },
    // ... 9 more questions
  ],
  "similarity_score": 0.92,
  "retrieval_method": "semantic"
}
```

---

## 📚 Documentation Files

- [RAG-QUIZ-SYSTEM.md](RAG-QUIZ-SYSTEM.md) — Detailed RAG system architecture
- [API-REFERENCE.md](API-REFERENCE.md) — Complete API documentation
- README.md — This file

---

## ✅ Checklist: Deploy RAG System

- [ ] Install new dependencies: `pip install -r requirements.txt`
- [ ] Start backend: `python -m uvicorn app.main:app --reload`
- [ ] Test `/select-quiz` endpoint with curl
- [ ] Add `rag-quiz-selector.js` to frontend
- [ ] Update frontend form to call `/select-quiz`
- [ ] Test with sample user profiles
- [ ] Verify quiz scores are correct
- [ ] Check `/analyze` still works with new quizzes
- [ ] Run demo with different user types
- [ ] Document new quiz selection logic

---

## 🎯 Next Steps

1. ✅ **Integrate with Frontend** — Update form flow to use RAG
2. **A/B Testing** — Compare results with fixed vs. dynamic quiz
3. **User Feedback** — Collect feedback on quiz selection quality
4. **Analytics** — Track which quiz sets are selected for different profiles
5. **Expand Quiz Bank** — Add more specialized quizzes (CV, RL, etc.)
6. **Fine-tuning** — Adjust similarity thresholds based on performance
7. **Advanced Matching** — Add weighting by topics, goals, prerequisites

---

**Happy Learning! 🚀**

VinUni AI20k Batch 02 · Day 06  
Last Updated: 2026-06-04
