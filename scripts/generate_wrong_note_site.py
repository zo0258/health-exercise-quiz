#!/usr/bin/env python3
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATTEMPTS_PATH = ROOT / "results" / "attempts.jsonl"
MASTERED_PATH = ROOT / "results" / "mastered.json"
QUIZ_DIR = ROOT / "data" / "quizzes"
BANK_DIR = ROOT / "data" / "question-bank"
REVIEW_DIR = ROOT / "data" / "review"
REVIEW_JSON = REVIEW_DIR / "wrong-note.json"
WRONG_NOTE_HTML = ROOT / "wrong-note.html"


def read_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_question_map():
    questions = {}
    for quiz_path in sorted(QUIZ_DIR.glob("*-daily.json")):
        for question in read_json(quiz_path).get("questions", []):
            questions[question["id"]] = question
    for bank_path in sorted(BANK_DIR.glob("*.jsonl")):
        for question in read_jsonl(bank_path):
            questions.setdefault(question["id"], question)
    return questions


def choice_label(value):
    labels = ["①", "②", "③", "④", "⑤"]
    try:
        return labels[int(value) - 1]
    except (TypeError, ValueError, IndexError):
        return str(value)


def build_data():
    attempts = read_jsonl(ATTEMPTS_PATH)
    mastered = read_json(MASTERED_PATH) if MASTERED_PATH.exists() else []
    questions = load_question_map()
    total_score = sum(int(attempt.get("score", 0)) for attempt in attempts)
    total_questions = sum(int(attempt.get("total", 0)) for attempt in attempts)
    wrong_rounds = Counter()
    wrong = []
    review = []

    for attempt in attempts:
        date = attempt.get("date", "")
        for item in attempt.get("wrong", []):
            question_id = item.get("questionId", "")
            question = questions.get(question_id, {})
            wrong_rounds[question_id] += 1
            wrong.append({
                "date": date,
                "quizId": attempt.get("quizId", ""),
                "subject": question.get("subject", attempt.get("subject", "")),
                "questionId": question_id,
                "topic": item.get("topic") or question.get("topic", ""),
                "selected": item.get("selected", "none"),
                "selectedLabel": choice_label(item.get("selected")),
                "answer": item.get("answer", ""),
                "answerLabel": choice_label(item.get("answer")),
                "wrongReason": item.get("wrongReason", "미선택"),
                "bookmarked": item.get("bookmarked", "no"),
                "question": question.get("question", ""),
                "choices": question.get("choices", []),
                "answerIndex": question.get("answerIndex"),
                "explanation": question.get("explanation", ""),
                "trap": question.get("trap", ""),
                "choiceExplanations": question.get("choiceExplanations", []),
            })
        for item in attempt.get("review", []):
            question_id = item.get("questionId", "")
            question = questions.get(question_id, {})
            review.append({
                "date": date,
                "quizId": attempt.get("quizId", ""),
                "subject": question.get("subject", attempt.get("subject", "")),
                "questionId": question_id,
                "topic": item.get("topic") or question.get("topic", ""),
                "reason": item.get("reason", "bookmarked"),
                "question": question.get("question", ""),
                "choices": question.get("choices", []),
                "answerIndex": question.get("answerIndex"),
                "explanation": question.get("explanation", ""),
                "trap": question.get("trap", ""),
                "choiceExplanations": question.get("choiceExplanations", []),
            })

    for item in wrong:
        item["reviewRound"] = wrong_rounds[item["questionId"]]

    accuracy = round(total_score / total_questions * 100, 1) if total_questions else 0
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "stats": {
            "attemptCount": len(attempts),
            "totalScore": total_score,
            "totalQuestions": total_questions,
            "accuracy": accuracy,
            "wrongCount": len(wrong),
            "wrongQuestionCount": len({item["questionId"] for item in wrong}),
            "reviewCount": len(review),
            "masteredCount": len(set(mastered)),
        },
        "mastered": sorted(set(mastered)),
        "wrong": wrong,
        "review": review,
    }


