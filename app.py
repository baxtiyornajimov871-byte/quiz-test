import os
import json
import random
import sqlite3
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
#  GROQ AI
# ─────────────────────────────────────────────

def extract_questions_with_groq(text, num_questions=30):
    client = Groq(api_key=GROQ_API_KEY)
    prompt = f"""
Quyidagi matndan {num_questions} ta test savoli va har biriga 4 ta javob varianti (A, B, C, D) yarating.
To'g'ri javobni ham belgilang.
FAQAT JSON formatida javob bering, boshqa hech narsa yozmang.
Format:
[
  {{
    "question": "Savol matni?",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct": 0
  }},
  ...
]
"correct" — to'g'ri javobning indeksi (0=A, 1=B, 2=C, 3=D).

MATN:
{text[:8000]}
"""
    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-70b-8192",
        temperature=0.7,
        max_tokens=6000,
    )
    raw = chat.choices[0].message.content.strip()
    # JSON ni ajratib olish
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError("AI JSON qaytarmadi")
    return json.loads(raw[start:end])

# ─────────────────────────────────────────────
#  HTML TEMPLATE
# ─────────────────────────────────────────────

BASE_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>QuizAI — Aqlli Test Platformasi</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
:root {
  --bg: #0b0c10;
  --surface: #13151a;
  --card: #1c1f27;
  --border: #2a2d37;
  --accent: #6ee7b7;
  --accent2: #818cf8;
  --danger: #f87171;
  --text: #e2e8f0;
  --muted: #64748b;
  --radius: 14px;
  --font-head: 'Syne', sans-serif;
  --font-body: 'DM Sans', sans-serif;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  min-height: 100vh;
  line-height: 1.6;
}
a { color: inherit; text-decoration: none; }
.nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 40px;
  border-bottom: 1px solid var(--border);
  background: rgba(11,12,16,0.95);
  position: sticky; top: 0; z-index: 100;
  backdrop-filter: blur(12px);
}
.nav-logo {
  font-family: var(--font-head);
  font-weight: 800; font-size: 22px;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px;
}
.nav-links { display: flex; gap: 10px; }
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px; border-radius: var(--radius);
  font-family: var(--font-body); font-size: 14px; font-weight: 500;
  border: none; cursor: pointer; transition: all 0.2s;
}
.btn-ghost {
  background: transparent; color: var(--muted);
  border: 1px solid var(--border);
}
.btn-ghost:hover { color: var(--text); border-color: var(--accent); }
.btn-primary {
  background: linear-gradient(135deg, var(--accent), #34d399);
  color: #0b0c10; font-weight: 600;
}
.btn-primary:hover { opacity: 0.88; transform: translateY(-1px); box-shadow: 0 8px 24px rgba(110,231,183,0.2); }
.btn-accent2 {
  background: linear-gradient(135deg, var(--accent2), #6366f1);
  color: #fff; font-weight: 600;
}
.btn-accent2:hover { opacity: 0.88; transform: translateY(-1px); }
.btn-danger {
  background: transparent; color: var(--danger);
  border: 1px solid var(--danger);
}
.btn-danger:hover { background: var(--danger); color: #fff; }
.container { max-width: 860px; margin: 0 auto; padding: 40px 20px; }
.hero {
  text-align: center; padding: 80px 20px 60px;
}
.hero h1 {
  font-family: var(--font-head); font-size: clamp(36px, 6vw, 64px);
  font-weight: 800; line-height: 1.1; letter-spacing: -2px;
  background: linear-gradient(135deg, #fff 40%, var(--accent));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  margin-bottom: 18px;
}
.hero p { color: var(--muted); font-size: 17px; max-width: 480px; margin: 0 auto 36px; }
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px;
  transition: border-color 0.2s, transform 0.2s;
}
.card:hover { border-color: var(--accent2); transform: translateY(-2px); }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px,1fr)); gap: 18px; }
.card h3 { font-family: var(--font-head); font-size: 18px; font-weight: 700; margin-bottom: 8px; }
.card p { color: var(--muted); font-size: 14px; margin-bottom: 16px; }
.badge {
  display: inline-block; padding: 3px 10px; border-radius: 20px;
  font-size: 12px; font-weight: 600;
  background: rgba(110,231,183,0.12); color: var(--accent);
  border: 1px solid rgba(110,231,183,0.25);
}
.form-group { margin-bottom: 20px; }
label { display: block; font-size: 13px; font-weight: 500; color: var(--muted); margin-bottom: 8px; }
input[type=text], input[type=password], textarea, select {
  width: 100%; padding: 12px 16px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; color: var(--text);
  font-family: var(--font-body); font-size: 15px;
  transition: border-color 0.2s;
  outline: none;
}
input:focus, textarea:focus, select:focus { border-color: var(--accent); }
textarea { resize: vertical; min-height: 220px; }
.alert {
  padding: 14px 18px; border-radius: 10px; font-size: 14px; margin-bottom: 20px;
}
.alert-success { background: rgba(110,231,183,0.1); border: 1px solid rgba(110,231,183,0.25); color: var(--accent); }
.alert-error { background: rgba(248,113,113,0.1); border: 1px solid rgba(248,113,113,0.25); color: var(--danger); }
.section-title {
  font-family: var(--font-head); font-size: 26px; font-weight: 700;
  margin-bottom: 24px; letter-spacing: -0.5px;
}
/* Quiz */
.quiz-header {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px 28px;
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 28px;
  flex-wrap: wrap; gap: 12px;
}
.quiz-progress-bar {
  height: 6px; background: var(--border); border-radius: 10px;
  margin-bottom: 28px; overflow: hidden;
}
.quiz-progress-fill {
  height: 100%; border-radius: 10px;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  transition: width 0.4s ease;
}
.question-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 32px;
  margin-bottom: 24px;
}
.question-number {
  font-size: 12px; font-weight: 600; color: var(--accent);
  letter-spacing: 1px; text-transform: uppercase; margin-bottom: 12px;
}
.question-text {
  font-family: var(--font-head); font-size: 20px; font-weight: 600;
  line-height: 1.4; margin-bottom: 24px;
}
.options { display: flex; flex-direction: column; gap: 12px; }
.option-btn {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px;
  background: var(--surface); border: 2px solid var(--border);
  border-radius: 10px; cursor: pointer;
  font-family: var(--font-body); font-size: 15px; color: var(--text);
  transition: all 0.15s; text-align: left;
  width: 100%;
}
.option-btn:hover { border-color: var(--accent2); background: rgba(129,140,248,0.06); }
.option-btn.selected { border-color: var(--accent2); background: rgba(129,140,248,0.12); }
.option-btn.correct { border-color: var(--accent); background: rgba(110,231,183,0.12); }
.option-btn.wrong { border-color: var(--danger); background: rgba(248,113,113,0.12); }
.option-label {
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--border); display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 13px; flex-shrink: 0;
}
.result-box {
  text-align: center; padding: 60px 30px;
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius);
}
.result-score {
  font-family: var(--font-head); font-size: 72px; font-weight: 800;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.result-label { color: var(--muted); font-size: 17px; margin: 10px 0 30px; }
/* Mode select */
.mode-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
.mode-card {
  background: var(--card); border: 2px solid var(--border);
  border-radius: var(--radius); padding: 24px;
  cursor: pointer; transition: all 0.2s; text-align: center;
}
.mode-card:hover, .mode-card.active { border-color: var(--accent2); background: rgba(129,140,248,0.07); }
.mode-card h4 { font-family: var(--font-head); font-size: 16px; font-weight: 700; margin-bottom: 8px; }
.mode-card p { font-size: 13px; color: var(--muted); }
.mode-icon { font-size: 30px; margin-bottom: 12px; }
.tag { 
  display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px;
  background: rgba(129,140,248,0.15); color: var(--accent2);
  border: 1px solid rgba(129,140,248,0.3); margin-right: 6px; margin-bottom: 6px;
}
.flex { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
.mt-16 { margin-top: 16px; }
.mt-24 { margin-top: 24px; }
.loading {
  display: none; text-align: center; padding: 40px;
}
.spinner {
  width: 40px; height: 40px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite; margin: 0 auto 16px;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<nav class="nav">
  <div class="nav-logo">⚡ QuizAI</div>
  <div class="nav-links">
    <a href="/" class="btn btn-ghost">🏠 Bosh sahifa</a>
    <a href="/admin" class="btn btn-ghost">🔐 Admin</a>
  </div>
</nav>
{% block content %}{% endblock %}
</body>
</html>
"""

INDEX_TEMPLATE = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="hero">
  <h1>Aqlli Test<br/>Platformasi</h1>
  <p>Matn yuklab, sun'iy intellekt yordamida bir zumda test yarating va yechib ko'ring.</p>
  <a href="#bases" class="btn btn-primary">Test bazalarini ko'rish →</a>
</div>

<div class="container" id="bases">
  <div class="section-title">📚 Test Bazalari</div>
  {% if bases %}
  <div class="card-grid">
    {% for b in bases %}
    <div class="card">
      <div style="margin-bottom:10px"><span class="badge">{{ b['q_count'] }} savol</span></div>
      <h3>{{ b['name'] }}</h3>
      <p>{{ b['description'] or "Tavsif yo'q" }}</p>
      <a href="/quiz/setup/{{ b['id'] }}" class="btn btn-primary" style="width:100%;justify-content:center">Test boshlash →</a>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="card" style="text-align:center;padding:60px">
    <div style="font-size:48px;margin-bottom:16px">📭</div>
    <h3 style="margin-bottom:8px">Hali test bazasi yo'q</h3>
    <p style="margin-bottom:24px">Admin panelidan matn yuklab, test yarating.</p>
    <a href="/admin" class="btn btn-accent2">Admin panelga o'tish</a>
  </div>
  {% endif %}
</div>
""")

ADMIN_LOGIN_TEMPLATE = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="container" style="max-width:420px;padding-top:80px">
  <div class="card">
    <h2 style="font-family:var(--font-head);font-size:24px;font-weight:700;margin-bottom:6px">🔐 Admin Panel</h2>
    <p style="color:var(--muted);margin-bottom:24px;font-size:14px">Kirish uchun parolingizni kiriting</p>
    {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}
    <form method="POST">
      <div class="form-group">
        <label>Parol</label>
        <input type="password" name="password" placeholder="••••••••" autofocus/>
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center">Kirish</button>
    </form>
  </div>
</div>
""")

ADMIN_PANEL_TEMPLATE = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="container" style="max-width:780px">
  <div class="flex" style="margin-bottom:28px;margin-top:16px">
    <div class="section-title" style="margin-bottom:0">⚙️ Admin Panel</div>
    <a href="/admin/logout" class="btn btn-ghost" style="margin-left:auto">Chiqish</a>
  </div>

  <div class="card" style="margin-bottom:32px">
    <h3 style="font-family:var(--font-head);margin-bottom:20px">➕ Yangi Test Bazasi Qo'shish</h3>
    {% if msg %}<div class="alert alert-{{ msg_type }}">{{ msg }}</div>{% endif %}
    <form method="POST" action="/admin/upload" id="uploadForm">
      <div class="form-group">
        <label>Baza nomi *</label>
        <input type="text" name="name" placeholder="Masalan: Biologiya 11-sinf" required/>
      </div>
      <div class="form-group">
        <label>Tavsif (ixtiyoriy)</label>
        <input type="text" name="description" placeholder="Qisqacha tavsif..."/>
      </div>
      <div class="form-group">
        <label>Matn * (kitob, darslik matni)</label>
        <textarea name="text" placeholder="Shu yerga matnni joylashtiring. AI avtomatik ravishda savollar yaratadi..." required></textarea>
      </div>
      <div class="form-group">
        <label>Nechta savol yaratilsin?</label>
        <select name="num_questions">
          <option value="20">20 ta</option>
          <option value="25">25 ta</option>
          <option value="30" selected>30 ta</option>
          <option value="35">35 ta</option>
          <option value="40">40 ta</option>
        </select>
      </div>
      <button type="submit" class="btn btn-primary" onclick="showLoading()">🤖 AI bilan savollar yaratish</button>
    </form>
    <div class="loading" id="loadingDiv">
      <div class="spinner"></div>
      <p style="color:var(--muted)">AI matnni tahlil qilyapti, savollar yaratilmoqda...</p>
    </div>
  </div>

  <div class="section-title">📚 Mavjud Bazalar</div>
  {% if bases %}
  <div style="display:flex;flex-direction:column;gap:14px">
    {% for b in bases %}
    <div class="card" style="display:flex;align-items:center;gap:16px;padding:20px 24px">
      <div style="flex:1">
        <div style="font-family:var(--font-head);font-weight:700;margin-bottom:4px">{{ b['name'] }}</div>
        <div style="font-size:13px;color:var(--muted)">{{ b['description'] or '' }} &nbsp;·&nbsp; <span class="badge">{{ b['q_count'] }} savol</span></div>
      </div>
      <a href="/quiz/setup/{{ b['id'] }}" class="btn btn-accent2">Test →</a>
      <form method="POST" action="/admin/delete/{{ b['id'] }}" style="margin:0" onsubmit="return confirm('O\'chirilsinmi?')">
        <button type="submit" class="btn btn-danger">🗑</button>
      </form>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="card" style="text-align:center;padding:40px;color:var(--muted)">Hali baza qo'shilmagan.</div>
  {% endif %}
</div>
<script>
function showLoading(){
  document.getElementById('loadingDiv').style.display='block';
}
</script>
""")

SETUP_TEMPLATE = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="container" style="max-width:640px">
  <div style="margin-top:16px;margin-bottom:24px">
    <a href="/" class="btn btn-ghost">← Orqaga</a>
  </div>
  <div class="card" style="margin-bottom:24px">
    <h2 style="font-family:var(--font-head);font-size:22px;font-weight:700;margin-bottom:6px">⚙️ Test Sozlamalari</h2>
    <p style="color:var(--muted);font-size:14px">{{ base['name'] }} &nbsp;·&nbsp; <span class="badge">{{ q_count }} savol bor</span></p>
  </div>

  <form method="POST">
    <div class="card" style="margin-bottom:20px">
      <label style="font-size:15px;font-weight:600;color:var(--text);margin-bottom:16px;display:block">📊 Nechta savol yechmoqchisiz?</label>
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        {% for n in [20,25,30,35,40] %}
        {% if n <= q_count %}
        <label style="cursor:pointer">
          <input type="radio" name="num" value="{{ n }}" {% if n==20 %}checked{% endif %} style="display:none" class="num-radio"/>
          <div class="tag num-label" data-val="{{ n }}" style="font-size:14px;padding:8px 18px;cursor:pointer">{{ n }} ta</div>
        </label>
        {% endif %}
        {% endfor %}
      </div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <label style="font-size:15px;font-weight:600;color:var(--text);margin-bottom:16px;display:block">🎮 Rejim tanlang</label>
      <div class="mode-grid">
        <div class="mode-card active" onclick="selectMode('random',this)">
          <div class="mode-icon">🎲</div>
          <h4>Random tanlov</h4>
          <p>N ta savoldan random tanlangan miqdorda yechish</p>
          <input type="radio" name="mode" value="random" checked style="display:none"/>
        </div>
        <div class="mode-card" onclick="selectMode('sequential',this)">
          <div class="mode-icon">📖</div>
          <h4>Ketma-ket bloklar</h4>
          <p>N ta savolni tanlangan miqdordan guruhlarga bo'lib yechish</p>
          <input type="radio" name="mode" value="sequential" style="display:none"/>
        </div>
      </div>
    </div>

    <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;font-size:16px;padding:14px">Testni Boshlash →</button>
  </form>
</div>
<script>
function selectMode(val, el){
  document.querySelectorAll('.mode-card').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
  el.querySelector('input[type=radio]').checked=true;
}
document.querySelectorAll('.num-radio').forEach(r=>{
  r.addEventListener('change',function(){
    document.querySelectorAll('.num-label').forEach(l=>l.style.background='rgba(129,140,248,0.15)');
    document.querySelector('.num-label[data-val="'+this.value+'"]').style.background='rgba(110,231,183,0.25)';
  });
});
</script>
""")

QUIZ_TEMPLATE = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="container" style="max-width:700px">
  <div class="quiz-header">
    <div>
      <div style="font-family:var(--font-head);font-weight:700;font-size:17px">{{ base_name }}</div>
      <div style="font-size:13px;color:var(--muted)">
        {% if block_info %}Blok {{ block_info[0] }}/{{ block_info[1] }}{% endif %}
      </div>
    </div>
    <div style="font-family:var(--font-head);font-size:22px;font-weight:800;color:var(--accent)">
      <span id="timer">--:--</span>
    </div>
    <div style="text-align:right">
      <div style="font-size:22px;font-weight:700;font-family:var(--font-head)">{{ questions|length }} savol</div>
      <div style="font-size:13px;color:var(--muted)">jami</div>
    </div>
  </div>

  <div class="quiz-progress-bar">
    <div class="quiz-progress-fill" id="progressFill" style="width:0%"></div>
  </div>

  <div id="quizArea">
    <div class="question-card" id="questionCard">
      <div class="question-number" id="qNum">SAVOL 1 / {{ questions|length }}</div>
      <div class="question-text" id="qText"></div>
      <div class="options" id="optionsArea"></div>
    </div>
    <div class="flex mt-24" style="justify-content:space-between">
      <button class="btn btn-ghost" id="prevBtn" onclick="goTo(current-1)">← Oldingi</button>
      <button class="btn btn-primary" id="nextBtn" onclick="goTo(current+1)">Keyingi →</button>
      <button class="btn btn-accent2" id="finishBtn" onclick="finishQuiz()" style="display:none">✅ Yakunlash</button>
    </div>
  </div>

  <div id="resultArea" style="display:none">
    <div class="result-box">
      <div class="result-score" id="scoreText"></div>
      <div class="result-label" id="scoreLabel"></div>
      <div style="display:flex;gap:16px;justify-content:center;flex-wrap:wrap;margin-top:16px" id="resultActions">
        <button class="btn btn-ghost" onclick="reviewAnswers()">📋 Ko'rib chiqish</button>
        {% if block_info and block_info[0] < block_info[1] %}
        <a href="/quiz/block/{{ base_id }}/{{ block_info[0]+1 }}/{{ block_size }}" class="btn btn-primary">Keyingi blok →</a>
        {% endif %}
        <a href="/" class="btn btn-accent2">🏠 Bosh sahifa</a>
      </div>
    </div>
    <div id="reviewArea" style="margin-top:28px"></div>
  </div>
</div>

<script>
const questions = {{ questions | tojson }};
let answers = new Array(questions.length).fill(null);
let current = 0;
let quizDone = false;
let startTime = Date.now();

function render(){
  const q = questions[current];
  document.getElementById('qNum').textContent = `SAVOL ${current+1} / ${questions.length}`;
  document.getElementById('qText').textContent = q.question;
  const area = document.getElementById('optionsArea');
  area.innerHTML = '';
  const labels = ['A','B','C','D'];
  q.options.forEach((opt,i)=>{
    const btn = document.createElement('button');
    btn.className = 'option-btn' + (answers[current]===i?' selected':'');
    btn.innerHTML = `<span class="option-label">${labels[i]}</span> ${opt}`;
    btn.onclick = ()=>{ answers[current]=i; render(); };
    area.appendChild(btn);
  });
  const pct = ((current+1)/questions.length)*100;
  document.getElementById('progressFill').style.width = pct+'%';
  document.getElementById('prevBtn').style.display = current===0?'none':'';
  const isLast = current === questions.length-1;
  document.getElementById('nextBtn').style.display = isLast?'none':'';
  document.getElementById('finishBtn').style.display = isLast?'':'none';
}

function goTo(idx){
  if(idx<0||idx>=questions.length) return;
  current=idx; render();
}

function finishQuiz(){
  if(answers.includes(null)){
    const unanswered = answers.filter(a=>a===null).length;
    if(!confirm(`${unanswered} ta savol javobsiz qoldi. Shunga qaramay yakunlaysizmi?`)) return;
  }
  quizDone=true;
  let correct=0;
  questions.forEach((q,i)=>{ if(answers[i]===q.correct) correct++; });
  const pct = Math.round(correct/questions.length*100);
  document.getElementById('quizArea').style.display='none';
  document.getElementById('resultArea').style.display='block';
  document.getElementById('scoreText').textContent = `${correct}/${questions.length}`;
  const label = pct>=90?'🏆 Ajoyib natija!'
    : pct>=70?'👍 Yaxshi natija!'
    : pct>=50?'📚 O\'rta daraja'
    : '💪 Ko\'proq mashq qiling!';
  document.getElementById('scoreLabel').textContent = `${pct}% — ${label}`;
  clearInterval(timerInterval);
}

function reviewAnswers(){
  const area = document.getElementById('reviewArea');
  if(area.innerHTML) { area.innerHTML=''; return; }
  const labels=['A','B','C','D'];
  questions.forEach((q,i)=>{
    const div = document.createElement('div');
    div.className='question-card';
    div.style.marginBottom='16px';
    const userAns = answers[i];
    const status = userAns===q.correct?'✅':'❌';
    div.innerHTML=`<div class="question-number">${status} SAVOL ${i+1}</div>
    <div class="question-text">${q.question}</div>
    <div class="options">
    ${q.options.map((opt,j)=>`<div class="option-btn ${j===q.correct?'correct':j===userAns&&j!==q.correct?'wrong':''}" style="cursor:default">
      <span class="option-label">${labels[j]}</span> ${opt}
    </div>`).join('')}
    </div>`;
    area.appendChild(div);
  });
}

// Timer
const timerInterval = setInterval(()=>{
  if(quizDone) return;
  const elapsed = Math.floor((Date.now()-startTime)/1000);
  const m=Math.floor(elapsed/60), s=elapsed%60;
  document.getElementById('timer').textContent = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
},1000);

render();
</script>
""")

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
        bases.append({"id": r["id"], "name": r["name"], "description": r["description"], "q_count": len(qs)})
    return render_template_string(INDEX_TEMPLATE, bases=bases)


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_panel"))
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        error = "Parol noto'g'ri!"
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=error)


