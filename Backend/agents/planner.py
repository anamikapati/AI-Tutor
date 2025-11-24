# backend/agents/planner.py
"""
Planner Agent

Decides:
 - action: "retrieve_and_explain" | "generate_quiz" | "followup"
 - topic: canonical topic string (in lowercase)
 - difficulty: "easy" | "medium" | "hard"

This planner is intentionally simple and deterministic (good for assignment).
It consults progress_db.topic_strength when available to set difficulty.
"""

from typing import Dict
import re
import logging

# Use the progress DB to read topic strength
try:
    from backend.progress_db import topic_strength
except Exception:
    topic_strength = None
    logging.exception("Could not import topic_strength from progress_db")

# canonical topic set (aligned with your PDF chapters)
VALID_TOPICS = [
    "relations and functions",
    "inverse trigonometric function",
    "matrices",
    "determinants",
    "continuity and differentiability",
    "application of derivatives",
    "integrals",
    "application of integrals",
    "differential equations",
    "vector algebra",
    "three dimensional geometry",
    "linear programming",
    "probability",
]


def _normalize_topic(t: str) -> str:
    if not t:
        return ""
    return t.strip().lower()


def _match_best_topic(text: str) -> str:
    if not text:
        return ""
    s = text.lower()
    # exact substring matching (quick and deterministic)
    for t in VALID_TOPICS:
        if t in s:
            return t
    # try singular/plural or stem-based heuristics
    if "matrix" in s or "matrices" in s:
        return "matrices"
    if "probability" in s or "conditional probability" in s:
        return "probability"
    # fallback empty
    return ""


def planner_decide(student_id: str, query: str = "", topic: str = None) -> Dict:
    """
    Return a plan dict:
      { "action": "...", "topic": "<topic>", "difficulty": "easy|medium|hard" }

    Behavior:
     - If query contains quiz intent keywords -> generate_quiz
     - If query contains explain keywords -> retrieve_and_explain
     - Else default to retrieve_and_explain (frontend can ask quiz after)
     - difficulty is inferred from topic_strength(student_id, topic) when available
    """
    q = (query or "").strip()
    chosen_topic = topic or _match_best_topic(q) or ""
    chosen_topic = _normalize_topic(chosen_topic or q)

    # detect high-level intent
    quiz_keywords = {"quiz", "practice", "test", "exercise", "questions", "mcq", "solve"}
    explain_keywords = {"explain", "understand", "stuck", "help", "why", "how", "define", "what is"}

    lower = q.lower()

    action = "retrieve_and_explain"
    if any(k in lower for k in quiz_keywords):
        action = "generate_quiz"
    elif any(k in lower for k in explain_keywords):
        action = "retrieve_and_explain"
    else:
        action = "retrieve_and_explain"

    # difficulty from student history
    diff = "medium"
    try:
        if student_id and topic_strength:
            strength = topic_strength(student_id, chosen_topic)
            if strength == "weak":
                diff = "easy"
            elif strength == "strong":
                diff = "hard"
            else:
                diff = "medium"
    except Exception:
        logging.exception("topic_strength lookup failed")

    # user overrides in query
    if re.search(r"\beasy\b", lower):
        diff = "easy"
    if re.search(r"\bhard\b|\bdifficult\b", lower):
        diff = "hard"

    plan = {
        "action": action,
        "topic": chosen_topic,
        "difficulty": diff,
        # frontend can use this flag to decide whether to attempt quiz generation after explanation
        "quiz_suggestion": True if action == "retrieve_and_explain" else False
    }
    return plan