def render_html(data):
    safe_data = (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("</script", "\\u003c/script")
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>건강운동관리사 오답노트</title>
  <style>
    :root {{ --bg:#f3f5f0; --surface:#fff; --ink:#17201a; --muted:#69736c; --line:#dfe5dc; --accent:#2f6b4f; --danger:#b64032; --danger-soft:#f8e8e5; --ok:#287a4b; --ok-soft:#e4f3e9; --radius:8px; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif; line-height:1.5; letter-spacing:0; }}
    main {{ width:min(820px,100%); min-height:100svh; margin:0 auto; padding:24px 16px 32px; background:var(--surface); border-left:1px solid rgba(23,32,26,.06); border-right:1px solid rgba(23,32,26,.06); }}
    .nav {{ display:flex; justify-content:space-between; gap:12px; margin-bottom:18px; }}
    .nav a {{ color:var(--accent); font-size:14px; font-weight:900; text-decoration:none; }}
    h1 {{ margin:0; font-size:24px; line-height:1.25; font-weight:900; }}
    .meta {{ margin-top:6px; color:var(--muted); font-size:13px; font-weight:700; }}
    .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin:20px 0 14px; }}
    .stat {{ min-height:72px; padding:12px 10px; border:1px solid var(--line); border-radius:var(--radius); background:#fbfcfa; }}
    .stat span {{ display:block; color:var(--muted); font-size:12px; font-weight:800; }}
    .stat strong {{ display:block; margin-top:5px; font-size:22px; line-height:1; font-weight:900; }}
    .toolbar {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px; margin:12px 0 18px; padding:12px; border:1px solid var(--line); border-radius:var(--radius); background:#fbfcfa; }}
    .toggle {{ display:inline-flex; align-items:center; gap:8px; color:var(--muted); font-size:14px; font-weight:850; }}
    .export {{ min-height:38px; border:1px solid var(--accent); border-radius:var(--radius); background:var(--accent); color:#fff; padding:8px 11px; font:inherit; font-size:13px; font-weight:900; }}
    .priority {{ margin:18px 0 14px; padding:14px; border:1px solid rgba(47,107,79,.18); border-radius:var(--radius); background:#f5faf6; }}
    .priority h2 {{ margin:0 0 10px; font-size:17px; font-weight:900; }}
    .priority-list {{ display:grid; gap:8px; }}
    .priority-item {{ padding:11px 12px; border:1px solid var(--line); border-radius:var(--radius); background:#fff; }}
    .priority-item strong {{ display:block; font-size:14px; }}
    .priority-item span {{ display:block; margin-top:3px; color:var(--muted); font-size:13px; font-weight:750; }}
    .list {{ display:grid; gap:12px; }}
    .card {{ border:1px solid var(--line); border-radius:var(--radius); background:#fff; overflow:hidden; }}
    .card.mastered {{ opacity:.62; }}
    .card-head {{ display:grid; grid-template-columns:1fr auto; gap:12px; padding:14px; border-bottom:1px solid var(--line); background:#fbfcfa; }}
    .topic {{ font-size:15px; font-weight:900; }}
    .sub {{ margin-top:3px; color:var(--muted); font-size:13px; font-weight:700; }}
    .master {{ display:inline-flex; align-items:center; gap:7px; color:var(--accent); font-size:13px; font-weight:900; white-space:nowrap; }}
    .body {{ padding:14px; }}
    .question {{ margin:0 0 12px; font-size:16px; font-weight:850; white-space:pre-line; }}
    .choices {{ display:grid; gap:7px; margin:10px 0 12px; }}
    .choice {{ display:grid; grid-template-columns:28px 1fr; gap:8px; padding:10px; border:1px solid var(--line); border-radius:var(--radius); background:#fff; font-size:14px; }}
    .choice.answer {{ border-color:var(--ok); background:var(--ok-soft); }}
    .choice.selected:not(.answer) {{ border-color:var(--danger); background:var(--danger-soft); }}
    .explanation {{ display:grid; gap:8px; margin-top:12px; }}
    .ex-row {{ padding:10px; border:1px solid rgba(23,32,26,.08); border-radius:var(--radius); background:#fbfcfa; }}
    .ex-row strong {{ display:block; margin-bottom:4px; color:var(--accent); font-size:13px; }}
    .ex-row span {{ color:#2c352f; font-size:14px; white-space:pre-line; }}
    .empty {{ padding:28px 14px; color:var(--muted); border:1px solid var(--line); border-radius:var(--radius); background:#fbfcfa; text-align:center; font-weight:800; }}
    textarea {{ width:100%; min-height:130px; margin-top:10px; padding:10px; border:1px solid var(--line); border-radius:var(--radius); font:inherit; font-size:13px; resize:vertical; }}
    @media (max-width:520px) {{ .stats {{ grid-template-columns:repeat(2,1fr); }} .card-head {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main>
    <div class="nav"><a href="index.html">데일리 퀴즈</a><a href="wrong-note.html">오답노트</a></div>
    <h1>건강운동관리사 오답노트</h1>
    <div class="meta">틀린 문제만 누적합니다. 숙지 완료 체크는 이 브라우저에 저장됩니다.</div>
    <section class="stats" id="stats"></section>
    <section class="priority" id="priority"></section>
    <section class="toolbar">
      <label class="toggle"><input type="checkbox" id="hideMastered"> 숙지 완료 숨기기</label>
      <button class="export" id="exportBtn" type="button">숙지 목록 복사</button>
    </section>
    <section class="list" id="list"></section>
    <textarea id="exportBox" readonly hidden></textarea>
  </main>
  <script id="wrong-note-data" type="application/json">{safe_data}</script>
  <script>
    const data = JSON.parse(document.getElementById('wrong-note-data').textContent);
    const circled = ['①','②','③','④','⑤'];
    const masteredKey = 'health-exercise-mastered';
    const list = document.getElementById('list');
    const stats = document.getElementById('stats');
    const priority = document.getElementById('priority');
    const hideMastered = document.getElementById('hideMastered');
    const exportBtn = document.getElementById('exportBtn');
    const exportBox = document.getElementById('exportBox');
    function loadMastered() {{
      try {{
        const local = JSON.parse(localStorage.getItem(masteredKey) || '[]');
        return new Set([].concat(data.mastered || [], local || []));
      }} catch (error) {{
        return new Set(data.mastered || []);
      }}
    }}
    function saveMastered(mastered) {{ localStorage.setItem(masteredKey, JSON.stringify(Array.from(mastered).sort())); }}
    function escapeHtml(value) {{ return String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#039;"); }}
    function groupedWrong() {{
      const byId = new Map();
      data.wrong.forEach(function(record) {{
        const current = byId.get(record.questionId);
        if (!current) {{ byId.set(record.questionId, Object.assign({{}}, record, {{ dates:[record.date], reasons:[record.wrongReason], attempts:[record] }})); return; }}
        current.dates.push(record.date);
        current.reasons.push(record.wrongReason);
        current.attempts.push(record);
        current.reviewRound = Math.max(current.reviewRound || 1, record.reviewRound || 1);
      }});
      return Array.from(byId.values()).sort(function(a, b) {{ return b.dates.join('').localeCompare(a.dates.join('')); }});
    }}
    function choiceExplanation(record, choiceIndex) {{
      if (Array.isArray(record.choiceExplanations) && record.choiceExplanations[choiceIndex]) return record.choiceExplanations[choiceIndex];
      if (choiceIndex === Number(record.answerIndex)) return '정답입니다. ' + (record.explanation || '최종정답 기준에 맞는 보기입니다.');
      return '오답입니다. ' + (record.trap || '문제 조건과 보기 표현을 분리해서 확인하세요.');
    }}
    function renderStats(items, mastered) {{
      const rows = [['누적 풀이', data.stats.attemptCount + '회'], ['누적 정답률', data.stats.accuracy + '%'], ['오답 문항', items.length + '개'], ['숙지 완료', mastered.size + '개']];
      stats.innerHTML = rows.map(function(row) {{ return '<div class="stat"><span>' + row[0] + '</span><strong>' + row[1] + '</strong></div>'; }}).join('');
    }}
    function renderPriority(items, mastered) {{
      const candidates = items.filter(function(item) {{ return !mastered.has(item.questionId); }}).slice().sort(function(a, b) {{
        const roundDiff = (b.reviewRound || 1) - (a.reviewRound || 1);
        if (roundDiff) return roundDiff;
        return b.dates.join('').localeCompare(a.dates.join(''));
      }}).slice(0, 3);
      if (!candidates.length) {{ priority.innerHTML = '<h2>오늘 복습 우선순위</h2><div class="priority-list"><div class="priority-item"><strong>누적 오답이 없습니다</strong><span>오늘 문제 풀이 후 자동으로 우선순위가 잡힙니다.</span></div></div>'; return; }}
      priority.innerHTML = '<h2>오늘 복습 우선순위</h2><div class="priority-list">' + candidates.map(function(item, index) {{
        return '<div class="priority-item"><strong>' + (index + 1) + '. ' + escapeHtml(item.topic || item.questionId) + '</strong><span>' + escapeHtml(item.subject) + ' · 회독 ' + (item.reviewRound || 1) + '회 · 최근 ' + escapeHtml(item.dates[item.dates.length - 1] || '') + '</span></div>';
      }}).join('') + '</div>';
    }}
    function renderList() {{
      const mastered = loadMastered();
      const items = groupedWrong();
      renderStats(items, mastered);
      renderPriority(items, mastered);
      const visible = hideMastered.checked ? items.filter(function(item) {{ return !mastered.has(item.questionId); }}) : items;
      if (!visible.length) {{ list.innerHTML = '<div class="empty">표시할 오답 문제가 없습니다.</div>'; return; }}
      list.innerHTML = visible.map(function(record) {{
        const isMastered = mastered.has(record.questionId);
        const selected = Number(record.selected) - 1;
        const answer = Number(record.answer) - 1;
        const choices = (record.choices || []).map(function(choice, index) {{
          const klass = 'choice ' + (index === answer ? 'answer ' : '') + (index === selected ? 'selected' : '');
          return '<div class="' + klass + '"><strong>' + (circled[index] || index + 1) + '</strong><span>' + escapeHtml(choice) + '</span></div>';
        }}).join('');
        const ex = (record.choices || []).map(function(choice, index) {{
          return '<div class="ex-row"><strong>' + (circled[index] || index + 1) + ' ' + (index === answer ? '정답' : '오답') + '</strong><span>' + escapeHtml(choiceExplanation(record, index)) + '</span></div>';
        }}).join('');
        return '<article class="card ' + (isMastered ? 'mastered' : '') + '"><div class="card-head"><div><div class="topic">' + escapeHtml(record.topic || record.questionId) + '</div><div class="sub">' + escapeHtml(record.subject) + ' · 틀린 날짜 ' + record.dates.map(escapeHtml).join(', ') + ' · 회독 ' + (record.reviewRound || 1) + '회 · 이유 ' + escapeHtml(record.reasons.join(', ')) + '</div></div><label class="master"><input type="checkbox" class="masteredBox" data-id="' + escapeHtml(record.questionId) + '"' + (isMastered ? ' checked' : '') + '> 숙지 완료</label></div><div class="body"><p class="question">' + escapeHtml(record.question || record.questionId) + '</p><div class="choices">' + choices + '</div><div class="explanation">' + ex + '</div></div></article>';
      }}).join('');
      list.querySelectorAll('.masteredBox').forEach(function(box) {{
        box.addEventListener('change', function() {{
          const next = loadMastered();
          if (box.checked) next.add(box.dataset.id); else next.delete(box.dataset.id);
          saveMastered(next);
          renderList();
        }});
      }});
    }}
    exportBtn.addEventListener('click', async function() {{
      const mastered = Array.from(loadMastered()).sort();
      const text = ['[HEALTH_EXERCISE_MASTERED]'].concat(mastered.map(function(id) {{ return 'mastered=' + id; }}), ['[/HEALTH_EXERCISE_MASTERED]']).join('\\n');
      exportBox.hidden = false;
      exportBox.value = text;
      exportBox.select();
      try {{ await navigator.clipboard.writeText(text); exportBtn.textContent = '복사 완료'; }} catch (error) {{ document.execCommand('copy'); exportBtn.textContent = '선택됨'; }}
    }});
    hideMastered.addEventListener('change', renderList);
    renderList();
  </script>
</body>
</html>
"""


def main():
    data = build_data()
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    WRONG_NOTE_HTML.write_text(render_html(data), encoding="utf-8")
    print(REVIEW_JSON)
    print(WRONG_NOTE_HTML)


if __name__ == "__main__":
    main()
