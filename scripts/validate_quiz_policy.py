#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from extract_kspo_question_bank import parse_answer_rows


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "daily-selection-policy.json"
ATTEMPTS_PATH = ROOT / "results" / "attempts.jsonl"
DELIVERY_HISTORY_PATH = ROOT / "data" / "delivery-history.jsonl"
QUESTION_BANK_DIR = ROOT / "data" / "question-bank"
HTML_QUIZ_DIR = ROOT / "quizzes"


SESSION_SUBJECTS = {
    1: ["운동생리학", "건강·체력평가", "운동처방론", "운동부하검사"],
    2: ["운동상해", "기능해부학", "병태생리학", "스포츠심리학"],
}


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


def load_question_bank(bank_dir):
    bank = {}
    duplicates = []
    for path in sorted(bank_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as file:
            for line_no, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                question = json.loads(line)
                question_id = question.get("id")
                if not question_id:
                    continue
                if question_id in bank:
                    duplicates.append(question_id)
                    continue
                bank[question_id] = {
                    "question": question,
                    "path": path,
                    "line": line_no,
                }
    if duplicates:
        duplicated = ", ".join(sorted(set(duplicates))[:20])
        raise ValueError(f"문제은행 questionId 중복: {duplicated}")
    return bank


def infer_session(question):
    source = question.get("source") or {}
    if source.get("session"):
        return int(source["session"])
    subject = question.get("subject")
    for session, subjects in SESSION_SUBJECTS.items():
        if subject in subjects:
            return session
    return None


def official_answer_index(question, answer_cache):
    source = question.get("source") or {}
    answer_file = source.get("answerFile")
    question_no = source.get("questionNo")
    session = infer_session(question)
    form = source.get("form") or "A"
    subject = question.get("subject")

    missing = []
    if not answer_file:
        missing.append("source.answerFile")
    if not question_no:
        missing.append("source.questionNo")
    if not session:
        missing.append("source.session 또는 subject")
    if subject not in SESSION_SUBJECTS.get(session, []):
        missing.append("subject")
    if missing:
        raise ValueError(f"공식 정답 대조 필드 누락: {', '.join(missing)}")

    answer_path = ROOT / answer_file
    if not answer_path.exists():
        raise FileNotFoundError(f"공식 정답 파일 없음: {answer_file}")

    rows = answer_cache.get(answer_path)
    if rows is None:
        rows = parse_answer_rows(answer_path)
        answer_cache[answer_path] = rows

    subjects = SESSION_SUBJECTS[session]
    subject_index = subjects.index(subject)
    return rows[(session, form)][subject_index][int(question_no) - 1]


def validate_answers(questions, bank):
    errors = []
    warnings = []
    answer_cache = {}

    for question in questions:
        question_id = question.get("id", "id없음")
        answer_index = int(question.get("answerIndex", -1))

        bank_record = bank.get(question_id)
        if not bank_record:
            warnings.append(f"문제은행에 없는 문항입니다: {question_id}")
        else:
            bank_answer = int(bank_record["question"].get("answerIndex", -1))
            if answer_index != bank_answer:
                errors.append(
                    f"문제은행 정답과 불일치: {question_id} "
                    f"quiz={answer_index + 1} bank={bank_answer + 1}"
                )

        try:
            official_answer = official_answer_index(question, answer_cache)
        except Exception as error:
            errors.append(f"공식 정답 대조 실패: {question_id} ({error})")
            continue

        if answer_index != official_answer:
            source = question.get("source") or {}
            errors.append(
                f"공식 최종정답과 불일치: {question_id} "
                f"Q{source.get('questionNo', '?')} quiz={answer_index + 1} official={official_answer + 1}"
            )

    return errors, warnings


def validate_bank_answers(bank):
    errors = []
    answer_cache = {}
    for question_id, record in sorted(bank.items()):
        question = record["question"]
        try:
            official_answer = official_answer_index(question, answer_cache)
        except Exception as error:
            errors.append(f"문제은행 공식 정답 대조 실패: {question_id} ({error})")
            continue
        answer_index = int(question.get("answerIndex", -1))
        if answer_index != official_answer:
            errors.append(
                f"문제은행 공식 최종정답과 불일치: {question_id} "
                f"bank={answer_index + 1} official={official_answer + 1}"
            )
    return errors


def validate(quiz, policy, attempts, history, bank):
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

    answer_errors, answer_warnings = validate_answers(questions, bank)
    errors.extend(answer_errors)
    warnings.extend(answer_warnings)

    return errors, warnings


def validate_one(quiz_path, policy, attempts, history, bank):
    quiz = load_json(quiz_path)
    return validate(quiz, policy, attempts, history, bank)


def html_quiz_path(quiz):
    slug = quiz.get("slug") or quiz["date"]
    return HTML_QUIZ_DIR / f"quiz-{slug}.html"


def load_html_quiz(path):
    raw = path.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="quiz-data" type="application/json">(.*?)</script>',
        raw,
        re.S,
    )
    if not match:
        raise ValueError("HTML quiz-data script를 찾지 못했습니다.")
    return json.loads(match.group(1))