@app.route("/admin/panel", methods=["GET"])
def admin_panel():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    msg = request.args.get("msg")
    msg_type = request.args.get("type", "success")
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, description, questions FROM test_bases ORDER BY id DESC").fetchall()
    bases = [{"id": r["id"], "name": r["name"], "description": r["description"],
              "q_count": len(json.loads(r["questions"]))} for r in rows]
    return render_template_string(ADMIN_PANEL_TEMPLATE, bases=bases, msg=msg, msg_type=msg_type)


@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    text = request.form.get("text", "").strip()
    num_questions = int(request.form.get("num_questions", 30))
    if not name or not text:
        return redirect(url_for("admin_panel") + "?msg=Nom+va+matn+majburiy&type=error")
    if not GROQ_API_KEY:
        return redirect(url_for("admin_panel") + "?msg=GROQ_API_KEY+topilmadi&type=error")
    try:
        questions = extract_questions_with_groq(text, num_questions)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO test_bases (name, description, questions) VALUES (?,?,?)",
                (name, description, json.dumps(questions, ensure_ascii=False))
            )
            conn.commit()
        return redirect(url_for("admin_panel") + f"?msg={len(questions)}+ta+savol+muvaffaqiyatli+yaratildi&type=success")
    except Exception as e:
        return redirect(url_for("admin_panel") + f"?msg=Xato:+{str(e)[:80]}&type=error")


