# API Reference — Quiz Selection & Analysis

## Base URL
```
http://127.0.0.1:8000
```

## Authentication
Current version: No authentication required. Optional auth endpoints available.

---

## Endpoints

### 1. Select Quiz (RAG-based)

**Endpoint:** `POST /api/select-quiz`

**Purpose:** Dynamically select a quiz set based on user profile using semantic similarity (RAG)

**Request:**
```json
{
  "user_id": "user_123",
  "learning_goal": "Learn Machine Learning from scratch",
  "background": "Computer Science student with Python basics",
  "current_level": "beginner",
  "target_role": "ML Engineer",
  "interests": ["Python", "Statistics", "Neural Networks"],
  "use_semantic": true
}
```

**Parameters:**
- `user_id` (string, required): Unique user identifier
- `learning_goal` (string, required): 5-500 characters. What the user wants to learn
- `background` (string, required): 5-300 characters. User's experience/background
- `current_level` (string, required): One of: `beginner`, `intermediate`, `advanced`, `expert`
- `target_role` (string, optional): Target job/role (e.g., "ML Engineer", "Data Scientist")
- `interests` (array, optional): List of topics user is interested in
- `use_semantic` (boolean, optional, default: true): Use RAG semantic search or fall back to metadata

**Response:**
```json
{
  "quiz_set_id": "fund-001",
  "quiz_set_name": "AI & ML Fundamentals",
  "quiz_set_description": "Basic concepts of AI, ML, Python, and Math foundations",
  "difficulty": "easy",
  "topics": ["AI Basics", "ML Definitions", "Math Foundation", "Python Basics"],
  "target_goals": ["Learn AI Basics", "Learn ML from scratch"],
  "questions": [
    {
      "id": "ch1-1",
      "text": "Machine Learning là gì?",
      "options": [
        { "label": "A", "text": "Một nhánh của thiết kế phần mềm truyền thống" },
        { "label": "B", "text": "Hệ thống dựa trên luật được lập trình thủ công" },
        { "label": "C", "text": "Một lĩnh vực nghiên cứu cho phép máy học từ dữ liệu mà không cần lập trình tường minh" },
        { "label": "D", "text": "Một phương pháp mã hóa dữ liệu" }
      ],
      "correct": 2,
      "explanation": "Đáp án C đúng vì định nghĩa này phản ánh đặc điểm cốt lõi của Machine Learning"
    },
    // ... 9 more questions
  ],
  "similarity_score": 0.85,
  "retrieval_method": "semantic"
}
```

**Response Fields:**
- `quiz_set_id`: Unique ID of selected quiz set
- `quiz_set_name`: Display name
- `quiz_set_description`: What this quiz covers
- `difficulty`: `easy`, `medium`, `hard`, `mixed`
- `topics`: List of topics covered
- `target_goals`: What goals this quiz is good for
- `questions`: Array of 10 questions, each with options and correct answer
- `similarity_score`: 0-1 (how well quiz matches user profile)
- `retrieval_method`: `semantic` (RAG), `metadata`, or `fallback`

**Status Codes:**
- `200 OK`: Successfully selected quiz
- `400 Bad Request`: Invalid input (e.g., goal text too short, guardrail violation)
- `500 Internal Server Error`: Server-side error

**Example Usage (JavaScript):**
```javascript
const response = await fetch('http://127.0.0.1:8000/api/select-quiz', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: 'user_123',
    learning_goal: 'Learn Deep Learning',
    background: 'Python developer',
    current_level: 'intermediate',
    interests: ['Neural Networks', 'Computer Vision']
  })
});

const quiz = await response.json();
console.log(`Selected: ${quiz.quiz_set_name} (score: ${quiz.similarity_score})`);
```

---

### 2. List All Quiz Sets

**Endpoint:** `GET /api/list-quiz-sets`

**Purpose:** Get metadata of all available quiz sets

**Request:**
```bash
GET /api/list-quiz-sets
```

