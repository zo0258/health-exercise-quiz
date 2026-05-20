#!/usr/bin/env python3
import argparse
from datetime import date
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = Path.home() / "Desktop" / "건강운동관리사"
DEFAULT_SITE_DIR = Path.home() / "Desktop" / "건강운동관리사_web"
EXAM_DATE = date(2026, 6, 13)
DAILY_SENTENCES = {
    "2026-05-20": "새로운 문제가 나와도 괜찮다. 이미 맞혀온 기준이 너를 지켜준다.",
    "2026-05-21": "불안은 준비가 부족해서가 아니라, 잘하고 싶어서 생기는 신호다.",
    "2026-05-22": "모르는 문제 몇 개보다, 이미 맞힐 수 있는 문제를 지키는 것이 더 중요하다.",
    "2026-05-23": "합격은 모든 문제를 아는 사람이 아니라, 흔들려도 기준을 잃지 않는 사람이 가져간다.",
    "2026-05-24": "오늘도 새로 증명할 필요 없다. 이미 쌓아온 점수를 유지하면 된다.",
    "2026-05-25": "불안한 날에도 풀 수 있는 문제가 있다. 그 문제들이 합격선을 만든다.",
    "2026-05-26": "처음 보는 문제는 누구에게나 낯설다. 익숙한 문제를 차분히 맞히면 된다.",
    "2026-05-27": "컨디션이 완벽하지 않아도 괜찮다. 기준대로 읽는 습관은 남아 있다.",
    "2026-05-28": "틀릴까 봐 걱정되는 건 자연스럽다. 그래도 지금까지 맞혀온 기록은 사라지지 않는다.",
    "2026-05-29": "새 문제를 두려워하기보다, 아는 문제를 놓치지 않는 데 마음을 둔다.",
    "2026-05-30": "2주 남았다. 더 잘하려고 애쓰기보다, 이미 되는 것을 안정시키면 된다.",
    "2026-05-31": "불안이 올라오면 문제를 작게 나눈다. 문장 하나, 보기 하나씩 보면 된다.",
    "2026-06-01": "오늘의 목표는 완벽한 확신이 아니라, 흔들려도 다시 돌아오는 연습이다.",
    "2026-06-02": "모르는 보기가 있어도 당황하지 않는다. 아는 기준부터 지우면 답은 좁혀진다.",
    "2026-06-03": "열흘 남았다. 지금부터는 실력을 늘리는 것보다 실수를 줄이는 시간이 더 크다.",
    "2026-06-04": "시험장에서 필요한 건 특별한 컨디션이 아니라, 평소처럼 읽는 힘이다.",
    "2026-06-05": "불안은 지나가고, 훈련한 기준은 남는다. 오늘도 그 기준만 확인하면 된다.",
    "2026-06-06": "일주일 남았다. 새로운 걱정보다 이미 맞힌 문제들을 믿어도 된다.",
    "2026-06-07": "당일에 낯선 문제가 보여도 괜찮다. 합격은 낯선 문제 몇 개로 무너지지 않는다.",
    "2026-06-08": "틀릴 수 있다는 생각보다, 맞힐 수 있는 문제를 차분히 지키는 생각이 먼저다.",
    "2026-06-09": "오늘은 불안을 없애려 하지 않는다. 불안해도 풀 수 있다는 감각을 확인한다.",
    "2026-06-10": "남은 3일은 더 몰아붙이는 시간이 아니다. 정리한 기준을 조용히 붙잡는 시간이다.",
    "2026-06-11": "컨디션이 조금 흔들려도, 익숙한 문제를 읽는 힘은 쉽게 사라지지 않는다.",
    "2026-06-12": "내일은 완벽해야 하는 날이 아니다. 준비한 만큼 차분히 꺼내면 되는 날이다.",
    "2026-06-13": "모르는 문제에 멈추지 말고, 아는 문제를 지킨다. 이미 합격선에 닿는 힘은 있다.",
}


