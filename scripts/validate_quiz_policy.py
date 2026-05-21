#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "daily-selection-policy.json"
ATTEMPTS_PATH = ROOT / "results" / "attempts.jsonl"
DELIVERY_HISTORY_PATH = ROOT / "data" / "delivery-history.jsonl"


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def normalize_stem(text):
    return "".join(str(text).split()).lower()


def has_extraction_artifact(question):
    artifact_patterns = ("건강운동관리사 필기시험", "A형 건강운동관리사", "B형 건강운동관리사")
    stem = question.get("question", "")
    has_images = bool(question.get("images"))
    figure_dependent_patterns = (
        "<그림>",
        "그림>",
        "분포도",
    )
    if any(pattern in stem for pattern in figure_dependent_patterns) and not has_images:
        return True
    if re.search(r"[㉠-㉧]\s*,\s*,", stem):
        return True
    if re.search(r",\s*,\s*모두에서|,\s*에서는", stem):
        return True
    for choice in question.get("choices", []):
        if any(pattern in choice for pattern in artifact_patterns):
            return True
        if any(marker in choice for marker in "①②③④⑤"):
            return True
    return False


def load_attempts(path):
    if not path.exists():
        return []
    attempts = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                attempts.append(json.loads(line))
    return attempts


def load_history(path):
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))
    return records


def validate(quiz, policy, attempts, history):
    errors = []
    warnings = []
    questions = quiz.get("questions", [])
    quiz_date = parse_date(quiz["date"])
    dedupe = policy["deduplication"]
    guards = policy["qualityGuards"]

    if len(questions) != policy["dailyQuestionCount"]:
        warnings.append(f"문항 수가 정책값과 다릅니다: {len(questions)} / {policy['dailyQuestionCount']}")

    ids = [q["id"] for q in questions]
    for question_id, count in Counter(ids).items():
        if count > 1:
            errors.append(f"같은 questionId가 하루 안에 중복되었습니다: {question_id}")

    subjects = Counter(q["subject"] for q in questions)
    topics = Counter(q["topic"] for q in questions)
    traps = Counter(q.get("trap", "") for q in questions if q.get("trap"))
    types = Counter(q.get("type", "미분류") for q in questions)
    answers = Counter(int(q["answerIndex"]) + 1 for q in questions)
    stems = Counter(normalize_stem(q["question"]) for q in questions)
    current_id_set = set(ids)

    for subject, count in subjects.items():
        if count > dedupe["maxSameSubjectPerDay"]:
            errors.append(f"하루 과목 상한 초과: {subject} {count}문항")

    for topic, count in topics.items():
        if count > dedupe["maxSameTopicPerDay"]:
            errors.append(f"하루 topic 상한 초과: {topic} {count}문항")

    for trap, count in traps.items():
        if count > 2:
            warnings.append(f"같은 trap이 하루 2문항을 넘었습니다: {trap} {count}문항")

    for qtype, count in types.items():
        if count > dedupe["maxSameTypePerDay"]:
            warnings.append(f"같은 문제 유형이 많습니다: {qtype} {count}문항")

    for answer, count in answers.items():
        if count > guards["answerBalance"]["maxSameAnswerCount"]:
            errors.append(f"정답 번호 편향 초과: {answer}번 {count}문항")

    for stem, count in stems.items():
        if count > 1:
            errors.append(f"normalizedStem 기준 동일 문항 중복 가능성: {stem[:40]}...")

    for question in questions:
        if has_extraction_artifact(question):
            errors.append(f"보기 추출 노이즈가 남아 있습니다: {question['id']}")

    for record in history:
        record_date_text = record.get("date")
        if record_date_text:
            try:
                record_date = parse_date(record_date_text)
            except ValueError:
                record_date = None
            if record_date and record_date >= quiz_date:
                continue
        history_ids = set(record.get("questionIds", []))
        if history_ids == current_id_set:
            continue
        duplicated = sorted(current_id_set & history_ids)
        if duplicated:
            errors.append(
                f"출제 이력 장부와 문항 중복: {record.get('date', '날짜없음')} "
                f"{', '.join(duplicated)}"
            )

    seen_recent_ids = {}
    seen_recent_topics = defaultdict(list)
    exact_cutoff = quiz_date - timedelta(days=dedupe["exactQuestionCooldownDays"])
    topic_cutoff = quiz_date - timedelta(days=dedupe["sameTopicCooldownDays"])

    for attempt in attempts:
        attempt_date_text = attempt.get("date")
        if not attempt_date_text:
            continue
        attempt_date = parse_date(attempt_date_text)
        for wrong in attempt.get("wrong", []):
            question_id = wrong.get("questionId")
            topic = wrong.get("topic")
            if question_id and exact_cutoff <= attempt_date < quiz_date:
                seen_recent_ids[question_id] = attempt_date_text
            if topic and topic_cutoff <= attempt_date < quiz_date:
                seen_recent_topics[topic].append(attempt_date_text)

    for question in questions:
        if question["id"] in seen_recent_ids:
            errors.append(f"최근 {dedupe['exactQuestionCooldownDays']}일 내 오답 원문 재출제: {question['id']} ({seen_recent_ids[question['id']]})")
        if question["topic"] in seen_recent_topics:
            warnings.append(f"최근 {dedupe['sameTopicCooldownDays']}일 내 topic 반복: {question['topic']} ({', '.join(seen_recent_topics[question['topic']])})")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate a daily quiz against selection and deduplication policy.")
    parser.add_argument("quiz_json", type=Path)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--attempts", type=Path, default=ATTEMPTS_PATH)
    parser.add_argument("--history", type=Path, default=DELIVERY_HISTORY_PATH)
    args = parser.parse_args()

    quiz_path = args.quiz_json if args.quiz_json.is_absolute() else ROOT / args.quiz_json
    policy_path = args.policy if args.policy.is_absolute() else ROOT / args.policy
    attempts_path = args.attempts if args.attempts.is_absolute() else ROOT / args.attempts
    history_path = args.history if args.history.is_absolute() else ROOT / args.history

    quiz = load_json(quiz_path)
    policy = load_json(policy_path)
    attempts = load_attempts(attempts_path)
    history = load_history(history_path)
    errors, warnings = validate(quiz, policy, attempts, history)

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        raise SystemExit(1)
    print("quiz-policy-ok")


if __name__ == "__main__":
    main()
