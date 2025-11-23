# backend/main.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import PlainTextResponse
import traceback
import sys
import os

# ensure imports work regardless of execution folder
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

app = FastAPI(title="OneClarity Tutor API")

# -------------------------------------------------------------------
# SAFE IMPORTS (print errors but don’t crash import stage)
# -------------------------------------------------------------------
def safe_import(name):
    try:
        module = __import__(name, fromlist=["*"])
        return module, None
    except Exception as e:
        # print without non-ascii issues
        print(f"[IMPORT ERROR] {name}: {repr(e)}")
        return None, e

retriever_mod, retriever_err = safe_import("backend.retriever")
quiz_mod, quiz_err = safe_import("backend.quiz_generator")
planner_mod, planner_err = safe_import("backend.planner")
pdb_mod, pdb_err = safe_import("backend.progress_db")

retrieve = getattr(retriever_mod, "retrieve", None) if retriever_mod else None
generate_quiz_for_topic = getattr(quiz_mod, "generate_quiz_for_topic", None) if quiz_mod else None
planner_decide = getattr(planner_mod, "planner_decide", None) if planner_mod else None

# progress DB
register_student = getattr(pdb_mod, "register_student", None) if pdb_mod else None
record_attempt = getattr(pdb_mod, "record_attempt", None) if pdb_mod else None
get_progress = getattr(pdb_mod, "get_progress", None) if pdb_mod else None
get_interactions = getattr(pdb_mod, "get_interactions", None) if pdb_mod else None
log_interaction = getattr(pdb_mod, "log_interaction", None) if pdb_mod else None

# -------------------------------------------------------------------
# Helper to show backend errors
# -------------------------------------------------------------------
def fail(e, context=""):
    print(f"\n[BACKEND ERROR] {context}\n{traceback.format_exc()}\n")
    return HTTPException(
        status_code=500,
        detail={"error": str(e), "context": context}
    )

# -------------------------------------------------------------------
# Register
# -------------------------------------------------------------------
@app.post("/register_student")
def register(student_id: str, name: str = ""):
    if not register_student:
        raise fail("register_student missing", "progress_db import failure")
    return register_student(student_id, name)

# -------------------------------------------------------------------
# ASK — major endpoint
# -------------------------------------------------------------------
@app.get("/ask")
def ask(student_id: str = Query(...), query: str = Query(...)):
    # 1) planner decision
    try:
        if planner_decide:
            plan = planner_decide(student_id, query=query)
        else:
            plan = {"action": "retrieve_and_explain", "topic": query, "difficulty": "medium"}
    except Exception as e:
        raise fail(e, "planner_decide() crashed")

    action = plan.get("action", "retrieve_and_explain")
    topic = plan.get("topic", query)
    difficulty = plan.get("difficulty", "medium")

    # 2) retrieval mode
    if action == "retrieve_and_explain":
        if not retrieve:
            raise fail("retrieve() unavailable", "retriever import failure")

        try:
            chunks = retrieve(topic, top_k=1)
        except Exception as e:
            raise fail(e, "retrieve() crashed")

        if not chunks:
            # log attempt (safe)
            try:
                if log_interaction:
                    log_interaction(student_id, query, plan=[plan], retrieved="None", quiz_meta={}, response="No explanation found.")
            except Exception:
                pass

            return {
                "action": "explain",
                "topic": topic,
                "difficulty": difficulty,
                "answer": "No explanation found.",
                "chapter": None,
                "quiz_suggestion": False
            }

        chunk = chunks[0]

        # log interaction safely
        try:
            if log_interaction:
                # store truncated snippet for safety
                log_interaction(student_id, query, plan=[plan],
                                retrieved=chunk.get("text", "")[:400],
                                quiz_meta={}, response=chunk.get("text", "")[:400])
        except Exception as e:
            print("[WARN] logging failed:", repr(e))

        return {
            "action": "explain",
            "topic": topic,
            "difficulty": difficulty,
            "answer": chunk.get("text", ""),
            "chapter": chunk.get("chapter", ""),
            "quiz_suggestion": True
        }

    # 3) quiz mode
    if not generate_quiz_for_topic:
        raise fail("Quiz generator missing", "quiz_generator import failure")

    try:
        quiz = generate_quiz_for_topic(topic, n_questions=3, difficulty=difficulty)
    except Exception as e:
        raise fail(e, "generate_quiz_for_topic crashed")

    # log quiz generation
    try:
        if log_interaction:
            log_interaction(student_id, query, plan=[plan],
                            retrieved="none",
                            quiz_meta={"num_questions": len(quiz), "difficulty": difficulty},
                            response="quiz generated")
    except Exception as e:
        print("[WARN] logging failed:", repr(e))

    return {"action": "quiz", "topic": topic, "difficulty": difficulty, "quiz": quiz}

# -------------------------------------------------------------------
# Independent Quiz
# -------------------------------------------------------------------
@app.get("/quiz")
def quiz(student_id: str = Query(...), topic: str = Query(...), difficulty: str = Query("auto")):
    if difficulty == "auto":
        try:
            if planner_decide:
                plan = planner_decide(student_id, topic=topic)
                difficulty = plan.get("difficulty", "medium")
            else:
                difficulty = "medium"
        except Exception:
            difficulty = "medium"

    if not generate_quiz_for_topic:
        raise fail("Quiz generator missing", "quiz_generator import failure")

    try:
        quiz = generate_quiz_for_topic(topic, n_questions=3, difficulty=difficulty)
    except Exception as e:
        raise fail(e, "generate_quiz_for_topic crashed")

    try:
        if log_interaction:
            log_interaction(student_id, query=f"[independent quiz] {topic}", plan=[{"action": "independent_quiz", "difficulty": difficulty}], retrieved="none", quiz_meta={"num_questions": len(quiz), "difficulty": difficulty}, response="Generated independent quiz")
    except Exception:
        pass

    return {"topic": topic, "difficulty": difficulty, "quiz": quiz}

# -------------------------------------------------------------------
# Submit Answer
# -------------------------------------------------------------------
@app.post("/submit_answer")
def submit_answer(student_id: str = Query(...),
                  topic: str = Query(...),
                  question: str = Query(...),
                  selected_option: str = Query(""),
                  correct_option: str = Query(""),
                  difficulty: str = Query("medium")):
    is_correct = False
    try:
        if selected_option and correct_option:
            is_correct = selected_option.strip() == correct_option.strip()
    except Exception:
        is_correct = False

    try:
        if record_attempt:
            record_attempt(student_id, topic, question, is_correct, difficulty=difficulty)
    except Exception as e:
        print("[WARN] record_attempt failed:", repr(e))

    return {"student_id": student_id, "topic": topic, "question": question, "selected": selected_option, "correct": correct_option, "is_correct": is_correct, "difficulty": difficulty, "status": "recorded"}

# -------------------------------------------------------------------
# Progress & interactions
# -------------------------------------------------------------------
@app.get("/progress/{student_id}")
def progress(student_id: str):
    if not get_progress:
        raise fail("get_progress missing", "progress_db import failure")
    try:
        return get_progress(student_id)
    except Exception as e:
        raise fail(e, "get_progress crashed")

@app.get("/interactions/{student_id}")
def interactions(student_id: str, limit: int = 100):
    if not get_interactions:
        raise fail("get_interactions missing", "progress_db import failure")
    try:
        items = get_interactions(student_id, limit=limit)
        return {"student_id": student_id, "interactions": items}
    except Exception as e:
        raise fail(e, "get_interactions crashed")
