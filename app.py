import os
import json
import random
import sqlite3
import hashlib
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey123")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
ADMIN_PASSWORD = "BAXTIYOR1234!@<>"
DB_PATH = "quiz.db"

# ─────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_bases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                questions TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def shuffle_options(questions):
    """Variant ichidagi A/B/C/D ni aralashtiradi va correct indeksini yangilaydi."""
    result = []
    for q in questions:
        opts = list(q["options"])
        correct_text = opts[q["correct"]]
        # A) B) C) D) prefikslarini olib tashlash
        clean_opts = []
        for o in opts:
            if len(o) > 2 and o[1] == ')':
                clean_opts.append(o[2:].strip())
            else:
                clean_opts.append(o.strip())
        correct_clean = clean_opts[q["correct"]]
        random.shuffle(clean_opts)
        new_correct = clean_opts.index(correct_clean)
        labels = ["A", "B", "C", "D"]
        labeled = [f"{labels[i]}) {clean_opts[i]}" for i in range(len(clean_opts))]
        result.append({
            "question": q["question"],
            "options": labeled,
            "correct": new_correct
        })
    return result

def prepare_quiz_questions(questions):
    """Frontend uchun correct indeksini olib tashlaydi (xavfsizlik)."""
    safe = []
    for q in questions:
        safe.append({
            "question": q["question"],
            "options": q["options"]
        })
    return safe

def get_answer_key(questions):
    """Faqat backend uchun to'g'ri javoblar ro'yxati."""
    return [q["correct"] for q in questions]

# ─────────────────────────────────────────────
#  GROQ AI
# ─────────────────────────────────────────────

def extract_questions_with_groq(text, num_questions=30):
    client = Groq(api_key=GROQ_API_KEY)
    prompt = f"""Quyidagi matndan {num_questions} ta test savoli va har biriga 4 ta javob varianti yarating.
MUHIM QOIDALAR:
- To'g'ri javob har doim turli variantlarda bo'lsin (faqat A da emas)
- Savollar matn mavzusiga mos bo'lsin
- FAQAT sof JSON qaytaring, boshqa hech narsa yozmang
- Prefiks yozmang (A), B) emas - faqat matn)

JSON format:
[
  {{
    "question": "Savol matni?",
    "options": ["variant1", "variant2", "variant3", "variant4"],
    "correct": 2
  }}
]
"correct" - to'g'ri javob indeksi (0,1,2 yoki 3).

MATN:
{text[:7000]}"""

    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-70b-8192",
        temperature=0.7,
        max_tokens=8000,
    )
    raw = chat.choices[0].message.content.strip()
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError("AI JSON qaytarmadi. Qaytadan urinib ko'ring.")
    parsed = json.loads(raw[start:end])
    if not parsed:
        raise ValueError("Savollar bo'sh qaytdi.")
    return parsed

# ─────────────────────────────────────────────
#  CSS & FONTS
# ─────────────────────────────────────────────

GLOBAL_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Fraunces:ital,wght@0,300;0,600;0,900;1,300;1,600&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --ink: #0d0f14;
  --ink2: #1a1d26;
  --ink3: #252836;
  --line: #2e3245;
  --mist: #4a5068;
  --fog: #7c849e;
  --snow: #c8cfe0;
  --white: #eef0f7;
  --gold: #f0c060;
  --gold2: #e8a830;
  --jade: #50d4a0;
  --jade2: #2ebd88;
  --rose: #f07090;
  --sky: #60b4f0;
  --r: 16px;
  --r2: 24px;
  --font-display: 'Fraunces', Georgia, serif;
  --font-body: 'Plus Jakarta Sans', sans-serif;
  --shadow: 0 2px 8px rgba(0,0,0,0.3), 0 8px 32px rgba(0,0,0,0.2);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.4), 0 24px 64px rgba(0,0,0,0.3);
  --glow-gold: 0 0 24px rgba(240,192,96,0.25);
  --glow-jade: 0 0 24px rgba(80,212,160,0.25);
}

html { scroll-behavior: smooth; }

body {
  background: var(--ink);
  color: var(--white);
  font-family: var(--font-body);
  min-height: 100vh;
  line-height: 1.6;
  overflow-x: hidden;
}

/* Fon teksturasi */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 10% 0%, rgba(80,212,160,0.06) 0%, transparent 60%),
    radial-gradient(ellipse 60% 80% at 90% 100%, rgba(240,192,96,0.05) 0%, transparent 60%);
  pointer-events: none;
  z-index: 0;
}

body > * { position: relative; z-index: 1; }

a { color: inherit; text-decoration: none; }

/* ── NAV ── */
.nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 40px; height: 64px;
  border-bottom: 1px solid var(--line);
  background: rgba(13,15,20,0.85);
  backdrop-filter: blur(20px);
  position: sticky; top: 0; z-index: 200;
}
.nav-logo {
  font-family: var(--font-display);
  font-weight: 900; font-size: 20px; letter-spacing: -0.5px;
  color: var(--gold);
  display: flex; align-items: center; gap: 10px;
}
.nav-logo span { color: var(--white); }
.nav-links { display: flex; gap: 8px; }

/* ── BUTTONS ── */
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 22px; border-radius: 100px;
  font-family: var(--font-body); font-size: 14px; font-weight: 600;
  border: none; cursor: pointer; transition: all 0.2s ease;
  letter-spacing: 0.01em; white-space: nowrap;
}
.btn-ghost {
  background: transparent; color: var(--fog);
  border: 1px solid var(--line);
}
.btn-ghost:hover { color: var(--white); border-color: var(--mist); background: var(--ink2); }

