#!/usr/bin/env python3
import argparse
from collections import Counter
from datetime import date, datetime
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = Path.home() / "Desktop" / "건강운동관리사"
DEFAULT_SITE_DIR = Path.home() / "Desktop" / "건강운동관리사_web"
EXAM_DATE = date(2026, 6, 13)
DAILY_SENTENCES = {
    "2026-05-20": "새로운 문제가 나와도 괜찮다. 그동안 쌓아온 실력이 너를 지켜준다.",
    "2026-05-21": "불안은 준비가 부족해서가 아니라, 잘해내고 싶은 마음이 크기 때문에 생긴다.",
    "2026-05-22": "모르는 문제 몇 개보다, 네가 맞힐 수 있는 문제를 놓치지 않는 게 더 중요하다.",
    "2026-05-23": "합격은 모든 걸 완벽히 아는 사람이 아니라, 흔들려도 자기 기준을 잃지 않는 사람이 가져간다.",
    "2026-05-24": "오늘도 다시 증명하려 하지 않아도 된다. 지금까지 해온 걸 유지하면 된다.",
    "2026-05-25": "불안한 날에도 네가 풀 수 있는 문제는 남아 있다. 그 문제들이 결국 합격선을 만든다.",
    "2026-05-26": "처음 보는 문제는 누구에게나 낯설다. 익숙한 문제를 평소처럼 풀어내면 된다.",
    "2026-05-27": "컨디션이 완벽하지 않아도 괜찮다. 반복해온 습관과 기준은 쉽게 흔들리지 않는다.",
    "2026-05-28": "틀릴까 봐 걱정되는 건 자연스럽다. 그래도 지금까지 쌓아온 실력은 사라지지 않는다.",
    "2026-05-29": "새로운 문제를 두려워하기보다, 아는 문제를 놓치지 않는 데 집중하면 된다.",
    "2026-05-30": "2주 남았다. 더 몰아붙이기보다, 이미 익숙한 것들을 안정시키는 시간이 더 중요하다.",
    "2026-05-31": "불안이 올라오면 문제를 작게 나눈다. 문장 하나, 보기 하나씩 차분히 읽으면 된다.",
    "2026-06-01": "오늘의 목표는 완벽한 확신이 아니다. 흔들려도 다시 집중할 수 있는 힘을 확인하면 된다.",
    "2026-06-02": "모르는 보기가 있어도 당황하지 않는다. 아는 기준부터 하나씩 지우면 답을 좁혀갈 수 있다.",
    "2026-06-03": "열흘 남았다. 지금부터는 실력을 더 늘리기보다, 실수를 줄이는 게 더 중요하다.",
    "2026-06-04": "시험장에서 가장 필요한 건 특별한 컨디션이 아니라, 평소처럼 읽고 판단하는 힘이다.",
    "2026-06-05": "불안은 지나가고, 반복해서 익힌 기준은 남는다. 오늘도 그 기준만 믿으면 된다.",
    "2026-06-06": "일주일 남았다. 새로운 걱정보다, 지금까지 맞혀온 문제들과 네 실력을 믿어도 된다.",
    "2026-06-07": "시험 당일 낯선 문제가 나와도 괜찮다. 합격은 몇 문제로 쉽게 결정되지 않는다.",
    "2026-06-08": "틀릴 수 있다는 생각보다, 맞힐 수 있는 문제를 끝까지 지켜내겠다는 마음이 더 중요하다.",
    "2026-06-09": "오늘은 불안을 없애려 하지 않는다. 불안해도 끝까지 풀어낼 수 있다는 감각을 확인하면 된다.",
    "2026-06-10": "남은 3일은 더 몰아붙이는 시간이 아니다. 정리해온 기준을 차분히 다시 확인하는 시간이다.",
    "2026-06-11": "컨디션이 조금 흔들려도 괜찮다. 익숙한 문제를 읽고 판단하는 힘은 쉽게 사라지지 않는다.",
    "2026-06-12": "내일은 완벽해야 하는 날이 아니다. 지금까지 해온 걸 차분히 꺼내면 되는 날이다.",
    "2026-06-13": "모르는 문제에 오래 멈추지 말고, 아는 문제를 끝까지 지켜낸다. 너는 이미 합격선에 닿을 만큼 충분히 준비해왔다.",
}


def find_quiz_files(source_dir):
    files = []
    for path in source_dir.glob("*.html"):
        normalized_name = unicodedata.normalize("NFC", path.name)
        if normalized_name.startswith("건강운동관리사_"):
            files.append(path)
    return sorted(files, key=quiz_sort_key, reverse=True)


