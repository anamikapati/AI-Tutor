# backend/retriever.py
"""
Retriever: loads kb_chunks.npy + kb_index.faiss from backend/ and returns high-quality text chunks.
This version:
 - avoids printing non-ASCII emoji (prevents charmap encoding errors)
 - uses a robust heuristic to detect math-heavy blocks instead of aggressively removing anything with a symbol
 - normalizes and strips control / non-UTF8 chars from returned text
"""

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import os
import re
import unicodedata

BASE_DIR = os.path.dirname(__file__)
KB_CHUNKS = os.path.join(BASE_DIR, "kb_chunks.npy")
KB_INDEX  = os.path.join(BASE_DIR, "kb_index.faiss")

model = None
chunks = None
index = None

# -------------------------------
# Utility: safe string cleanup (strip odd unicode like emojis for readability)
# -------------------------------
def _safe_text(t: str) -> str:
    if t is None:
        return ""
    # normalize, then remove non-printable control chars
    t = unicodedata.normalize("NFC", t)
    # remove control chars except newlines/tabs
    t = "".join(ch for ch in t if (ch.isprintable() or ch in "\n\t"))
    # encode-decode to strip characters that may break some consoles (ignore errors)
    try:
        t = t.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        pass
    # collapse excessive whitespace
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

# -------------------------------
# Load model once
# -------------------------------
def _load_model():
    global model
    if model is None:
        print("Loading sentence transformer model...")
        model = SentenceTransformer("all-MiniLM-L6-v2")
    return model

# -------------------------------
# Load KB data (chunks + FAISS index)
# -------------------------------
def _load_kb():
    global chunks, index

    if chunks is None:
        if not os.path.exists(KB_CHUNKS):
            raise FileNotFoundError("kb_chunks.npy missing — run kb_builder.py first.")
        print("Loading KB chunks...")
        chunks = list(np.load(KB_CHUNKS, allow_pickle=True))

    if index is None:
        if not os.path.exists(KB_INDEX):
            raise FileNotFoundError("kb_index.faiss missing — run kb_builder.py first.")
        print("Loading FAISS index...")
        index = faiss.read_index(KB_INDEX)

    return chunks, index

# -------------------------------
# Heuristic to detect math-heavy block
# -------------------------------
MATH_TOKENS = set(["\\frac", "\\sum", "\\int", "=", "<", ">", "×", "÷", "∫", "Σ", "π", "√", "^", "_", "lim", "exp"])
def is_math_block(text: str) -> bool:
    if not text:
        return False
    # token heuristic: presence of LaTeX tokens or math symbols
    count_tokens = sum(1 for t in MATH_TOKENS if t in text)
    # symbol ratio heuristic: fraction of characters that are not letters/numbers/punctuation/newline
    total_chars = max(1, len(text))
    non_alnum = sum(1 for ch in text if not (ch.isalnum() or ch.isspace() or ch in ".,;:-()[]{}'\"/"))
    symbol_ratio = non_alnum / total_chars
    # short lines with many digits likely an exercise item (skip)
    digits = sum(ch.isdigit() for ch in text)
    digit_ratio = digits / total_chars
    # decide
    if count_tokens >= 1:
        return True
    if symbol_ratio > 0.28 and digit_ratio > 0.05:
        return True
    # also, lines that are mostly numbers or sequences like "1. 2. 3." are math/exercises
    if re.search(r"^\s*\d+[\.\)]", text.strip()):
        return True
    return False

# -------------------------------
# Text cleaner
# -------------------------------
def _clean_text(t):
    if not t:
        return ""
    t = _safe_text(t)
    # remove excessive page/section markers like "----" or "..." sequences
    t = re.sub(r"[-]{3,}", "", t)
    t = re.sub(r"\.{3,}", ".", t)
    t = t.strip()
    return t

def clean_chunk(text):
    if not text:
        return None
    text = text.strip()
    # remove typical exercise headings or numbered problems
    if re.search(r"\b(Find|Calculate|Determine|Show that|Prove)\b", text):
        return None
    if re.match(r"^\d+\.", text):
        return None
    return text

# -------------------------------
# Main retrieval
# -------------------------------
def retrieve(query, top_k=3):
    """
    Retrieve high-quality TEXT chunks from the knowledge base.
    """
    _load_model()
    chunks_list, idx = _load_kb()

    # encode query safely
    q_emb = model.encode([query])
    D, I = idx.search(np.array(q_emb).astype("float32"), top_k)

    results = []
    seen = set()

    for i in I[0]:
        if i < 0 or i >= len(chunks_list):
            continue

        chunk = chunks_list[i]
        if isinstance(chunk, str):
            chunk = {"chapter": "unknown", "text": chunk, "type": "text"}

        ch_type = chunk.get("type", "text")
        if ch_type != "text":
            continue

        raw_text = str(chunk.get("text", ""))
        chapter = chunk.get("chapter", "unknown")

        # basic math block detection
        if is_math_block(raw_text):
            continue

        cleaned = _clean_text(raw_text)
        cleaned = clean_chunk(cleaned)
        if not cleaned or len(cleaned) < 20:
            continue

        # deduplicate nearly identical chunks
        key = (chapter, cleaned[:120])
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "chapter": str(chapter),
            "text": str(cleaned),
            "type": "text"
        })

    return results
