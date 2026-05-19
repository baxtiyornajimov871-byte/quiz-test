"""
AI-Powered Uzbek Quiz Platform
One-file Flask + SQLite + GROQ application
"""

import os
import json
import random
import sqlite3
import hashlib
import time
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template_string, request, redirect,
    url_for, session, jsonify, g
)
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DATABASE = "quiz_platform.db"
ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    hashlib.sha256("admin123".encode()).hexdigest()
)

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS quiz_bases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                options TEXT NOT NULL,
                correct_index INTEGER NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY (base_id) REFERENCES quiz_bases(id)
            );
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                questions_json TEXT NOT NULL,
                answers_json TEXT DEFAULT '{}',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP,
                score INTEGER,
                total INTEGER
            );
        """)
        db.commit()

# ─────────────────────────────────────────────
# GROQ API
# ─────────────────────────────────────────────

def groq_chat(messages, temperature=0.2, max_tokens=4096):
    if not GROQ_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-70b-8192",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=payload, timeout=60
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"GROQ Error: {e}")
        return None

def parse_quiz_with_ai(quiz_text, answer_instructions):
    system_prompt = """You are an expert quiz parser. Your job is to parse quiz questions and map answers.
Return ONLY valid JSON. No markdown, no explanation, no code blocks.

Output format:
{
  "questions": [
    {
      "question": "Clean question text without number",
      "options": ["Option text without A)", "Option text without B)", "Option text without C)", "Option text without D)"],
      "correct_index": 0
    }
  ],
  "errors": []
}

Rules:
- Remove question numbers (1., 2., etc.)
- Remove option labels (A), B), etc.) from option text
- correct_index is 0-based (A=0, B=1, C=2, D=3, E=4)
- Parse answer instructions intelligently:
  * "A" or "all A" or "hammasi A" = all questions get answer A (index 0)
  * "ABCDABCD..." = sequence of letters mapped to questions
  * "A B C D" = space-separated sequence
  * "1-20 A, 21-40 B" = range-based
  * "1A 2B 3C" = numbered
- If options count varies per question, handle it
- errors: list any issues found"""

    user_msg = f"""Parse these quiz questions and answers:

QUESTIONS:
{quiz_text}

ANSWER INSTRUCTIONS:
{answer_instructions}

Return valid JSON only."""

    response = groq_chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg}
    ])

    if not response:
        return None, "GROQ API javob bermadi."

    try:
        # Try to extract JSON from response
        text = response.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        data = json.loads(text)
        return data, None
    except json.JSONDecodeError as e:
        return None, f"AI javobi JSON formatida emas: {e}"

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
# TEMPLATES (all inline)
# ─────────────────────────────────────────────

BASE_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #080c14;
  --bg2: #0d1422;
  --bg3: #111827;
  --card: rgba(255,255,255,0.04);
  --card-border: rgba(255,255,255,0.08);
  --accent: #6366f1;
  --accent2: #8b5cf6;
  --accent3: #06b6d4;
  --gold: #f59e0b;
  --green: #10b981;
  --red: #ef4444;
  --text: #f1f5f9;
  --text2: #94a3b8;
  --text3: #475569;
  --glow: 0 0 40px rgba(99,102,241,0.15);
  --radius: 16px;
  --radius-sm: 10px;
  --shadow: 0 8px 32px rgba(0,0,0,0.4);
}

html { scroll-behavior: smooth; }

body {
  font-family: 'DM Sans', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
}

body::before {
  content: '';
  position: fixed; inset: 0; z-index: 0;
  background:
    radial-gradient(ellipse 80% 50% at 20% 10%, rgba(99,102,241,0.12) 0%, transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(139,92,246,0.08) 0%, transparent 60%),
    radial-gradient(ellipse 40% 60% at 60% 30%, rgba(6,182,212,0.05) 0%, transparent 50%);
  pointer-events: none;
}

.wrap { position: relative; z-index: 1; max-width: 1100px; margin: 0 auto; padding: 0 24px; }

/* NAV */
.nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 24px;
  background: rgba(8,12,20,0.8);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--card-border);
  position: sticky; top: 0; z-index: 100;
}
.nav-brand {
  font-family: 'Syne', sans-serif;
  font-size: 1.3rem; font-weight: 800;
  background: linear-gradient(135deg, var(--accent), var(--accent3));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.02em;
  text-decoration: none;
}
.nav-links { display: flex; gap: 8px; }
.nav-links a {
  color: var(--text2); text-decoration: none;
  padding: 8px 16px; border-radius: 8px;
  font-size: 0.875rem; font-weight: 500;
  transition: all 0.2s;
}
.nav-links a:hover { color: var(--text); background: var(--card); }

/* BUTTONS */
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 24px; border-radius: var(--radius-sm);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.9rem; font-weight: 600;
  cursor: pointer; border: none;
  transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
  text-decoration: none; white-space: nowrap;
  letter-spacing: 0.01em;
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: white;
  box-shadow: 0 4px 20px rgba(99,102,241,0.35);
}
.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(99,102,241,0.5);
}
.btn-secondary {
  background: var(--card);
  border: 1px solid var(--card-border);
  color: var(--text);
}
.btn-secondary:hover { background: rgba(255,255,255,0.08); transform: translateY(-1px); }
.btn-success {
  background: linear-gradient(135deg, #059669, #10b981);
  color: white;
  box-shadow: 0 4px 20px rgba(16,185,129,0.3);
}
.btn-success:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(16,185,129,0.45); }
.btn-danger {
  background: linear-gradient(135deg, #dc2626, #ef4444);
  color: white;
}
.btn-danger:hover { transform: translateY(-2px); }
.btn-lg { padding: 16px 32px; font-size: 1rem; border-radius: var(--radius); }
.btn-sm { padding: 8px 16px; font-size: 0.8rem; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; }

/* CARDS */
.card {
  background: var(--card);
  border: 1px solid var(--card-border);
  border-radius: var(--radius);
  padding: 28px;
  backdrop-filter: blur(10px);
  box-shadow: var(--shadow);
  transition: all 0.3s;
}
.card:hover { border-color: rgba(99,102,241,0.25); box-shadow: var(--glow); }

/* FORMS */
.form-group { margin-bottom: 20px; }
.form-label {
  display: block; margin-bottom: 8px;
  font-size: 0.875rem; font-weight: 500; color: var(--text2);
  letter-spacing: 0.02em;
}
.form-control {
  width: 100%; padding: 12px 16px;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.9rem;
  transition: all 0.2s;
  outline: none;
}
.form-control:focus {
  border-color: var(--accent);
  background: rgba(99,102,241,0.08);
  box-shadow: 0 0 0 3px rgba(99,102,241,0.15);
}
textarea.form-control { resize: vertical; min-height: 120px; }

/* ALERTS */
.alert {
  padding: 14px 18px; border-radius: var(--radius-sm);
  font-size: 0.875rem; margin-bottom: 20px;
}
.alert-error { background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3); color: #fca5a5; }
.alert-success { background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); color: #6ee7b7; }
.alert-info { background: rgba(99,102,241,0.12); border: 1px solid rgba(99,102,241,0.3); color: #a5b4fc; }

/* BADGE */
.badge {
  display: inline-flex; align-items: center;
  padding: 4px 10px; border-radius: 20px;
  font-size: 0.75rem; font-weight: 600;
}
.badge-accent { background: rgba(99,102,241,0.2); color: #a5b4fc; border: 1px solid rgba(99,102,241,0.3); }
.badge-green { background: rgba(16,185,129,0.2); color: #6ee7b7; border: 1px solid rgba(16,185,129,0.3); }

/* HEADINGS */
h1 { font-family: 'Syne', sans-serif; font-size: clamp(2rem, 5vw, 3.5rem); font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; }
h2 { font-family: 'Syne', sans-serif; font-size: clamp(1.5rem, 3vw, 2rem); font-weight: 700; letter-spacing: -0.02em; }
h3 { font-family: 'Syne', sans-serif; font-size: 1.2rem; font-weight: 700; }

/* LOADING */
.spinner {
  width: 40px; height: 40px;
  border: 3px solid rgba(99,102,241,0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* PROGRESS BAR */
.progress-bar-wrap {
  background: rgba(255,255,255,0.06);
  border-radius: 100px; height: 6px; overflow: hidden;
}
.progress-bar-fill {
  height: 100%; border-radius: 100px;
  background: linear-gradient(90deg, var(--accent), var(--accent3));
  transition: width 0.5s cubic-bezier(0.4,0,0.2,1);
  box-shadow: 0 0 10px rgba(99,102,241,0.5);
}

/* ANIMATIONS */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.92); }
  to { opacity: 1; transform: scale(1); }
}
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 20px rgba(99,102,241,0.3); }
  50% { box-shadow: 0 0 40px rgba(99,102,241,0.6); }
}

.animate-up { animation: fadeUp 0.5s ease both; }
.animate-in { animation: scaleIn 0.4s ease both; }

/* SCROLLBAR */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.4); border-radius: 3px; }

/* RESPONSIVE */
@media (max-width: 768px) {
  .nav { padding: 14px 16px; }
  .wrap { padding: 0 16px; }
  .card { padding: 20px; }
}
"""