**Response:**
```json
{
  "total_sets": 4,
  "quiz_sets": [
    {
      "set_id": "fund-001",
      "name": "AI & ML Fundamentals",
      "description": "Basic concepts of AI, ML, Python, and Math foundations",
      "difficulty": "easy",
      "topics": ["AI Basics", "ML Definitions", "Math Foundation", "Python Basics"],
      "target_goals": ["Learn AI Basics", "Learn ML from scratch"],
      "question_count": 10
    },
    {
      "set_id": "inter-001",
      "name": "Supervised Learning Deep Dive",
      "description": "Regression, Classification, Model Evaluation",
      "difficulty": "medium",
      "topics": ["Supervised Learning", "Regression", "Classification"],
      "target_goals": ["Build supervised learning models"],
      "question_count": 10
    },
    {
      "set_id": "biz-001",
      "name": "AI for Business Leaders",
      "description": "AI applications, business strategy, ROI",
      "difficulty": "easy",
      "topics": ["AI Applications", "Business Strategy"],
      "target_goals": ["Learn AI for business", "Lead AI projects"],
      "question_count": 10
    },
    {
      "set_id": "nlp-001",
      "name": "Natural Language Processing Basics",
      "description": "NLP, embeddings, transformers, LLM",
      "difficulty": "hard",
      "topics": ["NLP", "Transformers", "LLM"],
      "target_goals": ["Master NLP techniques"],
      "question_count": 10
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Successfully listed quiz sets
- `500 Internal Server Error`: Server error

**Example Usage:**
```javascript
const response = await fetch('http://127.0.0.1:8000/api/list-quiz-sets');
const data = await response.json();
console.log(`Available quizzes: ${data.quiz_sets.map(q => q.name).join(', ')}`);
```

---

### 3. Get Quiz by ID

**Endpoint:** `GET /api/quiz-by-id/{quiz_set_id}`

**Purpose:** Fetch a specific quiz set by its ID (direct access, no RAG matching)

**Request:**
```bash
GET /api/quiz-by-id/fund-001
```

**Parameters:**
- `quiz_set_id` (path param): ID of the quiz set (e.g., `fund-001`, `inter-001`)

**Response:** Same as `/select-quiz` response (see section 1)

**Status Codes:**
- `200 OK`: Successfully fetched quiz
- `404 Not Found`: Quiz set ID doesn't exist
- `500 Internal Server Error`: Server error

**Example Usage:**
```javascript
// Get quiz directly by ID (default quiz)
const defaultQuiz = await fetch('http://127.0.0.1:8000/api/quiz-by-id/fund-001')
  .then(r => r.json());

console.log(`Loaded: ${defaultQuiz.quiz_set_name}`);
```

---

### 4. Analyze Profile (Existing Endpoint)

**Endpoint:** `POST /api/analyze`

**Purpose:** Generate personalized learning roadmap based on quiz score and profile

**Request:**
```json
{
  "user_id": "user_123",
  "session_id": "session_456",
  "goal_description": "I want to learn machine learning to build AI products",
  "quiz_answers": [2, 1, 2, 2, 2, 3, 1, 0, 0, 3],
  "time_per_week": "10-15 hours",
  "current_job": "Software Engineer",
  "background": "CS degree with 3 years experience",
  "quiz_score": 7
}
```

**Response:**
```json
{
  "milestones": [
    {
      "milestone_title": "Python Fundamentals",
      "duration": "1 week",
      "resource_links": ["https://coursera.org/..."],
      "difficulty": "beginner",
      "description": "Learn Python basics, data types, functions"
    },
    // ... more milestones
  ],
  "confidence_score": 0.85,
  "path_type": "happy",
  "reasoning": "User has strong background with good quiz score",
  "personalization_notes": "Recommended intermediate + advanced tracks",
  "cost_info": {
    "tokens": 450,
    "cost_usd": 0.0045
  }
}
```

**Note:** Include `quiz_score` calculated from `/select-quiz` response

---

## Integration Workflow

### Step 1: Show Form (Goal Selection)
- User fills: learning goal, background, current level, target role

### Step 2: Call `/select-quiz` (RAG Matching)
```javascript
const selectedQuiz = await fetch('/api/select-quiz', {
  method: 'POST',
  body: JSON.stringify({
    user_id: 'user_' + Date.now(),
    learning_goal: form.goal,
    background: form.background,
    current_level: form.level,
    target_role: form.role
  })
}).then(r => r.json());

