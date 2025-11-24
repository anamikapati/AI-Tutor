# backend/agents/explainer.py
"""
Explainer Agent: simple logic to assemble retrieved chunks into a short
student-facing explanation. Uses backend.retriever via the retrieval_agent.
"""

import logging
from typing import List, Dict

try:
    from backend.agents.retrieval_agent import retrieve_text
except Exception:
    # If the agent package is not installed/available, try to import the top-level retriever
    try:
        from backend.retriever import retrieve as _raw_retrieve  # type: ignore
        def retrieve_text(q, top_k=3):
            ch = _raw_retrieve(q, top_k=top_k)
            return [{"chapter": c.get("chapter", ""), "text": c.get("text","")} for c in ch]
    except Exception:
        retrieve_text = lambda q, top_k=3: []
        logging.exception("Falling back: No retriever available")


def explain(topic: str, top_k: int = 3, max_chars: int = 1000) -> Dict:
    """
    Returns:
      {
        "topic": topic,
        "explanation": "concatenated useful text",
        "chapter": first_chapter_found,
        "sources": [ ... ]
      }
    """
    chunks = retrieve_text(topic, top_k=top_k)
    if not chunks:
        return {"topic": topic, "explanation": "No explanation found.", "chapter": None, "sources": []}

    # Pick up to top_k chunks, join them, and trim
    parts = []
    sources = []
    for c in chunks[:top_k]:
        t = c.get("text", "").strip()
        if not t:
            continue
        parts.append(t)
        chapter = c.get("chapter")
        if chapter:
            sources.append(chapter)

    explanation = "\n\n".join(parts)
    if len(explanation) > max_chars:
        explanation = explanation[:max_chars].rsplit(" ", 1)[0] + "..."

    first_chapter = sources[0] if sources else None
    return {"topic": topic, "explanation": explanation, "chapter": first_chapter, "sources": sources}