# ─────────────────────────────────────────────
# HOME PAGE
# ─────────────────────────────────────────────

HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QuizAI — AI Powered Quiz Platformasi</title>
  <style>{{ base_style }}</style>
  <style>
    .hero {
      min-height: 80vh;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      text-align: center; padding: 60px 24px;
      gap: 32px;
    }
    .hero-eyebrow {
      display: inline-flex; align-items: center; gap: 8px;
      background: rgba(99,102,241,0.1);
      border: 1px solid rgba(99,102,241,0.25);
      border-radius: 100px;
      padding: 6px 16px;
      font-size: 0.8rem; font-weight: 600; color: #a5b4fc;
      letter-spacing: 0.08em; text-transform: uppercase;
      animation: fadeIn 0.6s ease both;
    }
    .hero h1 {
      animation: fadeUp 0.7s ease both 0.1s;
      max-width: 700px;
    }
    .hero-gradient {
      background: linear-gradient(135deg, #fff 40%, var(--accent3));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .hero-sub {
      font-size: 1.1rem; color: var(--text2); max-width: 500px;
      line-height: 1.7;
      animation: fadeUp 0.7s ease both 0.2s;
    }
    .hero-cta {
      display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;
      animation: fadeUp 0.7s ease both 0.3s;
    }
    .bases-section { padding: 60px 0; }
    .section-title { margin-bottom: 36px; }
    .section-title h2 { margin-bottom: 8px; }
    .section-title p { color: var(--text2); }
    .bases-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 20px;
    }
    .base-card {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 28px;
      backdrop-filter: blur(10px);
      transition: all 0.3s;
      animation: fadeUp 0.5s ease both;
      text-decoration: none; color: inherit;
      display: block;
    }
    .base-card:hover {
      border-color: rgba(99,102,241,0.4);
      transform: translateY(-4px);
      box-shadow: 0 12px 40px rgba(0,0,0,0.3), 0 0 0 1px rgba(99,102,241,0.2);
    }
    .base-card-icon {
      width: 48px; height: 48px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-radius: 12px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.4rem; margin-bottom: 16px;
    }
    .base-card h3 { margin-bottom: 8px; font-size: 1.1rem; }
    .base-card p { color: var(--text2); font-size: 0.875rem; line-height: 1.6; margin-bottom: 16px; }
    .base-card-meta {
      display: flex; align-items: center; gap: 8px;
      font-size: 0.8rem; color: var(--text3);
    }
    .empty-state {
      text-align: center; padding: 80px 24px;
      color: var(--text2);
    }
    .empty-state-icon { font-size: 4rem; margin-bottom: 16px; opacity: 0.5; }
    .features {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 20px; padding: 60px 0;
    }
    .feature-card {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 24px;
      transition: all 0.3s;
    }
    .feature-card:hover { border-color: rgba(99,102,241,0.3); transform: translateY(-2px); }
    .feature-icon {
      width: 40px; height: 40px;
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.2rem; margin-bottom: 14px;
    }
    .fi-1 { background: rgba(99,102,241,0.2); }
    .fi-2 { background: rgba(6,182,212,0.2); }
    .fi-3 { background: rgba(245,158,11,0.2); }
    .fi-4 { background: rgba(16,185,129,0.2); }
  </style>
</head>
<body>
<nav class="nav">
  <a href="/" class="nav-brand">⚡ QuizAI</a>
  <div class="nav-links">
    <a href="/">Bosh sahifa</a>
    <a href="/admin">Admin</a>
  </div>
</nav>

<div class="wrap">
  <section class="hero">
    <div class="hero-eyebrow">✨ AI-Powered Platform</div>
    <h1><span class="hero-gradient">Aqlli Quiz</span><br>Platformasi</h1>
    <p class="hero-sub">AI yordamida savollarni tahlil qiladigan, o'zbek tilida ishlayدigan zamonaviy test platformasi.</p>
    <div class="hero-cta">
      <a href="#bases" class="btn btn-primary btn-lg">🚀 Testlarni ko'rish</a>
      <a href="/admin" class="btn btn-secondary btn-lg">⚙️ Admin panel</a>
    </div>
  </section>

  <div class="features">
    <div class="feature-card animate-up">
      <div class="feature-icon fi-1">🤖</div>
      <h3>AI Parsing</h3>
      <p style="color:var(--text2);font-size:0.875rem;line-height:1.6;margin-top:8px;">Savollarni va javoblarni avtomatik tahlil qiladi.</p>
    </div>
    <div class="feature-card animate-up" style="animation-delay:0.1s">
      <div class="feature-icon fi-2">🔀</div>
      <h3>Random Mode</h3>
      <p style="color:var(--text2);font-size:0.875rem;line-height:1.6;margin-top:8px;">Har safar turli savollar bilan aralash test.</p>
    </div>
    <div class="feature-card animate-up" style="animation-delay:0.2s">
      <div class="feature-icon fi-3">📚</div>
      <h3>Full Mode</h3>
      <p style="color:var(--text2);font-size:0.875rem;line-height:1.6;margin-top:8px;">Barcha savollarni bloklarga bo'lib ishlash.</p>
    </div>
    <div class="feature-card animate-up" style="animation-delay:0.3s">
      <div class="feature-icon fi-4">📊</div>
      <h3>Natijalar</h3>
      <p style="color:var(--text2);font-size:0.875rem;line-height:1.6;margin-top:8px;">Batafsil tahlil va xatolarni ko'rish imkoniyati.</p>
    </div>
  </div>

  <section class="bases-section" id="bases">
    <div class="section-title">
      <h2>Test bazalari</h2>
      <p>Mavjud testlardan birini tanlang va boshlang</p>
    </div>
    {% if bases %}
    <div class="bases-grid">
      {% for base in bases %}
      <a href="/quiz/setup/{{ base.id }}" class="base-card" style="animation-delay:{{ loop.index0 * 0.08 }}s">
        <div class="base-card-icon">📝</div>
        <h3>{{ base.name }}</h3>
        <p>{{ base.description or 'Tavsif yo\'q' }}</p>
        <div class="base-card-meta">
          <span class="badge badge-accent">{{ base.q_count }} savol</span>
          <span>•</span>
          <span>{{ base.created_at[:10] }}</span>
        </div>
      </a>
      {% endfor %}
    </div>
    {% else %}
    <div class="empty-state">
      <div class="empty-state-icon">📭</div>
      <h3 style="margin-bottom:8px;">Test bazalari yo'q</h3>
      <p>Admin panel orqali yangi test bazasi qo'shing.</p>
      <a href="/admin" class="btn btn-primary" style="margin-top:20px;">Admin panelga o'tish</a>
    </div>
    {% endif %}
  </section>
