#!/usr/bin/env python3
import argparse
import html
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


def render_index(files):
    items = []
    for path in files:
        label = date_label(path)
        cache_buster = str(int(path.stat().st_mtime))
        href = f"quizzes/{path.name}?v={cache_buster}"
        items.append(
            f'<li><a href="{html.escape(href, quote=True)}">'
            f'<span>{html.escape(label)}</span><small>건강운동관리사 데일리 퀴즈</small>'
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
      --bg: #f3f5f0;
      --surface: #fff;
      --ink: #17201a;
      --muted: #69736c;
      --line: #dfe5dc;
      --accent: #2f6b4f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(720px, 100%);
      min-height: 100svh;
      margin: 0 auto;
      padding: 28px 16px;
      background: var(--surface);
      border-left: 1px solid rgba(23, 32, 26, .06);
      border-right: 1px solid rgba(23, 32, 26, .06);
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.25;
      font-weight: 900;
    }}
    p {{
      margin: 8px 0 22px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 650;
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
      min-height: 64px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--ink);
      text-decoration: none;
      background: #fbfcfa;
    }}
    a:active {{ transform: scale(.99); }}
    span {{
      font-size: 18px;
      font-weight: 900;
    }}
    small {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-align: right;
    }}
  </style>
</head>
<body>
  <main>
    <h1>건강운동관리사 데일리 퀴즈</h1>
    <p>유소영님의 합격을 기원합니다.</p>
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
    (site_dir / "index.html").write_text(render_index(copied), encoding="utf-8")

    print(site_dir)
    print(f"quizzes={len(copied)}")


if __name__ == "__main__":
    main()
