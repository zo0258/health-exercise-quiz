#!/usr/bin/env python3
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_BASE_URL = "https://zo0258.github.io/health-exercise-quiz/"


def run(command, input_text=None, check=True):
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        input=input_text,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def has_staged_changes():
    return run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0


def read_payload(input_path):
    if input_path:
        return input_path.read_text(encoding="utf-8")
    return sys.stdin.read()


def commit_message(payload):
    for line in payload.splitlines():
        if line.startswith("date="):
            return f"Update quiz result status {line.split('=', 1)[1].strip()}"
    return "Update quiz result status"


def main():
    parser = argparse.ArgumentParser(
        description="Record a copied quiz result, rebuild public pages, commit, and push the free GitHub Pages site."
    )
    parser.add_argument("input", nargs="?", type=Path, help="Text file containing a HEALTH_EXERCISE_RESULT block. Reads stdin when omitted.")
    parser.add_argument("--no-push", action="store_true", help="Commit only. Do not push to origin.")
    args = parser.parse_args()

    payload = read_payload(args.input)
    if not payload.strip():
        raise SystemExit("결과 기록 payload가 비어 있습니다.")

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as temp:
        temp.write(payload)
        temp_path = Path(temp.name)

    try:
        run([sys.executable, "scripts/record_attempt.py", str(temp_path)])
    finally:
        temp_path.unlink(missing_ok=True)

    run([sys.executable, "scripts/build_static_site.py", "--site-dir", "."])

    paths = [
        "index.html",
        "wrong-note.html",
        "data/review/wrong-note.json",
    ]
    run(["git", "add", *paths])

    if has_staged_changes():
        run(["git", "commit", "-m", commit_message(payload)])
    else:
        print("공개 페이지 변경 사항이 없어 commit을 건너뜁니다.")

    if not args.no_push:
        run(["git", "push"])

    print(f"main: {PUBLIC_BASE_URL}")
    print(f"wrong-note: {PUBLIC_BASE_URL}wrong-note.html")


if __name__ == "__main__":
    main()