</div>
</body>
</html>
"""

# ─────────────────────────────────────────────
# ADMIN TEMPLATES
# ─────────────────────────────────────────────

ADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Admin Login — QuizAI</title>
  <style>{{ base_style }}</style>
  <style>
    .login-wrap {
      min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      padding: 24px;
    }
    .login-box {
      width: 100%; max-width: 400px;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 40px;
      animation: scaleIn 0.4s ease;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    }
    .login-icon {
      width: 64px; height: 64px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-radius: 16px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.8rem; margin: 0 auto 24px;
    }
    .login-box h2 { text-align: center; margin-bottom: 6px; }
    .login-sub { text-align: center; color: var(--text2); font-size: 0.875rem; margin-bottom: 32px; }
  </style>
</head>
<body>
<div class="login-wrap">
  <div class="login-box">
    <div class="login-icon">🔐</div>
    <h2>Admin kirish</h2>
    <p class="login-sub">Davom etish uchun parolni kiriting</p>
    {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}
    <form method="POST">
      <div class="form-group">
        <label class="form-label">Parol</label>
        <input type="password" name="password" class="form-control" placeholder="••••••••" autofocus required>
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;">Kirish</button>
    </form>
    <div style="text-align:center;margin-top:20px;">
      <a href="/" style="color:var(--text3);font-size:0.8rem;text-decoration:none;">← Bosh sahifaga</a>
    </div>
  </div>
</div>
</body>
</html>
"""

ADMIN_PANEL_TEMPLATE = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Admin Panel — QuizAI</title>
  <style>{{ base_style }}</style>
  <style>
    .admin-header { padding: 40px 0 30px; }
    .admin-header h1 { font-size: 2rem; margin-bottom: 8px; }
    .admin-header p { color: var(--text2); }
    .admin-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 24px; padding-bottom: 60px; }
    @media (max-width: 900px) { .admin-grid { grid-template-columns: 1fr; } }
    .sidebar-card { position: sticky; top: 80px; height: fit-content; }
    .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px; }
    .stat-box {
      background: var(--card); border: 1px solid var(--card-border);
      border-radius: var(--radius-sm); padding: 18px; text-align: center;
    }
    .stat-box .num {
      font-family: 'Syne', sans-serif; font-size: 2rem; font-weight: 800;
      background: linear-gradient(135deg, var(--accent), var(--accent3));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .stat-box .label { font-size: 0.75rem; color: var(--text3); margin-top: 4px; }
    .base-list { display: flex; flex-direction: column; gap: 12px; }
    .base-item {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-sm); padding: 16px;
      display: flex; align-items: center; gap: 12px;
      transition: all 0.2s;
    }
    .base-item:hover { border-color: rgba(99,102,241,0.3); background: rgba(99,102,241,0.05); }
    .base-item-info { flex: 1; }
    .base-item-info h4 { font-size: 0.95rem; margin-bottom: 4px; }
    .base-item-info p { font-size: 0.8rem; color: var(--text3); }
    .base-item-actions { display: flex; gap: 8px; }
    .form-section { background: var(--card); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 28px; }
    .form-section h3 { margin-bottom: 24px; display: flex; align-items: center; gap: 8px; }
    .loading-overlay {
      display: none; position: fixed; inset: 0;
      background: rgba(8,12,20,0.9); z-index: 9999;
      align-items: center; justify-content: center;
      flex-direction: column; gap: 20px;
    }
    .loading-overlay.active { display: flex; }
    .loading-text { color: var(--text2); font-size: 0.95rem; animation: pulse 1.5s ease infinite; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  </style>
</head>
<body>
<nav class="nav">
  <a href="/" class="nav-brand">⚡ QuizAI</a>
  <div class="nav-links">
    <span style="color:var(--text3);font-size:0.875rem;">Admin panel</span>
    <a href="/admin/logout">Chiqish</a>
  </div>
</nav>

<div id="loadingOverlay" class="loading-overlay">
  <div class="spinner"></div>
  <p class="loading-text">AI savollarni tahlil qilmoqda...</p>
</div>

<div class="wrap">
  <div class="admin-header animate-up">
    <h1>⚙️ Admin Panel</h1>
    <p>Test bazalarini boshqarish va yangi bazalar qo'shish</p>
  </div>

  <div class="stats-row animate-up">
    <div class="stat-box">
      <div class="num">{{ stats.bases }}</div>
      <div class="label">Bazalar</div>
    </div>
    <div class="stat-box">
      <div class="num">{{ stats.questions }}</div>
      <div class="label">Savollar</div>
    </div>
    <div class="stat-box">
      <div class="num">{{ stats.sessions }}</div>
      <div class="label">Testlar</div>
    </div>
  </div>

  {% if error %}<div class="alert alert-error animate-up">{{ error }}</div>{% endif %}
  {% if success %}<div class="alert alert-success animate-up">{{ success }}</div>{% endif %}

  <div class="admin-grid">
    <div>
      <div class="card sidebar-card">
        <h3 style="margin-bottom:20px;">📚 Mavjud bazalar</h3>
        {% if bases %}
        <div class="base-list">
          {% for b in bases %}
          <div class="base-item">
            <div style="width:40px;height:40px;background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;">📝</div>
            <div class="base-item-info">
              <h4>{{ b.name }}</h4>
              <p>{{ b.q_count }} savol</p>
            </div>
            <div class="base-item-actions">
              <form method="POST" action="/admin/delete/{{ b.id }}" onsubmit="return confirm('Bazani o\'chirasizmi?')">
                <button class="btn btn-danger btn-sm" type="submit">🗑</button>
              </form>
            </div>
          </div>
          {% endfor %}
        </div>
        {% else %}
        <p style="color:var(--text3);text-align:center;padding:20px 0;">Bazalar yo'q</p>
        {% endif %}
      </div>
    </div>

    <div class="form-section animate-in">
      <h3>➕ Yangi baza qo'shish</h3>
      <form method="POST" action="/admin/add" id="addForm">
        <div class="form-group">
          <label class="form-label">Baza nomi *</label>
          <input type="text" name="name" class="form-control" placeholder="Masalan: Matematika 2024" required>
        </div>
        <div class="form-group">
          <label class="form-label">Tavsif (ixtiyoriy)</label>
          <input type="text" name="description" class="form-control" placeholder="Qisqacha tavsif">
        </div>
        <div class="form-group">
          <label class="form-label">Savollar matni *
            <span style="color:var(--text3);font-weight:400;"> — A/B/C/D variantlari bilan</span>
          </label>
          <textarea name="quiz_text" class="form-control" style="min-height:200px;" placeholder="1. Savol matni?
   A) Variant 1
   B) Variant 2
   C) Variant 3
   D) Variant 4