.btn-gold {
  background: linear-gradient(135deg, var(--gold), var(--gold2));
  color: var(--ink); font-weight: 700;
  box-shadow: 0 4px 16px rgba(240,192,96,0.3);
}
.btn-gold:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(240,192,96,0.4); }
.btn-gold:active { transform: translateY(0); }

.btn-jade {
  background: linear-gradient(135deg, var(--jade), var(--jade2));
  color: var(--ink); font-weight: 700;
  box-shadow: 0 4px 16px rgba(80,212,160,0.3);
}
.btn-jade:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(80,212,160,0.4); }

.btn-danger {
  background: transparent; color: var(--rose);
  border: 1px solid rgba(240,112,144,0.3);
}
.btn-danger:hover { background: rgba(240,112,144,0.1); border-color: var(--rose); }

.btn-outline {
  background: transparent; color: var(--snow);
  border: 1px solid var(--line);
}
.btn-outline:hover { background: var(--ink2); border-color: var(--mist); }

.btn-lg { padding: 14px 32px; font-size: 16px; border-radius: 100px; }

/* ── LAYOUT ── */
.container { max-width: 900px; margin: 0 auto; padding: 48px 24px; }
.container-sm { max-width: 560px; margin: 0 auto; padding: 48px 24px; }
.container-md { max-width: 720px; margin: 0 auto; padding: 48px 24px; }

/* ── CARDS ── */
.card {
  background: var(--ink2);
  border: 1px solid var(--line);
  border-radius: var(--r2);
  padding: 32px;
  transition: border-color 0.25s, box-shadow 0.25s, transform 0.25s;
}
.card-hover:hover {
  border-color: rgba(240,192,96,0.3);
  box-shadow: var(--glow-gold);
  transform: translateY(-3px);
}

/* ── FORMS ── */
.form-group { margin-bottom: 22px; }
.form-label {
  display: block; font-size: 12px; font-weight: 700;
  color: var(--fog); letter-spacing: 0.08em; text-transform: uppercase;
  margin-bottom: 10px;
}
.form-input, .form-textarea, .form-select {
  width: 100%; padding: 13px 18px;
  background: var(--ink3); border: 1px solid var(--line);
  border-radius: var(--r); color: var(--white);
  font-family: var(--font-body); font-size: 15px;
  transition: border-color 0.2s, box-shadow 0.2s; outline: none;
  appearance: none;
}
.form-input:focus, .form-textarea:focus, .form-select:focus {
  border-color: var(--gold); box-shadow: 0 0 0 3px rgba(240,192,96,0.12);
}
.form-input::placeholder, .form-textarea::placeholder { color: var(--mist); }
.form-textarea { resize: vertical; min-height: 200px; line-height: 1.7; }
.form-select {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%237c849e' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 16px center;
  padding-right: 44px;
}
.form-select option { background: var(--ink3); }

/* ── ALERTS ── */
.alert {
  padding: 14px 20px; border-radius: var(--r); font-size: 14px;
  font-weight: 500; margin-bottom: 24px; display: flex; align-items: center; gap: 10px;
}
.alert-ok { background: rgba(80,212,160,0.1); border: 1px solid rgba(80,212,160,0.25); color: var(--jade); }
.alert-err { background: rgba(240,112,144,0.1); border: 1px solid rgba(240,112,144,0.25); color: var(--rose); }

/* ── BADGES ── */
.badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 12px; border-radius: 100px; font-size: 12px; font-weight: 700;
  letter-spacing: 0.03em;
}
.badge-gold { background: rgba(240,192,96,0.12); color: var(--gold); border: 1px solid rgba(240,192,96,0.2); }
.badge-jade { background: rgba(80,212,160,0.12); color: var(--jade); border: 1px solid rgba(80,212,160,0.2); }
.badge-sky { background: rgba(96,180,240,0.12); color: var(--sky); border: 1px solid rgba(96,180,240,0.2); }

/* ── HERO ── */
.hero {
  min-height: 72vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  text-align: center; padding: 80px 24px;
  position: relative;
}
.hero-tag {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 16px; border-radius: 100px;
  background: rgba(240,192,96,0.1); border: 1px solid rgba(240,192,96,0.2);
  color: var(--gold); font-size: 13px; font-weight: 600;
  margin-bottom: 28px; letter-spacing: 0.05em;
}
.hero h1 {
  font-family: var(--font-display);
  font-size: clamp(48px, 8vw, 88px);
  font-weight: 900; line-height: 0.95; letter-spacing: -3px;
  margin-bottom: 24px;
}
.hero h1 em {
  font-style: italic; color: var(--gold);
}
.hero p {
  color: var(--fog); font-size: 18px; max-width: 460px;
  margin: 0 auto 40px; line-height: 1.7;
}
.hero-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }

/* ── SECTION ── */
.section-label {
  font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--mist); margin-bottom: 12px;
  display: flex; align-items: center; gap: 10px;
}
.section-label::after {
  content: ''; flex: 1; height: 1px; background: var(--line);
}
.section-title {
  font-family: var(--font-display);
  font-size: 32px; font-weight: 700; letter-spacing: -1px;
  margin-bottom: 32px; color: var(--white);
}

/* ── BASE GRID CARDS ── */
.base-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px,1fr)); gap: 20px; }
.base-card {
  background: var(--ink2); border: 1px solid var(--line);
  border-radius: var(--r2); padding: 28px;
  display: flex; flex-direction: column; gap: 14px;
  transition: all 0.25s;
  position: relative; overflow: hidden;
}
.base-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, var(--gold), var(--jade));
  opacity: 0; transition: opacity 0.25s;
}
.base-card:hover { border-color: rgba(240,192,96,0.3); transform: translateY(-4px); box-shadow: var(--glow-gold); }
.base-card:hover::before { opacity: 1; }
.base-card-title { font-family: var(--font-display); font-size: 20px; font-weight: 700; color: var(--white); }
.base-card-desc { font-size: 14px; color: var(--fog); line-height: 1.6; flex: 1; }

