# backend/quiz_generator.py
"""
Quiz generator (JEE-style MCQs) using definition/formula patterns and a robust fallback.
Imports the retriever from backend.retriever (works when run as package).
"""

import re
import random
from backend.retriever import retrieve

# Basic distractor bank (academic-themed)
BASE_DISTRACTORS = [
    "Limit", "Derivative", "Integral", "Matrix", "Determinant",
    "Probability", "Permutation", "Combination", "Vector",
    "Scalar", "Continuity", "Differentiability", "Gradient", "Rank"
]

# Patterns that indicate clean definition phrases
DEF_PATTERNS = [
    re.compile(r"\b([A-Za-z][A-Za-z\s]{2,50}) is defined as (.+)", re.IGNORECASE),
    re.compile(r"\b([A-Za-z][A-Za-z\s]{2,50}) is (an|a) (.+)", re.IGNORECASE),
    re.compile(r"\bThe definition of ([A-Za-z][A-Za-z\s]{1,50}) is (.+)", re.IGNORECASE),
    re.compile(r"\b([A-Za-z][A-Za-z\s]{2,50}) refers to (.+)", re.IGNORECASE),
]

DEF_RE_SIMPLE = re.compile(r"^([A-Za-z][A-Za-z\s]{1,40}) is (.+)", re.IGNORECASE)

def clean_text(t):
    if not t:
        return ""
    t = re.sub(r"[]", "", t)
    t = re.sub(r"\bFig\b.*", "", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()

def is_bad_concept(c):
    c = c.lower().strip()
    if len(c) < 3:
        return True
    if any(w in c for w in ("what","which","this","that","how","why","where","when")):
        return True
    if re.search(r"\d", c):
        return True
    if len(c.split()) > 5:
        return True
    return False

def generate_distractors_for(concept, correct):
    # Prefer distractors similar domain from BASE_DISTRACTORS
    picks = [d for d in BASE_DISTRACTORS if d.lower() != concept.lower()]
    random.shuffle(picks)
    distractors = picks[:3]
    # fallback: random labels
    while len(distractors) < 3:
        distractors.append("Option " + str(random.randint(10, 99)))
    return distractors

def extract_candidate_sentences(text):
    sents = re.split(r"(?<=[.!?])\s+", text)
    cleaned = []
    for s in sents:
        s2 = clean_text(s)
        if 20 < len(s2) < 300:
            cleaned.append(s2)
    return cleaned

def sentence_to_mcq(sentence, chapter):
    # try multiple definition patterns
    for pat in DEF_PATTERNS:
        m = pat.search(sentence)
        if m:
            # pick groups flexibly
            concept = m.group(1).strip()
            definition = m.group(2).strip() if m.lastindex >= 2 else sentence
            if not is_bad_concept(concept) and len(definition) > 12:
                correct = definition
                distractors = generate_distractors_for(concept, correct)
                options = distractors + [correct]
                random.shuffle(options)
                return {
                    "chapter": chapter,
                    "question": f"What is {concept.strip()}?",
                    "options": options,
                    "answer": chr(options.index(correct) + 65),
                    "explanation": definition
                }

    # fallback: simpler regex
    m = DEF_RE_SIMPLE.search(sentence)
    if m:
        concept = m.group(1).strip()
        definition = m.group(2).strip()
        if not is_bad_concept(concept) and len(definition) > 12:
            correct = definition
            distractors = generate_distractors_for(concept, correct)
            options = distractors + [correct]
            random.shuffle(options)
            return {
                "chapter": chapter,
                "question": f"What is {concept}?",
                "options": options,
                "answer": chr(options.index(correct) + 65),
                "explanation": definition
            }

    return None

def fallback_mcq(topic, chapter=""):
    # Safe fallback: ask a generic conceptual question with plausible distractors
    concept = topic.split()[:3]
    concept = " ".join(concept).strip() or "the topic"
    correct = f"A brief description of {concept}."
    distractors = generate_distractors_for(concept, correct)
    options = distractors + [correct]
    random.shuffle(options)
    return {
        "chapter": chapter,
        "question": f"Which of the following best describes {concept}?",
        "options": options,
        "answer": chr(options.index(correct) + 65),
        "explanation": correct
    }

def generate_quiz_for_topic(topic, n_questions=3, difficulty=None):
    # retrieve more chunks to have richer material
    chunks = retrieve(topic, top_k=20)
    mcqs = []

    for ch in chunks:
        text = clean_text(ch.get("text", ""))
        chapter = ch.get("chapter", "")

        sents = extract_candidate_sentences(text)
        for s in sents:
            mcq = sentence_to_mcq(s, chapter)
            if mcq:
                mcqs.append(mcq)
            if len(mcqs) >= n_questions:
                return mcqs

    # If no MCQs found from chunks, try to create fallbacks using small heuristics:
    if not mcqs:
        # try using the first chunk's title/words as concept
        if chunks:
            ch0 = chunks[0]
            ch_text = ch0.get("text", "")
            # try to extract noun phrase as concept
            words = re.findall(r"[A-Za-z]{3,}", topic)
            guess = " ".join(words[:3]) if words else topic
            # generate 3 fallback MCQs (slightly varied)
            for i in range(n_questions):
                q = fallback_mcq(guess or topic, chapter=ch0.get("chapter",""))
                mcqs.append(q)
            return mcqs

    # final fallback minimal MCQ
    return mcqs[:n_questions] if mcqs else [{
        "chapter": "",
        "question": f"No clear MCQs found for '{topic}'.",
        "options": ["-", "-", "-", "-"],
        "answer": "A",
        "explanation": "No definitional or formula-based content detected."
    }]