def find_quiz_files(source_dir):
    files = []
    for path in source_dir.glob("*.html"):
        normalized_name = unicodedata.normalize("NFC", path.name)
        if normalized_name.startswith("건강운동관리사_"):
            files.append(path)
    return sorted(files, key=lambda path: path.name, reverse=True)


def date_label(path):
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    return match.group(1) if match else path.stem


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
        date = record.get("date")
        if date:
            completed[date] = {
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


def status_badges(label, attempts, review_dates):
    if label in attempts:
        score = attempts[label].get("score")
        total = attempts[label].get("total")
        score_text = f"{score}/{total}" if score is not None and total else "완료"
        badges = [f'<span class="badge done">풀이완료 {html.escape(score_text)}</span>']
        if label in review_dates:
            badges.append('<span class="badge review">오답노트 반영</span>')
        return "".join(badges)
    return '<span class="badge pending">미완료</span>'


def today_sentence():
    today = date.today()
    key = today.isoformat()
    sentence = DAILY_SENTENCES.get(key)
    if sentence is None:
        sentence = DAILY_SENTENCES["2026-05-20"] if today < date(2026, 5, 20) else DAILY_SENTENCES["2026-06-13"]
    days_left = (EXAM_DATE - today).days
    dday = "D-Day" if days_left == 0 else f"D-{days_left}" if days_left > 0 else "시험 완료"
    return dday, sentence


def render_index(files):
    attempts = load_attempt_status()
    review_dates = load_review_dates()
    dday_label, daily_sentence = today_sentence()
    completed_count = sum(1 for path in files if date_label(path) in attempts)
    review_count = sum(1 for path in files if date_label(path) in review_dates)
    pending_count = max(len(files) - completed_count, 0)
    items = []
    latest_href = "wrong-note.html"
    latest_label = "준비 중"
    latest_status = "퀴즈 준비 중"
    latest_status_class = "pending"
    for path in files:
        label = date_label(path)
        cache_buster = str(int(path.stat().st_mtime))
        href = f"quizzes/{path.name}?v={cache_buster}"
        if latest_label == "준비 중":
            latest_href = href
            latest_label = label
            if label in attempts:
                score = attempts[label].get("score")
                total = attempts[label].get("total")
                score_text = f"{score}/{total}" if score is not None and total else "완료"
                latest_status = f"풀이완료 · {score_text} · 복습 가능"
                latest_status_class = "done"
            else:
                latest_status = "미풀이 · 10문항 남음"
        badges = status_badges(label, attempts, review_dates)
        items.append(
            f'<li><a class="quiz-row" href="{html.escape(href, quote=True)}">'
            f'<span class="date">{html.escape(label)}</span>'
            f'<span class="row-meta"><span class="badges">{badges}</span></span>'
            "</a></li>"
        )

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
      margin: 14px auto 0;
      padding: 11px 13px;
      border: 1px solid rgba(102, 115, 93, .18);
      border-radius: 13px;
      background: rgba(255,255,255,.58);
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
      font-size: 12px;
      font-weight: 950;
    }}
    .daily-word-day {{
      flex: 0 0 auto;
      color: var(--accent);
      font-size: 11px;
      font-weight: 950;
      white-space: nowrap;
    }}
    .daily-word p {{
      margin: 0;
      color: #4b554c;
      font-size: 13px;
      font-weight: 760;
      line-height: 1.48;
      word-break: keep-all;
      overflow-wrap: anywhere;
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
      .daily-word {{ width: calc(100% - 8px); margin-top: 12px; padding: 10px 11px; }}
      .daily-word-head {{ margin-bottom: 4px; }}
      .daily-word-title {{ font-size: 11.5px; }}
      .daily-word-day {{ font-size: 10.5px; }}
      .daily-word p {{ font-size: 12.5px; line-height: 1.45; }}
      .history-wrap {{ width: calc(100% - 8px); }}
      .history-bar {{ margin: 19px 0 10px; }}
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
      <p>{html.escape(daily_sentence)}</p>
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
        target = quiz_dir / f"quiz-{date_label(path)}.html"
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
