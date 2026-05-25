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
REVIEW_STATE_JSON = REVIEW_DIR / "review-state.json"
WRONG_NOTE_HTML = ROOT / "wrong-note.html"
CONFIG_PATH = ROOT / "config" / "sync.json"


def read_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_json_safe(path, fallback):
    if not path.exists():
        return fallback
    try:
        return read_json(path)
    except json.JSONDecodeError:
        return fallback


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
    if isinstance(value, str) and "," in value:
        return ", ".join(choice_label(item.strip()) for item in value.split(",") if item.strip())
    try:
        return labels[int(value) - 1]
    except (TypeError, ValueError, IndexError):
        return str(value)


def build_data():
    attempts = read_jsonl(ATTEMPTS_PATH)
    mastered = read_json(MASTERED_PATH) if MASTERED_PATH.exists() else []
    sync_config = read_json_safe(CONFIG_PATH, {})
    review_state = read_json_safe(REVIEW_STATE_JSON, {
        "importance": {},
        "mastered": [],
        "choiceFlags": {},
        "updatedAt": {},
    })
    questions = load_question_map()
    total_score = sum(int(attempt.get("score", 0)) for attempt in attempts)
    total_questions = sum(int(attempt.get("total", 0)) for attempt in attempts)
    wrong_rounds = Counter()
    wrong = []
    review = []
    objections = []

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
        seen_objections = set()
        for item in attempt.get("objections", []):
            question_id = item.get("questionId", "")
            if not question_id or question_id in seen_objections:
                continue
            seen_objections.add(question_id)
            question = questions.get(question_id, {})
            objections.append({
                "date": date,
                "quizId": attempt.get("quizId", ""),
                "subject": question.get("subject", attempt.get("subject", "")),
                "questionId": question_id,
                "topic": item.get("topic") or question.get("topic", ""),
                "selected": item.get("selected", "none"),
                "selectedLabel": choice_label(item.get("selected")),
                "answer": item.get("answer", ""),
                "answerLabel": choice_label(item.get("answer")),
                "reason": item.get("reason", "user_flagged"),
                "question": question.get("question", ""),
                "choices": question.get("choices", []),
                "answerIndex": question.get("answerIndex"),
                "explanation": question.get("explanation", ""),
                "trap": question.get("trap", ""),
                "choiceExplanations": question.get("choiceExplanations", []),
                "status": "검토 대기",
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
            "objectionCount": len(objections),
            "masteredCount": len(set(mastered) | set(review_state.get("mastered", []))),
        },
        "mastered": sorted(set(mastered) | set(review_state.get("mastered", []))),
        "reviewState": {
            "importance": review_state.get("importance", {}),
            "mastered": sorted(set(review_state.get("mastered", []))),
            "choiceFlags": review_state.get("choiceFlags", {}),
            "updatedAt": review_state.get("updatedAt", {}),
        },
        "syncConfig": {
            "enabled": bool(sync_config.get("enabled")),
            "submitUrl": sync_config.get("submitUrl", ""),
        },
        "wrong": wrong,
        "review": review,
        "objections": objections,
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
    .priority, .objection-panel {{ margin:14px 0 14px; padding:14px; border:1px solid rgba(47,107,79,.22); border-left:3px solid var(--accent); border-radius:13px; background:linear-gradient(135deg, rgba(233,238,228,.78), rgba(255,255,255,.76)); box-shadow:0 8px 20px rgba(36,37,34,.04); }}
    .priority h2 {{ margin:0 0 10px; color:var(--accent-dark); font-size:18px; font-weight:950; }}
    .objection-panel {{ border-color:rgba(161,107,24,.24); border-left-color:#a16b18; background:linear-gradient(135deg, rgba(255,243,220,.82), rgba(255,255,255,.80)); }}
    .objection-panel h2 {{ margin:0 0 8px; color:#7d5113; font-size:18px; font-weight:950; }}
    .objection-panel p {{ margin:0 0 10px; color:#705323; font-size:13px; line-height:1.5; font-weight:800; }}
    .objection-list {{ display:grid; gap:8px; }}
    .objection-item {{ display:block; padding:12px; border:1px solid rgba(161,107,24,.22); border-radius:10px; background:#fff; color:var(--ink); text-decoration:none; }}
    .objection-item strong {{ display:block; font-size:14px; font-weight:950; }}
    .objection-item span {{ display:block; margin-top:3px; color:#705323; font-size:12.5px; font-weight:800; }}
    .priority-list {{ display:grid; gap:8px; }}
    .priority-item {{ display:block; padding:12px; border:1px solid rgba(102,115,93,.2); border-radius:10px; background:#fff; color:var(--ink); text-decoration:none; }}
    .priority-item strong {{ display:block; font-size:14px; font-weight:950; }}
    .priority-item span {{ display:block; margin-top:3px; color:var(--muted); font-size:12.5px; font-weight:800; }}
    .list {{ display:grid; gap:12px; }}
    .list-head {{ display:flex; align-items:center; justify-content:space-between; margin:2px 2px -2px; color:var(--accent-dark); font-size:16px; font-weight:950; }}
    .list-head span {{ color:var(--muted); font-size:12px; font-weight:850; }}
    .card {{ border:1px solid var(--line); border-radius:13px; background:#fff; overflow:hidden; scroll-margin-top:14px; }}
    details.card summary {{ list-style:none; cursor:pointer; }}
    details.card summary::-webkit-details-marker {{ display:none; }}
    .open-hint {{ margin-top:8px; color:var(--accent); font-size:13px; font-weight:950; }}
    .card.mastered {{ opacity:.62; }}
    .card-head {{ display:block; padding:14px; border-bottom:1px solid var(--line); background:#fbfcfa; }}
    .topic {{ font-size:15px; font-weight:950; }}
    .sub {{ margin-top:3px; color:var(--muted); font-size:13px; font-weight:700; }}
    .review-controls {{ display:flex; align-items:center; justify-content:space-between; gap:9px; margin:0 0 10px; padding:8px; border:1px solid rgba(102,115,93,.14); border-radius:14px; background:#fbfcfa; }}
    .importance {{ display:grid; grid-template-columns:auto repeat(3, minmax(40px, 1fr)); align-items:center; gap:7px; flex:1 1 auto; min-width:0; padding:5px 6px 5px 10px; border:1px solid rgba(102,115,93,.18); border-radius:999px; background:#fff; }}
    .importance-label {{ margin:0 3px 0 0; color:var(--ink); font-size:12px; font-weight:950; white-space:nowrap; }}
    .importance button {{ min-width:40px; min-height:34px; border:0; border-radius:999px; background:transparent; color:var(--muted); font:inherit; font-size:13px; font-weight:950; }}
    .importance button.active {{ background:var(--accent); color:#fff; }}
    .master-toggle {{ flex:0 0 auto; min-height:42px; padding:8px 12px; border:1px solid rgba(102,115,93,.22); border-radius:999px; background:#fff; color:var(--accent); font:inherit; font-size:12px; font-weight:950; white-space:nowrap; }}
    .master-toggle.active {{ background:var(--sage); color:var(--accent-dark); }}
    .body {{ padding:14px; }}
    .question {{ margin:0 0 11px; font-size:15.2px; font-weight:850; line-height:1.46; white-space:pre-line; word-break:keep-all; overflow-wrap:anywhere; }}
    .choices {{ display:grid; gap:7px; margin:10px 0 12px; }}
    .choice {{ display:grid; grid-template-columns:24px 1fr 38px; gap:7px; align-items:center; padding:9px; border:1px solid var(--line); border-radius:var(--radius); background:#fff; font-size:13.4px; line-height:1.38; cursor:pointer; }}
    .choice strong {{ align-self:start; }}
    .choice span {{ transition:color .15s ease, text-decoration-color .15s ease; }}
    .choice.answer {{ border-color:var(--ok); background:var(--ok-soft); }}
    .choice.selected:not(.answer) {{ border-color:var(--danger); background:var(--danger-soft); }}
    .choice.flagged {{ border-color:rgba(176,65,65,.28); background:#fff3f1; }}
    .choice.flagged strong {{ color:#b04141; opacity:.72; }}
    .choice.flagged span {{ color:rgba(57,43,37,.58); text-decoration:line-through; text-decoration-thickness:1.5px; text-decoration-color:rgba(176,65,65,.55); }}
    .choice-check {{ width:38px; min-width:38px; min-height:38px; border:1px solid rgba(102,115,93,.28); border-radius:11px; background:#fff; color:var(--muted); font:inherit; font-size:18px; font-weight:950; }}
    .choice-check.active {{ border-color:#b04141; background:#ffe4df; color:#b04141; }}
    .explain-toggle {{ width:100%; min-height:42px; margin-top:8px; border:0; border-radius:10px; background:var(--accent); color:#fff; font:inherit; font-size:14px; font-weight:950; }}
    .explanation {{ display:grid; gap:8px; margin-top:12px; }}
    .explanation[hidden] {{ display:none; }}
    .ex-row {{ padding:10px; border:1px solid rgba(23,32,26,.08); border-radius:var(--radius); background:#fbfcfa; }}
    .ex-row strong {{ display:block; margin-bottom:4px; color:var(--accent); font-size:13px; }}
    .ex-row span {{ color:#2c352f; font-size:14px; white-space:pre-line; }}
    .empty {{ padding:28px 14px; color:var(--muted); border:1px solid var(--line); border-radius:var(--radius); background:#fbfcfa; text-align:center; font-weight:800; }}
    textarea {{ width:100%; min-height:130px; margin-top:10px; padding:10px; border:1px solid var(--line); border-radius:var(--radius); font:inherit; font-size:13px; resize:vertical; }}
    @media (max-width:520px) {{ main {{ padding:18px 12px 28px; }} h1 {{ font-size:25px; }} .back {{ font-size:12px; }} .stats {{ margin-bottom:15px; }} .stat {{ min-height:27px; padding:4px 8px; }} .priority {{ padding:13px 12px; }} .priority h2 {{ font-size:17px; }} .card-head {{ padding:13px; }} .body {{ padding:13px; }} .review-controls {{ gap:7px; padding:7px; }} .importance {{ grid-template-columns:auto repeat(3, minmax(36px, 1fr)); gap:6px; padding-left:9px; }} .importance button {{ min-width:36px; min-height:34px; }} .master-toggle {{ min-height:40px; padding:7px 10px; }} .question {{ font-size:14.6px; }} .choice {{ grid-template-columns:23px 1fr 38px; padding:8px 9px; font-size:13px; }} }}
  </style>
</head>
<body>
  <main>
    <div class="topline"><h1>소빵이의 오답노트</h1><a class="back" href="index.html">Dashboard</a></div>
    <section class="stats" id="stats"></section>
    <section class="priority" id="priority"></section>
    <section class="objection-panel" id="objections" hidden></section>
    <section class="list" id="list"></section>
  </main>
  <script id="wrong-note-data" type="application/json">{safe_data}</script>
  <script>
    const data = JSON.parse(document.getElementById('wrong-note-data').textContent);
    const syncConfig = data.syncConfig || {{}};
    const circled = ['①','②','③','④','⑤'];
    const masteredKey = 'health-exercise-mastered';
    const list = document.getElementById('list');
    const stats = document.getElementById('stats');
    const priority = document.getElementById('priority');
    const objections = document.getElementById('objections');
    const importanceKey = 'health-exercise-importance';
    const choiceFlagKey = 'health-exercise-choice-flags';
    const localUpdatedSuffix = ':updated';
    const importanceRank = {{ high: 3, mid: 2, low: 1 }};
    const importanceLabel = {{ high: '상', mid: '중', low: '하' }};
    function loadMastered() {{
      try {{
        const local = JSON.parse(localStorage.getItem(masteredKey) || '[]');
        return new Set([].concat(data.mastered || [], (data.reviewState || {{}}).mastered || [], local || []));
      }} catch (error) {{
        return new Set([].concat(data.mastered || [], (data.reviewState || {{}}).mastered || []));
      }}
    }}
    function saveMastered(mastered) {{ localStorage.setItem(masteredKey, JSON.stringify(Array.from(mastered).sort())); }}
    function loadMap(key, serverValue) {{
      const base = Object.assign({{}}, serverValue || {{}});
      const serverUpdated = ((data.reviewState || {{}}).updatedAt || {{}});
      try {{
        const local = JSON.parse(localStorage.getItem(key) || '{{}}') || {{}};
        const localUpdated = JSON.parse(localStorage.getItem(key + localUpdatedSuffix) || '{{}}') || {{}};
        Object.keys(local).forEach(function(id) {{
          const localTime = Date.parse(localUpdated[id] || '');
          const serverTime = Date.parse(serverUpdated[id] || '');
          if (!serverUpdated[id] || localTime > serverTime) base[id] = local[id];
        }});
        return base;
      }} catch (error) {{ return base; }}
    }}
    function saveMap(key, value, touchedId) {{
      localStorage.setItem(key, JSON.stringify(value));
      if (touchedId) {{
        let localUpdated = {{}};
        try {{ localUpdated = JSON.parse(localStorage.getItem(key + localUpdatedSuffix) || '{{}}') || {{}}; }} catch (error) {{}}
        localUpdated[touchedId] = new Date().toISOString();
        localStorage.setItem(key + localUpdatedSuffix, JSON.stringify(localUpdated));
      }}
    }}
    function postReviewState(questionId, patch) {{
      if (!syncConfig.enabled || !syncConfig.submitUrl) return;
      const payload = Object.assign({{
        source: 'so0258house',
        kind: 'reviewState',
        submittedAt: new Date().toISOString(),
        questionId: questionId
      }}, patch || {{}});
      try {{
        fetch(syncConfig.submitUrl, {{
          method: 'POST',
          mode: 'no-cors',
          headers: {{ 'Content-Type': 'text/plain;charset=utf-8' }},
          body: JSON.stringify(payload)
        }}).catch(function() {{}});
      }} catch (error) {{}}
    }}
    function defaultImportance(item) {{ return (item.reviewRound || 1) > 1 ? 'high' : 'mid'; }}
    function loadImportance() {{ return loadMap(importanceKey, (data.reviewState || {{}}).importance); }}
    function saveImportance(value, touchedId) {{ saveMap(importanceKey, value, touchedId); }}
    function loadChoiceFlags() {{ return loadMap(choiceFlagKey, (data.reviewState || {{}}).choiceFlags); }}
    function saveChoiceFlags(value, touchedId) {{ saveMap(choiceFlagKey, value, touchedId); }}
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
      const rows = [['틀린 문제', items.length + '개'], ['이의제기', (data.objections || []).length + '개'], ['숙지 완료', mastered.size + '개']];
      stats.innerHTML = rows.map(function(row) {{ return '<div class="stat"><span>' + row[0] + '</span><strong>' + row[1] + '</strong></div>'; }}).join('');
    }}
    function renderObjections() {{
      const items = data.objections || [];
      if (!items.length) {{ objections.hidden = true; objections.innerHTML = ''; return; }}
      objections.hidden = false;
      objections.innerHTML = '<h2>이의제기 문제</h2><p>사용자가 답안 또는 해설 확인을 요청한 문항입니다. 별도 검수 후 피드백 대상으로 분류됩니다.</p><div class="objection-list">' + items.map(function(item, index) {{
        return '<div class="objection-item"><strong>' + (index + 1) + '. ' + escapeHtml(item.topic || item.questionId) + '</strong><span>' + escapeHtml(item.subject || '') + ' · ' + escapeHtml(item.date || '') + ' · ' + escapeHtml(item.status || '검토 대기') + ' · 내 답 ' + escapeHtml(item.selectedLabel || item.selected || '미응답') + ' / 정답 ' + escapeHtml(item.answerLabel || item.answer || '') + '</span><span>' + escapeHtml(item.question || item.questionId) + '</span></div>';
      }}).join('') + '</div>';
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
      if (!candidates.length) {{ priority.innerHTML = '<h2>오늘 복습할 문제</h2><div class="priority-list"><div class="priority-item"><strong>틀린 문제가 없습니다</strong><span>오늘 문제를 풀면 자동으로 정리됩니다.</span></div></div>'; return; }}
      priority.innerHTML = '<h2>오늘 복습할 문제</h2><div class="priority-list">' + candidates.map(function(item, index) {{
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
      renderObjections();
      const visible = items;
      if (!visible.length) {{ list.innerHTML = '<div class="empty">표시할 오답 문제가 없습니다.</div>'; return; }}
      const cards = visible.map(function(record) {{
        const isMastered = mastered.has(record.questionId);
        const currentImportance = importance[record.questionId] || defaultImportance(record);
        const flagged = new Set(choiceFlags[record.questionId] || []);
        const answer = Number(record.answer) - 1;
        const choices = (record.choices || []).map(function(choice, index) {{
          const checked = flagged.has(String(index));
          return '<div class="choice ' + (checked ? 'flagged' : '') + '" role="button" tabindex="0" data-answer="' + answer + '" data-index="' + index + '"><strong>' + (circled[index] || index + 1) + '</strong><span>' + escapeHtml(choice) + '</span><button class="choice-check ' + (checked ? 'active' : '') + '" type="button" data-id="' + escapeHtml(record.questionId) + '" data-choice="' + index + '" aria-pressed="' + (checked ? 'true' : 'false') + '" aria-label="보기 소거 표시">' + (checked ? '☑' : '☐') + '</button></div>';
        }}).join('');
        const ex = (record.choices || []).map(function(choice, index) {{
          return '<div class="ex-row"><strong>' + (circled[index] || index + 1) + ' ' + (index === answer ? '정답' : '오답') + '</strong><span>' + escapeHtml(choiceExplanation(record, index)) + '</span></div>';
        }}).join('');
        const importanceButtons = ['high','mid','low'].map(function(level) {{
          return '<button type="button" class="' + (currentImportance === level ? 'active' : '') + '" data-id="' + escapeHtml(record.questionId) + '" data-importance="' + level + '">' + importanceLabel[level] + '</button>';
        }}).join('');
        return '<details class="card ' + (isMastered ? 'mastered' : '') + '" id="' + anchorId(record.questionId) + '"><summary class="card-head"><div class="topic">' + escapeHtml(record.topic || record.questionId) + '</div><div class="sub">' + escapeHtml(record.subject) + ' · 복습 ' + (record.reviewRound || 1) + '회</div><div class="open-hint">문제 보기</div></summary><div class="body"><div class="review-controls"><div class="importance"><span class="importance-label">중요도</span>' + importanceButtons + '</div><button class="master-toggle ' + (isMastered ? 'active' : '') + '" type="button" data-id="' + escapeHtml(record.questionId) + '">' + (isMastered ? '완료됨' : '숙지 완료') + '</button></div><p class="question">' + escapeHtml(record.question || record.questionId) + '</p><div class="choices">' + choices + '</div><button class="explain-toggle" type="button">해설 보기</button><div class="explanation" hidden>' + ex + '</div></div></details>';
      }}).join('');
      list.innerHTML = '<div class="list-head">전체 오답 <span>' + visible.length + '개</span></div>' + cards;
      list.querySelectorAll('.importance button').forEach(function(button) {{
        button.addEventListener('click', function(event) {{
          event.preventDefault();
          event.stopPropagation();
          const next = loadImportance();
          next[button.dataset.id] = button.dataset.importance;
          saveImportance(next, button.dataset.id);
          postReviewState(button.dataset.id, {{ importance: button.dataset.importance }});
          const group = button.closest('.importance');
          group.querySelectorAll('button').forEach(function(item) {{
            item.classList.toggle('active', item === button);
          }});
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
          saveChoiceFlags(next, id);
          postReviewState(id, {{ choiceFlags: Array.from(set).sort() }});
          const active = set.has(choice);
          button.classList.toggle('active', active);
          button.setAttribute('aria-pressed', active ? 'true' : 'false');
          button.textContent = active ? '☑' : '☐';
          const row = button.closest('.choice');
          if (row) row.classList.toggle('flagged', active);
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
          postReviewState(box.dataset.id, {{ mastered: next.has(box.dataset.id) }});
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
