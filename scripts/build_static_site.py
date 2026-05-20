#!/usr/bin/env python3
import argparse
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = Path.home() / "Desktop" / "건강운동관리사"
DEFAULT_SITE_DIR = Path.home() / "Desktop" / "건강운동관리사_web"


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
            badges.append('<span class="badge review">오답반영</span>')
        return "".join(badges)
    return '<span class="badge pending">미완료</span>'


def render_index(files):
    attempts = load_attempt_status()
    review_dates = load_review_dates()
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
            f'<span class="row-meta"><small>전과목 10문항</small><span class="badges">{badges}</span></span>'
            "</a></li>"
        )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>건강운동관리사 데일리 퀴즈</title>
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
      display: grid;
      grid-template-columns: minmax(118px, 150px) 1fr;
      align-items: center;
      gap: 18px;
      margin-bottom: 14px;
      text-align: left;
    }}
    .logo-plate {{
      width: 100%;
      margin: 0;
      padding: 0;
      background: transparent;
    }}
    .logo-plate img {{
      width: 100%;
      height: auto;
      display: block;
      mix-blend-mode: multiply;
    }}
    .dashboard-title {{
      margin: 0;
      display: grid;
      align-content: center;
      min-height: 78px;
      line-height: 1.02;
      font-weight: 700;
      letter-spacing: 0;
      color: var(--ink);
    }}
    .title-brand {{
      display: block;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 32px;
      font-weight: 600;
      letter-spacing: 0;
    }}
    .title-label {{
      display: block;
      margin-top: 5px;
      color: var(--accent);
      font-size: 20px;
      font-weight: 900;
      letter-spacing: .04em;
    }}
    .module {{
      padding: 19px;
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
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin: 0 0 12px;
    }}
    .stat {{
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255, 255, 255, .66);
      box-shadow: 0 8px 18px rgba(36, 37, 34, .03);
    }}
    .stat strong {{
      display: block;
      font-size: 24px;
      font-weight: 950;
      color: var(--accent-dark);
    }}
    .stat small {{
      display: block;
      margin-top: 2px;
      text-align: left;
      font-size: 12px;
    }}
    .today-status {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 12px;
      padding: 13px 14px;
      border: 1px solid rgba(102, 115, 93, .22);
      border-radius: 12px;
      background: rgba(255,255,255,.72);
    }}
    .today-status strong {{
      display: block;
      color: var(--accent-dark);
      font-size: 16px;
      font-weight: 950;
    }}
    .today-status span {{
      display: inline-flex;
      min-height: 26px;
      align-items: center;
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 900;
    }}
    .today-status span.done {{ color: #2f583a; background: #e1eddf; }}
    .today-status span.pending {{ color: #5f6661; background: #ecefed; }}
    .quick {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 0;
    }}
    .quick a {{
      min-height: 84px;
      align-items: flex-start;
      flex-direction: column;
      justify-content: center;
      background: rgba(255,255,255,.84);
      border-color: rgba(102, 115, 93, .22);
      box-shadow: 0 10px 24px rgba(36, 37, 34, .045);
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
      font-size: 20px;
      font-weight: 900;
    }}
    .quick small {{
      display: block;
      margin-top: 4px;
      text-align: left;
      line-height: 1.35;
      font-size: 13px;
    }}
    .history-title {{
      margin: 15px 0 9px;
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
      min-height: 68px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 10px;
      color: var(--ink);
      text-decoration: none;
      background: rgba(255, 255, 255, .86);
      box-shadow: 0 8px 20px rgba(36, 37, 34, .03);
    }}
    a:active {{ transform: scale(.99); }}
    .date {{
      font-size: 20px;
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
      .dashboard-hero {{ grid-template-columns: 96px 1fr; gap: 10px; margin-bottom: 12px; }}
      .dashboard-title {{ min-height: 62px; }}
      .title-brand {{ font-size: 25px; line-height: 1.02; }}
      .title-label {{ margin-top: 3px; font-size: 16px; letter-spacing: .03em; }}
      .module {{ padding: 14px 12px 12px; }}
      .section-head {{ gap: 6px; margin-bottom: 10px; }}
      .section-head h2 {{ font-size: 17px; line-height: 1.1; }}
      .section-head span {{ min-height: 22px; padding: 3px 6px; font-size: 9.5px; }}
      .stats {{ grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 10px; }}
      .stat {{ padding: 8px 9px; }}
      .stat strong {{ font-size: 19px; }}
      .stat small {{ font-size: 11px; }}
      .today-status {{ padding: 10px 11px; margin-bottom: 10px; }}
      .today-status strong {{ font-size: 14px; }}
      .today-status span {{ font-size: 11px; }}
      .quick {{ grid-template-columns: 1fr 1fr; gap: 7px; }}
      .quick a {{ min-height: 78px; padding: 11px; }}
      .quick strong {{ font-size: 17px; }}
      .quick small {{ font-size: 11px; line-height: 1.25; }}
      .history-title {{ margin: 13px 0 8px; font-size: 15px; }}
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
      <div class="logo-plate"><img src="assets/soo2-logo.png" alt="So02 House"></div>
      <h1 class="dashboard-title"><span class="title-brand">So02 House</span><span class="title-label">DashBoard</span></h1>
    </header>
    <section class="module">
      <div class="section-head"><h2>건강운동관리사 데일리 퀴즈</h2><span>전과목 10문항</span></div>
      <section class="stats" aria-label="학습 현황">
        <div class="stat"><strong>{completed_count}</strong><small>풀이완료</small></div>
        <div class="stat"><strong>{review_count}</strong><small>오답반영</small></div>
        <div class="stat"><strong>{pending_count}</strong><small>미완료</small></div>
      </section>
      <section class="today-status" aria-label="오늘 학습 상태">
        <strong>오늘 {html.escape(latest_label)}</strong><span class="{latest_status_class}">{html.escape(latest_status)}</span>
      </section>
      <section class="quick" aria-label="빠른 이동">
        <a href="{html.escape(latest_href, quote=True)}"><strong>오늘 문제 풀기</strong><small>{html.escape(latest_label)} 퀴즈 바로가기</small></a>
        <a href="wrong-note.html"><strong>오답노트 보기</strong><small>틀린 문제·다시 볼 문제</small></a>
      </section>
    </section>
    <div class="history-title">학습 기록</div>
    <ul>
      {''.join(items)}
    </ul>
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
