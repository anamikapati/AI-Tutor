# progress_db.py
import sqlite3
import datetime
from typing import Dict, Any, List
import json

DB_PATH = "students.db"


# ============================================================
# 1. Initialize Database
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ---------------- Students table ----------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT UNIQUE,
            created_at TEXT
        )
    """)

    # ---------------- Attempts table ----------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            topic TEXT,
            question TEXT,
            is_correct INTEGER,
            difficulty TEXT,
            timestamp TEXT
        )
    """)

    # ---------------- Interaction Log (required for assignment) ----------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            query TEXT,
            plan TEXT,          -- JSON list of planner actions
            retrieved TEXT,     -- short retrieved text snippet
            quiz_meta TEXT,     -- JSON describing quiz features
            response TEXT,      -- natural language response shown to student
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# 2. Student Lookup Helpers
# ============================================================
def student_exists(student_id: str = None, name: str = None) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if student_id:
        c.execute("SELECT 1 FROM students WHERE student_id=?", (student_id,))
        if c.fetchone():
            conn.close()
            return True

    if name:
        c.execute("SELECT 1 FROM students WHERE name=?", (name,))
        if c.fetchone():
            conn.close()
            return True

    conn.close()
    return False


# ============================================================
# 3. Register Student (Duplicate-protected)
# ============================================================
def register_student(student_id: str, name: str = "") -> Dict[str, Any]:
    """
    Registers a student safely.
    Prevents:
        - duplicate ID
        - duplicate name
    """
    if student_exists(student_id=student_id):
        return {"success": False, "message": f"Student ID '{student_id}' is already registered!"}

    if name and student_exists(name=name):
        return {"success": False, "message": f"Student name '{name}' is already registered!"}

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO students(student_id, name, created_at) VALUES (?, ?, ?)",
        (student_id, name, datetime.datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    return {"success": True, "message": f"Student '{name}' registered successfully."}


# ============================================================
# 4. Record Quiz Attempts
# ============================================================
def record_attempt(student_id: str, topic: str, question: str,
                   is_correct: bool, difficulty: str = None) -> None:

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO attempts(student_id, topic, question, is_correct, difficulty, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (student_id, topic, question, int(is_correct), difficulty or "",
         datetime.datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


# ============================================================
# 5. Fetch Progress Summary
# ============================================================
def get_progress(student_id: str) -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT topic, SUM(is_correct) as correct, COUNT(*) as attempts
        FROM attempts WHERE student_id=? GROUP BY topic
    """, (student_id,))
    rows = c.fetchall()
    conn.close()

    prof = {}
    for topic, correct, attempts in rows:
        accuracy = (correct / attempts) if attempts else 0.0

        # Strength classification
        if attempts >= 3 and accuracy >= 0.8:
            strength = "strong"
        elif attempts >= 2 and accuracy <= 0.5:
            strength = "weak"
        else:
            strength = "medium"

        prof[topic] = {
            "accuracy": round(accuracy * 100, 1),
            "attempts": attempts,
            "strength": strength
        }

    return prof


def topic_strength(student_id: str, topic: str) -> str:
    prof = get_progress(student_id)
    return prof.get(topic, {}).get("strength", "medium")


# ============================================================
# 6. Interaction Logging (Planner / Retrieval / Quiz)
# ============================================================
def log_interaction(student_id: str, query: str,
                    plan: list, retrieved: str,
                    quiz_meta: dict, response: str):
    """
    Logs every AI action (required by assignment):
      - planner steps
      - retrieved text
      - quiz generation meta
      - natural language explanation
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO interactions(student_id, query, plan, retrieved, quiz_meta, response, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            student_id,
            query,
            json.dumps(plan),
            retrieved[:250],
            json.dumps(quiz_meta),
            response[:500],
            datetime.datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    conn.close()

def get_interactions(student_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Return recent interaction logs for a student as a list of dicts.
    Each dict contains: id, query, plan (parsed JSON), retrieved, quiz_meta (parsed JSON), response, timestamp
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, query, plan, retrieved, quiz_meta, response, timestamp
        FROM interactions
        WHERE student_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (student_id, limit))
    rows = c.fetchall()
    conn.close()

    out = []
    for r in rows:
        id_, query, plan_j, retrieved, quiz_meta_j, response, timestamp = r
        try:
            plan = json.loads(plan_j) if plan_j else []
        except Exception:
            plan = [plan_j] if plan_j else []
        try:
            quiz_meta = json.loads(quiz_meta_j) if quiz_meta_j else {}
        except Exception:
            quiz_meta = {}
        out.append({
            "id": id_,
            "query": query,
            "plan": plan,
            "retrieved": retrieved,
            "quiz_meta": quiz_meta,
            "response": response,
            "timestamp": timestamp
        })
    return out
# Initialize DB when module loads
init_db()