/* ── QUIZ SETUP ── */
.num-pills { display: flex; flex-wrap: wrap; gap: 10px; }
.num-pill input { display: none; }
.num-pill-label {
  display: flex; align-items: center; justify-content: center;
  width: 72px; height: 48px;
  border-radius: var(--r); border: 1.5px solid var(--line);
  background: var(--ink3); color: var(--fog);
  font-weight: 700; font-size: 16px; cursor: pointer;
  transition: all 0.2s;
}
.num-pill input:checked + .num-pill-label {
  border-color: var(--gold); color: var(--gold);
  background: rgba(240,192,96,0.1);
  box-shadow: 0 0 16px rgba(240,192,96,0.2);
}
.num-pill-label:hover { border-color: var(--mist); color: var(--snow); }

.mode-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.mode-card {
  background: var(--ink3); border: 2px solid var(--line);
  border-radius: var(--r2); padding: 24px 20px;
  cursor: pointer; transition: all 0.2s; text-align: center;
}
.mode-card input { display: none; }
.mode-card.selected { border-color: var(--jade); background: rgba(80,212,160,0.06); }
.mode-card-icon { font-size: 32px; margin-bottom: 12px; }
.mode-card-title { font-weight: 700; font-size: 15px; margin-bottom: 6px; color: var(--white); }
.mode-card-desc { font-size: 13px; color: var(--fog); line-height: 1.5; }

/* ── QUIZ PLAY ── */
.quiz-shell {
  max-width: 740px; margin: 0 auto; padding: 32px 24px 80px;
}
.quiz-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 28px; flex-wrap: wrap; gap: 12px;
}
.quiz-top-title { font-family: var(--font-display); font-size: 18px; font-weight: 700; color: var(--snow); }
.quiz-top-meta { font-size: 13px; color: var(--fog); margin-top: 2px; }
.quiz-timer {
  font-family: var(--font-display); font-size: 26px; font-weight: 900;
  color: var(--gold); letter-spacing: -1px;
  background: rgba(240,192,96,0.1); border: 1px solid rgba(240,192,96,0.2);
  padding: 6px 20px; border-radius: 100px;
}
.quiz-count { text-align: right; }
.quiz-count-num { font-family: var(--font-display); font-size: 24px; font-weight: 900; color: var(--white); }
.quiz-count-lbl { font-size: 12px; color: var(--fog); }

.progress-track {
  height: 5px; background: var(--line); border-radius: 10px;
  margin-bottom: 36px; overflow: hidden;
}
.progress-fill {
  height: 100%; border-radius: 10px;
  background: linear-gradient(90deg, var(--gold), var(--jade));
  transition: width 0.5s cubic-bezier(0.4,0,0.2,1);
}

.question-box {
  background: var(--ink2); border: 1px solid var(--line);
  border-radius: var(--r2); padding: 36px;
  margin-bottom: 20px;
  animation: fadeUp 0.3s ease;
}
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
.q-num {
  font-size: 11px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--gold); margin-bottom: 14px;
  display: flex; align-items: center; gap: 8px;
}
.q-num::before {
  content: ''; width: 24px; height: 2px; background: var(--gold);
  border-radius: 2px;
}
.q-text {
  font-family: var(--font-display); font-size: 22px; font-weight: 600;
  line-height: 1.45; color: var(--white); margin-bottom: 28px;
}
.options-list { display: flex; flex-direction: column; gap: 10px; }
.option-item {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 20px;
  background: var(--ink3); border: 1.5px solid var(--line);
  border-radius: var(--r); cursor: pointer;
  font-size: 15px; color: var(--snow);
  transition: all 0.15s ease;
  text-align: left; width: 100%;
  position: relative; overflow: hidden;
}
.option-item::before {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(90deg, rgba(240,192,96,0.05), transparent);
  opacity: 0; transition: opacity 0.2s;
}
.option-item:hover { border-color: var(--mist); color: var(--white); }
.option-item:hover::before { opacity: 1; }
.option-item.picked { border-color: var(--gold); color: var(--white); background: rgba(240,192,96,0.08); }
.option-item.picked::before { opacity: 1; }
.option-item.correct-ans { border-color: var(--jade); background: rgba(80,212,160,0.1); color: var(--white); }
.option-item.wrong-ans { border-color: var(--rose); background: rgba(240,112,144,0.08); color: var(--snow); }
.option-circle {
  width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
  background: var(--ink); border: 1.5px solid var(--line);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 12px; color: var(--fog);
  transition: all 0.15s;
}
.option-item.picked .option-circle { background: var(--gold); color: var(--ink); border-color: var(--gold); }
.option-item.correct-ans .option-circle { background: var(--jade); color: var(--ink); border-color: var(--jade); }
.option-item.wrong-ans .option-circle { background: var(--rose); color: var(--white); border-color: var(--rose); }
.option-text { flex: 1; line-height: 1.5; }

.quiz-nav {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; flex-wrap: wrap;
}