def quiz_sort_key(path):
    date_text, _, _, _ = quiz_identity(path)
    match = re.search(r"(\d{4}-\d{2}-\d{2})(?:-(\d+))?", path.name)
    sequence = int(match.group(2)) if match and match.group(2) else 1
    return (date_text, sequence)


def sequence_label(sequence):
    if sequence == "1":
        return "오전"
    if sequence == "2":
        return "저녁"
    return f"{sequence}회"


def display_label(date_text, sequence=None):
    if not sequence:
        return date_text
    return f"{date_text} ({sequence_label(sequence)})"


def quiz_identity(path):
    match = re.search(r"(\d{4}-\d{2}-\d{2})(?:-(\d+))?", path.name)
    if not match:
        return path.stem, path.stem, path.stem, None
    date_text = match.group(1)
    sequence = match.group(2)
    slug = f"{date_text}-{sequence}" if sequence else date_text
    display = display_label(date_text, sequence)
    quiz_id = f"{date_text}-daily-{sequence}-all-subjects" if sequence else f"{date_text}-daily-all-subjects"
    return date_text, display, slug, quiz_id


def load_attempt_status():
    attempts_path = ROOT / "results" / "attempts.jsonl"
    completed = {}
    if not attempts_path.exists():
        return completed
    for line in attempts_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        quiz_key = record.get("quizId") or record.get("date")
        if quiz_key:
            completed[quiz_key] = {
                "score": record.get("score"),
                "total": record.get("total"),
            }
    return completed