@app.route("/admin/delete/<int:base_id>", methods=["POST"])
def admin_delete(base_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    with get_db() as conn:
        conn.execute("DELETE FROM test_bases WHERE id=?", (base_id,))
        conn.commit()
    return redirect(url_for("admin_panel") + "?msg=Baza+o'chirildi&type=success")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/quiz/setup/<int:base_id>", methods=["GET", "POST"])
def quiz_setup(base_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM test_bases WHERE id=?", (base_id,)).fetchone()
    if not row:
        return redirect(url_for("index"))
    questions = json.loads(row["questions"])
    if request.method == "POST":
        num = int(request.form.get("num", 20))
        mode = request.form.get("mode", "random")
        num = min(num, len(questions))
        if mode == "random":
            selected = random.sample(questions, num)
            random.shuffle(selected)
            session["quiz_questions"] = selected
            session["quiz_base_id"] = base_id
            session["quiz_base_name"] = row["name"]
            session["quiz_block_info"] = None
            return redirect(url_for("quiz_play"))
        else:
            # Sequential blocks
            all_q = list(questions)
            random.shuffle(all_q)
            blocks = [all_q[i:i+num] for i in range(0, len(all_q), num)]
            session["quiz_blocks"] = blocks
            session["quiz_base_id"] = base_id
            session["quiz_base_name"] = row["name"]
            session["quiz_block_size"] = num
            # Go to block 1
            return redirect(url_for("quiz_block", base_id=base_id, block_num=1, block_size=num))
    return render_template_string(
        SETUP_TEMPLATE,
        base={"name": row["name"]},
        q_count=len(questions),
        base_id=base_id
    )


@app.route("/quiz/block/<int:base_id>/<int:block_num>/<int:block_size>")
def quiz_block(base_id, block_num, block_size):
    blocks = session.get("quiz_blocks")
    if not blocks:
        return redirect(url_for("quiz_setup", base_id=base_id))
    idx = block_num - 1
    if idx < 0 or idx >= len(blocks):
        return redirect(url_for("index"))
    selected = blocks[idx]
    random.shuffle(selected)
    session["quiz_questions"] = selected
    session["quiz_base_name"] = session.get("quiz_base_name", "Test")
    session["quiz_block_info"] = [block_num, len(blocks)]
    session["quiz_base_id"] = base_id
    return redirect(url_for("quiz_play"))


@app.route("/quiz/play")
def quiz_play():
    questions = session.get("quiz_questions")
    if not questions:
        return redirect(url_for("index"))
    base_name = session.get("quiz_base_name", "Test")
    block_info = session.get("quiz_block_info")
    base_id = session.get("quiz_base_id", 0)
    block_size = session.get("quiz_block_size", 0)
    return render_template_string(
        QUIZ_TEMPLATE,
        questions=questions,
        base_name=base_name,
        block_info=block_info,
        base_id=base_id,
        block_size=block_size
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
