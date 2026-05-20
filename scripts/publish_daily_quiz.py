#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command, check=True):
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def has_staged_changes():
    result = run(["git", "diff", "--cached", "--quiet"], check=False)
    return result.returncode != 0


def verify_public_url(quiz_date, attempts=5, delay=15):
    url = f"https://zo0258.github.io/so0258house/quizzes/quiz-{quiz_date}.html"
    if attempts <= 0:
        return
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(request, timeout=20) as response:
                status = response.status
            if status == 200:
                print(f"published: {url}")
                return
            print(f"공개 URL 확인 대기: HTTP {status} ({attempt}/{attempts})")
        except urllib.error.HTTPError as error:
            print(f"공개 URL 확인 대기: HTTP {error.code} ({attempt}/{attempts})")
        except Exception as error:
            print(f"공개 URL 확인 대기: {error} ({attempt}/{attempts})")
        if attempt < attempts:
            time.sleep(delay)
    raise SystemExit(f"공개 URL 200 확인 실패: {url}")


def main():
    parser = argparse.ArgumentParser(description="Generate, validate, build, commit, and push a daily quiz.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Quiz date, YYYY-MM-DD.")
    parser.add_argument("--count", type=int, help="Question count override.")
    parser.add_argument("--no-push", action="store_true", help="Commit only. Do not push to origin.")
    args = parser.parse_args()

    generate_command = [sys.executable, "scripts/generate_daily_quiz.py", "--date", args.date, "--html"]
    if args.count:
        generate_command.extend(["--count", str(args.count)])
    run(generate_command)
    run([sys.executable, "scripts/validate_quiz_policy.py", f"data/quizzes/{args.date}-daily.json"])
    run([sys.executable, "scripts/build_static_site.py", "--site-dir", "."])

    paths = [
        f"data/quizzes/{args.date}-daily.json",
        f"quizzes/quiz-{args.date}.html",
        "index.html",
    ]
    run(["git", "add", *paths])

    if has_staged_changes():
        run(["git", "commit", "-m", f"Publish quiz {args.date}"])
    else:
        print("변경 사항이 없어 commit을 건너뜁니다.")

    if not args.no_push:
        run(["git", "push"])
        verify_public_url(args.date)


if __name__ == "__main__":
    main()
