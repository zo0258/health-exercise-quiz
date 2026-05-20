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
    for path in files:
        label = date_label(path)
        cache_buster = str(int(path.stat().st_mtime))
        href = f"quizzes/{path.name}?v={cache_buster}"
        if latest_label == "준비 중":
            latest_href = href
            latest_label = label
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
      --bg: #f5f4ef;
      --surface: #fff;
      --ink: #171b18;
      --muted: #66706a;
      --line: #e0e2dc;
      --accent: #49664f;
      --accent-dark: #243d2d;
      --sage: #e9efe7;
      --cream: #fbfaf4;
      --gold: #c7a766;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at 8% 0, rgba(73, 102, 79, .16), transparent 25rem),
        linear-gradient(180deg, #fffdf7 0%, var(--bg) 100%);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(820px, 100%);
      min-height: 100svh;
      margin: 0 auto;
      padding: 28px 18px 34px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 22px;
    }}
    .brand img {{
      width: 142px;
      height: auto;
      display: block;
      filter: drop-shadow(0 12px 22px rgba(23, 32, 26, .10));
    }}
    .brand strong {{
      display: block;
      font-size: 15px;
      font-weight: 900;
      letter-spacing: 0;
      color: var(--accent-dark);
    }}
    .hero {{
      padding: 26px 22px 22px;
      border: 1px solid rgba(73, 102, 79, .16);
      border-radius: 16px;
      background:
        linear-gradient(135deg, rgba(255,255,255,.96) 0%, rgba(246,249,244,.94) 100%);
      box-shadow: 0 20px 55px rgba(23, 32, 26, .08);
    }}
    h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.25;
      font-weight: 900;
    }}
    .quick {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 22px;
    }}
    .quick a {{
      min-height: 118px;
      align-items: flex-start;
      flex-direction: column;
      justify-content: center;
      background: rgba(255,255,255,.82);
      border-color: rgba(73, 102, 79, .18);
      box-shadow: 0 10px 24px rgba(23, 32, 26, .05);
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
      font-size: 22px;
      font-weight: 900;
    }}
    .quick small {{
      display: block;
      margin-top: 4px;
      text-align: left;
      line-height: 1.35;
      font-size: 14px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      margin: 16px 0 20px;
    }}
    .stat {{
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255, 255, 255, .78);
      box-shadow: 0 8px 20px rgba(23, 32, 26, .035);
    }}
    .stat strong {{
      display: block;
      font-size: 24px;
      font-weight: 900;
      color: var(--accent-dark);
    }}
    .stat small {{
      display: block;
      margin-top: 2px;
      text-align: left;
      font-size: 12px;
    }}
    ul {{
      display: grid;
      gap: 10px;
      list-style: none;
      margin: 0;
      padding: 0;
    }}
    a {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 76px;
      padding: 16px 18px;
      border: 1px solid var(--line);
      border-radius: 10px;
      color: var(--ink);
      text-decoration: none;
      background: rgba(255, 255, 255, .86);
      box-shadow: 0 8px 20px rgba(23, 32, 26, .03);
    }}
    a:active {{ transform: scale(.99); }}
    .date {{
      font-size: 21px;
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
    .done {{ color: #174b35; background: #dfeee2; }}
    .review {{ color: #5b451d; background: #f2e7cf; }}
    .pending {{ color: #5f6661; background: #ecefed; }}
    @media (max-width: 430px) {{
      .quick {{ grid-template-columns: 1fr; }}
      main {{ padding: 22px 14px 28px; }}
      .brand {{ align-items: flex-start; }}
      .brand img {{ width: 118px; }}
      .brand strong {{ font-size: 13px; }}
      .stats {{ grid-template-columns: 1fr 1fr 1fr; gap: 7px; }}
      .stat {{ padding: 10px; }}
      .stat strong {{ font-size: 20px; }}
      .quiz-row {{ align-items: flex-start; }}
      .row-meta {{ align-items: flex-end; max-width: 52%; }}
      .hero {{ padding: 20px 15px 15px; }}
      h1 {{ font-size: 29px; }}
      .quick strong {{ font-size: 21px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="brand">
      <img src="assets/soo2-logo.svg" alt="So02 House">
      <div><strong>So02 House DashBoard</strong></div>
    </header>
    <section class="hero">
      <h1>건강운동관리사 데일리 퀴즈</h1>
      <section class="quick" aria-label="빠른 이동">
        <a href="{html.escape(latest_href, quote=True)}"><strong>오늘 문제 풀기</strong><small>{html.escape(latest_label)} 퀴즈 바로가기</small></a>
        <a href="wrong-note.html"><strong>오답노트 보기</strong><small>틀린 문제와 다시 볼 문제 모아보기</small></a>
      </section>
    </section>
    <section class="stats" aria-label="학습 현황">
      <div class="stat"><strong>{completed_count}</strong><small>풀이완료</small></div>
      <div class="stat"><strong>{review_count}</strong><small>오답반영</small></div>
      <div class="stat"><strong>{pending_count}</strong><small>미완료</small></div>
    </section>
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
