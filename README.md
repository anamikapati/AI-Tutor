# Agentic AI Tutor — Adaptive Learning System

## 1. Overview

This project implements an Agentic AI Tutor capable of adaptive learning, doubt solving, quiz generation, and progress tracking. The system uses a planner agent to decide appropriate actions, a retrieval agent powered by FAISS for contextual grounding, and separate LLM-based agents for explanation and quiz creation.

Technologies used:
- FastAPI backend
- Streamlit frontend
- FAISS vector search
- SentenceTransformers embeddings
- LLM-based agent modules

---

## 2. System Architecture

```
 ┌───────────────────────┐
 │      Streamlit UI     │
 │  - Ask tutor          │
 │  - Generate quiz      │
 │  - Progress analytics │
 └───────────┬───────────┘
             │ REST API
             ▼
 ┌───────────────────────────────┐
 │           Backend             │
 │          FastAPI              │
 │  /ask /quiz /progress /submit │
 └───────────┬───────────────────┘
             │ uses agents
             ▼
 ┌───────────────────────────────┐
 │           Agent Layer         │
 │  planner.py                   │
 │  explainer.py                 │
 │  quiz_agent.py                │
 │  retrieval_agent.py           │
 └───────────┬───────────────────┘
             ▼
 ┌───────────────────────────────┐
 │    Knowledge Base (FAISS)     │
 │  Embeddings + textbook chunks │
 └───────────────────────────────┘
```

---

## 3. Agent Descriptions

### Planner Agent
Decides action flow:
- explain
- quiz
- explain_then_quiz

Decision is based on topic difficulty, student performance, retrieval confidence, and query intent.

### Retrieval Agent
- Loads FAISS index
- Retrieves relevant textbook chunks
- Provides grounded context for the LLM

### Explainer Agent
- Generates correct, contextual, step-by-step explanations
- Avoids hallucinations by grounding on retrieved chunks

### Quiz Agent
- Produces MCQs with difficulty levels (easy/medium/hard)
- JSON format:
```
{
  "question": "...",
  "options": ["A", "B", "C", "D"],
  "answer": "A"
}
```

---

## 4. API Endpoints (FastAPI)

### GET `/ask`
Returns explanation + planner action.

**Response:**
```
{
  "query": "...",
  "action": "explain",
  "answer": "text",
  "retrieved": ["..."],
  "chapter": "Chapter 3",
  "topic": "Matrix",
  "difficulty": "medium",
  "quiz_suggestion": true
}
```

---

### GET `/quiz`
Generates quiz.

Parameters:
- student_id
- topic
- difficulty

---

### POST `/submit_answer`
Stores student quiz answers and correctness.

---

### GET `/progress/{student_id}`
Returns per-topic analytics:
```
{
  "Topic": {
    "accuracy": 78,
    "attempts": 11,
    "strength": "medium"
  }
}
```

---

### GET `/interactions/{student_id}`
Returns planner decisions over time.

---

## 5. Knowledge Base Pipeline

1. Extract textbook PDF content  
2. Split text into overlapping chunks  
3. Generate embeddings using `all-MiniLM-L6-v2`  
4. Build FAISS index  
5. Load at runtime for retrieval  

---

## 6. Student Modeling Features

The system tracks:
- accuracy per topic  
- attempts  
- difficulty progression  
- weaknesses  
- recommended difficulty  
- planner decision patterns  

These feed into adaptive tutoring.

---

## 7. Planner Logic Summary

```
if query is factual → EXPLAIN
if student weak → EXPLAIN + EASY QUIZ
if medium → MEDIUM QUIZ
if strong → HARD QUIZ
if user explicitly asks for quiz → QUIZ
```

Planner returns:
```
[
  {"action": "explain"},
  {"action": "quiz", "difficulty": "medium"}
]
```

---

## 8. Running the Project

### Backend
```
uvicorn backend.main:app --reload
```

### Frontend
```
streamlit run streamlit_app.py
```

Backend: http://127.0.0.1:8000  
Frontend: http://localhost:8501

---

## 9. Folder Structure

```
OneClarity/
│
├── backend/
│   ├── main.py
│   ├── planner.py
│   ├── agents/
│   │   ├── planner.py
│   │   ├── explainer.py
│   │   ├── quiz_agent.py
│   │   └── retrieval_agent.py
│   ├── data/
│   │   ├── kb_chunks.pkl
│   │   ├── embeddings.npy
│   │   └── faiss.index
│
├── streamlit_app.py
├── README.md
└── requirements.txt
```

---

## 10. Conclusion

This project demonstrates a fully working Agentic AI Tutor architecture with:
- FAISS retrieval  
- Modular agent design  
- Adaptive difficulty quizzes  
- Student progress analytics  
- Planner-driven multi-step actions  

## 11. Deployed Link: https://ai-tutor-4ask9vxskiydmvzvr5jybj.streamlit.app/