2. Savol matni?
   A) Variant 1
   ..." required></textarea>
        </div>
        <div class="form-group">
          <label class="form-label">Javoblar *
            <span style="color:var(--text3);font-weight:400;"> — Har qanday formatda</span>
          </label>
          <textarea name="answer_instructions" class="form-control" style="min-height:80px;" placeholder="Misol: ABCDABCD yoki 'hammasi A' yoki '1-20 A, 21-40 B' yoki '1A 2B 3C'" required></textarea>
          <div style="font-size:0.78rem;color:var(--text3);margin-top:6px;">
            Qabul qilinadigan formatlar: A, hammasi A, ABCD..., A B C D, 1-20 A 21-40 B, 1A 2B 3C
          </div>
        </div>
        <button type="submit" class="btn btn-primary" id="submitBtn" onclick="showLoading()">
          🤖 AI bilan tahlil qilish va saqlash
        </button>
      </form>
    </div>
  </div>
</div>

<script>
function showLoading() {
  setTimeout(() => {
    document.getElementById('loadingOverlay').classList.add('active');
  }, 100);
}
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
# QUIZ SETUP TEMPLATE
# ─────────────────────────────────────────────

QUIZ_SETUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ base.name }} — QuizAI</title>
  <style>{{ base_style }}</style>
  <style>
    .setup-page { max-width: 680px; margin: 0 auto; padding: 60px 0; }
    .setup-header { text-align: center; margin-bottom: 40px; }
    .setup-header .icon {
      width: 72px; height: 72px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-radius: 20px; font-size: 2rem;
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 20px;
      box-shadow: 0 8px 30px rgba(99,102,241,0.4);
      animation: pulse-glow 2s ease infinite;
    }
    .mode-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 28px 0; }
    @media (max-width: 480px) { .mode-cards { grid-template-columns: 1fr; } }
    .mode-card {
      background: var(--card);
      border: 2px solid var(--card-border);
      border-radius: var(--radius);
      padding: 24px; cursor: pointer;
      transition: all 0.25s; text-align: left;
    }
    .mode-card:hover { border-color: rgba(99,102,241,0.5); transform: translateY(-2px); }
    .mode-card.selected {
      border-color: var(--accent);
      background: rgba(99,102,241,0.12);
      box-shadow: 0 0 0 1px var(--accent), 0 8px 30px rgba(99,102,241,0.2);
    }
    .mode-card .mode-icon { font-size: 2rem; margin-bottom: 12px; }
    .mode-card h4 { margin-bottom: 6px; }
    .mode-card p { color: var(--text2); font-size: 0.8rem; line-height: 1.5; }
    .count-selector { margin: 28px 0; }
    .count-grid { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .count-btn {
      width: 56px; height: 56px;
      background: var(--card);
      border: 2px solid var(--card-border);
      border-radius: var(--radius-sm);
      color: var(--text); font-size: 0.95rem; font-weight: 600;
      cursor: pointer; transition: all 0.2s;
      display: flex; align-items: center; justify-content: center;
    }
    .count-btn:hover { border-color: rgba(99,102,241,0.5); }
    .count-btn.selected {
      background: var(--accent); border-color: var(--accent);
      color: white; box-shadow: 0 4px 16px rgba(99,102,241,0.4);
    }
    .info-bar {
      background: rgba(6,182,212,0.08); border: 1px solid rgba(6,182,212,0.2);
      border-radius: var(--radius-sm); padding: 14px 18px;
      font-size: 0.875rem; color: #67e8f9; margin-bottom: 24px;
      display: flex; align-items: center; gap: 8px;
    }
    .start-section { text-align: center; margin-top: 36px; }
  </style>
</head>
<body>
<nav class="nav">
  <a href="/" class="nav-brand">⚡ QuizAI</a>
  <div class="nav-links">
    <a href="/">← Orqaga</a>
  </div>
</nav>
<div class="wrap">
  <div class="setup-page animate-up">
    <div class="setup-header">
      <div class="icon">📝</div>
      <h2>{{ base.name }}</h2>
      <p style="color:var(--text2);margin-top:8px;">{{ base.description or 'Test sozlamalarini tanlang' }}</p>
      <div style="margin-top:14px;">
        <span class="badge badge-accent">{{ q_count }} savol mavjud</span>
      </div>
    </div>

    <form method="POST" action="/quiz/start">
      <input type="hidden" name="base_id" value="{{ base.id }}">
      <input type="hidden" name="mode" id="modeInput" value="">
      <input type="hidden" name="count" id="countInput" value="">

      <div class="count-selector">
        <label class="form-label">Test rejimi</label>
        <div class="mode-cards">
          <div class="mode-card" onclick="selectMode('random', this)">
            <div class="mode-icon">🔀</div>
            <h4>Random Mode</h4>
            <p>Bazadan tasodifiy savollar tanlanadi. Har urinish farqli bo'ladi.</p>
          </div>
          <div class="mode-card" onclick="selectMode('full', this)">
            <div class="mode-icon">📚</div>
            <h4>Full Mode</h4>
            <p>Barcha savollar bloklarga bo'linadi. Tartib bilan ishlaysiz.</p>
          </div>
        </div>
      </div>

      <div class="count-selector">
        <label class="form-label">Har blokda nechta savol?</label>
        <div class="count-grid">
          {% for c in [20, 25, 30, 35, 40] %}
          <button type="button" class="count-btn" onclick="selectCount({{ c }}, this)">{{ c }}</button>
          {% endfor %}
        </div>
      </div>

      <div class="info-bar" id="infoBar" style="display:none;">
        ℹ️ <span id="infoText"></span>
      </div>

      <div class="start-section">
        <button type="button" id="startBtn" class="btn btn-primary btn-lg" disabled onclick="submitForm()" style="min-width:200px;">
          🚀 Testni boshlash
        </button>
        <p style="color:var(--text3);font-size:0.8rem;margin-top:12px;">Rejim va savol sonini tanlang</p>
      </div>
    </form>
  </div>
</div>

<script>
let selectedMode = '', selectedCount = 0;
const qCount = {{ q_count }};

function selectMode(mode, el) {
  selectedMode = mode;
  document.getElementById('modeInput').value = mode;
  document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  updateUI();
}

function selectCount(count, el) {
  selectedCount = count;
  document.getElementById('countInput').value = count;
  document.querySelectorAll('.count-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  updateUI();
}

function updateUI() {
  const btn = document.getElementById('startBtn');
  const bar = document.getElementById('infoBar');
  const txt = document.getElementById('infoText');
  if (selectedMode && selectedCount) {
    btn.disabled = false;
    bar.style.display = 'flex';
    if (selectedMode === 'random') {
      txt.textContent = `Bazadan ${selectedCount} ta tasodifiy savol tanlanadi.`;
    } else {
      const blocks = Math.ceil(qCount / selectedCount);
      txt.textContent = `${qCount} ta savol ${blocks} ta blokga bo'linadi (${selectedCount} tadan). Barcha bloklarni yechib chiqasiz.`;
    }
  } else { btn.disabled = true; bar.style.display = 'none'; }
}

function submitForm() {
  if (!selectedMode || !selectedCount) return;
  document.querySelector('form').submit();
}
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
# QUIZ PLAY TEMPLATE
# ─────────────────────────────────────────────

QUIZ_PLAY_TEMPLATE = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Test — QuizAI</title>
  <style>{{ base_style }}</style>
  <style>
    .quiz-layout { max-width: 760px; margin: 0 auto; padding: 24px 0 60px; }
    .quiz-topbar {
      background: var(--card); border: 1px solid var(--card-border);
      border-radius: var(--radius); padding: 16px 20px;
      display: flex; align-items: center; gap: 16px;
      margin-bottom: 24px; flex-wrap: wrap;
    }
    .quiz-topbar-info { display: flex; align-items: center; gap: 16px; flex: 1; flex-wrap: wrap; }
    .timer-box {
      display: flex; align-items: center; gap: 6px;
      background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.25);
      border-radius: 8px; padding: 6px 14px;
      font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 700; color: var(--gold);
      min-width: 80px;
    }
    .q-counter { color: var(--text2); font-size: 0.875rem; }
    .q-counter strong { color: var(--text); font-family: 'Syne', sans-serif; }
    .progress-wrap { padding: 0 0 20px; }
    .q-card {
      background: var(--card); border: 1px solid var(--card-border);
      border-radius: var(--radius); padding: 32px;
      box-shadow: var(--shadow); animation: scaleIn 0.35s ease;
    }
    .q-number {
      font-size: 0.75rem; font-weight: 700; letter-spacing: 0.1em;
      color: var(--accent); text-transform: uppercase; margin-bottom: 14px;
    }
    .q-text {
      font-size: 1.1rem; line-height: 1.7; font-weight: 500;
      margin-bottom: 28px; color: var(--text);
    }
    .options { display: flex; flex-direction: column; gap: 10px; }
    .option-btn {
      display: flex; align-items: center; gap: 14px;
      background: rgba(255,255,255,0.03);
      border: 2px solid var(--card-border);
      border-radius: var(--radius-sm); padding: 14px 18px;
      cursor: pointer; transition: all 0.2s;
      text-align: left; color: var(--text);
      font-size: 0.95rem; line-height: 1.5; width: 100%;
    }
    .option-btn:hover {
      border-color: rgba(99,102,241,0.5);
      background: rgba(99,102,241,0.07);
      transform: translateX(4px);
    }
    .option-btn.selected {
      border-color: var(--accent);
      background: rgba(99,102,241,0.15);
      box-shadow: 0 0 0 1px rgba(99,102,241,0.3);
    }
    .option-label {
      width: 32px; height: 32px; flex-shrink: 0;
      background: rgba(255,255,255,0.07);
      border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 0.8rem;
      transition: all 0.2s;
    }
    .option-btn.selected .option-label {
      background: var(--accent); color: white;
    }
    .q-nav {
      display: flex; align-items: center; justify-content: space-between;
      margin-top: 24px; gap: 12px;
    }
    .q-dots {
      display: flex; flex-wrap: wrap; gap: 6px;
      max-width: 400px; justify-content: center;
    }
    .q-dot {
      width: 28px; height: 28px; border-radius: 6px;
      background: rgba(255,255,255,0.07);
      border: 1px solid var(--card-border);
      cursor: pointer; transition: all 0.2s;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.7rem; color: var(--text3);
    }
    .q-dot.answered { background: rgba(99,102,241,0.25); border-color: rgba(99,102,241,0.4); color: #a5b4fc; }
    .q-dot.current { background: var(--accent); border-color: var(--accent); color: white; }
    .finish-modal-bg {
      display: none; position: fixed; inset: 0;
      background: rgba(8,12,20,0.85); z-index: 500;
      align-items: center; justify-content: center;
      backdrop-filter: blur(8px);
    }
    .finish-modal-bg.active { display: flex; }
    .finish-modal {
      background: var(--bg3); border: 1px solid var(--card-border);
      border-radius: 20px; padding: 36px;
      max-width: 400px; width: 100%; text-align: center;
      animation: scaleIn 0.3s ease;
      box-shadow: 0 20px 60px rgba(0,0,0,0.6);
    }
    .finish-modal h3 { margin-bottom: 12px; }
    .finish-modal p { color: var(--text2); margin-bottom: 24px; font-size: 0.9rem; }
    .finish-modal .btn-row { display: flex; gap: 10px; justify-content: center; }
  </style>
</head>
<body>
<nav class="nav">
  <a href="/" class="nav-brand">⚡ QuizAI</a>
  <div class="nav-links">
    <span style="color:var(--text3);font-size:0.875rem;">{{ base_name }}</span>
  </div>
</nav>
<div class="wrap">
  <div class="quiz-layout">
    <div class="quiz-topbar animate-up">
      <div class="quiz-topbar-info">
        <div class="timer-box">⏱ <span id="timerDisplay">00:00</span></div>
        <div class="q-counter">Savol: <strong id="qNumDisplay">1</strong> / {{ total }}</div>
        <div class="q-counter" id="answeredDisplay">Javob berildi: <strong>0</strong></div>
      </div>
      <button class="btn btn-danger btn-sm" onclick="confirmFinish()">✓ Tugatish</button>
    </div>

    <div class="progress-wrap">
      <div class="progress-bar-wrap">
        <div class="progress-bar-fill" id="progressBar" style="width:0%"></div>
      </div>
    </div>

    <div class="q-card" id="qCard">
      <div class="q-number" id="qNumber">SAVOL 1</div>
      <div class="q-text" id="qText"></div>
      <div class="options" id="optionsContainer"></div>
    </div>

    <div class="q-nav">
      <button class="btn btn-secondary" id="prevBtn" onclick="navigate(-1)" disabled>← Oldingi</button>
      <div class="q-dots" id="qDots"></div>
      <button class="btn btn-secondary" id="nextBtn" onclick="navigate(1)">Keyingi →</button>
    </div>
  </div>
</div>

<!-- FINISH MODAL -->
<div class="finish-modal-bg" id="finishModal">
  <div class="finish-modal">
    <div style="font-size:2.5rem;margin-bottom:16px;">🏁</div>
    <h3>Testni tugatmoqchimisiz?</h3>
    <p id="finishStats">Barcha savollar tekshiriladi va natija ko'rsatiladi.</p>
    <div class="btn-row">
      <button class="btn btn-secondary" onclick="closeModal()">Bekor</button>
      <button class="btn btn-success" onclick="submitQuiz()">✓ Tugatish</button>
    </div>
  </div>
</div>

<script>
const questions = {{ questions_json | safe }};
const sessionId = {{ session_id }};
const totalQ = questions.length;
let current = 0;
let answers = {};
let startTime = Date.now();
let timerInterval;
const LABELS = ['A', 'B', 'C', 'D', 'E', 'F'];

function startTimer() {
  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
    const s = String(elapsed % 60).padStart(2, '0');
    document.getElementById('timerDisplay').textContent = `${m}:${s}`;
  }, 1000);
}

