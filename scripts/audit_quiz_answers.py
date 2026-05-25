#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from extract_kspo_question_bank import SESSION_SUBJECTS, parse_answer_rows


ROOT = Path(__file__).resolve().parents[1]
ANSWER_KEY_PATH = ROOT / "data/verification/answer-key-2018-2025.json"


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_form(value):
    return str(value or "A").upper()


def answer_key_indexes(records):
    by_id = {}
    by_source = {}
    for record in records:
        indexes = record.get("officialAnswerIndexes")
        if indexes is None:
            indexes = [record.get("officialAnswerIndex")]
        indexes = sorted(int(index) for index in indexes if index is not None)
        if not indexes:
            continue
        by_id[record["id"]] = indexes
        source_key = (
            int(record["year"]),
            int(record["session"]),
            normalize_form(record.get("form")),
            int(record["subjectCode"]),
            int(record["questionNo"]),
        )
        by_source[source_key] = indexes
    return by_id, by_source


def source_key(question):
    source = question.get("source") or {}
    required = ["year", "session", "subjectCode", "questionNo"]
    values = {
        "year": question.get("year") or source.get("year"),
        "session": source.get("session"),
        "subjectCode": source.get("subjectCode"),
        "questionNo": source.get("questionNo"),
    }
    missing = [key for key in required if values.get(key) in (None, "")]
    if missing:
        raise ValueError(f"공식 정답 대조 필드 누락: {', '.join(missing)}")
    return (
        int(values["year"]),
        int(values["session"]),
        normalize_form(source.get("form")),
        int(values["subjectCode"]),
        int(values["questionNo"]),
    )


def evidence_indexes(question):
    evidence = question.get("answerEvidence") or {}
    values = evidence.get("officialAnswerIndexes")
    if values is not None:
        return sorted(int(value) for value in values)
    value = evidence.get("officialAnswerIndex")
    if value is not None:
        return [int(value)]
    return []


def official_from_source_file(question, cache):
    source = question.get("source") or {}
    answer_file = source.get("answerFile")
    if not answer_file:
        return None
    answer_path = ROOT / answer_file
    rows = cache.get(answer_path)
    if rows is None:
        rows = parse_answer_rows(answer_path)
        cache[answer_path] = rows

    session = int(source.get("session"))
    form = normalize_form(source.get("form"))
    question_no = int(source.get("questionNo"))
    subject = question.get("subject")
    subjects = [name for name, _code in SESSION_SUBJECTS[session]]
    subject_index = subjects.index(subject)
    value = rows[(session, form)][subject_index][question_no - 1]
    return value if isinstance(value, list) else [value]


def audit(quiz, answer_key):
    records = answer_key.get("records") or []
    by_id, by_source = answer_key_indexes(records)
    errors = []
    checked = 0
    source_answer_cache = {}

    for position, question in enumerate(quiz.get("questions") or [], start=1):
        question_id = question.get("id") or f"Q{position}"
        answer_index = int(question.get("answerIndex", -1))
        official = by_id.get(question_id)
        try:
            official_by_source = by_source.get(source_key(question))
        except Exception as error:
            errors.append(f"{question_id}: {error}")
            continue

        if official is None:
            official = official_by_source
        elif official_by_source is not None and official != official_by_source:
            errors.append(
                f"{question_id}: 공식 정답표 id/source 대조값 불일치 "
                f"id={','.join(str(i + 1) for i in official)} "
                f"source={','.join(str(i + 1) for i in official_by_source)}"
            )

        if official is None:
            try:
                official = official_from_source_file(question, source_answer_cache)
            except Exception as error:
                errors.append(f"{question_id}: 공식 정답표에서 문항을 찾지 못함 ({error})")
                continue

        checked += 1
        if answer_index not in official:
            errors.append(
                f"{question_id}: 퀴즈 정답 불일치 "
                f"quiz={answer_index + 1} official={','.join(str(i + 1) for i in official)}"
            )

        evidence = evidence_indexes(question)
        if evidence and evidence != official:
            errors.append(
                f"{question_id}: answerEvidence와 공식 정답표 불일치 "
                f"evidence={','.join(str(i + 1) for i in evidence)} "
                f"official={','.join(str(i + 1) for i in official)}"
            )

        explanations = question.get("choiceExplanations") or []
        correct_verdicts = [
            index for index, item in enumerate(explanations)
            if isinstance(item, dict) and item.get("verdict") == "correct"
        ]
        if correct_verdicts and sorted(correct_verdicts) != official:
            errors.append(
                f"{question_id}: 선택지별 해설 correct 표시 불일치 "
                f"choiceExplanations={','.join(str(i + 1) for i in correct_verdicts)} "
                f"official={','.join(str(i + 1) for i in official)}"
            )

    return checked, errors


def main():
    parser = argparse.ArgumentParser(description="Audit quiz answers against the independent official answer key.")
    parser.add_argument("quiz_json", type=Path)
    parser.add_argument("--answer-key", type=Path, default=ANSWER_KEY_PATH)
    args = parser.parse_args()

    quiz_path = args.quiz_json if args.quiz_json.is_absolute() else ROOT / args.quiz_json
    answer_key_path = args.answer_key if args.answer_key.is_absolute() else ROOT / args.answer_key
    quiz = load_json(quiz_path)
    answer_key = load_json(answer_key_path)
    checked, errors = audit(quiz, answer_key)

    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        raise SystemExit(1)
    print(f"answer-audit-ok checked={checked}")


if __name__ == "__main__":
    main()