console.log(`Selected quiz: ${selectedQuiz.quiz_set_name}`);
```

### Step 3: Display Quiz (10 Questions)
```javascript
selectedQuiz.questions.forEach((q, idx) => {
  displayQuestion(q, idx);
});
```

### Step 4: User Takes Quiz
- Show one question at a time or all at once
- Record answers in `quiz_answers` array

### Step 5: Calculate Score
```javascript
let correctCount = 0;
selectedQuiz.questions.forEach((q, idx) => {
  if (quiz_answers[idx] === q.correct) correctCount++;
});
const quiz_score = Math.round((correctCount / selectedQuiz.questions.length) * 10);
```

### Step 6: Call `/analyze` (Generate Roadmap)
```javascript
const roadmap = await fetch('/api/analyze', {
  method: 'POST',
  body: JSON.stringify({
    user_id: 'user_' + Date.now(),
    session_id: 'session_' + Date.now(),
    goal_description: selectedQuiz.quiz_set_name,
    quiz_answers: quiz_answers,
    quiz_score: quiz_score,
    time_per_week: '10 hours',
    current_job: form.background,
    background: form.background
  })
}).then(r => r.json());

displayRoadmap(roadmap);
```

---

## Available Quiz Sets

| ID | Name | Difficulty | Best For | Topics |
|---|---|---|---|---|
| `fund-001` | AI & ML Fundamentals | Easy | Complete beginners | AI, ML basics, Python, Math |
| `inter-001` | Supervised Learning | Medium | Developers with ML basics | Regression, Classification, Model Evaluation |
| `biz-001` | AI for Business | Easy | Business/non-technical | AI applications, ROI, strategy |
| `nlp-001` | NLP Basics | Hard | ML engineers | NLP, Transformers, LLM |

---

## Error Handling

### Common Errors

**400 - Bad Request:**
```json
{
  "detail": "learning_goal: ensure this value has at least 5 characters"
}
```
Solution: Check input validation rules

**400 - Guardrail Violation:**
```json
{
  "detail": "Request contains prohibited content"
}
```
Solution: Avoid harmful/spam keywords

**404 - Not Found:**
```json
{
  "detail": "Quiz set not found: invalid-id"
}
```
Solution: Use valid quiz set IDs

**500 - Server Error:**
```json
{
  "detail": "Internal server error. Check logs."
}
```
Solution: Server-side issue, retry later

---

## Performance & Limits

| Metric | Value |
|--------|-------|
| Quiz selection latency | 100-200ms |
| Request timeout | 30 seconds |
| Max goal description length | 500 chars |
| Max background length | 300 chars |
| Questions per quiz | 10 (fixed) |
| Concurrent users | 100+ |
| Rate limit | 5 requests/minute per IP |

---

## Testing

### Quick Test Script

```bash
#!/bin/bash

# Test 1: List quiz sets
echo "📋 Listing quiz sets..."
curl http://127.0.0.1:8000/api/list-quiz-sets | jq

# Test 2: Select quiz for beginner
echo "🎯 Selecting quiz for beginner..."
curl -X POST http://127.0.0.1:8000/api/select-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_beginner",
    "learning_goal": "Learn machine learning from scratch",
    "background": "Student with no ML experience",
    "current_level": "beginner"
  }' | jq

# Test 3: Get quiz by ID
echo "📥 Getting quiz by ID..."
curl http://127.0.0.1:8000/api/quiz-by-id/fund-001 | jq '.quiz_set_name, .questions | length'
```

---

## Changelog

### Version 1.0 (2026-06-04)
- Initial release
- RAG-based quiz selection
- 4 quiz sets
- Semantic similarity matching
- Metadata fallback
- Integration with analyze API

---

## Support

For issues or questions:
1. Check logs: `backend/data/cost_logs.jsonl`
2. Enable debug logging: `level=logging.DEBUG`
3. Contact: VinUni AI20k Batch 02 - Day 06

---

**Last Updated:** 2026-06-04  
**API Version:** 1.0