function renderQuestion(idx) {
  const q = questions[idx];
  current = idx;
  document.getElementById('qNumber').textContent = `SAVOL ${idx + 1}`;
  document.getElementById('qNumDisplay').textContent = idx + 1;
  document.getElementById('qText').textContent = q.question;

  const container = document.getElementById('optionsContainer');
  container.innerHTML = '';
  q.options.forEach((opt, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'option-btn' + (answers[idx] === i ? ' selected' : '');
    btn.innerHTML = `<span class="option-label">${LABELS[i]}</span><span>${opt}</span>`;
    btn.onclick = () => selectAnswer(idx, i);
    container.appendChild(btn);
  });

  document.getElementById('qCard').style.animation = 'none';
  requestAnimationFrame(() => {
    document.getElementById('qCard').style.animation = 'scaleIn 0.3s ease';
  });

  document.getElementById('prevBtn').disabled = idx === 0;
  document.getElementById('nextBtn').disabled = idx === totalQ - 1;
  document.getElementById('nextBtn').textContent = idx === totalQ - 1 ? 'Tugatish ✓' : 'Keyingi →';
  if (idx === totalQ - 1) {
    document.getElementById('nextBtn').onclick = confirmFinish;
  } else {
    document.getElementById('nextBtn').onclick = () => navigate(1);
  }

  updateProgress();
  renderDots();
}