def load_review_dates():
    review_path = ROOT / "data" / "review" / "wrong-note.json"
    dates = set()
    if not review_path.exists():
        return dates
    try:
        data = json.loads(review_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dates
    for section in ("wrong", "review", "mastered"):
        for record in data.get(section, []):
            date = record.get("date")
            if date:
                dates.add(date)
    return dates


def read_review_generated_at():
    for path in (ROOT / "data" / "review" / "review-state.json", ROOT / "data" / "review" / "wrong-note.json"):
        if not path.exists():
            continue
        try:
            generated_at = json.loads(path.read_text(encoding="utf-8")).get("generatedAt", "")
        except json.JSONDecodeError:
            continue
        if not generated_at:
            continue
        try:
            return datetime.fromisoformat(generated_at).strftime("%H:%M")
        except ValueError:
            return generated_at
    return "대기 중"


def status_badges(date_text, quiz_id, attempts, review_dates):
    attempt = attempts.get(quiz_id) or attempts.get(date_text)
    if attempt:
        score = attempt.get("score")
        total = attempt.get("total")
        score_text = f"{score}/{total}" if score is not None and total else "완료"
        badges = [f'<span class="badge done">풀이완료 {html.escape(score_text)}</span>']
        if date_text in review_dates:
            badges.append('<span class="badge review">오답노트 반영</span>')
        return "".join(badges)
    return '<span class="badge pending">미완료</span>'


def today_sentence():
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    key = today.isoformat()
    sentence = DAILY_SENTENCES.get(key)
    if sentence is None:
        sentence = DAILY_SENTENCES["2026-05-20"] if today < date(2026, 5, 20) else DAILY_SENTENCES["2026-06-13"]
    days_left = (EXAM_DATE - today).days
    dday = "D-Day" if days_left == 0 else f"D-{days_left}" if days_left > 0 else "시험 완료"
    return dday, sentence


def sentence_lines(sentence):
    lines = re.split(r"(?<=\.)\s+", sentence.strip())
    return [line.strip() for line in lines if line.strip()]


def render_index(files):
    attempts = load_attempt_status()
    review_dates = load_review_dates()
    sync_time = read_review_generated_at()
    dday_label, daily_sentence = today_sentence()
    daily_sentence_html = "".join(f"<span>{html.escape(line)}</span>" for line in sentence_lines(daily_sentence))
    date_counts = Counter(quiz_identity(path)[0] for path in files)
    completed_count = 0
    review_count = 0
    for path in files:
        date_text, _, _, quiz_id = quiz_identity(path)
        if quiz_id in attempts or date_text in attempts:
            completed_count += 1
        if date_text in review_dates:
            review_count += 1
    pending_count = max(len(files) - completed_count, 0)
    items = []
    latest_href = "wrong-note.html"
    latest_label = "준비 중"
    latest_status = "퀴즈 준비 중"
    latest_status_class = "pending"
    latest_candidate = None
    latest_candidate_status = None
    for path in files:
        date_text, label, _, quiz_id = quiz_identity(path)
        if date_counts[date_text] > 1 and label == date_text:
            label = display_label(date_text, "1")
        cache_buster = str(int(path.stat().st_mtime))
        href = f"quizzes/{path.name}?v={cache_buster}"
        latest_attempt = attempts.get(quiz_id) or attempts.get(date_text)
        candidate = (href, label, latest_attempt)
        if latest_candidate is None:
            latest_candidate = candidate
        if latest_candidate_status is None and not latest_attempt:
            latest_candidate_status = candidate
        badges = status_badges(date_text, quiz_id, attempts, review_dates)
        items.append(
            f'<li><a class="quiz-row" href="{html.escape(href, quote=True)}">'
            f'<span class="date">{html.escape(label)}</span>'
            f'<span class="row-meta"><span class="badges">{badges}</span></span>'
            "</a></li>"
        )

    selected_latest = latest_candidate_status or latest_candidate
    if selected_latest:
        latest_href, latest_label, latest_attempt = selected_latest
        if latest_attempt:
            score = latest_attempt.get("score")
            total = latest_attempt.get("total")
            score_text = f"{score}/{total}" if score is not None and total else "완료"
            latest_status = f"풀이완료 · {score_text} · 복습 가능"
            latest_status_class = "done"
        else:
            latest_status = "미풀이 · 10문항 남음"

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>So02 House DashBoard</title>
  <style>
    :root {{
      --bg: #f8f4f1;
      --surface: #fff;
      --ink: #242522;
      --muted: #6e746d;
      --line: #ddd7ca;
      --accent: #66735d;
      --accent-dark: #2f3d32;
      --sage: #e9eee4;
      --cream: #f8f4f1;
      --gold: #b89b62;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at 50% -12%, rgba(102, 115, 93, .12), transparent 18rem),
        linear-gradient(180deg, #f8f4f1 0%, #f3eee7 100%);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(860px, 100%);
      min-height: 100svh;
      margin: 0 auto;
      padding: 24px 18px 32px;
    }}
    .dashboard-hero {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 11px;
      min-height: 50px;
      margin-bottom: 14px;
      text-align: left;
    }}
    .brand-lockup {{
      display: flex;
      align-items: center;
      gap: 11px;
      min-width: 0;
    }}
    .logo-plate {{
      flex: 0 0 auto;
      margin: 0;
      padding: 0;
      background: transparent;
    }}
    .logo-plate img {{
      width: auto;
      height: 50px;
      display: block;
      mix-blend-mode: multiply;
    }}
    .dashboard-title {{
      margin: 0;
      display: flex;
      align-items: center;
      min-height: 50px;
      line-height: 1;
      font-weight: 950;
      letter-spacing: 0;
      color: var(--accent-dark);
    }}
    .title-label {{
      display: block;
      color: var(--accent);
      font-size: 32px;
      font-weight: 950;
      letter-spacing: .01em;
      transform: translateY(1px);
    }}
    .today-chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 30px;
      padding: 5px 10px;
      border: 1px solid rgba(102, 115, 93, .22);
      border-radius: 999px;
      background: rgba(255,255,255,.72);
      color: var(--accent-dark);
      font-size: 12px;
      font-weight: 950;
      white-space: nowrap;
      text-decoration: none;
      transform: translateY(-4px);
    }}
    .module {{
      padding: 16px;
      border: 1px solid rgba(102, 115, 93, .20);
      border-radius: 16px;
      background:
        linear-gradient(135deg, rgba(255,255,255,.72) 0%, rgba(248,244,241,.92) 100%);
      box-shadow: 0 14px 34px rgba(36, 37, 34, .06);
    }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 12px;
    }}
    .section-head h2 {{
      margin: 0;
      min-width: 0;
      font-size: 27px;
      line-height: 1.12;
      font-weight: 950;
      color: var(--accent-dark);
      letter-spacing: 0;
      white-space: nowrap;
    }}
    .section-head span {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 9px;
      border-radius: 999px;
      color: var(--accent-dark);
      background: var(--sage);
      font-size: 12px;
      font-weight: 900;
      white-space: nowrap;
      flex: 0 0 auto;
    }}
    .history-bar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin: 20px 0 10px;
      padding: 0 2px;
    }}
    .history-wrap {{
      width: calc(100% - 10px);
      margin: 0 auto;
    }}
    .history-summary {{
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      min-width: 0;
      padding: 4px;
      border: 1px solid rgba(102, 115, 93, .18);
      border-radius: 999px;
      background: rgba(255,255,255,.62);
      white-space: nowrap;
    }}
    .history-summary span {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      min-height: 27px;
      padding: 4px 9px;
      border-radius: 999px;
      background: rgba(248,244,241,.78);
      color: var(--muted);
      font-size: 11px;
      font-weight: 900;
    }}
    .history-summary strong {{
      display: inline-block;
      font-size: 12px;
      font-weight: 950;
      color: var(--accent-dark);
    }}
    .sync-note {{
      margin: -3px 2px 9px;
      color: var(--muted);
      font-size: 11.5px;
      font-weight: 800;
      text-align: right;
    }}
    .quick {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 0;
    }}
    .quick a {{
      min-height: 72px;
      align-items: flex-start;
      flex-direction: column;
      justify-content: center;
      background: rgba(255,255,255,.84);
      border-color: rgba(102, 115, 93, .22);
      box-shadow: none;
    }}
    .quick a:first-child {{
      color: #fff;
      background:
        linear-gradient(135deg, var(--accent-dark) 0%, var(--accent) 100%);
      border-color: var(--accent-dark);
    }}
    .quick a:first-child small {{ color: rgba(255, 255, 255, .82); }}
    .quick strong {{
      display: block;
      font-size: 18px;
      font-weight: 900;
    }}
    .quick small {{
      display: block;
      margin-top: 4px;
      text-align: left;
      line-height: 1.35;
      font-size: 12px;
    }}
    .daily-word {{
      width: calc(100% - 10px);
      margin: 16px auto 0;
      padding: 13px 14px 13px 15px;
      border: 1px solid rgba(102, 115, 93, .24);
      border-left: 3px solid var(--accent);
      border-radius: 13px;
      background: linear-gradient(135deg, rgba(233,238,228,.72), rgba(255,255,255,.70));
      box-shadow: 0 8px 20px rgba(36,37,34,.04);
    }}
    .daily-word-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 5px;
    }}
    .daily-word-title {{
      color: var(--accent-dark);
      font-size: 12.5px;
      font-weight: 950;
    }}
    .daily-word-day {{
      flex: 0 0 auto;
      min-height: 24px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 3px 8px;
      border-radius: 999px;
      background: var(--sage);
      color: var(--accent-dark);
      font-size: 11px;
      font-weight: 950;
      white-space: nowrap;
    }}
    .daily-word p {{
      margin: 0;
      color: #4b554c;
      font-size: 13.5px;
      font-weight: 820;
      line-height: 1.52;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}
    .daily-word p span {{
      display: block;
    }}
    .daily-word p span + span {{
      margin-top: 2px;
    }}
    .history-title {{
      margin: 0;
      color: var(--accent-dark);
      font-size: 16px;
      font-weight: 950;
    }}
    ul {{
      display: grid;
      gap: 8px;
      list-style: none;
      margin: 0;
      padding: 0;
    }}
    a {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 58px;
      padding: 11px 13px;
      border: 1px solid var(--line);
      border-radius: 10px;
      color: var(--ink);
      text-decoration: none;
      background: rgba(255, 255, 255, .86);
      box-shadow: none;
    }}
    a:active {{ transform: scale(.99); }}
    .date {{
      font-size: 17px;
      font-weight: 900;
    }}
    small {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-align: right;
    }}
    .row-meta {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 8px;
    }}
    .badges {{
      display: flex;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 900;
      white-space: nowrap;
    }}
    .done {{ color: #2f583a; background: #e1eddf; }}
    .review {{ color: #6b5425; background: #f0e4ca; }}
    .pending {{ color: #5f6661; background: #ecefed; }}
    @media (max-width: 430px) {{
      main {{ padding: 18px 12px 24px; }}
      .dashboard-hero {{ gap: 10px; min-height: 48px; margin-bottom: 12px; }}
      .brand-lockup {{ gap: 10px; }}
      .logo-plate img {{ height: 46px; }}
      .dashboard-title {{ min-height: 46px; }}
      .title-label {{ font-size: 29px; letter-spacing: 0; transform: translateY(1px); }}
      .today-chip {{ min-height: 27px; padding: 4px 8px; font-size: 11px; transform: translateY(-4px); }}
      .module {{ padding: 13px 12px; }}
      .section-head {{ gap: 6px; margin-bottom: 10px; }}
      .section-head h2 {{ font-size: 17px; line-height: 1.1; }}
      .section-head span {{ display:none; }}
      .quick {{ grid-template-columns: 1fr 1fr; gap: 7px; }}
      .quick a {{ min-height: 66px; padding: 10px; }}
      .quick strong {{ font-size: 16px; }}
      .quick small {{ font-size: 10.5px; line-height: 1.22; }}
      .daily-word {{ width: calc(100% - 8px); margin-top: 13px; padding: 12px 12px 12px 13px; }}
      .daily-word-head {{ margin-bottom: 4px; }}
      .daily-word-title {{ font-size: 12px; }}
      .daily-word-day {{ font-size: 10.5px; }}
      .daily-word p {{ font-size: 12.8px; line-height: 1.48; }}
      .history-wrap {{ width: calc(100% - 8px); }}
      .history-bar {{ margin: 19px 0 10px; }}
      .sync-note {{ text-align: left; font-size: 11px; }}
      .history-title {{ font-size: 15px; }}
      .history-summary {{ gap: 5px; padding: 3px; }}
      .history-summary span {{ min-height: 25px; padding: 3px 7px; font-size: 10.5px; }}
      .history-summary strong {{ font-size: 11.5px; }}
      .quiz-row {{ align-items: flex-start; }}
      .row-meta {{ align-items: flex-end; max-width: 52%; }}
      a {{ min-height: 62px; padding: 12px; }}
      .date {{ font-size: 18px; }}
      small {{ font-size: 12px; }}
      .badge {{ min-height: 23px; padding: 3px 7px; font-size: 11px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="dashboard-hero">
      <div class="brand-lockup">
        <div class="logo-plate"><img src="assets/soo2-logo.png" alt="So02 House"></div>
        <h1 class="dashboard-title"><span class="title-label">DashBoard</span></h1>
      </div>
      <a class="today-chip" href="{html.escape(latest_href, quote=True)}">{html.escape(latest_label)}</a>
    </header>
    <section class="module">
      <div class="section-head"><h2>건강운동관리사 데일리 퀴즈</h2></div>
      <section class="quick" aria-label="빠른 이동">
        <a href="{html.escape(latest_href, quote=True)}"><strong>오늘 문제 풀기</strong><small>{html.escape(latest_status)}</small></a>
        <a href="wrong-note.html"><strong>오답노트 보기</strong><small>틀린 문제·다시 볼 문제</small></a>
      </section>
    </section>
    <section class="daily-word" aria-label="오늘의 한 문장">
      <div class="daily-word-head">
        <div class="daily-word-title">오늘의 한 문장</div>
        <div class="daily-word-day">{html.escape(dday_label)}</div>
      </div>
      <p>{daily_sentence_html}</p>
    </section>
    <div class="history-wrap">
      <div class="history-bar">
        <div class="history-title">학습 기록</div>
        <div class="history-summary" aria-label="학습 현황">
          <span>풀이완료 <strong>{completed_count}</strong></span>
          <span>오답노트 <strong>{review_count}</strong></span>
          <span>미완료 <strong>{pending_count}</strong></span>
        </div>
      </div>
      <div class="sync-note">마지막 반영 {html.escape(sync_time)}</div>
      <ul>
        {''.join(items)}
      </ul>
    </div>
  </main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Build a small static quiz site for iPhone-friendly web delivery.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
    args = parser.parse_args()

    source_dir = args.source_dir.expanduser()
    site_dir = args.site_dir.expanduser()
    quiz_dir = site_dir / "quizzes"
    files = find_quiz_files(source_dir)
    if not files:
        raise SystemExit(f"HTML 퀴즈 파일을 찾지 못했습니다: {source_dir}")

    if site_dir.exists() and (site_dir / ".git").exists():
        if quiz_dir.exists():
            shutil.rmtree(quiz_dir)
    elif site_dir.exists():
        shutil.rmtree(site_dir)
    quiz_dir.mkdir(parents=True)
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")
    copied = []
    for path in files:
        _, _, slug, _ = quiz_identity(path)
        target = quiz_dir / f"quiz-{slug}.html"
        shutil.copy2(path, target)
        copied.append(target)
    wrong_note = ROOT / "wrong-note.html"
    if wrong_note.exists():
        wrong_note_target = site_dir / "wrong-note.html"
        if wrong_note.resolve() != wrong_note_target.resolve():
            shutil.copy2(wrong_note, wrong_note_target)
    review_dir = ROOT / "data" / "review"
    if review_dir.exists():
        target_review_dir = site_dir / "data" / "review"
        if review_dir.resolve() != target_review_dir.resolve():
            if target_review_dir.exists():
                shutil.rmtree(target_review_dir)
            shutil.copytree(review_dir, target_review_dir)
    assets_dir = ROOT / "assets"
    if assets_dir.exists():
        target_assets_dir = site_dir / "assets"
        if assets_dir.resolve() != target_assets_dir.resolve():
            if target_assets_dir.exists():
                shutil.rmtree(target_assets_dir)
            shutil.copytree(assets_dir, target_assets_dir)
    (site_dir / "index.html").write_text(render_index(copied), encoding="utf-8")

    print(site_dir)
    print(f"quizzes={len(copied)}")


if __name__ == "__main__":
    main()
