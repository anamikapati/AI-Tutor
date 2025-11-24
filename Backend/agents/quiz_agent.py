# backend/agents/quiz_agent.py
"""
Quiz Agent wrapper.

Prefer to call the project's existing quiz generator (backend.quiz_generator).
If unavailable, provides a minimal fallback that returns a safe placeholder MCQ.
"""

import logging
from typing import List, Dict

try:
    from backend.quiz_generator import generate_quiz_for_topic as _core_quiz
except Exception:
    _core_quiz = None
    logging.exception("Failed to import backend.quiz_generator")


def generate_quiz(topic: str, n_questions: int = 3, difficulty: str = None) -> List[Dict]:
    """
    Returns a list of MCQ dicts:
    { "chapter": "...", "question": "...", "options": [...], "answer": "A", "explanation": "..." }
    """
    if _core_quiz is None:
        # fallback: produce placeholder questions
        placeholder = []
        for i in range(1, n_questions + 1):
            placeholder.append({
                "chapter": "",
                "question": f"No generated MCQs found for '{topic}'. Placeholder Q{i}",
                "options": ["-", "-", "-", "-"],
                "answer": "A",
                "explanation": "No content available to generate MCQs."
            })
        return placeholder

    try:
        quiz = _core_quiz(topic, n_questions=n_questions, difficulty=difficulty)
        # Ensure it's a list and trim/normalize
        if not isinstance(quiz, list):
            return []
        return quiz[:n_questions]
    except Exception as e:
        logging.exception("generate_quiz failed: %s", e)
        return []
