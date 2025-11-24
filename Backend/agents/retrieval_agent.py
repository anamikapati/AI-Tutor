# backend/agents/retrieval_agent.py
"""
Retrieval Agent wrapper.
Uses the existing backend.retriever.retrieve function and provides a small
cleaning / summarization helper to return a short explanation string + metadata.
"""

import logging
import unicodedata
from typing import List, Dict

# import the project's retriever (already present in backend/retriever.py)
try:
    from backend.retriever import retrieve as _core_retrieve
except Exception as e:
    _core_retrieve = None
    logging.exception("Failed importing backend.retriever: %s", e)


def _safe_normalize(text: str) -> str:
    if not text:
        return ""
    try:
        text = unicodedata.normalize("NFC", text)
    except Exception:
        pass
    return text.strip()


def retrieve_text(query: str, top_k: int = 3) -> List[Dict]:
    """
    Return a list of retrieved clean chunks:
      [ { "chapter": "...", "text": "..." }, ... ]
    If the core retriever is unavailable, returns an empty list.
    """
    if _core_retrieve is None:
        logging.warning("Core retriever not available")
        return []

    try:
        chunks = _core_retrieve(query, top_k=top_k)
        out = []
        for c in chunks:
            t = _safe_normalize(c.get("text", "") if isinstance(c, dict) else str(c))
            chapter = c.get("chapter", "") if isinstance(c, dict) else ""
            out.append({"chapter": chapter, "text": t})
        return out
    except Exception as e:
        logging.exception("retrieve_text failed: %s", e)
        return []
