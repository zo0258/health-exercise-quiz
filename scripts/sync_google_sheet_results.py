#!/usr/bin/env python3
import argparse
import csv
import json
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATTEMPTS_PATH = ROOT / "results" / "attempts.jsonl"
CONFIG_PATH = ROOT / "config" / "sync.json"
REVIEW_STATE_PATH = ROOT / "data" / "review" / "review-state.json"


def run(command, check=True):
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def read_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def parse_key(result_text):
    data = {}
    for line in str(result_text or "").splitlines():
        if "=" not in line or line.startswith(("wrong=", "review=", "answerLog=", "unanswered=", "objection=")):
            continue
        key, value = line.split("=", 1)
        data[key] = value
    return data.get("date", ""), data.get("quizId", "")


def row_result_text(row):
    result_text = row.get("resultText", "")
    if result_text:
        return result_text
    payload_json = row.get("payloadJson", "")
    if not payload_json:
        return ""
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return ""
    return payload.get("resultText", "")


def row_payload(row):
    payload_json = row.get("payloadJson", "")
    if not payload_json:
        return {}
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def default_review_state():
    return {
        "generatedAt": "",
        "importance": {},
        "mastered": [],
        "choiceFlags": {},
        "updatedAt": {},
    }


def normalize_review_state(state):
    normalized = default_review_state()
    if isinstance(state, dict):
        normalized.update({key: state.get(key, normalized[key]) for key in normalized})
    normalized["importance"] = {
        str(question_id): level
        for question_id, level in dict(normalized.get("importance") or {}).items()
        if level in {"high", "mid", "low"}
    }
    normalized["mastered"] = sorted({str(question_id) for question_id in (normalized.get("mastered") or []) if question_id})
    choice_flags = {}
    for question_id, values in dict(normalized.get("choiceFlags") or {}).items():
        flags = sorted({str(value) for value in (values or []) if str(value) != ""})
        if flags:
            choice_flags[str(question_id)] = flags
    normalized["choiceFlags"] = choice_flags
    normalized["updatedAt"] = {
        str(question_id): str(value)
        for question_id, value in dict(normalized.get("updatedAt") or {}).items()
        if question_id and value
    }
    return normalized


def load_review_state():
    if not REVIEW_STATE_PATH.exists():
        return default_review_state()
    return normalize_review_state(read_json(REVIEW_STATE_PATH))


def import_review_state(rows):
    previous = load_review_state()
    state = normalize_review_state(previous)
    mastered = set(state.get("mastered", []))

    for row in rows:
        payload = row_payload(row)
        if payload.get("kind") != "reviewState":
            continue
        question_id = str(payload.get("questionId", "")).strip()
        if not question_id:
            continue

        if "importance" in payload:
            level = payload.get("importance")
            if level in {"high", "mid", "low"}:
                state["importance"][question_id] = level
            elif level in ("", None):
                state["importance"].pop(question_id, None)

        if "mastered" in payload:
            if payload.get("mastered"):
                mastered.add(question_id)
            else:
                mastered.discard(question_id)

        if "choiceFlags" in payload:
            flags = sorted({str(value) for value in (payload.get("choiceFlags") or []) if str(value) != ""})
            if flags:
                state["choiceFlags"][question_id] = flags
            else:
                state["choiceFlags"].pop(question_id, None)

        state["updatedAt"][question_id] = str(payload.get("submittedAt") or row.get("receivedAt") or "")

    state["mastered"] = sorted(mastered)
    state = normalize_review_state(state)
    if state != previous:
        from datetime import datetime
        state["generatedAt"] = datetime.now().isoformat(timespec="seconds")
        write_json(REVIEW_STATE_PATH, state)
        return True
    return False


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc)


def load_existing_import_state():
    imported_rows = set()
    latest_by_quiz = {}
    for row in read_jsonl(ATTEMPTS_PATH):
        date_text = row.get("date", "")
        quiz_id = row.get("quizId", "")
        if not date_text or not quiz_id:
            continue
        source_received_at = row.get("sourceReceivedAt")
        if source_received_at:
            imported_rows.add((date_text, quiz_id, source_received_at))
        recorded_at = parse_datetime(row.get("recordedAt"))
        key = (date_text, quiz_id)
        if recorded_at and (key not in latest_by_quiz or recorded_at > latest_by_quiz[key]):
            latest_by_quiz[key] = recorded_at
    return imported_rows, latest_by_quiz