function selectAnswer(qIdx, optIdx) {
  answers[qIdx] = optIdx;
  document.querySelectorAll('.option-btn').forEach((btn, i) => {
    btn.classList.toggle('selected', i === optIdx);
  });
  const cnt = Object.keys(answers).length;
  document.getElementById('answeredDisplay').innerHTML = `Javob berildi: <strong>${cnt}</strong>`;
  updateProgress();
  renderDots();
  setTimeout(() => { if (current < totalQ - 1) navigate(1); }, 400);
}

function navigate(dir) {
  const next = current + dir;
  if (next >= 0 && next < totalQ) renderQuestion(next);
}

function updateProgress() {
  const pct = (Object.keys(answers).length / totalQ) * 100;
  document.getElementById('progressBar').style.width = pct + '%';
}

function renderDots() {
  const container = document.getElementById('qDots');
  container.innerHTML = '';
  const show = Math.min(totalQ, 30);
  for (let i = 0; i < show; i++) {
    const d = document.createElement('div');
    d.className = 'q-dot' + (answers[i] !== undefined ? ' answered' : '') + (i === current ? ' current' : '');
    d.textContent = i + 1;
    d.onclick = () => renderQuestion(i);
    container.appendChild(d);
  }
  if (totalQ > 30) {
    const more = document.createElement('div');
    more.style.cssText = 'font-size:0.75rem;color:var(--text3);display:flex;align-items:center;';
    more.textContent = `+${totalQ - 30}`;
    container.appendChild(more);
  }
}

function confirmFinish() {
  const answered = Object.keys(answers).length;
  const unanswered = totalQ - answered;
  document.getElementById('finishStats').textContent =
    unanswered > 0
      ? `${answered} savol javoblandi, ${unanswered} savol javobsiz qolgan.`
      : `Barcha ${totalQ} savol javoblandi. Natija ko'rsatiladi.`;
  document.getElementById('finishModal').classList.add('active');
}

function closeModal() {
  document.getElementById('finishModal').classList.remove('active');
}

function submitQuiz() {
  clearInterval(timerInterval);
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  fetch('/quiz/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, answers: answers, time_spent: elapsed })
  })
  .then(r => r.json())
  .then(d => {
    if (d.redirect) window.location.href = d.redirect;
  });
}

startTimer();
renderQuestion(0);
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
# RESULT TEMPLATE
# ─────────────────────────────────────────────