/* ── RESULT ── */
.result-card {
  background: var(--ink2); border: 1px solid var(--line);
  border-radius: var(--r2); padding: 56px 40px;
  text-align: center; position: relative; overflow: hidden;
}
.result-card::after {
  content: ''; position: absolute;
  top: -60px; right: -60px; width: 200px; height: 200px;
  background: radial-gradient(circle, rgba(240,192,96,0.08) 0%, transparent 70%);
}
.result-ring {
  width: 140px; height: 140px; border-radius: 50%;
  background: conic-gradient(var(--gold) var(--pct,0%), var(--ink3) 0%);
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 28px;
  position: relative;
  box-shadow: 0 0 0 4px var(--ink2), 0 0 0 6px rgba(240,192,96,0.2);
}
.result-ring-inner {
  width: 108px; height: 108px; border-radius: 50%;
  background: var(--ink2);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.result-pct {
  font-family: var(--font-display); font-size: 34px; font-weight: 900;
  color: var(--gold); line-height: 1;
}
.result-pct-lbl { font-size: 11px; color: var(--fog); font-weight: 600; }
.result-score-text {
  font-family: var(--font-display); font-size: 42px; font-weight: 900;
  letter-spacing: -2px; margin-bottom: 8px;
}
.result-label { font-size: 16px; color: var(--fog); margin-bottom: 36px; }
.result-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }

.stat-row {
  display: grid; grid-template-columns: repeat(3,1fr); gap: 16px;
  margin: 28px 0;
}
.stat-box {
  background: var(--ink3); border: 1px solid var(--line);
  border-radius: var(--r); padding: 18px 12px; text-align: center;
}
.stat-val { font-family: var(--font-display); font-size: 28px; font-weight: 900; }
.stat-lbl { font-size: 12px; color: var(--fog); margin-top: 4px; font-weight: 600; }

/* ── REVIEW ── */
.review-list { display: flex; flex-direction: column; gap: 16px; margin-top: 28px; }
.review-card {
  background: var(--ink2); border: 1px solid var(--line);
  border-radius: var(--r2); padding: 28px;
}
.review-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 14px;
}
.review-status {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 800; flex-shrink: 0;
}
.review-status.ok { background: rgba(80,212,160,0.15); color: var(--jade); }
.review-status.fail { background: rgba(240,112,144,0.15); color: var(--rose); }
.review-q { font-weight: 600; font-size: 16px; color: var(--white); line-height: 1.4; }
.review-opts { display: flex; flex-direction: column; gap: 8px; }
.review-opt {
  padding: 10px 16px; border-radius: 10px;
  font-size: 14px; color: var(--snow);
  background: var(--ink3); border: 1px solid var(--line);
}
.review-opt.correct-opt { background: rgba(80,212,160,0.1); border-color: rgba(80,212,160,0.3); color: var(--jade); }
.review-opt.wrong-opt { background: rgba(240,112,144,0.08); border-color: rgba(240,112,144,0.25); color: var(--rose); }

/* ── ADMIN ── */
.admin-base-row {
  background: var(--ink2); border: 1px solid var(--line);
  border-radius: var(--r2); padding: 20px 24px;
  display: flex; align-items: center; gap: 16px;
  transition: border-color 0.2s;
}
.admin-base-row:hover { border-color: var(--mist); }
.admin-base-info { flex: 1; }
.admin-base-name { font-weight: 700; font-size: 16px; color: var(--white); margin-bottom: 4px; }
.admin-base-meta { font-size: 13px; color: var(--fog); }
.admin-base-actions { display: flex; gap: 8px; }

