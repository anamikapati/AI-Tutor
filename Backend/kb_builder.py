# backend/kb_builder.py
"""
kb_builder.py — improved KB builder that:
 - saves files inside backend/
 - uses a better math-block detection heuristic to avoid removing definitional text
 - prints ASCII-only messages to avoid encoding issues
"""

import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import random
import re
from collections import Counter
import os
import unicodedata

BASE_DIR = os.path.dirname(__file__)
KB_CHUNKS_PATH = os.path.join(BASE_DIR, "kb_chunks.npy")
KB_INDEX_PATH  = os.path.join(BASE_DIR, "kb_index.faiss")

PDF_COUNT = 13
pdf_files = [os.path.join(BASE_DIR, f"{i}.pdf") for i in range(1, PDF_COUNT + 1)]

print("Processing PDFs:", pdf_files)

# math heuristics (same idea as retriever)
MATH_TOKENS = set(["\\frac", "\\sum", "\\int", "=", "<", ">", "×", "÷", "∫", "Σ", "π", "√", "^", "_", "lim"])

def is_math_block(text: str) -> bool:
    if not text:
        return False
    # if it contains LaTeX tokens or many math symbols -> math
    count_tokens = sum(1 for t in MATH_TOKENS if t in text)
    total_chars = max(1, len(text))
    non_alnum = sum(1 for ch in text if not (ch.isalnum() or ch.isspace() or ch in ".,;:-()[]{}'\"/"))
    symbol_ratio = non_alnum / total_chars
    digits = sum(ch.isdigit() for ch in text)
    digit_ratio = digits / total_chars
    if count_tokens >= 1:
        return True
    if symbol_ratio > 0.28 and digit_ratio > 0.05:
        return True
    if re.search(r"^\s*\d+[\.\)]", text.strip()):
        return True
    return False

def find_repeated_headers(pdf_path, sample_pages=10):
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        print(f"Could not open PDF: {pdf_path}")
        return []
    texts = []
    for i, page in enumerate(doc):
        if i >= sample_pages:
            break
        blocks = page.get_text("blocks") or []
        if not blocks:
            continue
        blocks = sorted(blocks, key=lambda b: b[1])
        top = blocks[0][4].strip() if blocks else ""
        bottom = blocks[-1][4].strip() if blocks else ""
        if len(top) > 5:
            texts.append(top)
        if len(bottom) > 5:
            texts.append(bottom)
    repeated = [t for t, c in Counter(texts).items() if c >= 3]
    return repeated

def extract_clean_chunks(pdf_path, header_footer=None, max_len=6000):
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        print(f"Could not open PDF: {pdf_path}")
        return []
    chunks = []
    hf = header_footer or []
    for page in doc:
        blocks = page.get_text("blocks") or []
        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
        for b in blocks:
            text = b[4].strip()
            if not text:
                continue
            # Remove header/footer
            if any(h in text for h in hf):
                continue
            # Remove page numbers
            if re.fullmatch(r'\d{1,3}', text):
                continue
            # normalize unicode and remove control chars
            text = unicodedata.normalize("NFC", text)
            # detect math/exercise blocks
            if is_math_block(text):
                continue
            # normalize breaks
            text = re.sub(r'\r\n?', '\n', text)
            paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 25]
            for para in paragraphs:
                if len(para) > max_len:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    buff = ""
                    for s in sentences:
                        if len(buff) + len(s) > max_len:
                            chunks.append({
                                "chapter": os.path.basename(pdf_path),
                                "text": buff.strip()
                            })
                            buff = s
                        else:
                            buff += " " + s
                    if buff.strip():
                        chunks.append({
                            "chapter": os.path.basename(pdf_path),
                            "text": buff.strip()
                        })
                else:
                    chunks.append({
                        "chapter": os.path.basename(pdf_path),
                        "text": para
                    })
    return chunks

# Collect chunks
chunk_objs = []
for pdf in pdf_files:
    print(f"\nExtracting from: {pdf}")
    if not os.path.exists(pdf):
        print(f" Missing PDF: {pdf}")
        continue
    hf = find_repeated_headers(pdf)
    cleaned = extract_clean_chunks(pdf, header_footer=hf)
    chunk_objs.extend(cleaned)

print("\nTotal clean text chunks:", len(chunk_objs))

# show a few samples
print("\n=== SAMPLE CHUNKS ===")
for obj in random.sample(chunk_objs, min(6, len(chunk_objs))):
    print(f"[{obj['chapter']}] {obj['text'][:200]}...\n")

# Embedding
texts = [c["text"] for c in chunk_objs]
print("\nEmbedding", len(texts), "chunks. This can take a while...")
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(texts, show_progress_bar=True)

# Build FAISS Index
dim = embeddings.shape[1]
index = faiss.IndexFlatL2(dim)
index.add(np.array(embeddings).astype("float32"))

faiss.write_index(index, KB_INDEX_PATH)
np.save(KB_CHUNKS_PATH, np.array(chunk_objs, dtype=object))

print("\n✔ KB BUILD COMPLETE")
print("Saved:", KB_INDEX_PATH)
print("Saved:", KB_CHUNKS_PATH)

# Quick test
def search_chunks(query, k=3):
    emb = model.encode([query])
    D, I = index.search(np.array(emb).astype("float32"), k)
    return [chunk_objs[i] for i in I[0] if i < len(chunk_objs)]

print("\n=== TEST SEARCH: 'conditional probability' ===")
for obj in search_chunks("conditional probability"):
    print(f"[{obj['chapter']}] {obj['text'][:200]}...\n")