def validate_html_matches_json(quiz):
    errors = []
    path = html_quiz_path(quiz)
    if not path.exists():
        errors.append(f"HTML 퀴즈 파일 없음: {path.relative_to(ROOT)}")
        return errors

    html_quiz = load_html_quiz(path)
    json_questions = quiz.get("questions", [])
    html_questions = html_quiz.get("questions", [])
    if len(json_questions) != len(html_questions):
        errors.append(
            f"HTML 문항 수 불일치: {path.relative_to(ROOT)} "
            f"json={len(json_questions)} html={len(html_questions)}"
        )
        return errors

    for index, (json_question, html_question) in enumerate(zip(json_questions, html_questions), start=1):
        if json_question.get("id") != html_question.get("id"):
            errors.append(
                f"HTML 문항 순서 불일치: {path.relative_to(ROOT)} Q{index} "
                f"json={json_question.get('id')} html={html_question.get('id')}"
            )
            continue
        for field in ("answerIndex", "explanation", "question", "choices"):
            if json_question.get(field) != html_question.get(field):
                errors.append(
                    f"HTML {field} 불일치: {path.relative_to(ROOT)} "
                    f"{json_question.get('id')}"
                )
    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate a daily quiz against selection and deduplication policy.")
    parser.add_argument("quiz_json", nargs="?", type=Path)
    parser.add_argument("--all", action="store_true", help="Validate every data/quizzes/*-daily.json file.")
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--attempts", type=Path, default=ATTEMPTS_PATH)
    parser.add_argument("--history", type=Path, default=DELIVERY_HISTORY_PATH)
    parser.add_argument("--bank-dir", type=Path, default=QUESTION_BANK_DIR)
    args = parser.parse_args()

    if not args.all and not args.quiz_json:
        parser.error("quiz_json 또는 --all 중 하나가 필요합니다.")

    policy_path = args.policy if args.policy.is_absolute() else ROOT / args.policy
    attempts_path = args.attempts if args.attempts.is_absolute() else ROOT / args.attempts
    history_path = args.history if args.history.is_absolute() else ROOT / args.history
    bank_dir = args.bank_dir if args.bank_dir.is_absolute() else ROOT / args.bank_dir

    policy = load_json(policy_path)
    attempts = load_attempts(attempts_path)
    history = load_history(history_path)
    bank = load_question_bank(bank_dir)

    quiz_paths = []
    if args.all:
        quiz_paths = sorted((ROOT / "data" / "quizzes").glob("*-daily.json"))
    else:
        quiz_path = args.quiz_json if args.quiz_json.is_absolute() else ROOT / args.quiz_json
        quiz_paths = [quiz_path]

    all_errors = []
    all_warnings = []
    if args.all:
        all_errors.extend(validate_bank_answers(bank))
    for quiz_path in quiz_paths:
        quiz = load_json(quiz_path)
        errors, warnings = validate(quiz, policy, attempts, history, bank)
        if args.all:
            errors.extend(validate_html_matches_json(quiz))
        all_warnings.extend(f"{quiz_path.relative_to(ROOT)}: {warning}" for warning in warnings)
        all_errors.extend(f"{quiz_path.relative_to(ROOT)}: {error}" for error in errors)

    for warning in all_warnings:
        print(f"WARNING: {warning}")
    for error in all_errors:
        print(f"ERROR: {error}")

    if all_errors:
        raise SystemExit(1)
    print("quiz-policy-ok")


if __name__ == "__main__":
    main()