/* ── LOADING ── */
.loading-overlay {
  display: none; position: fixed; inset: 0; z-index: 999;
  background: rgba(13,15,20,0.92); backdrop-filter: blur(8px);
  flex-direction: column; align-items: center; justify-content: center; gap: 20px;
}
.loading-overlay.active { display: flex; }
.loader-ring {
  width: 56px; height: 56px; border-radius: 50%;
  border: 3px solid var(--line);
  border-top-color: var(--gold);
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loader-text {
  font-family: var(--font-display); font-size: 18px;
  color: var(--snow); letter-spacing: -0.5px;
}
.loader-sub { font-size: 14px; color: var(--fog); }

/* ── MISC ── */
.divider { height: 1px; background: var(--line); margin: 32px 0; }
.flex { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.flex-between { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.text-gold { color: var(--gold); }
.text-jade { color: var(--jade); }
.text-fog { color: var(--fog); }
.text-rose { color: var(--rose); }
.mt-8 { margin-top: 8px; }
.mt-16 { margin-top: 16px; }
.mt-24 { margin-top: 24px; }
.mt-32 { margin-top: 32px; }
.mb-8 { margin-bottom: 8px; }
.mb-16 { margin-bottom: 16px; }
.mb-24 { margin-bottom: 24px; }

.empty-state {
  text-align: center; padding: 72px 32px;
  background: var(--ink2); border: 1px dashed var(--line);
  border-radius: var(--r2);
}
.empty-icon { font-size: 52px; margin-bottom: 16px; }
.empty-title { font-family: var(--font-display); font-size: 22px; font-weight: 700; margin-bottom: 8px; }
.empty-desc { color: var(--fog); font-size: 15px; margin-bottom: 28px; }

@media (max-width: 600px) {
  .nav { padding: 0 20px; }
  .hero h1 { letter-spacing: -2px; }
  .mode-cards { grid-template-columns: 1fr; }
  .stat-row { grid-template-columns: 1fr 1fr; }
  .result-card { padding: 36px 24px; }
  .question-box { padding: 24px 20px; }
}
"""

# ─────────────────────────────────────────────
#  BASE LAYOUT
# ─────────────────────────────────────────────

def base_layout(content, title="QuizAI"):
    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{title} — QuizAI</title>
<style>{GLOBAL_CSS}</style>
</head>
<body>
<nav class="nav">
  <a href="/" class="nav-logo">✦ <span>Quiz</span>AI</a>
  <div class="nav-links">
    <a href="/" class="btn btn-ghost">Bosh sahifa</a>
    <a href="/admin" class="btn btn-gold">⚙ Admin</a>
  </div>
</nav>
{content}
</body>
</html>"""

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, description, questions FROM test_bases ORDER BY id DESC").fetchall()
    bases = []
    for r in rows:
        qs = json.loads(r["questions"])
        bases.append({"id": r["id"], "name": r["name"],
                       "description": r["description"], "q_count": len(qs)})

    if bases:
        cards_html = '<div class="base-grid">'
        for b in bases:
            desc = b["description"] or "Tavsif mavjud emas"
            cards_html += f"""
            <div class="base-card">
              <div><span class="badge badge-gold">✦ {b['q_count']} savol</span></div>
              <div class="base-card-title">{b['name']}</div>
              <div class="base-card-desc">{desc}</div>
              <a href="/quiz/setup/{b['id']}" class="btn btn-jade" style="justify-content:center">
                Testni boshlash →
              </a>
            </div>"""
        cards_html += '</div>'
    else:
        cards_html = """
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <div class="empty-title">Hali test bazasi yo'q</div>
          <div class="empty-desc">Admin panelidan matn yuklab, birinchi test bazangizni yarating.</div>
          <a href="/admin" class="btn btn-gold btn-lg">Admin panelga o'tish →</a>
        </div>"""

    content = f"""
    <section class="hero">
      <div class="hero-tag">✦ AI bilan test tayyorlash platformasi</div>
      <h1>Bilimni<br/><em>sinab</em> ko'r</h1>
      <p>Matn yuklab, sun'iy intellekt yordamida bir zumda test yarating va yechib ko'ring.</p>
      <div class="hero-actions">
        <a href="#bazalar" class="btn btn-gold btn-lg">Test bazalarini ko'rish</a>
        <a href="/admin" class="btn btn-outline btn-lg">Admin panel</a>
      </div>
    </section>
    <div class="container" id="bazalar">
      <div class="section-label">Mavjud bazalar</div>
      <div class="section-title">Test Bazalari</div>
      {cards_html}
    </div>"""
    return base_layout(content, "Bosh sahifa")


# ── ADMIN LOGIN ──
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_panel"))
    error = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        error = '<div class="alert alert-err">❌ Parol noto\'g\'ri!</div>'

    content = f"""
    <div class="container-sm">
      <div class="card mt-32">
        <div class="mb-24">
          <div class="section-label">Xavfsizlik</div>
          <h2 style="font-family:var(--font-display);font-size:28px;font-weight:900;letter-spacing:-1px">Admin Panel</h2>
          <p class="text-fog mt-8" style="font-size:15px">Kirish uchun admin parolini kiriting.</p>
        </div>
        {error}
        <form method="POST">
          <div class="form-group">
            <label class="form-label">Parol</label>
            <input type="password" name="password" class="form-input" placeholder="••••••••••" autofocus/>
          </div>
          <button type="submit" class="btn btn-gold" style="width:100%;justify-content:center;padding:14px">
            Kirish →
          </button>
        </form>
      </div>
    </div>"""
    return base_layout(content, "Admin Kirish")


# ── ADMIN PANEL ──
@app.route("/admin/panel", methods=["GET"])
def admin_panel():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    msg = request.args.get("msg", "")
    msg_type = request.args.get("type", "ok")
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, description, questions FROM test_bases ORDER BY id DESC").fetchall()
    bases = [{"id": r["id"], "name": r["name"], "description": r["description"],
               "q_count": len(json.loads(r["questions"]))} for r in rows]

    alert_html = f'<div class="alert alert-{msg_type}">{msg}</div>' if msg else ""

    bases_html = ""
    if bases:
        bases_html = '<div style="display:flex;flex-direction:column;gap:12px">'
        for b in bases:
            desc = b['description'] or ''
            bases_html += f"""
            <div class="admin-base-row">
              <div class="admin-base-info">
                <div class="admin-base-name">{b['name']}</div>
                <div class="admin-base-meta">{desc}{'  ·  ' if desc else ''}<span class="badge badge-gold">{b['q_count']} savol</span></div>
              </div>
              <div class="admin-base-actions">
                <a href="/quiz/setup/{b['id']}" class="btn btn-jade" style="padding:8px 18px;font-size:13px">Test →</a>
                <form method="POST" action="/admin/delete/{b['id']}" style="margin:0" onsubmit="return confirm('O\\'chirilsinmi?')">
                  <button type="submit" class="btn btn-danger" style="padding:8px 14px;font-size:13px">🗑</button>
                </form>
              </div>
            </div>"""
        bases_html += '</div>'
    else:
        bases_html = '<div class="text-fog" style="text-align:center;padding:32px;background:var(--ink3);border-radius:var(--r2);font-size:15px">Hali baza qo\'shilmagan</div>'

    content = f"""
    <div class="container-md">
      <div class="flex-between mt-16 mb-24">
        <div>
          <div class="section-label">Boshqaruv markazi</div>
          <h1 style="font-family:var(--font-display);font-size:32px;font-weight:900;letter-spacing:-1px">Admin Panel</h1>
        </div>
        <a href="/admin/logout" class="btn btn-ghost">Chiqish</a>
      </div>

      <div class="card mb-32">
        <div class="mb-24">
          <div class="section-label">Yangi baza</div>
          <h3 style="font-family:var(--font-display);font-size:22px;font-weight:700">Test Bazasi Qo'shish</h3>
        </div>
        {alert_html}
        <form method="POST" action="/admin/upload" id="uploadForm">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <div class="form-group" style="margin-bottom:0">
              <label class="form-label">Baza nomi *</label>
              <input type="text" name="name" class="form-input" placeholder="Biologiya 11-sinf" required/>
            </div>
            <div class="form-group" style="margin-bottom:0">
              <label class="form-label">Tavsif (ixtiyoriy)</label>
              <input type="text" name="description" class="form-input" placeholder="Qisqacha tavsif..."/>
            </div>
          </div>
          <div class="form-group mt-16">
            <label class="form-label">Matn * — kitob, darslik yoki istalgan matn</label>
            <textarea name="text" class="form-textarea" placeholder="Shu yerga matnni joylashtiring. AI avtomatik ravishda savollar va variantlar yaratadi..." required></textarea>
          </div>
          <div class="flex-between" style="align-items:flex-end">
            <div class="form-group" style="margin-bottom:0">
              <label class="form-label">Savol soni</label>
              <select name="num_questions" class="form-select" style="width:160px">
                <option value="20">20 ta savol</option>
                <option value="25">25 ta savol</option>
                <option value="30" selected>30 ta savol</option>
                <option value="35">35 ta savol</option>
                <option value="40">40 ta savol</option>
              </select>
            </div>
            <button type="submit" class="btn btn-gold" onclick="showLoader()" style="padding:13px 28px">
              ✦ AI bilan yaratish
            </button>
          </div>
        </form>
      </div>

      <div class="section-label mb-16">Bazalar ro'yxati</div>
      {bases_html}
    </div>

    <div class="loading-overlay" id="loader">
      <div class="loader-ring"></div>
      <div class="loader-text">AI ishlamoqda...</div>
      <div class="loader-sub">Matndan savollar va variantlar yaratilmoqda</div>
    </div>
    <script>
    function showLoader(){{
      document.getElementById('loader').classList.add('active');
    }}
    </script>"""
    return base_layout(content, "Admin Panel")


# ── ADMIN UPLOAD ──
@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    text = request.form.get("text", "").strip()
    num_questions = int(request.form.get("num_questions", 30))
    if not name or not text:
        return redirect(url_for("admin_panel") + "?msg=Nom+va+matn+majburiy&type=alert-err")
    if not GROQ_API_KEY:
        return redirect(url_for("admin_panel") + "?msg=GROQ_API_KEY+topilmadi&type=alert-err")
    try:
        questions = extract_questions_with_groq(text, num_questions)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO test_bases (name, description, questions) VALUES (?,?,?)",
                (name, description, json.dumps(questions, ensure_ascii=False))
            )
            conn.commit()
        return redirect(url_for("admin_panel") + f"?msg=✦+{len(questions)}+ta+savol+muvaffaqiyatli+yaratildi&type=alert-ok")
    except Exception as e:
        err = str(e)[:100]
        return redirect(url_for("admin_panel") + f"?msg=Xato:+{err}&type=alert-err")


# ── ADMIN DELETE ──
@app.route("/admin/delete/<int:base_id>", methods=["POST"])
def admin_delete(base_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    with get_db() as conn:
        conn.execute("DELETE FROM test_bases WHERE id=?", (base_id,))
        conn.commit()
    return redirect(url_for("admin_panel") + "?msg=Baza+o'chirildi&type=alert-ok")


# ── ADMIN LOGOUT ──
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


# ── QUIZ SETUP ──
@app.route("/quiz/setup/<int:base_id>", methods=["GET", "POST"])
def quiz_setup(base_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM test_bases WHERE id=?", (base_id,)).fetchone()
    if not row:
        return redirect(url_for("index"))
    questions = json.loads(row["questions"])
    q_count = len(questions)

    if request.method == "POST":
        num = min(int(request.form.get("num", 20)), q_count)
        mode = request.form.get("mode", "random")
        if mode == "random":
            selected = random.sample(questions, num)
            random.shuffle(selected)
            selected = shuffle_options(selected)
            session["quiz_questions"] = selected
            session["quiz_answer_key"] = get_answer_key(selected)
            session["quiz_base_id"] = base_id
            session["quiz_base_name"] = row["name"]
            session["quiz_block_info"] = None
            session["quiz_block_size"] = 0
            return redirect(url_for("quiz_play"))
        else:
            all_q = list(questions)
            random.shuffle(all_q)
            blocks = [shuffle_options(all_q[i:i+num]) for i in range(0, len(all_q), num)]
            session["quiz_blocks"] = blocks
            session["quiz_blocks_keys"] = [get_answer_key(b) for b in blocks]
            session["quiz_base_id"] = base_id
            session["quiz_base_name"] = row["name"]
            session["quiz_block_size"] = num
            return redirect(url_for("quiz_block", base_id=base_id, block_num=1, block_size=num))

    # Pill options
    pills_html = '<div class="num-pills">'
    for n in [20, 25, 30, 35, 40]:
        if n <= q_count:
            checked = "checked" if n == 20 else ""
            pills_html += f"""
            <label class="num-pill">
              <input type="radio" name="num" value="{n}" {checked}/>
              <div class="num-pill-label">{n}</div>
            </label>"""
    pills_html += '</div>'

    content = f"""
    <div class="container-md">
      <div class="mt-16 mb-24">
        <a href="/" class="btn btn-ghost">← Orqaga</a>
      </div>
      <div class="card mb-24">
        <div class="section-label">Test sozlamalari</div>
        <h2 style="font-family:var(--font-display);font-size:26px;font-weight:900;letter-spacing:-1px;margin-bottom:8px">{row['name']}</h2>
        <span class="badge badge-gold">✦ {q_count} ta savol mavjud</span>
      </div>
      <form method="POST">
        <div class="card mb-20">
          <div class="form-label" style="font-size:13px;margin-bottom:20px">📊 Nechta savol yechmoqchisiz?</div>
          {pills_html}
        </div>
        <div class="card mb-24">
          <div class="form-label" style="font-size:13px;margin-bottom:20px">🎮 Rejim tanlang</div>
          <div class="mode-cards" id="modeCards">
            <div class="mode-card selected" onclick="selectMode('random', this)">
              <input type="radio" name="mode" value="random" checked/>
              <div class="mode-card-icon">🎲</div>
              <div class="mode-card-title">Random tanlov</div>
              <div class="mode-card-desc">Bazadagi savollardan tasodifiy tanlangan miqdorini yechish</div>
            </div>
            <div class="mode-card" onclick="selectMode('sequential', this)">
              <input type="radio" name="mode" value="sequential"/>
              <div class="mode-card-icon">📖</div>
              <div class="mode-card-title">Ketma-ket bloklar</div>
              <div class="mode-card-desc">Barcha savollarni tanlangan miqdordan bloklab, ketma-ket yechish</div>
            </div>
          </div>
        </div>
        <button type="submit" class="btn btn-gold btn-lg" style="width:100%;justify-content:center">
          ✦ Testni Boshlash
        </button>
      </form>
    </div>
    <script>
    function selectMode(val, el){{
      document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
      el.classList.add('selected');
      el.querySelector('input[type=radio]').checked = true;
    }}
    </script>"""
    return base_layout(content, row["name"])


# ── QUIZ BLOCK ──
@app.route("/quiz/block/<int:base_id>/<int:block_num>/<int:block_size>")
def quiz_block(base_id, block_num, block_size):
    blocks = session.get("quiz_blocks")
    keys = session.get("quiz_blocks_keys")
    if not blocks:
        return redirect(url_for("quiz_setup", base_id=base_id))
    idx = block_num - 1
    if idx < 0 or idx >= len(blocks):
        return redirect(url_for("index"))
    session["quiz_questions"] = blocks[idx]
    session["quiz_answer_key"] = keys[idx]
    session["quiz_base_name"] = session.get("quiz_base_name", "Test")
    session["quiz_block_info"] = [block_num, len(blocks)]
    session["quiz_base_id"] = base_id
    return redirect(url_for("quiz_play"))


# ── QUIZ PLAY ──
@app.route("/quiz/play")
def quiz_play():
    questions = session.get("quiz_questions")
    if not questions:
        return redirect(url_for("index"))
    base_name = session.get("quiz_base_name", "Test")
    block_info = session.get("quiz_block_info")
    base_id = session.get("quiz_base_id", 0)
    block_size = session.get("quiz_block_size", 0)
    safe_questions = prepare_quiz_questions(questions)

    block_meta = ""
    if block_info:
        block_meta = f"Blok {block_info[0]}/{block_info[1]}"

    next_block_btn = ""
    if block_info and block_info[0] < block_info[1]:
        next_block_btn = f'<a href="/quiz/block/{base_id}/{block_info[0]+1}/{block_size}" class="btn btn-jade" id="nextBlockBtn" style="display:none">Keyingi blok →</a>'

    content = f"""
    <div class="quiz-shell">
      <div class="quiz-top">
        <div>
          <div class="quiz-top-title">{base_name}</div>
          <div class="quiz-top-meta">{block_meta}</div>
        </div>
        <div class="quiz-timer" id="timer">00:00</div>
        <div class="quiz-count">
          <div class="quiz-count-num" id="qCountDisplay">1 / {len(questions)}</div>
          <div class="quiz-count-lbl">savol</div>
        </div>
      </div>

      <div class="progress-track">
        <div class="progress-fill" id="progressFill" style="width:{100/len(questions):.1f}%"></div>
      </div>

      <div id="quizArea">
        <div class="question-box" id="questionBox">
          <div class="q-num" id="qNum">SAVOL 1</div>
          <div class="q-text" id="qText"></div>
          <div class="options-list" id="optionsList"></div>
        </div>
        <div class="quiz-nav">
          <button class="btn btn-ghost" id="prevBtn" onclick="goTo(current-1)">← Oldingi</button>
          <div style="font-size:13px;color:var(--fog)" id="answeredCount">0 / {len(questions)} javoblandi</div>
          <button class="btn btn-outline" id="nextBtn" onclick="goTo(current+1)">Keyingi →</button>
          <button class="btn btn-gold" id="finishBtn" onclick="submitQuiz()" style="display:none">✦ Yakunlash</button>
        </div>
      </div>

      <div id="resultArea" style="display:none">
        <div class="result-card">
          <div class="result-ring" id="resultRing" style="--pct:0%">
            <div class="result-ring-inner">
              <div class="result-pct" id="resultPct">0%</div>
              <div class="result-pct-lbl">natija</div>
            </div>
          </div>
          <div class="result-score-text" id="resultScore"></div>
          <div class="result-label" id="resultLabel"></div>
          <div class="stat-row" id="statRow"></div>
          <div class="result-actions">
            <button class="btn btn-outline" onclick="toggleReview()">📋 Ko'rib chiqish</button>
            {next_block_btn}
            <a href="/" class="btn btn-ghost">🏠 Bosh sahifa</a>
          </div>
        </div>
        <div id="reviewList" class="review-list" style="display:none"></div>
      </div>
    </div>

    <script>
    const questions = {json.dumps(safe_questions, ensure_ascii=False)};
    const totalCount = questions.length;
    let answers = new Array(totalCount).fill(null);
    let current = 0;
    let quizDone = false;
    let correctAnswers = null; // backend'dan keladi
    let startTime = Date.now();

    function render() {{
      const q = questions[current];
      document.getElementById('qNum').textContent = 'SAVOL ' + (current+1);
      document.getElementById('qText').textContent = q.question;
      document.getElementById('qCountDisplay').textContent = (current+1) + ' / ' + totalCount;
      const pct = ((current+1) / totalCount * 100).toFixed(1);
      document.getElementById('progressFill').style.width = pct + '%';

      const list = document.getElementById('optionsList');
      list.innerHTML = '';
      const labels = ['A','B','C','D'];
      q.options.forEach((opt, i) => {{
        const btn = document.createElement('button');
        btn.className = 'option-item' + (answers[current] === i ? ' picked' : '');
        btn.innerHTML = `<span class="option-circle">${{labels[i]}}</span><span class="option-text">${{opt}}</span>`;
        btn.onclick = () => {{ answers[current] = i; render(); }};
        list.appendChild(btn);
      }});

      const answered = answers.filter(a => a !== null).length;
      document.getElementById('answeredCount').textContent = answered + ' / ' + totalCount + ' javoblandi';
      document.getElementById('prevBtn').style.display = current === 0 ? 'none' : '';
      const isLast = current === totalCount - 1;
      document.getElementById('nextBtn').style.display = isLast ? 'none' : '';
      document.getElementById('finishBtn').style.display = isLast ? '' : 'none';
    }}

    function goTo(idx) {{
      if (idx < 0 || idx >= totalCount) return;
      current = idx; render();
    }}

    async function submitQuiz() {{
      const unanswered = answers.filter(a => a === null).length;
      if (unanswered > 0 && !confirm(unanswered + ' ta savol javobsiz. Baribir yakunlaysizmi?')) return;
      quizDone = true;
      clearInterval(timerInterval);

      // Backend ga yuborish
      const resp = await fetch('/quiz/check', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ answers: answers }})
      }});
      const data = await resp.json();
      if (!data.ok) {{ alert('Xato yuz berdi.'); return; }}
      correctAnswers = data.correct_list;
      showResult(data.score, data.total, data.correct_list);
    }}

    function showResult(score, total, correctList) {{
      document.getElementById('quizArea').style.display = 'none';
      const area = document.getElementById('resultArea');
      area.style.display = 'block';

      const pct = Math.round(score / total * 100);
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const m = Math.floor(elapsed/60), s = elapsed%60;
      const timeStr = String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');

      document.getElementById('resultPct').textContent = pct + '%';
      document.getElementById('resultRing').style.setProperty('--pct', pct + '%');
      document.getElementById('resultScore').textContent = score + ' / ' + total;

      const label = pct >= 90 ? '🏆 Ajoyib! Zo\'r natija!'
        : pct >= 70 ? '👍 Yaxshi natija!'
        : pct >= 50 ? '📚 O\'rta daraja'
        : '💪 Ko\'proq mashq qiling!';
      document.getElementById('resultLabel').textContent = label;

      const wrong = total - score;
      document.getElementById('statRow').innerHTML = `
        <div class="stat-box">
          <div class="stat-val text-jade">${{score}}</div>
          <div class="stat-lbl">To'g'ri</div>
        </div>
        <div class="stat-box">
          <div class="stat-val text-rose">${{wrong}}</div>
          <div class="stat-lbl">Xato</div>
        </div>
        <div class="stat-box">
          <div class="stat-val text-gold">${{timeStr}}</div>
          <div class="stat-lbl">Vaqt</div>
        </div>`;

      const nbb = document.getElementById('nextBlockBtn');
      if (nbb) nbb.style.display = '';
    }}

    function toggleReview() {{
      const rl = document.getElementById('reviewList');
      if (rl.style.display === 'none') {{
        buildReview();
        rl.style.display = 'flex';
      }} else {{
        rl.style.display = 'none';
      }}
    }}

    function buildReview() {{
      const rl = document.getElementById('reviewList');
      rl.innerHTML = '';
      const labels = ['A','B','C','D'];
      questions.forEach((q, i) => {{
        const userAns = answers[i];
        const corrAns = correctAnswers[i];
        const isOk = userAns === corrAns;
        const div = document.createElement('div');
        div.className = 'review-card';
        let optsHtml = '';
        q.options.forEach((opt, j) => {{
          let cls = '';
          if (j === corrAns) cls = 'correct-opt';
          else if (j === userAns && !isOk) cls = 'wrong-opt';
          optsHtml += `<div class="review-opt ${{cls}}">${{labels[j]}}) ${{opt}}</div>`;
        }});
        div.innerHTML = `
          <div class="review-header">
            <div class="review-status ${{isOk ? 'ok' : 'fail'}}">${{isOk ? '✓' : '✕'}}</div>
            <div class="review-q">${{i+1}}. ${{q.question}}</div>
          </div>
          <div class="review-opts">${{optsHtml}}</div>`;
        rl.appendChild(div);
      }});
    }}

    // Timer
    const timerInterval = setInterval(() => {{
      if (quizDone) return;
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const m = Math.floor(elapsed/60), s = elapsed%60;
      document.getElementById('timer').textContent =
        String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
    }}, 1000);

    render();
    </script>"""
    return base_layout(content, base_name)


# ── QUIZ CHECK (Backend javob tekshiruvi) ──
@app.route("/quiz/check", methods=["POST"])
def quiz_check():
    answer_key = session.get("quiz_answer_key")
    if not answer_key:
        return jsonify({"ok": False, "error": "Sessiya topilmadi"})
    data = request.get_json()
    user_answers = data.get("answers", [])
    if len(user_answers) != len(answer_key):
        return jsonify({"ok": False, "error": "Javoblar soni mos emas"})
    score = sum(1 for i, a in enumerate(user_answers) if a == answer_key[i])
    return jsonify({
        "ok": True,
        "score": score,
        "total": len(answer_key),
        "correct_list": answer_key
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
