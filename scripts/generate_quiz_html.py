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


def render_html(quiz):
    data_json = json.dumps(quiz, ensure_ascii=False)
    safe_data = (
        data_json
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("</script", "\\u003c/script")
    )
    title = html.escape(quiz["title"])
    subject = html.escape(quiz["subject"])
    date = html.escape(quiz["date"])
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{title} | {date}</title>
  <style>
    :root {{
      --bg: #f3f5f0;
      --surface: #ffffff;
      --ink: #17201a;
      --muted: #69736c;
      --line: #dfe5dc;
      --accent: #2f6b4f;
      --accent-strong: #234d39;
      --accent-soft: #e5f1ea;
      --danger: #b64032;
      --danger-soft: #f8e8e5;
      --ok: #287a4b;
      --ok-soft: #e4f3e9;
      --warn: #a16b18;
      --shadow: 0 18px 42px rgba(23, 32, 26, .10);
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
        linear-gradient(180deg, rgba(47, 107, 79, .08), rgba(47, 107, 79, 0) 260px),
        var(--bg);
    }}

    button, textarea {{
      font: inherit;
    }}

    .app {{
      width: min(760px, 100%);
      min-height: 100svh;
      margin: 0 auto;
      background: var(--surface);
      box-shadow: var(--shadow);
      border-left: 1px solid rgba(23, 32, 26, .06);
      border-right: 1px solid rgba(23, 32, 26, .06);
    }}

    .topbar {{
      position: sticky;
      top: 0;
      z-index: 10;
      background: rgba(255, 255, 255, .96);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(14px);
    }}

    .topbar-inner {{
      padding: 16px 16px 12px;
    }}

    .title-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}

    h1 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.25;
      font-weight: 800;
    }}

    .meta {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
    }}

    .score-chip {{
      flex: 0 0 auto;
      min-width: 64px;
      padding: 9px 11px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      text-align: center;
      font-size: 13px;
      font-weight: 800;
    }}

    .progress-track {{
      height: 6px;
      margin-top: 12px;
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
      padding: 20px 16px 28px;
    }}

    .question-card {{
      display: none;
    }}

    .question-card.active {{
      display: block;
      animation: questionIn .18s ease-out;
    }}

    @keyframes questionIn {{
      from {{ opacity: .72; transform: translateY(4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    .q-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 16px;
    }}

    .q-count {{
      color: var(--accent);
      font-size: 13px;
      font-weight: 800;
      padding: 5px 9px;
      border-radius: 999px;
      background: var(--accent-soft);
    }}

    .topic {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-align: right;
    }}

    .question {{
      margin: 0 0 20px;
      font-size: 20px;
      line-height: 1.48;
      font-weight: 760;
    }}

    .q-line {{
      margin: 0 0 7px;
    }}

    .q-line:last-child {{
      margin-bottom: 0;
    }}

    .q-label {{
      margin-top: 10px;
      color: var(--accent-strong);
      font-weight: 900;
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
      gap: 11px;
    }}

    .choice {{
      display: grid;
      grid-template-columns: 28px 1fr;
      align-items: start;
      gap: 8px;
      width: 100%;
      min-height: 58px;
      padding: 15px 14px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      color: var(--ink);
      text-align: left;
      cursor: pointer;
      transition: border-color .15s ease, background .15s ease, transform .15s ease;
    }}

    .choice:hover {{
      border-color: rgba(47, 107, 79, .45);
      background: #fbfdfb;
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
      background: #f7f8f5;
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
      margin: 8px 0 0;
      color: #2c352f;
      font-size: 15px;
      white-space: pre-line;
    }}

    .explanation.visible {{
      display: block;
    }}

    .trap {{
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 14px;
    }}

    .review-tools {{
      display: grid;
      gap: 10px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }}

    .bookmark-toggle {{
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      color: var(--ink);
      font-size: 14px;
      font-weight: 850;
      text-align: left;
      padding: 10px 12px;
      cursor: pointer;
    }}

    .bookmark-toggle.active {{
      border-color: var(--warn);
      background: #fff7e8;
      color: #7a4d0d;
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
      margin: 24px -16px -28px;
      padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
      background: rgba(255, 255, 255, .96);
      border-top: 1px solid var(--line);
      backdrop-filter: blur(14px);
    }}

    .btn {{
      min-height: 48px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      color: var(--ink);
      font-size: 15px;
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
      padding: 22px 0 16px;
    }}

    .result-score {{
      font-size: 44px;
      line-height: 1;
      font-weight: 900;
    }}

    .result-sub {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 15px;
      font-weight: 650;
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
      grid-template-columns: repeat(3, 1fr);
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

    .copy-box {{
      width: 100%;
      min-height: 180px;
      margin-top: 12px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      color: #273029;
      background: #fbfcfa;
      font-size: 13px;
      resize: vertical;
    }}

    .section-title {{
      margin: 24px 0 8px;
      font-size: 17px;
      font-weight: 900;
    }}

    @media (max-width: 420px) {{
      .question {{
        font-size: 18px;
      }}

      .actions {{
        grid-template-columns: .9fr 1.2fr .9fr;
      }}

      .btn {{
        font-size: 14px;
      }}
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
            <div class="meta">{date} · {subject} · <span id="positionLabel">1 / 10</span></div>
          </div>
          <div class="score-chip" id="scoreChip">0점</div>
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
  <script>
    const quiz = JSON.parse(document.getElementById('quiz-data').textContent);
    const circled = ['①', '②', '③', '④', '⑤'];
    const wrongReasonOptions = ['개념 모름', '헷갈림', '계산 실수', '문제 잘못 읽음'];
    const state = {{
      current: 0,
      answers: Array(quiz.questions.length).fill(null),
      explanationOpen: Array(quiz.questions.length).fill(false),
      bookmarked: Array(quiz.questions.length).fill(false),
      wrongReasons: Array(quiz.questions.length).fill('')
    }};

    const quizView = document.getElementById('quizView');
    const resultView = document.getElementById('resultView');
    const positionLabel = document.getElementById('positionLabel');
    const scoreChip = document.getElementById('scoreChip');
    const progressBar = document.getElementById('progressBar');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const explainBtn = document.getElementById('explainBtn');
    const actions = document.getElementById('actions');

    function score() {{
      return state.answers.reduce((total, selected, index) => {{
        return total + (selected === quiz.questions[index].answerIndex ? 1 : 0);
      }}, 0);
    }}

    function answeredCount() {{
      return state.answers.filter(value => value !== null).length;
    }}

    function renderQuiz() {{
      quizView.innerHTML = quiz.questions.map((q, index) => `
        <article class="question-card ${{index === state.current ? 'active' : ''}}" data-index="${{index}}">
          <div class="q-head">
            <div class="q-count">Q${{index + 1}}</div>
            <div class="topic">${{q.year}} · ${{q.topic}}</div>
          </div>
          <div class="question">${{questionMarkup(q.question)}}</div>
          <div class="choices">
            ${{q.choices.map((choice, choiceIndex) => choiceMarkup(q, index, choice, choiceIndex)).join('')}}
          </div>
          <div class="feedback ${{state.answers[index] !== null ? 'visible' : ''}}">
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
          if (choiceIndex !== quiz.questions[questionIndex].answerIndex) {{
            state.explanationOpen[questionIndex] = true;
          }}
          render();
        }});
      }});

      quizView.querySelectorAll('.bookmark-toggle').forEach(button => {{
        button.addEventListener('click', () => {{
          const questionIndex = Number(button.dataset.question);
          state.bookmarked[questionIndex] = !state.bookmarked[questionIndex];
          render();
        }});
      }});

      quizView.querySelectorAll('.reason-chip').forEach(button => {{
        button.addEventListener('click', () => {{
          const questionIndex = Number(button.dataset.question);
          state.wrongReasons[questionIndex] = button.dataset.reason;
          render();
        }});
      }});
    }}

    function choiceMarkup(q, questionIndex, choice, choiceIndex) {{
      const selected = state.answers[questionIndex];
      const answered = selected !== null;
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
      return normalizeQuestionText(text)
        .split('\\n')
        .map(line => {{
          const trimmed = line.trim();
          if (!trimmed) return '<div class="q-line"></div>';
          return `<div class="${{questionLineClass(trimmed)}}">${{escapeHtml(trimmed)}}</div>`;
        }})
        .join('');
    }}

    function questionLineClass(line) {{
      if (line === '<보기>' || line === '<그림>' || line === '<표>') return 'q-line q-label';
      if (/^[㉠㉡㉢㉣㉤]/.test(line)) return 'q-line q-hang';
      if (/^[∙•·▪□]/.test(line)) return 'q-line q-dot';
      return 'q-line';
    }}

    function feedbackMarkup(q, index) {{
      const selected = state.answers[index];
      if (selected === null) return '';
      const ok = selected === q.answerIndex;
      const title = ok ? '정답입니다' : `오답입니다 · 정답 ${{circled[q.answerIndex]}}`;
      return `
        <p class="feedback-title ${{ok ? 'ok' : 'bad'}}">${{title}}</p>
        <p class="explanation ${{state.explanationOpen[index] ? 'visible' : ''}}">${{escapeHtml(q.explanation)}}</p>
        <div class="trap">오답 포인트: ${{escapeHtml(q.trap)}}</div>
        <div class="review-tools">
          <button class="bookmark-toggle ${{state.bookmarked[index] ? 'active' : ''}}" type="button" data-question="${{index}}">
            ${{state.bookmarked[index] ? '다시 볼 문제로 표시됨' : '다시 볼 문제로 표시'}}
          </button>
          ${{ok ? '' : reasonMarkup(index)}}
        </div>
      `;
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
        .filter(item => item.selected !== item.q.answerIndex);
      const total = quiz.questions.length;
      const currentScore = score();
      const reviewItems = buildReviewItems(wrong);
      const resultText = buildResultText(wrong, reviewItems, currentScore, total);
      const message = buildEncouragement(currentScore, total, wrong.length);

      resultView.innerHTML = `
        <div class="result-hero">
          <div class="result-score">${{currentScore}}/${{total}}</div>
          <div class="result-sub">${{quiz.subject}} · ${{wrong.length === 0 ? '오답 없음' : `오답 ${{wrong.length}}개`}}</div>
        </div>
        <section class="result-message">
          <h2>${{escapeHtml(message.title)}}</h2>
          <p>${{escapeHtml(message.body)}}</p>
        </section>
        <div class="summary-grid">
          <div class="summary-item"><div class="summary-label">풀이</div><div class="summary-value">${{answeredCount()}}</div></div>
          <div class="summary-item"><div class="summary-label">정답</div><div class="summary-value">${{currentScore}}</div></div>
          <div class="summary-item"><div class="summary-label">오답</div><div class="summary-value">${{wrong.length}}</div></div>
        </div>
        <h2 class="section-title">오답 결과 복사</h2>
        <button class="btn primary" id="copyBtn" type="button">결과 복사</button>
        <textarea class="copy-box" id="copyBox" readonly>${{escapeHtml(resultText)}}</textarea>
      `;

      const copyBtn = document.getElementById('copyBtn');
      const copyBox = document.getElementById('copyBox');
      copyBtn.addEventListener('click', async () => {{
        copyBox.select();
        try {{
          await navigator.clipboard.writeText(copyBox.value);
          copyBtn.textContent = '복사 완료';
        }} catch (error) {{
          document.execCommand('copy');
          copyBtn.textContent = '선택됨';
        }}
      }});
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

    function buildEncouragement(currentScore, total, wrongCount) {{
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

    function buildResultText(wrong, reviewItems, currentScore, total) {{
      const lines = [
        '[HEALTH_EXERCISE_RESULT]',
        `date=${{quiz.date}}`,
        `quizId=${{quiz.quizId}}`,
        `subject=${{quiz.subject}}`,
        `score=${{currentScore}}`,
        `total=${{total}}`,
        `answered=${{answeredCount()}}`
      ];

      wrong.forEach(item => {{
        const reason = state.wrongReasons[item.index] || '미선택';
        const bookmarked = state.bookmarked[item.index] ? 'yes' : 'no';
        lines.push(`wrong=${{item.q.id}}|topic=${{item.q.topic}}|selected=${{item.selected === null ? 'none' : item.selected + 1}}|answer=${{item.q.answerIndex + 1}}|wrongReason=${{reason}}|bookmarked=${{bookmarked}}`);
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
        positionLabel.textContent = '결과';
        progressBar.style.width = '100%';
        scoreChip.textContent = `${{score()}}점`;
        renderResult();
        return;
      }}

      renderQuiz();
      const q = quiz.questions[state.current];
      const selected = state.answers[state.current];
      const progress = ((state.current + 1) / quiz.questions.length) * 100;
      positionLabel.textContent = `${{state.current + 1}} / ${{quiz.questions.length}}`;
      progressBar.style.width = `${{progress}}%`;
      scoreChip.textContent = `${{score()}}점`;
      prevBtn.disabled = state.current === 0;
      nextBtn.textContent = state.current === quiz.questions.length - 1 ? '결과' : '다음';
      explainBtn.disabled = selected === null;
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
      render();
    }});

    nextBtn.addEventListener('click', () => {{
      state.current = Math.min(quiz.questions.length, state.current + 1);
      render();
    }});

    explainBtn.addEventListener('click', () => {{
      if (state.answers[state.current] === null) return;
      state.explanationOpen[state.current] = !state.explanationOpen[state.current];
      render();
    }});

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
    output = args.output or DEFAULT_DELIVERY_DIR / f"건강운동관리사_{quiz['date']}.html"
    output = output if output.is_absolute() else ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(quiz), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