RESULT_TEMPLATE = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Natija — QuizAI</title>
  <style>{{ base_style }}</style>
  <style>
    .result-page { max-width: 800px; margin: 0 auto; padding: 40px 0 80px; }
    .result-hero { text-align: center; padding: 40px 0; }
    .score-ring-wrap {
      position: relative; width: 180px; height: 180px;
      margin: 0 auto 28px;
    }
    .score-ring {
      width: 180px; height: 180px;
      transform: rotate(-90deg);
    }
    .score-ring circle {
      fill: none; stroke-width: 12; stroke-linecap: round;
    }
    .ring-bg { stroke: rgba(255,255,255,0.07); }
    .ring-fill {
      stroke-dasharray: 0 502;
      transition: stroke-dasharray 1.5s cubic-bezier(0.4,0,0.2,1) 0.3s;
    }
    .score-ring-text {
      position: absolute; inset: 0;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
    }
    .score-pct {
      font-family: 'Syne', sans-serif; font-size: 2.4rem; font-weight: 800;
      line-height: 1;
    }
    .score-label { font-size: 0.75rem; color: var(--text3); margin-top: 2px; }
    .motivational {
      font-size: 1.2rem; font-weight: 600; margin-bottom: 8px;
    }
    .motivational-sub { color: var(--text2); font-size: 0.9rem; }
    .stats-grid {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 16px; margin: 32px 0;
    }
    .stat-card {
      background: var(--card); border: 1px solid var(--card-border);
      border-radius: var(--radius); padding: 20px; text-align: center;
      transition: all 0.3s;
    }
    .stat-card:hover { transform: translateY(-2px); }
    .stat-card .val {
      font-family: 'Syne', sans-serif; font-size: 1.8rem; font-weight: 800;
      margin-bottom: 4px;
    }
    .stat-card .lbl { font-size: 0.8rem; color: var(--text3); }
    .val-green { color: var(--green); }
    .val-red { color: var(--red); }
    .val-gold { color: var(--gold); }
    .review-section { margin-top: 40px; }
    .review-section h2 { margin-bottom: 24px; }
    .review-item {
      background: var(--card); border: 1px solid var(--card-border);
      border-radius: var(--radius); padding: 24px; margin-bottom: 16px;
      transition: all 0.2s;
    }
    .review-item.correct { border-left: 4px solid var(--green); }
    .review-item.wrong { border-left: 4px solid var(--red); }
    .review-item.unanswered { border-left: 4px solid var(--text3); }
    .q-title {
      font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em;
      margin-bottom: 10px; text-transform: uppercase;
    }
    .q-title.correct { color: var(--green); }
    .q-title.wrong { color: var(--red); }
    .q-title.unanswered { color: var(--text3); }
    .review-q { font-size: 0.95rem; line-height: 1.6; margin-bottom: 14px; }
    .review-opts { display: flex; flex-direction: column; gap: 6px; }
    .review-opt {
      display: flex; align-items: center; gap: 10px;
      padding: 10px 14px; border-radius: 8px;
      font-size: 0.875rem;
    }
    .review-opt.correct-ans { background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); color: #6ee7b7; }
    .review-opt.wrong-ans { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.25); color: #fca5a5; }
    .review-opt.neutral { background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); color: var(--text2); }
    .opt-icon { font-size: 0.8rem; }
    .cta-row { text-align: center; margin-top: 40px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
  </style>
</head>
<body>
<nav class="nav">
  <a href="/" class="nav-brand">⚡ QuizAI</a>
  <div class="nav-links">
    <a href="/">Bosh sahifa</a>
  </div>
</nav>
<div class="wrap">
  <div class="result-page animate-up">
    <div class="result-hero">
      <div class="score-ring-wrap">
        <svg class="score-ring" viewBox="0 0 180 180">
          <circle class="ring-bg" cx="90" cy="90" r="80"/>
          <circle class="ring-fill" id="ringFill" cx="90" cy="90" r="80"
            stroke="{{ ring_color }}"
            style="stroke-dasharray:0 502"/>
        </svg>
        <div class="score-ring-text">
          <span class="score-pct" style="color:{{ ring_color }};">{{ pct }}%</span>
          <span class="score-label">ball</span>
        </div>
      </div>
      <div class="motivational">{{ motivation }}</div>
      <div class="motivational-sub">{{ result.total }} savoldan {{ result.score }} tasiga to'g'ri javob berdingiz</div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="val val-green">{{ result.score }}</div>
        <div class="lbl">✅ To'g'ri</div>
      </div>
      <div class="stat-card">
        <div class="val val-red">{{ result.wrong }}</div>
        <div class="lbl">❌ Noto'g'ri</div>
      </div>
      <div class="stat-card">
        <div class="val val-gold">{{ result.unanswered }}</div>
        <div class="lbl">⬜ Javobsiz</div>
      </div>
      <div class="stat-card">
        <div class="val" style="color:var(--accent3);">{{ time_str }}</div>
        <div class="lbl">⏱ Vaqt</div>
      </div>
    </div>

    <div class="review-section">
      <h2>📋 Javoblarni ko'rish</h2>
      {% for item in review %}
      <div class="review-item {{ item.status }}">
        <div class="q-title {{ item.status }}">
          {% if item.status == 'correct' %}✅ To'g'ri — {% elif item.status == 'wrong' %}❌ Noto'g'ri — {% else %}⬜ Javob berilmadi — {% endif %}
          Savol {{ loop.index }}
        </div>
        <div class="review-q">{{ item.question }}</div>
        <div class="review-opts">
          {% for i, opt in enumerate(item.options) %}
          <div class="review-opt {% if i == item.correct_index %}correct-ans{% elif item.user_answer == i %}wrong-ans{% else %}neutral{% endif %}">
            <span class="opt-icon">
              {% if i == item.correct_index %}✓{% elif item.user_answer == i %}✗{% else %}·{% endif %}
            </span>
            <span>{{ LABELS[i] }}. {{ opt }}</span>
          </div>
          {% endfor %}
        </div>
      </div>
      {% endfor %}
    </div>

    <div class="cta-row">
      <a href="/quiz/setup/{{ base_id }}" class="btn btn-primary btn-lg">🔄 Qayta urinish</a>
      <a href="/" class="btn btn-secondary btn-lg">🏠 Bosh sahifa</a>
    </div>
  </div>
</div>

<script>
const pct = {{ pct }};
const circumference = 2 * Math.PI * 80;
const fill = (pct / 100) * circumference;
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.getElementById('ringFill').style.strokeDasharray = `${fill} ${circumference - fill}`;
  }, 200);
});
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def home():
    db = get_db()
    rows = db.execute("""
        SELECT qb.*, COUNT(q.id) as q_count
        FROM quiz_bases qb
        LEFT JOIN questions q ON q.base_id = qb.id
        GROUP BY qb.id ORDER BY qb.created_at DESC
    """).fetchall()
    bases = [dict(r) for r in rows]
    return render_template_string(
        HOME_TEMPLATE, base_style=BASE_STYLE, bases=bases
    )

# ─── ADMIN ───

@app.route("/admin")
@admin_required
def admin_panel():
    db = get_db()
    bases = db.execute("""
        SELECT qb.*, COUNT(q.id) as q_count
        FROM quiz_bases qb
        LEFT JOIN questions q ON q.base_id = qb.id
        GROUP BY qb.id ORDER BY qb.created_at DESC
    """).fetchall()
    stats = {
        "bases": db.execute("SELECT COUNT(*) FROM quiz_bases").fetchone()[0],
        "questions": db.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
        "sessions": db.execute("SELECT COUNT(*) FROM quiz_sessions").fetchone()[0],
    }
    return render_template_string(
        ADMIN_PANEL_TEMPLATE, base_style=BASE_STYLE,
        bases=[dict(b) for b in bases], stats=stats,
        error=session.pop("admin_error", None),
        success=session.pop("admin_success", None)
    )

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if hashlib.sha256(pw.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_panel"))
        return render_template_string(
            ADMIN_LOGIN_TEMPLATE, base_style=BASE_STYLE,
            error="Parol noto'g'ri!"
        )
    return render_template_string(ADMIN_LOGIN_TEMPLATE, base_style=BASE_STYLE, error=None)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("home"))

@app.route("/admin/add", methods=["POST"])
@admin_required
def admin_add():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    quiz_text = request.form.get("quiz_text", "").strip()
    answer_instructions = request.form.get("answer_instructions", "").strip()

    if not all([name, quiz_text, answer_instructions]):
        session["admin_error"] = "Barcha majburiy maydonlarni to'ldiring."
        return redirect(url_for("admin_panel"))

    parsed, err = parse_quiz_with_ai(quiz_text, answer_instructions)
    if err or not parsed:
        session["admin_error"] = f"AI xatosi: {err or 'Noma\'lum xato'}"
        return redirect(url_for("admin_panel"))

    questions = parsed.get("questions", [])
    if not questions:
        session["admin_error"] = "Savollar topilmadi. Matnni tekshiring."
        return redirect(url_for("admin_panel"))

    db = get_db()
    cur = db.execute(
        "INSERT INTO quiz_bases (name, description) VALUES (?, ?)",
        (name, description)
    )
    base_id = cur.lastrowid

    for pos, q in enumerate(questions):
        opts = q.get("options", [])
        db.execute(
            "INSERT INTO questions (base_id, question, options, correct_index, position) VALUES (?, ?, ?, ?, ?)",
            (base_id, q["question"], json.dumps(opts, ensure_ascii=False),
             q.get("correct_index", 0), pos + 1)
        )
    db.commit()

    errors = parsed.get("errors", [])
    msg = f"✅ '{name}' bazasi qo'shildi. {len(questions)} savol saqlandi."
    if errors:
        msg += f" Ogohlantirish: {'; '.join(errors[:2])}"
    session["admin_success"] = msg
    return redirect(url_for("admin_panel"))

@app.route("/admin/delete/<int:base_id>", methods=["POST"])
@admin_required
def admin_delete(base_id):
    db = get_db()
    db.execute("DELETE FROM questions WHERE base_id=?", (base_id,))
    db.execute("DELETE FROM quiz_bases WHERE id=?", (base_id,))
    db.commit()
    session["admin_success"] = "Baza o'chirildi."
    return redirect(url_for("admin_panel"))

# ─── QUIZ ───

