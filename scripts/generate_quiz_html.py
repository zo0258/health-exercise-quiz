#!/usr/bin/env python3
import argparse
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DELIVERY_DIR = Path.home() / "Desktop" / "건강운동관리사"


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


def latest_attempt_for_quiz(quiz):
    attempts_path = ROOT / "results" / "attempts.jsonl"
    quiz_id = quiz.get("quizId")
    attempts = [attempt for attempt in read_jsonl(attempts_path) if quiz_id and attempt.get("quizId") == quiz_id]
    if not attempts and not quiz.get("sequence"):
        attempts = [attempt for attempt in read_jsonl(attempts_path) if attempt.get("date") == quiz.get("date")]
    return attempts[-1] if attempts else None


def load_sync_config():
    path = ROOT / "config" / "sync.json"
    if not path.exists():
        return {"enabled": False, "submitUrl": "", "mode": "copy"}
    config = read_json(path)
    return {
        "enabled": bool(config.get("enabled") and config.get("submitUrl")),
        "submitUrl": config.get("submitUrl", ""),
        "mode": config.get("mode", "google-apps-script"),
    }


def render_html(quiz):
    data_json = json.dumps(quiz, ensure_ascii=False)
    attempt = latest_attempt_for_quiz(quiz)
    attempt_json = json.dumps(attempt, ensure_ascii=False)
    sync_json = json.dumps(load_sync_config(), ensure_ascii=False)
    safe_data = (
        data_json
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("</script", "\\u003c/script")
    )
    safe_attempt = (
        attempt_json
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("</script", "\\u003c/script")
    )
    safe_sync = (
        sync_json
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("</script", "\\u003c/script")
    )
    title = html.escape(quiz["title"])
    subject = html.escape(quiz["subject"])
    date = html.escape(quiz.get("displayDate") or quiz["date"])
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta http-equiv="cache-control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="pragma" content="no-cache">
  <meta http-equiv="expires" content="0">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{title} | {date}</title>
  <style>
    :root {{
      --bg: #f8f4f1;
      --surface: #ffffff;
      --ink: #242522;
      --muted: #6e746d;
      --line: #ddd7ca;
      --accent: #66735d;
      --accent-strong: #2f3d32;
      --accent-soft: #e9eee4;
      --accent-wash: #f7faf4;
      --danger: #b64032;
      --danger-soft: #f8e8e5;
      --ok: #287a4b;
      --ok-soft: #e4f3e9;
      --warn: #a16b18;
      --shadow: none;
      --radius: 8px;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", sans-serif;
      line-height: 1.5;
      letter-spacing: 0;
    }}

    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: -1;
      background:
        radial-gradient(circle at 50% -12%, rgba(102, 115, 93, .12), transparent 18rem),
        linear-gradient(180deg, #f8f4f1 0%, #f3eee7 100%),
        var(--bg);
    }}

    button, textarea {{
      font: inherit;
    }}

    .app {{
      width: min(760px, 100%);
      min-height: 100svh;
      margin: 0 auto;
      background: transparent;
      box-shadow: var(--shadow);
      border-left: 0;
      border-right: 0;
    }}

    .topbar {{
      position: sticky;
      top: 0;
      z-index: 10;
      background: rgba(248, 244, 241, .94);
      border-bottom: 1px solid rgba(102, 115, 93, .16);
      backdrop-filter: blur(14px);
    }}

    .topbar-inner {{
      padding: 14px 14px 10px;
    }}

    .title-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}

    h1 {{
      margin: 0;
      font-size: 21px;
      line-height: 1.25;
      font-weight: 950;
      color: var(--accent-strong);
    }}

    .progress-chip {{
      flex: 0 0 auto;
      min-width: 58px;
      padding: 8px 11px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent-strong);
      text-align: center;
      font-size: 12px;
      font-weight: 950;
    }}

    .progress-track {{
      height: 5px;
      margin-top: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: #e8ece6;
    }}

    .progress-bar {{
      width: 0%;
      height: 100%;
      border-radius: inherit;
      background: var(--accent);
      transition: width .25s ease;
    }}

    main {{
      padding: 16px 14px 26px;
    }}

    .question-card {{
      display: none;
    }}

    .question-card.active {{
      display: block;
      padding: 16px;
      border: 1px solid rgba(102, 115, 93, .18);
      border-radius: 14px;
      background: rgba(255,255,255,.76);
      animation: questionIn .18s ease-out;
    }}

    @keyframes questionIn {{
      from {{ opacity: .72; transform: translateY(4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    .q-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }}

    .q-count {{
      color: var(--accent-strong);
      font-size: 13px;
      font-weight: 900;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
    }}

    .topic {{
      display: inline-flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-align: right;
    }}

    .question {{
      margin: 0 0 18px;
      font-size: 19px;
      line-height: 1.56;
      font-weight: 760;
    }}

    .question-figures {{
      display: grid;
      gap: 8px;
      margin: -4px 0 16px;
    }}

    .question-figures img {{
      display: block;
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}

    .q-line {{
      margin: 0 0 8px;
    }}

    .q-line:last-child {{
      margin-bottom: 0;
    }}

    .q-label {{
      margin-top: 10px;
      color: var(--accent-strong);
      font-weight: 900;
    }}

    .q-block {{
      margin: 14px 0 16px;
      padding: 14px 14px 12px;
      border: 1px solid rgba(47, 107, 79, .22);
      border-radius: var(--radius);
      background: var(--accent-wash);
    }}

    .q-block .q-label {{
      margin: 0 0 10px;
      font-size: 16px;
    }}

    .q-block .q-line {{
      margin-bottom: 10px;
    }}

    .q-block .q-line:last-child {{
      margin-bottom: 0;
    }}

    .q-hang {{
      padding-left: 1.65em;
      text-indent: -1.65em;
    }}

    .q-dot {{
      padding-left: 1em;
      text-indent: -1em;
    }}

    .choices {{
      display: grid;
      gap: 9px;
    }}

    .choice {{
      display: grid;
      grid-template-columns: 28px 1fr;
      align-items: start;
      gap: 8px;
      width: 100%;
      min-height: 56px;
      padding: 13px 13px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255,255,255,.9);
      color: var(--ink);
      text-align: left;
      cursor: pointer;
      transition: border-color .15s ease, background .15s ease, transform .15s ease;
    }}

    .choice:hover {{
      border-color: rgba(102, 115, 93, .45);
      background: #fbfcfa;
    }}

    .choice:active {{
      transform: scale(.99);
    }}

    .choice:disabled {{
      cursor: default;
    }}

    .choice:disabled:hover {{
      border-color: var(--line);
      background: #fff;
    }}

    .review-summary {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin: 0 0 14px;
    }}

    .review-summary div {{
      min-height: 58px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfa;
    }}

    .review-summary span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }}

    .review-summary strong {{
      display: block;
      margin-top: 4px;
      color: var(--accent-strong);
      font-size: 20px;
      line-height: 1;
      font-weight: 900;
    }}

    .choice-prefix {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 26px;
      height: 26px;
      border-radius: 50%;
      background: #eef2ed;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }}

    .choice-text {{
      min-width: 0;
      padding-top: 1px;
    }}

    .choice.correct {{
      border-color: var(--ok);
      background: var(--ok-soft);
    }}

    .choice.wrong {{
      border-color: var(--danger);
      background: var(--danger-soft);
    }}

    .choice.selected .choice-prefix {{
      background: var(--ink);
      color: #fff;
    }}

    .feedback {{
      display: none;
      margin-top: 18px;
      padding: 15px;
      border-radius: var(--radius);
      background: linear-gradient(180deg, #fbfcfa, #f6f8f5);
      border: 1px solid var(--line);
    }}

    .feedback.visible {{
      display: block;
    }}

    .feedback-title {{
      margin: 0 0 8px;
      font-size: 15px;
      font-weight: 850;
    }}

    .feedback-title.ok {{ color: var(--ok); }}
    .feedback-title.bad {{ color: var(--danger); }}

    .explanation {{
      display: none;
      gap: 9px;
      margin: 10px 0 0;
    }}

    .explanation.visible {{
      display: grid;
    }}

    .ex-row {{
      display: grid;
      gap: 4px;
      padding: 10px 11px;
      border: 1px solid rgba(23, 32, 26, .08);
      border-radius: var(--radius);
      background: #fff;
    }}

    .ex-row strong {{
      color: var(--accent-strong);
      font-size: 13px;
      font-weight: 900;
    }}

    .ex-row span {{
      color: #2c352f;
      font-size: 14px;
      line-height: 1.62;
      white-space: pre-line;
    }}

    .review-tools {{
      display: grid;
      gap: 10px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }}

    .bookmark-toggle {{
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      min-height: 36px;
      border: 1px solid rgba(102, 115, 93, .34);
      border-radius: 999px;
      background: rgba(255,255,255,.92);
      color: var(--accent-strong);
      font-size: 13px;
      font-weight: 900;
      padding: 8px 12px;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(42, 50, 38, .07);
      transition: background .15s ease, border-color .15s ease, color .15s ease, transform .15s ease;
    }}

    .bookmark-toggle:active {{
      transform: scale(.98);
    }}

    .bookmark-toggle.active {{
      border-color: var(--accent-strong);
      background: var(--accent-strong);
      color: #fff;
      box-shadow: 0 4px 12px rgba(47, 61, 50, .18);
    }}

    .bookmark-icon {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 18px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent-strong);
      font-size: 12px;
      line-height: 1;
    }}

    .bookmark-toggle.active .bookmark-icon {{
      background: rgba(255,255,255,.22);
      color: #fff;
    }}

    .reason-panel {{
      display: grid;
      gap: 8px;
    }}

    .reason-label {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }}

    .reason-options {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }}

    .reason-chip {{
      min-height: 36px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      cursor: pointer;
    }}

    .reason-chip.active {{
      border-color: var(--danger);
      background: var(--danger-soft);
      color: var(--danger);
    }}

    .actions {{
      position: sticky;
      bottom: 0;
      display: grid;
      grid-template-columns: 1fr 1.2fr 1fr;
      gap: 8px;
      margin: 22px -14px -26px;
      padding: 10px 14px calc(10px + env(safe-area-inset-bottom));
      background: rgba(248, 244, 241, .94);
      border-top: 1px solid rgba(102, 115, 93, .16);
      backdrop-filter: blur(14px);
    }}

    .btn {{
      min-height: 46px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fff;
      color: var(--ink);
      font-size: 14px;
      font-weight: 800;
      cursor: pointer;
    }}

    .btn.primary {{
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }}

    .btn.primary:hover {{
      background: var(--accent-strong);
    }}

    .btn.ghost {{
      color: var(--muted);
    }}

    .btn:disabled {{
      opacity: .45;
      cursor: not-allowed;
    }}

    .result {{
      display: none;
    }}

    .result.active {{
      display: block;
    }}

    .result-hero {{
      padding: 18px 0 14px;
    }}

    .result-score {{
      font-size: 25px;
      line-height: 1;
      font-weight: 950;
      color: var(--accent-strong);
    }}

    .result-sub {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 800;
    }}

    .result-message {{
      margin: 16px 0 18px;
      padding: 18px;
      border: 1px solid rgba(47, 107, 79, .18);
      border-radius: var(--radius);
      background: #f5faf6;
    }}

    .result-message h2 {{
      margin: 0 0 10px;
      font-size: 18px;
      line-height: 1.3;
      font-weight: 900;
    }}

    .result-message p {{
      margin: 0;
      color: #334138;
      font-size: 15px;
      line-height: 1.65;
      white-space: pre-line;
    }}

    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      margin: 16px 0;
    }}

    .summary-item {{
      padding: 12px 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfa;
    }}

    .summary-label {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
    }}

    .summary-value {{
      margin-top: 4px;
      font-size: 20px;
      font-weight: 900;
    }}

    .summary-value.warn {{
      color: var(--warn);
    }}

    .wrong-list {{
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }}

    .wrong-item,
    .review-item {{
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
    }}

    .wrong-item strong,
    .review-item strong {{
      display: block;
      margin-bottom: 4px;
      font-size: 15px;
    }}

    .wrong-item span,
    .review-item span {{
      color: var(--muted);
      font-size: 14px;
    }}

    .review-list {{
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }}

    .section-title {{
      margin: 24px 0 8px;
      font-size: 17px;
      font-weight: 900;
    }}

    .result-actions {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin: 14px 0 18px;
    }}

    .result-actions a {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 46px;
      border: 1px solid var(--accent);
      border-radius: var(--radius);
      background: var(--accent);
      color: #fff;
      text-decoration: none;
      font-size: 14px;
      font-weight: 900;
    }}

    .result-actions a.secondary {{
      background: #fff;
      color: var(--accent);
    }}

    .wrong-summary {{
      display: grid;
      gap: 8px;
      margin: 12px 0 18px;
    }}

    .wrong-summary div {{
      padding: 11px 12px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fbfcfa;
      color: #2c352f;
      font-size: 14px;
      font-weight: 800;
    }}

    .result-review {{
      margin: 18px 0;
    }}

    .result-review h2 {{
      margin: 0 0 10px;
      color: var(--accent-strong);
      font-size: 18px;
      font-weight: 950;
    }}

    .result-review-list {{
      display: grid;
      gap: 10px;
    }}

    .result-review-card {{
      padding: 13px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
    }}

    .result-review-meta {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
    }}

    .result-review-meta span:last-child {{
      flex: 0 0 auto;
      color: var(--accent);
    }}

    .result-review-question {{
      margin: 0 0 9px;
      color: var(--ink);
      font-size: 14.5px;
      font-weight: 850;
      line-height: 1.48;
      white-space: pre-line;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}

    .result-review-choices {{
      display: grid;
      gap: 6px;
    }}

    .result-review-choice {{
      display: grid;
      grid-template-columns: 24px 1fr;
      gap: 6px;
      align-items: start;
      padding: 8px 9px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fbfcfa;
      color: #354039;
      font-size: 13px;
      line-height: 1.38;
    }}

    .result-review-choice.correct {{
      border-color: rgba(47, 107, 79, .28);
      background: var(--sage);
      color: var(--accent-strong);
      font-weight: 850;
    }}

    .result-review-choice.picked:not(.correct) {{
      border-color: rgba(193, 116, 62, .24);
      background: #fff3ea;
      color: #8b4a1f;
    }}

    .result-review-explanation {{
      margin: 9px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-line;
    }}

    .result-clear {{
      padding: 13px;
      border: 1px solid rgba(47, 107, 79, .16);
      border-radius: var(--radius);
      background: #f7fbf7;
      color: var(--accent-strong);
      font-size: 14px;
      font-weight: 850;
      line-height: 1.5;
    }}

    .sync-status {{
      margin: 10px 0 12px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }}

    .sync-status.ok {{ color: var(--ok); }}
    .sync-status.bad {{ color: var(--danger); }}

    @media (max-width: 420px) {{
      .question {{
        font-size: 18px;
      }}

      .summary-grid {{
        grid-template-columns: repeat(2, 1fr);
      }}

      .result-review-meta {{
        align-items: flex-start;
      }}

      .actions {{
        grid-template-columns: .9fr 1.2fr .9fr;
      }}

      .btn {{
        font-size: 14px;
      }}

      .review-summary {{ grid-template-columns: repeat(3, 1fr); gap: 6px; }}
      .review-summary div {{ padding: 8px; min-height: 52px; }}
      .review-summary strong {{ font-size: 17px; }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="title-row">
          <div>
            <h1>{title}</h1>
          </div>
          <div class="progress-chip" id="positionLabel">1/10</div>
        </div>
        <div class="progress-track"><div class="progress-bar" id="progressBar"></div></div>
      </div>
    </header>

    <main>
      <section id="quizView"></section>
      <section id="resultView" class="result"></section>
      <nav class="actions" id="actions">
        <button class="btn ghost" id="prevBtn" type="button">이전</button>
        <button class="btn primary" id="explainBtn" type="button">해설 보기</button>
        <button class="btn" id="nextBtn" type="button">다음</button>
      </nav>
    </main>
  </div>

  <script id="quiz-data" type="application/json">{safe_data}</script>
  <script id="attempt-data" type="application/json">{safe_attempt}</script>
  <script id="sync-config" type="application/json">{safe_sync}</script>
  <script>
    const quiz = JSON.parse(document.getElementById('quiz-data').textContent);
    const completedAttempt = JSON.parse(document.getElementById('attempt-data').textContent);
    const syncConfig = JSON.parse(document.getElementById('sync-config').textContent);
    const reviewMode = Boolean(completedAttempt);
    const circled = ['①', '②', '③', '④', '⑤'];
    const wrongReasonOptions = ['개념 모름', '헷갈림', '계산 실수', '문제 잘못 읽음'];
    const resultMessages = {{
      '2026-05-20': {{ d: 'D-24', body: '오늘도 한 세트를 끝냈다는 것 자체가 의미 있는 흐름입니다. 틀린 문제는 부족함이 아니라, 다음에 더 단단해질 부분입니다.' }},
      '2026-05-21': {{ d: 'D-23', body: '오늘의 기록은 차곡차곡 쌓입니다. 맞힌 문제는 기준이 되고, 틀린 문제는 실수를 줄여주는 경험이 됩니다.' }},
      '2026-05-22': {{ d: 'D-22', body: '오늘도 멈추지 않았습니다. 매일 문제를 푸는 힘이 시험장에서 가장 믿을 수 있는 루틴이 됩니다.' }},
      '2026-05-23': {{ d: 'D-21', body: '틀린 문제 몇 개보다 중요한 건 오늘도 끝까지 풀어냈다는 사실입니다. 그 꾸준함이 결국 합격에 가까워지게 합니다.' }},
      '2026-05-24': {{ d: 'D-20', body: '오늘의 한 세트도 잘 지나왔습니다. 완벽하지 않아도 괜찮습니다. 반복한 만큼 실전에서 흔들림은 줄어듭니다.' }},
      '2026-05-25': {{ d: 'D-19', body: '오늘도 실력을 하나씩 확인했습니다. 모르는 문제는 줄어들고, 익숙한 기준은 더 선명해지고 있습니다.' }},
      '2026-05-26': {{ d: 'D-18', body: '틀린 문제는 오늘 다시 정리하면 됩니다. 중요한 건 오늘도 공부의 흐름을 이어갔다는 점입니다.' }},
      '2026-05-27': {{ d: 'D-17', body: '하루하루의 기록이 시험 당일의 안정감이 됩니다. 오늘도 그 안정감을 하나 더 쌓았습니다.' }},
      '2026-05-28': {{ d: 'D-16', body: '오늘도 충분히 잘해냈습니다. 잠깐의 불안보다, 지금까지 반복해온 시간이 훨씬 더 강합니다.' }},
      '2026-05-29': {{ d: 'D-15', body: '오늘 풀어낸 문제들이 실전 감각을 만들고 있습니다. 점수보다 중요한 건 흐름을 유지하는 힘입니다.' }},
      '2026-05-30': {{ d: 'D-14', body: '2주 남았습니다. 지금부터는 더 많이 하기보다, 아는 문제를 안정적으로 지켜내는 시간이 더 중요합니다.' }},
      '2026-05-31': {{ d: 'D-13', body: '오늘도 기준을 다시 확인했습니다. 틀린 문제는 다시 보면 되고, 맞힌 문제는 자신 있게 믿으면 됩니다.' }},
      '2026-06-01': {{ d: 'D-12', body: '오늘의 공부는 불안을 줄이는 가장 현실적인 방법입니다. 한 세트씩 쌓아온 힘은 쉽게 사라지지 않습니다.' }},
      '2026-06-02': {{ d: 'D-11', body: '오늘도 끝까지 잘 풀어냈습니다. 시험장에서 필요한 건 특별함보다, 평소처럼 읽고 판단하는 힘입니다.' }},
      '2026-06-03': {{ d: 'D-10', body: '열흘 남았습니다. 지금부터는 실력을 더 늘리기보다, 실수를 줄이고 익숙한 기준을 지키는 연습이 더 중요합니다.' }},
      '2026-06-04': {{ d: 'D-9', body: '오늘도 합격선에 가까운 감각을 유지했습니다. 낯선 문제보다 익숙한 문제를 지켜내는 힘을 믿어도 됩니다.' }},
      '2026-06-05': {{ d: 'D-8', body: '오늘의 오답은 시험장에서 같은 실수를 줄여주는 경험이 됩니다. 지금 확인한 만큼 더 단단해졌습니다.' }},
      '2026-06-06': {{ d: 'D-7', body: '일주일 남았습니다. 여기까지 꾸준히 해온 과정 자체가 이미 충분한 준비의 증거입니다.' }},
      '2026-06-07': {{ d: 'D-6', body: '오늘도 평소의 리듬을 잘 지켜냈습니다. 시험 당일에도 가장 필요한 건 이 리듬을 그대로 유지하는 것입니다.' }},
      '2026-06-08': {{ d: 'D-5', body: '남은 시간은 불안을 키우는 시간이 아니라, 기준을 정리하는 시간입니다. 오늘도 그 기준을 다시 확인했습니다.' }},
      '2026-06-09': {{ d: 'D-4', body: '오늘도 충분히 잘해냈습니다. 완벽하지 않아도, 끝까지 풀어내는 힘은 이미 충분히 만들어졌습니다.' }},
      '2026-06-10': {{ d: 'D-3', body: '이제는 새롭게 증명하려 하지 않아도 됩니다. 지금까지 쌓아온 실력을 차분히 꺼내는 연습이면 충분합니다.' }},
      '2026-06-11': {{ d: 'D-2', body: '오늘은 흔들리지 않는 기준을 다시 확인한 날입니다. 컨디션보다 중요한 건 익숙한 문제를 놓치지 않는 힘입니다.' }},
      '2026-06-12': {{ d: 'D-1', body: '마지막 하루입니다. 더 몰아붙이기보다, 지금까지 해온 것을 믿고 차분히 정리하면 됩니다.' }},
      '2026-06-13': {{ d: 'D-Day', body: '오늘은 완벽해야 하는 날이 아닙니다. 아는 문제를 끝까지 지키고, 모르는 문제에 오래 멈추지 않으면 됩니다. 충분히 준비해왔습니다.' }}
    }};
    const storageKey = 'health-exercise-quiz:' + quiz.quizId;
    const reviewAnswers = new Map((completedAttempt?.answerLog || []).map(item => [
      item.questionId,
      item.selected === 'none' ? null : Number(item.selected) - 1
    ]));
    const initialReviewIds = new Set([
      ...(completedAttempt?.review || []),
      ...(completedAttempt?.wrong || [])
    ].map(item => typeof item === 'string' ? item : item?.questionId).filter(Boolean));
    const state = {{
      current: 0,
      answers: Array(quiz.questions.length).fill(null),
      explanationOpen: Array(quiz.questions.length).fill(false),
      bookmarked: quiz.questions.map(q => initialReviewIds.has(q.id)),
      wrongReasons: Array(quiz.questions.length).fill('')
    }};

    const quizView = document.getElementById('quizView');
    const resultView = document.getElementById('resultView');
    const positionLabel = document.getElementById('positionLabel');
    const progressBar = document.getElementById('progressBar');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const explainBtn = document.getElementById('explainBtn');
    const actions = document.getElementById('actions');

    function normalizeArray(value, fallback) {{
      if (!Array.isArray(value)) return [...fallback];
      return fallback.map((item, index) => value[index] ?? item);
    }}

    function loadSavedState() {{
      try {{
        if (reviewMode) return;
        const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
        if (!saved || saved.quizId !== quiz.quizId) return;
        state.current = Math.min(Math.max(Number(saved.current || 0), 0), quiz.questions.length);
        state.answers = normalizeArray(saved.answers, state.answers).map(value => value === null ? null : Number(value));
        state.explanationOpen = normalizeArray(saved.explanationOpen, state.explanationOpen).map(Boolean);
        state.bookmarked = normalizeArray(saved.bookmarked, state.bookmarked).map(Boolean);
        state.wrongReasons = normalizeArray(saved.wrongReasons, state.wrongReasons).map(value => String(value || ''));
      }} catch (error) {{
        console.warn('Saved quiz state could not be loaded.', error);
      }}
    }}

    function saveState() {{
      if (reviewMode) return;
      const payload = {{
        quizId: quiz.quizId,
        date: quiz.date,
        savedAt: new Date().toISOString(),
        current: state.current,
        answers: state.answers,
        explanationOpen: state.explanationOpen,
        bookmarked: state.bookmarked,
        wrongReasons: state.wrongReasons
      }};
      localStorage.setItem(storageKey, JSON.stringify(payload));
    }}

    function score() {{
      if (reviewMode) return Number(completedAttempt.score || 0);
      return state.answers.reduce((total, selected, index) => {{
        return total + (selected === quiz.questions[index].answerIndex ? 1 : 0);
      }}, 0);
    }}

    function answeredCount() {{
      if (reviewMode) return Number(completedAttempt.answered || completedAttempt.total || quiz.questions.length);
      return state.answers.filter(value => value !== null).length;
    }}

    function unansweredIndexes() {{
      return state.answers
        .map((value, index) => value === null ? index : null)
        .filter(value => value !== null);
    }}

    function unansweredCount() {{
      if (reviewMode) return Number(completedAttempt.unansweredCount || 0);
      return unansweredIndexes().length;
    }}

    function renderQuiz() {{
      quizView.innerHTML = quiz.questions.map((q, index) => `
        <article class="question-card ${{index === state.current ? 'active' : ''}}" data-index="${{index}}">
          ${{reviewMode && index === 0 ? reviewSummaryMarkup() : ''}}
          <div class="q-head">
            <div class="q-count">Q${{index + 1}} · ${{escapeHtml(q.topic)}}</div>
            <div class="topic">
              <span>${{q.year}} 기출</span>
              <button class="bookmark-toggle ${{state.bookmarked[index] ? 'active' : ''}}" type="button" data-question="${{index}}" aria-label="다시 볼 문제 표시" aria-pressed="${{state.bookmarked[index] ? 'true' : 'false'}}">
                <span class="bookmark-icon">${{state.bookmarked[index] ? '☑' : '☐'}}</span><span>다시 보기</span>
              </button>
            </div>
          </div>
          <div class="question">${{questionMarkup(q.question)}}</div>
          ${{questionImagesMarkup(q)}}
          <div class="choices">
            ${{q.choices.map((choice, choiceIndex) => choiceMarkup(q, index, choice, choiceIndex)).join('')}}
          </div>
          <div class="feedback ${{state.explanationOpen[index] || (!reviewMode && state.answers[index] !== null) ? 'visible' : ''}}">
            ${{feedbackMarkup(q, index)}}
          </div>
        </article>
      `).join('');

      quizView.querySelectorAll('.choice').forEach(button => {{
        button.addEventListener('click', () => {{
          const questionIndex = Number(button.dataset.question);
          if (state.answers[questionIndex] !== null) return;
          const choiceIndex = Number(button.dataset.choice);
          state.answers[questionIndex] = choiceIndex;
          if (reviewMode || choiceIndex !== quiz.questions[questionIndex].answerIndex) {{
            state.explanationOpen[questionIndex] = true;
          }}
          saveState();
          render();
        }});
      }});

      quizView.querySelectorAll('.bookmark-toggle').forEach(button => {{
        button.addEventListener('click', () => {{
          const questionIndex = Number(button.dataset.question);
          state.bookmarked[questionIndex] = !state.bookmarked[questionIndex];
          saveState();
          render();
        }});
      }});

      quizView.querySelectorAll('.reason-chip').forEach(button => {{
        button.addEventListener('click', () => {{
          const questionIndex = Number(button.dataset.question);
          state.wrongReasons[questionIndex] = button.dataset.reason;
          saveState();
          render();
        }});
      }});
    }}

    function choiceMarkup(q, questionIndex, choice, choiceIndex) {{
      const selected = selectedForQuestion(questionIndex);
      const answered = reviewMode ? state.explanationOpen[questionIndex] : selected !== null;
      const isCorrect = choiceIndex === q.answerIndex;
      const isSelected = choiceIndex === selected;
      const disabled = answered ? 'disabled' : '';
      const classes = [
        'choice',
        answered && isCorrect ? 'correct' : '',
        answered && isSelected && !isCorrect ? 'wrong selected' : '',
        answered && isSelected && isCorrect ? 'selected' : ''
      ].filter(Boolean).join(' ');

      return `
        <button class="${{classes}}" type="button" data-question="${{questionIndex}}" data-choice="${{choiceIndex}}" ${{disabled}}>
          <span class="choice-prefix">${{circled[choiceIndex]}}</span><span class="choice-text">${{escapeHtml(choice)}}</span>
        </button>
      `;
    }}

    function questionImagesMarkup(q) {{
      if (!Array.isArray(q.images) || !q.images.length) return '';
      const images = q.images.map(image => {{
        let src = String(image.src || '');
        if (src.startsWith('./')) src = src.slice(2);
        if (src.startsWith('/')) src = src.slice(1);
        if (!src) return '';
        const alt = image.alt || '문항 그림';
        return '<img src="../' + escapeHtml(src) + '" alt="' + escapeHtml(alt) + '" loading="lazy">';
      }}).join('');
      return '<div class="question-figures">' + images + '</div>';
    }}

    function selectedForQuestion(questionIndex) {{
      if (reviewMode) {{
        if (state.answers[questionIndex] !== null) return state.answers[questionIndex];
        return state.explanationOpen[questionIndex] ? (reviewAnswers.get(quiz.questions[questionIndex].id) ?? null) : null;
      }}
      return state.answers[questionIndex];
    }}

    function reviewSummaryMarkup() {{
      const wrongCount = Number((completedAttempt?.wrong || []).length);
      const reviewCount = Number((completedAttempt?.review || []).length);
      return `
        <section class="review-summary" aria-label="복습 요약">
          <div><span>완료 점수</span><strong>${{completedAttempt.score || 0}}/${{completedAttempt.total || quiz.questions.length}}</strong></div>
          <div><span>오답</span><strong>${{wrongCount}}</strong></div>
          <div><span>다시 볼 문제</span><strong>${{reviewCount}}</strong></div>
        </section>
      `;
    }}

    function normalizeQuestionText(text) {{
      const normalized = String(text)
        .replaceAll('&lt;', '<')
        .replaceAll('&gt;', '>')
        .replace(/<보기>\\s*\\./g, '<보기>')
        .replace(/<그림>\\s*\\./g, '<그림>')
        .replace(/<표>\\s*\\./g, '<표>');
      return mergeWrappedLines(normalized);
    }}

    function mergeWrappedLines(text) {{
      const lines = text.split('\\n').map(line => line.trim());
      const merged = [];
      lines.forEach(line => {{
        if (!line) return;
        if (isSectionLabel(line) || isListStart(line) || !merged.length || isSectionLabel(merged[merged.length - 1])) {{
          merged.push(line);
          return;
        }}
        if (isContinuationLine(line)) {{
          merged[merged.length - 1] = `${{merged[merged.length - 1]}} ${{line}}`;
          return;
        }}
        merged.push(line);
      }});
      return merged.join('\\n');
    }}

    function isSectionLabel(line) {{
      return line === '<보기>' || line === '<그림>' || line === '<표>';
    }}

    function isListStart(line) {{
      return /^[㉠㉡㉢㉣㉤∙•·▪□]/.test(line);
    }}

    function isContinuationLine(line) {{
      return !isListStart(line) && !isSectionLabel(line);
    }}

    function questionMarkup(text) {{
      const lines = normalizeQuestionText(text).split('\\n').map(line => line.trim()).filter(Boolean);
      const parts = [];
      let blockLines = [];

      lines.forEach(line => {{
        if (isSectionLabel(line)) {{
          if (blockLines.length) parts.push(renderQuestionBlock(blockLines));
          blockLines = [line];
          return;
        }}
        if (blockLines.length) {{
          blockLines.push(line);
          return;
        }}
        parts.push(renderQuestionLine(line));
      }});

      if (blockLines.length) parts.push(renderQuestionBlock(blockLines));
      return parts.join('');
    }}

    function renderQuestionBlock(lines) {{
      return `<div class="q-block">${{lines.map(line => renderQuestionLine(line)).join('')}}</div>`;
    }}

    function renderQuestionLine(line) {{
      return `<div class="${{questionLineClass(line)}}">${{escapeHtml(line)}}</div>`;
    }}

    function questionLineClass(line) {{
      if (line === '<보기>' || line === '<그림>' || line === '<표>') return 'q-line q-label';
      if (/^[㉠㉡㉢㉣㉤]/.test(line)) return 'q-line q-hang';
      if (/^[∙•·▪□]/.test(line)) return 'q-line q-dot';
      return 'q-line';
    }}

    function feedbackMarkup(q, index) {{
      const selected = selectedForQuestion(index);
      if (reviewMode && !state.explanationOpen[index]) return '';
      if (!reviewMode && selected === null) return '';
      const ok = selected === q.answerIndex;
      const title = reviewMode
        ? `풀이완료 · 정답 ${{circled[q.answerIndex]}}`
        : (ok ? '정답입니다' : `오답입니다 · 정답 ${{circled[q.answerIndex]}}`);
      const reviewPoint = `${{q.topic}} 기준을 다시 확인하고, 같은 표현이 다른 보기로 바뀌어도 핵심어를 먼저 찾기`;
      return `
        <p class="feedback-title ${{ok ? 'ok' : 'bad'}}">${{title}}</p>
        <div class="explanation ${{state.explanationOpen[index] ? 'visible' : ''}}">
          ${{choiceExplanationMarkup(q)}}
          <div class="ex-row"><strong>다음에 볼 포인트</strong><span>${{escapeHtml(reviewPoint)}}</span></div>
        </div>
        ${{reviewMode || ok ? '' : '<div class="review-tools">' + reasonMarkup(index) + '</div>'}}
      `;
    }}

    function choiceExplanationMarkup(q) {{
      const rows = Array.isArray(q.choiceExplanations) && q.choiceExplanations.length === q.choices.length
        ? q.choiceExplanations
        : fallbackChoiceExplanations(q);
      return rows.map((text, choiceIndex) => {{
        const label = choiceIndex === q.answerIndex ? `${{circled[choiceIndex]}} 정답` : `${{circled[choiceIndex]}} 오답`;
        return `<div class="ex-row"><strong>${{escapeHtml(label)}}</strong><span>${{escapeHtml(text)}}</span></div>`;
      }}).join('');
    }}

    function fallbackChoiceExplanations(q) {{
      return q.choices.map((choice, choiceIndex) => {{
        if (choiceIndex === q.answerIndex) {{
          return `정답입니다. ${{q.explanation || '최종정답 기준에 맞는 보기입니다.'}}`;
        }}
        return `정답 기준과 맞지 않는 보기입니다. ${{q.trap || '문제의 핵심 조건과 보기 표현을 나누어 확인하세요.'}} 선택지 표현: ${{choice}}`;
      }});
    }}

    function reasonMarkup(index) {{
      return `
        <div class="reason-panel">
          <div class="reason-label">틀린 이유</div>
          <div class="reason-options">
            ${{wrongReasonOptions.map(reason => `
              <button class="reason-chip ${{state.wrongReasons[index] === reason ? 'active' : ''}}" type="button" data-question="${{index}}" data-reason="${{escapeHtml(reason)}}">
                ${{escapeHtml(reason)}}
              </button>
            `).join('')}}
          </div>
        </div>
      `;
    }}

    function renderResult() {{
      const wrong = quiz.questions
        .map((q, index) => ({{ q, index, selected: state.answers[index] }}))
        .filter(item => item.selected !== null && item.selected !== item.q.answerIndex);
      const unanswered = quiz.questions
        .map((q, index) => ({{ q, index, selected: state.answers[index] }}))
        .filter(item => item.selected === null);
      const total = quiz.questions.length;
      const currentScore = score();
      const reviewItems = buildReviewItems(wrong);
      const resultText = buildResultText(wrong, unanswered, reviewItems, currentScore, total);
      const message = buildEncouragement(currentScore, total, wrong.length, unanswered.length);

      resultView.innerHTML = `
        <div class="result-hero">
          <div class="result-score">오늘 풀이 완료</div>
          <div class="result-sub">전체 정답률 ${{currentScore}}/${{total}} · 틀린 문제 ${{wrong.length}}개 · 미응답 ${{unanswered.length}}개</div>
        </div>
        <section class="result-message">
          <h2>${{escapeHtml(message.title)}}</h2>
          <p>${{escapeHtml(message.body)}}</p>
        </section>
        <section class="result-review">
          <h2>오늘 다시 볼 문제</h2>
          ${{resultReviewMarkup(wrong, unanswered)}}
        </section>
        ${{syncConfig.enabled ? '<button class="btn primary" id="submitBtn" type="button">결과 저장</button><div class="sync-status" id="syncStatus">저장하면 대시보드와 오답노트에 반영됩니다.</div>' : ''}}
        <div class="result-actions">
          <a href="../wrong-note.html">오답노트 보기</a>
          <a class="secondary" href="../index.html">메인으로</a>
        </div>
      `;

      const submitBtn = document.getElementById('submitBtn');
      const syncStatus = document.getElementById('syncStatus');
      if (submitBtn) {{
        submitBtn.addEventListener('click', async () => submitResult(resultText, submitBtn, syncStatus));
      }}
    }}

    async function submitResult(resultText, submitBtn, syncStatus) {{
      if (!syncConfig.enabled || !syncConfig.submitUrl) return;
      submitBtn.disabled = true;
      submitBtn.textContent = '제출 중';
      syncStatus.className = 'sync-status';
      syncStatus.textContent = '결과 저장 중입니다.';
      const payload = {{
        source: 'so0258house',
        submittedAt: new Date().toISOString(),
        quizId: quiz.quizId,
        date: quiz.date,
        subject: quiz.subject,
        resultText,
        userAgent: navigator.userAgent
      }};
      try {{
        await fetch(syncConfig.submitUrl, {{
          method: 'POST',
          mode: 'no-cors',
          headers: {{ 'Content-Type': 'text/plain;charset=utf-8' }},
          body: JSON.stringify(payload)
        }});
        submitBtn.textContent = '제출 완료';
        syncStatus.className = 'sync-status ok';
        syncStatus.textContent = '저장 요청 완료. 잠시 후 대시보드와 오답노트에 반영됩니다.';
      }} catch (error) {{
        submitBtn.disabled = false;
        submitBtn.textContent = '다시 저장';
        syncStatus.className = 'sync-status bad';
        syncStatus.textContent = '저장 실패. 잠시 후 다시 시도해 주세요.';
      }}
    }}

    function resultReviewMarkup(wrong, unanswered) {{
      if (!wrong.length && !unanswered.length) {{
        return '<div class="result-clear">오답 없이 마무리했습니다. 오늘은 누적 오답만 가볍게 확인하면 충분합니다.</div>';
      }}
      const rows = [...wrong, ...unanswered].map(item => {{
        const selectedLabel = item.selected === null ? '미응답' : circled[item.selected];
        const choices = item.q.choices.map((choice, index) => {{
          const classes = [
            'result-review-choice',
            index === item.q.answerIndex ? 'correct' : '',
            index === item.selected ? 'picked' : ''
          ].filter(Boolean).join(' ');
          return `<div class="${{classes}}"><strong>${{circled[index]}}</strong><span>${{escapeHtml(choice)}}</span></div>`;
        }}).join('');
        return `
          <article class="result-review-card">
            <div class="result-review-meta">
              <span>Q${{item.index + 1}} · ${{escapeHtml(item.q.topic)}}</span>
              <span>내 답 ${{selectedLabel}} / 정답 ${{circled[item.q.answerIndex]}}</span>
            </div>
            <p class="result-review-question">${{escapeHtml(item.q.question)}}</p>
            <div class="result-review-choices">${{choices}}</div>
            <p class="result-review-explanation">${{escapeHtml(item.q.explanation || '정답 기준을 다시 확인하세요.')}}</p>
          </article>
        `;
      }});
      return `<div class="result-review-list">${{rows.join('')}}</div>`;
    }}

    function buildReviewItems(wrong) {{
      const wrongMap = new Map(wrong.map(item => [item.index, item]));
      const reviewMap = new Map();
      wrong.forEach(item => reviewMap.set(item.index, {{ ...item, priority: 'wrong' }}));
      quiz.questions.forEach((q, index) => {{
        if (state.bookmarked[index] && !reviewMap.has(index)) {{
          reviewMap.set(index, {{ q, index, selected: state.answers[index], priority: 'bookmarked' }});
        }}
      }});
      return Array.from(reviewMap.values()).sort((a, b) => {{
        const aReason = state.wrongReasons[a.index] ? 0 : 1;
        const bReason = state.wrongReasons[b.index] ? 0 : 1;
        if (aReason !== bReason) return aReason - bReason;
        if (a.priority !== b.priority) return a.priority === 'wrong' ? -1 : 1;
        return a.index - b.index;
      }});
    }}

    function buildEncouragement(currentScore, total, wrongCount, unansweredCountValue) {{
      if (unansweredCountValue > 0) {{
        return {{
          title: '끝까지 확인하면 점수가 됩니다',
          body: '아직 답하지 않은 문제가 남아 있어요. 오늘의 목표는 완벽함보다 끝까지 확인하는 습관입니다.\\n남은 문제까지 차분히 눌러 보고, 헷갈린 기준만 표시해두면 오늘 공부는 충분히 의미 있게 끝납니다.'
        }};
      }}
      const daily = resultMessages[quiz.date];
      if (daily) {{
        return {{
          title: daily.d + ' · 오늘도 잘 마무리했습니다',
          body: daily.body
        }};
      }}
      const rate = total ? currentScore / total : 0;
      if (rate >= .9) {{
        return {{
          title: '오늘도 충분히 잘했습니다',
          body: '잘하고 있어요. 오늘 맞힌 문제들은 그냥 운이 아니라, 버티면서 쌓아온 시간이 만든 결과입니다.\\n남은 건 완벽해지는 일이 아니라, 흔들려도 다시 기준을 떠올리는 연습입니다. 고생 많았고, 오늘 하루도 차분하게 마무리해요.'
        }};
      }}
      if (rate >= .7) {{
        return {{
          title: '좋은 흐름 안에 있습니다',
          body: '틀린 문제보다 중요한 건 오늘 끝까지 풀었다는 사실입니다. 지금의 오답은 부족함의 증거가 아니라, 시험 전에 발견한 힌트입니다.\\n오늘 헷갈린 기준만 다시 잡으면 내일은 더 가볍게 넘어갈 수 있어요. 잘될 거예요.'
        }};
      }}
      return {{
        title: '오늘의 오답은 내일의 점수입니다',
        body: '많이 틀린 날도 공부가 무너진 날은 아닙니다. 오히려 지금 틀려서 다행인 문제들이 있습니다.\\n오늘은 고생 많았어요. 정답보다 중요한 건 다시 확인할 기준을 얻었다는 것, 그리고 포기하지 않고 여기까지 왔다는 것입니다. 내일도 한 문제씩 가면 됩니다.'
      }};
    }}

    function buildResultText(wrong, unanswered, reviewItems, currentScore, total) {{
      const lines = [
        '[HEALTH_EXERCISE_RESULT]',
        `date=${{quiz.date}}`,
        `quizId=${{quiz.quizId}}`,
        `subject=${{quiz.subject}}`,
        `score=${{currentScore}}`,
        `total=${{total}}`,
        `answered=${{answeredCount()}}`,
        `unansweredCount=${{unanswered.length}}`
      ];

      quiz.questions.forEach((q, index) => {{
        const selected = state.answers[index];
        const selectedText = selected === null ? 'none' : selected + 1;
        const bookmarked = state.bookmarked[index] ? 'yes' : 'no';
        const reason = state.wrongReasons[index] || '';
        const correct = selected !== null && selected === q.answerIndex ? 'yes' : 'no';
        lines.push(`answerLog=${{q.id}}|topic=${{q.topic}}|selected=${{selectedText}}|answer=${{q.answerIndex + 1}}|correct=${{correct}}|bookmarked=${{bookmarked}}|wrongReason=${{reason || 'none'}}`);
      }});

      wrong.forEach(item => {{
        const reason = state.wrongReasons[item.index] || '미선택';
        const bookmarked = state.bookmarked[item.index] ? 'yes' : 'no';
        lines.push(`wrong=${{item.q.id}}|topic=${{item.q.topic}}|selected=${{item.selected === null ? 'none' : item.selected + 1}}|answer=${{item.q.answerIndex + 1}}|wrongReason=${{reason}}|bookmarked=${{bookmarked}}`);
      }});

      unanswered.forEach(item => {{
        lines.push(`unanswered=${{item.q.id}}|topic=${{item.q.topic}}|answer=${{item.q.answerIndex + 1}}`);
      }});

      reviewItems
        .filter(item => item.selected === item.q.answerIndex && state.bookmarked[item.index])
        .forEach(item => {{
          lines.push(`review=${{item.q.id}}|topic=${{item.q.topic}}|reason=bookmarked`);
      }});

      lines.push('[/HEALTH_EXERCISE_RESULT]');
      return lines.join('\\n');
    }}

    function render() {{
      const isResult = state.current >= quiz.questions.length;
      quizView.style.display = isResult ? 'none' : 'block';
      resultView.classList.toggle('active', isResult);
      actions.style.display = isResult ? 'none' : 'grid';

      if (isResult) {{
        positionLabel.textContent = '완료';
        progressBar.style.width = '100%';
        renderResult();
        return;
      }}

      renderQuiz();
      const q = quiz.questions[state.current];
      const selected = selectedForQuestion(state.current);
      const progress = ((state.current + 1) / quiz.questions.length) * 100;
      positionLabel.textContent = `${{state.current + 1}}/${{quiz.questions.length}}`;
      progressBar.style.width = `${{progress}}%`;
      prevBtn.disabled = state.current === 0;
      nextBtn.textContent = state.current === quiz.questions.length - 1 ? '결과 보기' : '다음';
      if (!reviewMode && state.current === quiz.questions.length - 1 && unansweredCount() > 0) {{
        nextBtn.textContent = `미응답 ${{unansweredCount()}}개`;
      }}
      nextBtn.disabled = !reviewMode && selected === null;
      explainBtn.disabled = !reviewMode && selected === null;
      explainBtn.textContent = state.explanationOpen[state.current] ? '해설 숨김' : '해설 보기';
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }}

    prevBtn.addEventListener('click', () => {{
      state.current = Math.max(0, state.current - 1);
      saveState();
      render();
    }});

    nextBtn.addEventListener('click', () => {{
      if (state.current === quiz.questions.length - 1) {{
        const missing = unansweredIndexes();
        if (!reviewMode && missing.length) {{
          state.current = missing[0];
          render();
          return;
        }}
      }}
      state.current = Math.min(quiz.questions.length, state.current + 1);
      saveState();
      render();
    }});

    explainBtn.addEventListener('click', () => {{
      if (!reviewMode && state.answers[state.current] === null) return;
      state.explanationOpen[state.current] = !state.explanationOpen[state.current];
      saveState();
      render();
    }});

    loadSavedState();
    render();
  </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Generate a mobile quiz HTML file from a quiz JSON file.")
    parser.add_argument("quiz_json", type=Path, help="Path to quiz JSON")
    parser.add_argument("-o", "--output", type=Path, help="Output HTML path")
    args = parser.parse_args()

    quiz_path = args.quiz_json if args.quiz_json.is_absolute() else ROOT / args.quiz_json
    quiz = read_json(quiz_path)
    output_slug = quiz.get("slug") or quiz["date"]
    output = args.output or DEFAULT_DELIVERY_DIR / f"건강운동관리사_{output_slug}.html"
    output = output if output.is_absolute() else ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(quiz), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
