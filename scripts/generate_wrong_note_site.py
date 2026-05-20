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
  <title>소빵이의 오답노트</title>
  <style>
    :root {{ --bg:#f3f5f0; --surface:#fff; --ink:#17201a; --muted:#69736c; --line:#dfe5dc; --accent:#2f6b4f; --accent-dark:#214735; --danger:#b64032; --danger-soft:#f8e8e5; --ok:#287a4b; --ok-soft:#e4f3e9; --sage:#e9eee4; --radius:8px; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif; line-height:1.5; letter-spacing:0; }}
    main {{ width:min(820px,100%); min-height:100svh; margin:0 auto; padding:22px 16px 32px; background:var(--surface); border-left:1px solid rgba(23,32,26,.06); border-right:1px solid rgba(23,32,26,.06); }}
    .topline {{ display:flex; align-items:flex-start; justify-content:space-between; gap:14px; margin-bottom:16px; }}
    .back {{ color:var(--accent); font-size:13px; font-weight:950; text-decoration:none; white-space:nowrap; transform:translateY(4px); }}
    h1 {{ margin:0; color:var(--accent-dark); font-size:28px; line-height:1.15; font-weight:950; }}
    .stats {{ display:flex; flex-wrap:wrap; gap:7px; margin:2px 0 16px; }}
    .stat {{ display:inline-flex; align-items:center; gap:5px; min-height:29px; padding:5px 9px; border:1px solid rgba(102,115,93,.18); border-radius:999px; background:#fbfcfa; }}
    .stat span {{ color:var(--muted); font-size:11.5px; font-weight:850; }}
    .stat strong {{ color:var(--accent-dark); font-size:12.5px; line-height:1; font-weight:950; }}
    .priority {{ margin:14px 0 14px; padding:14px; border:1px solid rgba(47,107,79,.22); border-left:3px solid var(--accent); border-radius:13px; background:linear-gradient(135deg, rgba(233,238,228,.78), rgba(255,255,255,.76)); box-shadow:0 8px 20px rgba(36,37,34,.04); }}
    .priority h2 {{ margin:0 0 10px; color:var(--accent-dark); font-size:18px; font-weight:950; }}
    .priority-list {{ display:grid; gap:8px; }}
    .priority-item {{ display:block; padding:12px; border:1px solid rgba(102,115,93,.2); border-radius:10px; background:#fff; color:var(--ink); text-decoration:none; }}
    .priority-item strong {{ display:block; font-size:14px; font-weight:950; }}
    .priority-item span {{ display:block; margin-top:3px; color:var(--muted); font-size:12.5px; font-weight:800; }}
    .list {{ display:grid; gap:12px; }}
    .card {{ border:1px solid var(--line); border-radius:13px; background:#fff; overflow:hidden; scroll-margin-top:14px; }}
    details.card summary {{ list-style:none; cursor:pointer; }}
    details.card summary::-webkit-details-marker {{ display:none; }}
    .open-hint {{ margin-top:8px; color:var(--accent); font-size:13px; font-weight:950; }}
    .card.mastered {{ opacity:.62; }}
    .card-head {{ display:block; padding:14px; border-bottom:1px solid var(--line); background:#fbfcfa; }}
    .topic {{ font-size:15px; font-weight:950; }}
    .sub {{ margin-top:3px; color:var(--muted); font-size:13px; font-weight:700; }}
    .review-controls {{ display:grid; grid-template-columns:1fr auto; gap:10px; align-items:center; margin:0 0 12px; padding:10px; border:1px solid rgba(102,115,93,.16); border-radius:12px; background:#fbfcfa; }}
    .importance {{ display:inline-flex; align-items:center; gap:3px; width:max-content; padding:3px; border:1px solid rgba(102,115,93,.2); border-radius:999px; background:#fff; }}
    .importance-label {{ margin-right:3px; color:var(--muted); font-size:11px; font-weight:900; }}
    .importance button {{ min-width:28px; min-height:26px; border:0; border-radius:999px; background:transparent; color:var(--muted); font:inherit; font-size:12px; font-weight:950; }}
    .importance button.active {{ background:var(--accent); color:#fff; }}
    .master-toggle {{ min-height:34px; padding:6px 10px; border:1px solid rgba(102,115,93,.22); border-radius:999px; background:#fff; color:var(--accent); font:inherit; font-size:12.5px; font-weight:950; white-space:nowrap; }}
    .master-toggle.active {{ background:var(--sage); color:var(--accent-dark); }}
    .body {{ padding:14px; }}
    .question {{ margin:0 0 12px; font-size:16px; font-weight:850; white-space:pre-line; }}
    .choices {{ display:grid; gap:7px; margin:10px 0 12px; }}
    .choice {{ display:grid; grid-template-columns:28px 1fr auto; gap:8px; align-items:center; padding:10px; border:1px solid var(--line); border-radius:var(--radius); background:#fff; font-size:14px; cursor:pointer; }}
    .choice strong {{ align-self:start; }}
    .choice.answer {{ border-color:var(--ok); background:var(--ok-soft); }}
    .choice.selected:not(.answer) {{ border-color:var(--danger); background:var(--danger-soft); }}
    .choice-check {{ min-width:38px; min-height:38px; border:1px solid rgba(102,115,93,.28); border-radius:10px; background:#fff; color:var(--muted); font:inherit; font-size:18px; font-weight:950; }}
    .choice-check.active {{ border-color:var(--accent); background:var(--sage); color:var(--accent-dark); }}
    .explain-toggle {{ width:100%; min-height:42px; margin-top:8px; border:0; border-radius:10px; background:var(--accent); color:#fff; font:inherit; font-size:14px; font-weight:950; }}
    .explanation {{ display:grid; gap:8px; margin-top:12px; }}
    .explanation[hidden] {{ display:none; }}
    .ex-row {{ padding:10px; border:1px solid rgba(23,32,26,.08); border-radius:var(--radius); background:#fbfcfa; }}
    .ex-row strong {{ display:block; margin-bottom:4px; color:var(--accent); font-size:13px; }}
    .ex-row span {{ color:#2c352f; font-size:14px; white-space:pre-line; }}
    .empty {{ padding:28px 14px; color:var(--muted); border:1px solid var(--line); border-radius:var(--radius); background:#fbfcfa; text-align:center; font-weight:800; }}
    textarea {{ width:100%; min-height:130px; margin-top:10px; padding:10px; border:1px solid var(--line); border-radius:var(--radius); font:inherit; font-size:13px; resize:vertical; }}
    @media (max-width:520px) {{ main {{ padding:18px 12px 28px; }} h1 {{ font-size:25px; }} .back {{ font-size:12px; }} .stats {{ margin-bottom:15px; }} .stat {{ min-height:27px; padding:4px 8px; }} .priority {{ padding:13px 12px; }} .priority h2 {{ font-size:17px; }} .card-head {{ padding:13px; }} .review-controls {{ grid-template-columns:1fr; gap:8px; }} .body {{ padding:13px; }} .question {{ font-size:15.5px; }} .choice {{ grid-template-columns:26px 1fr 38px; padding:9px; }} }}
  </style>
</head>
<body>
  <main>
    <div class="topline"><h1>소빵이의 오답노트</h1><a class="back" href="index.html">Dashboard</a></div>
    <section class="stats" id="stats"></section>
    <section class="priority" id="priority"></section>
    <section class="list" id="list"></section>
  </main>
  <script id="wrong-note-data" type="application/json">{safe_data}</script>
  <script>
    const data = JSON.parse(document.getElementById('wrong-note-data').textContent);
    const circled = ['①','②','③','④','⑤'];
    const masteredKey = 'health-exercise-mastered';
    const list = document.getElementById('list');
    const stats = document.getElementById('stats');
    const priority = document.getElementById('priority');
    const importanceKey = 'health-exercise-importance';
    const choiceFlagKey = 'health-exercise-choice-flags';
    const importanceRank = {{ high: 3, mid: 2, low: 1 }};
    const importanceLabel = {{ high: '상', mid: '중', low: '하' }};
    function loadMastered() {{
      try {{
        const local = JSON.parse(localStorage.getItem(masteredKey) || '[]');
        return new Set([].concat(data.mastered || [], local || []));
      }} catch (error) {{
        return new Set(data.mastered || []);
      }}
    }}
    function saveMastered(mastered) {{ localStorage.setItem(masteredKey, JSON.stringify(Array.from(mastered).sort())); }}
    function loadMap(key) {{
      try {{ return JSON.parse(localStorage.getItem(key) || '{{}}') || {{}}; }} catch (error) {{ return {{}}; }}
    }}
    function saveMap(key, value) {{ localStorage.setItem(key, JSON.stringify(value)); }}
    function defaultImportance(item) {{ return (item.reviewRound || 1) > 1 ? 'high' : 'mid'; }}
    function loadImportance() {{ return loadMap(importanceKey); }}
    function saveImportance(value) {{ saveMap(importanceKey, value); }}
    function loadChoiceFlags() {{ return loadMap(choiceFlagKey); }}
    function saveChoiceFlags(value) {{ saveMap(choiceFlagKey, value); }}
    function escapeHtml(value) {{ return String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#039;"); }}
    function anchorId(value) {{ return 'wrong-' + String(value ?? '').replace(/[^a-zA-Z0-9_-]/g, '-'); }}
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
      const rows = [['틀린 문제', items.length + '개'], ['숙지 완료', mastered.size + '개'], ['전체 정답률', data.stats.accuracy + '%']];
      stats.innerHTML = rows.map(function(row) {{ return '<div class="stat"><span>' + row[0] + '</span><strong>' + row[1] + '</strong></div>'; }}).join('');
    }}
    function renderPriority(items, mastered) {{
      const importance = loadImportance();
      const candidates = items.filter(function(item) {{ return !mastered.has(item.questionId); }}).slice().sort(function(a, b) {{
        const aImportance = importance[a.questionId] || defaultImportance(a);
        const bImportance = importance[b.questionId] || defaultImportance(b);
        const importanceDiff = importanceRank[bImportance] - importanceRank[aImportance];
        if (importanceDiff) return importanceDiff;
        const roundDiff = (b.reviewRound || 1) - (a.reviewRound || 1);
        if (roundDiff) return roundDiff;
        return b.dates.join('').localeCompare(a.dates.join(''));
      }}).slice(0, 3);
      if (!candidates.length) {{ priority.innerHTML = '<h2>오늘 복습할 문제 3개</h2><div class="priority-list"><div class="priority-item"><strong>틀린 문제가 없습니다</strong><span>오늘 문제를 풀면 자동으로 정리됩니다.</span></div></div>'; return; }}
      priority.innerHTML = '<h2>오늘 복습할 문제 3개</h2><div class="priority-list">' + candidates.map(function(item, index) {{
        return '<a class="priority-item" href="#' + anchorId(item.questionId) + '"><strong>' + (index + 1) + '. ' + escapeHtml(item.topic || item.questionId) + '</strong><span>' + escapeHtml(item.subject) + ' · 문제 먼저 풀어보기</span></a>';
      }}).join('') + '</div>';
    }}
    function renderList() {{
      const mastered = loadMastered();
      const importance = loadImportance();
      const choiceFlags = loadChoiceFlags();
      const items = groupedWrong();
      renderStats(items, mastered);
      renderPriority(items, mastered);
      const visible = items;
      if (!visible.length) {{ list.innerHTML = '<div class="empty">표시할 오답 문제가 없습니다.</div>'; return; }}
      list.innerHTML = visible.map(function(record) {{
        const isMastered = mastered.has(record.questionId);
        const currentImportance = importance[record.questionId] || defaultImportance(record);
        const flagged = new Set(choiceFlags[record.questionId] || []);
        const answer = Number(record.answer) - 1;
        const choices = (record.choices || []).map(function(choice, index) {{
          const checked = flagged.has(String(index));
          return '<div class="choice" role="button" tabindex="0" data-answer="' + answer + '" data-index="' + index + '"><strong>' + (circled[index] || index + 1) + '</strong><span>' + escapeHtml(choice) + '</span><button class="choice-check ' + (checked ? 'active' : '') + '" type="button" data-id="' + escapeHtml(record.questionId) + '" data-choice="' + index + '" aria-pressed="' + (checked ? 'true' : 'false') + '">' + (checked ? '☑' : '☐') + '</button></div>';
        }}).join('');
        const ex = (record.choices || []).map(function(choice, index) {{
          return '<div class="ex-row"><strong>' + (circled[index] || index + 1) + ' ' + (index === answer ? '정답' : '오답') + '</strong><span>' + escapeHtml(choiceExplanation(record, index)) + '</span></div>';
        }}).join('');
        const importanceButtons = ['high','mid','low'].map(function(level) {{
          return '<button type="button" class="' + (currentImportance === level ? 'active' : '') + '" data-id="' + escapeHtml(record.questionId) + '" data-importance="' + level + '">' + importanceLabel[level] + '</button>';
        }}).join('');
        return '<details class="card ' + (isMastered ? 'mastered' : '') + '" id="' + anchorId(record.questionId) + '"><summary class="card-head"><div class="topic">' + escapeHtml(record.topic || record.questionId) + '</div><div class="sub">' + escapeHtml(record.subject) + ' · 복습 ' + (record.reviewRound || 1) + '회</div><div class="open-hint">문제 보기</div></summary><div class="body"><div class="review-controls"><div class="importance"><span class="importance-label">중요도</span>' + importanceButtons + '</div><button class="master-toggle ' + (isMastered ? 'active' : '') + '" type="button" data-id="' + escapeHtml(record.questionId) + '">' + (isMastered ? '숙지 완료됨' : '숙지 완료') + '</button></div><p class="question">' + escapeHtml(record.question || record.questionId) + '</p><div class="choices">' + choices + '</div><button class="explain-toggle" type="button">해설 보기</button><div class="explanation" hidden>' + ex + '</div></div></details>';
      }}).join('');
      list.querySelectorAll('.importance button').forEach(function(button) {{
        button.addEventListener('click', function(event) {{
          event.preventDefault();
          event.stopPropagation();
          const next = loadImportance();
          next[button.dataset.id] = button.dataset.importance;
          saveImportance(next);
          renderList();
        }});
      }});
      list.querySelectorAll('.choice').forEach(function(choice) {{
        choice.addEventListener('click', function() {{
          const card = choice.closest('.card');
          const answer = Number(choice.dataset.answer);
          const picked = Number(choice.dataset.index);
          card.querySelectorAll('.choice').forEach(function(row) {{
            const rowIndex = Number(row.dataset.index);
            row.classList.toggle('answer', rowIndex === answer);
            row.classList.toggle('selected', rowIndex === picked);
          }});
          const explanation = card.querySelector('.explanation');
          const button = card.querySelector('.explain-toggle');
          if (explanation) explanation.removeAttribute('hidden');
          if (button) button.textContent = '해설 숨김';
        }});
      }});
      list.querySelectorAll('.choice-check').forEach(function(button) {{
        button.addEventListener('click', function(event) {{
          event.preventDefault();
          event.stopPropagation();
          const next = loadChoiceFlags();
          const id = button.dataset.id;
          const choice = button.dataset.choice;
          const set = new Set(next[id] || []);
          if (set.has(choice)) set.delete(choice); else set.add(choice);
          next[id] = Array.from(set).sort();
          if (!next[id].length) delete next[id];
          saveChoiceFlags(next);
          renderList();
        }});
      }});
      list.querySelectorAll('.explain-toggle').forEach(function(button) {{
        button.addEventListener('click', function() {{
          const explanation = button.nextElementSibling;
          const isHidden = explanation.hasAttribute('hidden');
          if (isHidden) {{
            explanation.removeAttribute('hidden');
            button.textContent = '해설 숨김';
          }} else {{
            explanation.setAttribute('hidden', '');
            button.textContent = '해설 보기';
          }}
        }});
      }});
      list.querySelectorAll('.master-toggle').forEach(function(box) {{
        box.addEventListener('click', function(event) {{
          event.preventDefault();
          event.stopPropagation();
          const next = loadMastered();
          if (next.has(box.dataset.id)) next.delete(box.dataset.id); else next.add(box.dataset.id);
          saveMastered(next);
          renderList();
        }});
      }});
      priority.querySelectorAll('a[href^="#wrong-"]').forEach(function(link) {{
        link.addEventListener('click', function() {{
          const card = document.querySelector(link.getAttribute('href'));
          if (card) {{
            card.open = true;
            const explanation = card.querySelector('.explanation');
            const button = card.querySelector('.explain-toggle');
            if (explanation) explanation.setAttribute('hidden', '');
            if (button) button.textContent = '해설 보기';
            setTimeout(function() {{ card.scrollIntoView({{ behavior: 'smooth', block: 'start' }}); }}, 0);
          }}
        }});
      }});
    }}
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