def should_import_row(key, row, imported_rows, latest_by_quiz):
    source_received_at = str(row.get("receivedAt") or "")
    if source_received_at and (*key, source_received_at) in imported_rows:
        return False
    received_at = parse_datetime(source_received_at)
    latest_recorded_at = latest_by_quiz.get(key)
    if latest_recorded_at and received_at and received_at <= latest_recorded_at:
        return False
    if latest_recorded_at and not received_at:
        return False
    return True


def attach_source_received_at(result_text, source_received_at):
    if not source_received_at or "sourceReceivedAt=" in result_text:
        return result_text
    marker = "[/HEALTH_EXERCISE_RESULT]"
    if marker not in result_text:
        return result_text
    return result_text.replace(marker, f"sourceReceivedAt={source_received_at}\n{marker}", 1)


def fetch_csv_rows(csv_url):
    with urllib.request.urlopen(csv_url, timeout=30) as response:
        text = response.read().decode("utf-8-sig")
    return list(csv.DictReader(text.splitlines()))


def fetch_web_app_rows(submit_url):
    query = urllib.parse.urlencode({"action": "rows"})
    separator = "&" if "?" in submit_url else "?"
    url = f"{submit_url}{separator}{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise SystemExit(f"Apps Script rows 조회 실패: {payload}")
    return payload.get("rows", [])


def fetch_rows(config, csv_url=None, web_app_url=None):
    if csv_url:
        return fetch_csv_rows(csv_url)
    submit_url = web_app_url or config.get("submitUrl")
    if submit_url:
        return fetch_web_app_rows(submit_url)
    raise SystemExit("csvUrl 또는 submitUrl이 없습니다. config/sync.json 설정을 확인해주세요.")


def has_staged_changes():
    return run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0


def main():
    parser = argparse.ArgumentParser(description="Import submitted quiz results from Google Sheets or Apps Script and republish static pages.")
    parser.add_argument("--csv-url", help="Google Sheets CSV export URL. Defaults to config/sync.json csvUrl.")
    parser.add_argument("--web-app-url", help="Apps Script Web App URL. Defaults to config/sync.json submitUrl.")
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()

    config = read_json(CONFIG_PATH) if CONFIG_PATH.exists() else {}
    csv_url = args.csv_url or config.get("csvUrl")

    rows = fetch_rows(config, csv_url=csv_url, web_app_url=args.web_app_url)
    review_state_changed = import_review_state(rows)

    imported_rows, latest_by_quiz = load_existing_import_state()
    imported_dates = set()
    for row in rows:
        result_text = row_result_text(row)
        key = parse_key(result_text)
        if not all(key) or not should_import_row(key, row, imported_rows, latest_by_quiz):
            continue
        result_text = attach_source_received_at(result_text, str(row.get("receivedAt") or ""))
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as temp:
            temp.write(result_text)
            temp_path = Path(temp.name)
        try:
            run([sys.executable, "scripts/record_attempt.py", str(temp_path)])
        finally:
            temp_path.unlink(missing_ok=True)
        if row.get("receivedAt"):
            imported_rows.add((*key, str(row.get("receivedAt"))))
        latest_by_quiz[key] = datetime.now(timezone.utc)
        imported_dates.add(key[0])

    for quiz_date in sorted(imported_dates):
        quiz_json = ROOT / "data" / "quizzes" / f"{quiz_date}-daily.json"
        if quiz_json.exists():
            run([sys.executable, "scripts/generate_quiz_html.py", str(quiz_json)])

    if imported_dates or review_state_changed:
        if review_state_changed and not imported_dates:
            run([sys.executable, "scripts/generate_wrong_note_site.py"])
        run([sys.executable, "scripts/build_static_site.py", "--site-dir", "."])
        paths = ["index.html", "wrong-note.html", "data/review/wrong-note.json"]
        if REVIEW_STATE_PATH.exists():
            paths.append("data/review/review-state.json")
        paths.extend(f"quizzes/quiz-{quiz_date}.html" for quiz_date in sorted(imported_dates) if (ROOT / "quizzes" / f"quiz-{quiz_date}.html").exists())
        run(["git", "add", *paths])
        if has_staged_changes():
            run(["git", "commit", "-m", "Sync Google Sheets quiz results"])
        if not args.no_push:
            run(["git", "push"])
    print(f"imported={len(imported_dates)}")


if __name__ == "__main__":
    main()
