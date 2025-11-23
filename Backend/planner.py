# planner.py
from typing import Dict
import re
from backend.progress_db import topic_strength


# -----------------------------------------
# Normalize topics for consistent matching
# -----------------------------------------
def _normalize_topic(topic: str) -> str:
    if not topic:
        return ""
    return topic.strip().lower()


# -----------------------------------------
# MASTER TOPIC LIST (Aligned with 1–13 PDFs)
# -----------------------------------------
VALID_TOPICS = {
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
}

def _match_best_topic(text: str) -> str:
    text = text.lower()
    for t in VALID_TOPICS:
        if t in text:
            return t
    return ""


# -----------------------------------------
# THE MAIN DECISION ENGINE
# -----------------------------------------
def planner_decide(student_id: str, query: str = "", topic: str = None) -> Dict:
    """
    Decide high-level action + topic + difficulty.
    Output:
      {
        "action": "retrieve_and_explain" | "generate_quiz",
        "topic": "<topic>",
        "difficulty": "easy" | "medium" | "hard"
      }
    """
    q = (query or "").strip().lower()

    # ------------------------------------------------------------
    # 1. Determine topic (user-given or inferred)
    # ------------------------------------------------------------
    chosen_topic = topic or _match_best_topic(q) or ""

    if not chosen_topic:
        # No topic found → assume query IS the topic
        chosen_topic = q

    chosen_topic = _normalize_topic(chosen_topic)

    # ------------------------------------------------------------
    # 2. Detect ACTION (quiz or explanation)
    # ------------------------------------------------------------
    quiz_intent_keywords = ["quiz", "practice", "test", "exercise", "questions", "mcq"]
    explain_keywords = ["explain", "understand", "stuck", "help", "why", "how", "define"]

    if any(k in q for k in quiz_intent_keywords):
        action = "generate_quiz"
    elif any(k in q for k in explain_keywords):
        action = "retrieve_and_explain"
    else:
        # Default behavior: EXPLAIN first, then frontend may call quiz
        action = "retrieve_and_explain"

    # ------------------------------------------------------------
    # 3. Choose difficulty using student history
    # ------------------------------------------------------------
    if student_id:
        strength = topic_strength(student_id, chosen_topic)
    else:
        strength = "medium"

    if strength == "weak":
        difficulty = "easy"
    elif strength == "strong":
        difficulty = "hard"
    else:
        difficulty = "medium"

    # User explicit overrides:
    if "easy" in q:
        difficulty = "easy"
    if "hard" in q or "difficult" in q:
        difficulty = "hard"

    # ------------------------------------------------------------
    # FINAL OUTPUT
    # ------------------------------------------------------------
    return {
        "action": action,
        "topic": chosen_topic,
        "difficulty": difficulty
    }