@app.route("/quiz/setup/<int:base_id>")
def quiz_setup(base_id):
    db = get_db()
    base = db.execute("SELECT * FROM quiz_bases WHERE id=?", (base_id,)).fetchone()
    if not base:
        return redirect(url_for("home"))
    q_count = db.execute("SELECT COUNT(*) FROM questions WHERE base_id=?", (base_id,)).fetchone()[0]
    return render_template_string(
        QUIZ_SETUP_TEMPLATE, base_style=BASE_STYLE,
        base=dict(base), q_count=q_count
    )

@app.route("/quiz/start", methods=["POST"])
def quiz_start():
    base_id = int(request.form.get("base_id", 0))
    mode = request.form.get("mode", "random")
    count = int(request.form.get("count", 20))
    block = int(request.form.get("block", 0))

    db = get_db()
    all_qs = db.execute(
        "SELECT * FROM questions WHERE base_id=? ORDER BY position", (base_id,)
    ).fetchall()
    all_qs = [dict(q) for q in all_qs]

    if not all_qs:
        return redirect(url_for("quiz_setup", base_id=base_id))

    if mode == "random":
        selected = random.sample(all_qs, min(count, len(all_qs)))
    else:
        start = block * count
        selected = all_qs[start:start + count]
        if not selected:
            return redirect(url_for("quiz_setup", base_id=base_id))

    # Build question list with shuffled options
    quiz_questions = []
    for q in selected:
        opts = json.loads(q["options"])
        orig_correct = q["correct_index"]
        # Create indexed list and shuffle
        indexed = list(enumerate(opts))
        random.shuffle(indexed)
        new_opts = [o for _, o in indexed]
        old_to_new = {old: new for new, (old, _) in enumerate(indexed)}
        new_correct = old_to_new[orig_correct]
        quiz_questions.append({
            "id": q["id"],
            "question": q["question"],
            "options": new_opts,
            "correct_index": new_correct
        })

    # Store only IDs + correct indices in session (not exposed to frontend)
    session_data = {
        "base_id": base_id,
        "mode": mode,
        "count": count,
        "block": block,
        "questions": [{"id": q["id"], "correct_index": q["correct_index"]} for q in quiz_questions],
        "total_questions": len(all_qs),
    }

    # Frontend questions (no correct_index)
    frontend_qs = [{"question": q["question"], "options": q["options"]} for q in quiz_questions]

    cur = db.execute(
        "INSERT INTO quiz_sessions (base_id, mode, questions_json) VALUES (?, ?, ?)",
        (base_id, mode, json.dumps(session_data))
    )
    sess_id = cur.lastrowid
    db.commit()

    base = db.execute("SELECT name FROM quiz_bases WHERE id=?", (base_id,)).fetchone()

    return render_template_string(
        QUIZ_PLAY_TEMPLATE, base_style=BASE_STYLE,
        questions_json=json.dumps(frontend_qs, ensure_ascii=False),
        session_id=sess_id,
        total=len(quiz_questions),
        base_name=base["name"] if base else ""
    )

@app.route("/quiz/submit", methods=["POST"])
def quiz_submit():
    data = request.get_json()
    sess_id = data.get("session_id")
    user_answers = data.get("answers", {})
    time_spent = data.get("time_spent", 0)

    db = get_db()
    sess = db.execute("SELECT * FROM quiz_sessions WHERE id=?", (sess_id,)).fetchone()
    if not sess:
        return jsonify({"error": "Session not found"}), 404

    session_data = json.loads(sess["questions_json"])
    correct_list = session_data["questions"]  # [{"id":..,"correct_index":..}]

    score = 0
    wrong = 0
    unanswered = 0
    total = len(correct_list)

    result_detail = []
    for i, cq in enumerate(correct_list):
        ua = user_answers.get(str(i))
        if ua is None:
            unanswered += 1
        elif int(ua) == cq["correct_index"]:
            score += 1
        else:
            wrong += 1

    db.execute(
        "UPDATE quiz_sessions SET answers_json=?, finished_at=CURRENT_TIMESTAMP, score=?, total=? WHERE id=?",
        (json.dumps(user_answers), score, total, sess_id)
    )
    db.commit()

    return jsonify({
        "redirect": f"/quiz/result/{sess_id}?time={time_spent}"
    })

@app.route("/quiz/result/<int:sess_id>")
def quiz_result(sess_id):
    time_spent = int(request.args.get("time", 0))
    db = get_db()
    sess = db.execute("SELECT * FROM quiz_sessions WHERE id=?", (sess_id,)).fetchone()
    if not sess:
        return redirect(url_for("home"))

    session_data = json.loads(sess["questions_json"])
    user_answers = json.loads(sess["answers_json"] or "{}")
    correct_list = session_data["questions"]
    base_id = session_data["base_id"]

    score = sess["score"] or 0
    total = sess["total"] or len(correct_list)
    wrong = sum(
        1 for i, cq in enumerate(correct_list)
        if user_answers.get(str(i)) is not None
        and int(user_answers.get(str(i))) != cq["correct_index"]
    )
    unanswered = total - score - wrong
    pct = round((score / total * 100) if total else 0)

    # Motivational text
    if pct >= 90:
        motivation = "🏆 A'lo! Zo'r natija!"
        ring_color = "#10b981"
    elif pct >= 70:
        motivation = "👏 Yaxshi! Davom eting!"
        ring_color = "#6366f1"
    elif pct >= 50:
        motivation = "💪 O'rtacha. Ko'proq mashq qiling!"
        ring_color = "#f59e0b"
    else:
        motivation = "📖 Qiyin bo'ldi. Qayta o'qib chiqing!"
        ring_color = "#ef4444"

    # Build review
    LABELS = ["A", "B", "C", "D", "E", "F"]
    review = []
    for i, cq in enumerate(correct_list):
        q_row = db.execute("SELECT * FROM questions WHERE id=?", (cq["id"],)).fetchone()
        if not q_row:
            continue
        opts = json.loads(q_row["options"])
        ua = user_answers.get(str(i))
        ua_int = int(ua) if ua is not None else None
        if ua_int is None:
            status = "unanswered"
        elif ua_int == cq["correct_index"]:
            status = "correct"
        else:
            status = "wrong"
        review.append({
            "question": q_row["question"],
            "options": opts,
            "correct_index": cq["correct_index"],
            "user_answer": ua_int,
            "status": status
        })

    # Time format
    m = time_spent // 60
    s = time_spent % 60
    time_str = f"{m}:{str(s).zfill(2)}"

    result = {"score": score, "total": total, "wrong": wrong, "unanswered": unanswered}

    return render_template_string(
        RESULT_TEMPLATE, base_style=BASE_STYLE,
        result=result, pct=pct, motivation=motivation,
        ring_color=ring_color, review=review,
        time_str=time_str, base_id=base_id,
        enumerate=enumerate, LABELS=LABELS
    )

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"""
╔══════════════════════════════════════╗
║      QuizAI — Uzbek Quiz Platform     ║
╠══════════════════════════════════════╣
║  URL: http://localhost:{port}           ║
║  Admin: http://localhost:{port}/admin   ║
║  Default password: admin123           ║
╚══════════════════════════════════════╝
Env vars needed:
  GROQ_API_KEY   — required for AI parsing
  SECRET_KEY     — change in production
  ADMIN_PASSWORD_HASH — sha256 of password
    """)
    app.run(host="0.0.0.0", port=port, debug=debug)
