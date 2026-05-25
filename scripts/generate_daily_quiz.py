#!/usr/bin/env python3
import argparse
import json
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from verified_question_data import VERIFIED_BANK_DIR, load_verified_bank


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "daily-selection-policy.json"
QUIZ_DIR = ROOT / "data" / "quizzes"
ATTEMPTS_PATH = ROOT / "results" / "attempts.jsonl"
MASTERED_PATH = ROOT / "results" / "mastered.json"
DELIVERY_HISTORY_PATH = ROOT / "data" / "delivery-history.jsonl"


def read_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_jsonl(path):
    if not path.exists():
        return []
    items = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_no} JSONL 파싱 실패: {error}") from error
    return items


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        "<표>",
        "분포도",
    )
    if any(pattern in stem for pattern in figure_dependent_patterns) and not has_images:
        return True
    if re.search(r"[㉠-㉧]\s*,\s*,", stem) and not has_images:
        return True
    if re.search(r",\s*,\s*모두에서|,\s*에서는", stem) and not has_images:
        return True
    for choice in question.get("choices", []):
        if any(pattern in choice for pattern in artifact_patterns):
            return True
        if any(marker in choice for marker in "①②③④⑤"):
            return True
    return False


def load_bank(bank_dir):
    return load_verified_bank(bank_dir)


def load_attempts(path):
    return read_jsonl(path)


def load_mastered(path):
    if not path.exists():
        return set()
    return set(read_json(path))


def load_delivered_quizzes(quiz_dir, history_path, bank):
    bank_by_id = {question["id"]: question for question in bank}
    delivered = []
    for path in sorted(quiz_dir.glob("*-daily.json")):
        quiz = read_json(path)
        try:
            quiz_date = parse_date(quiz["date"])
        except (KeyError, ValueError):
            continue
        delivered.append((quiz_date, quiz))
    for record in read_jsonl(history_path):
        try:
            quiz_date = parse_date(record["date"])
        except (KeyError, ValueError):
            continue
        questions = []
        for question_id in record.get("questionIds", []):
            question = bank_by_id.get(question_id)
            if question:
                questions.append(question)
            else:
                questions.append({
                    "id": question_id,
                    "question": question_id,
                    "topic": f"history:{question_id}",
                })
        delivered.append((quiz_date, {
            "date": record["date"],
            "quizId": record.get("quizId", ""),
            "questions": questions,
        }))
    return delivered


def append_delivery_history(path, quiz):
    record = {
        "date": quiz["date"],
        "quizId": quiz["quizId"],
        "questionIds": [question["id"] for question in quiz["questions"]],
    }
    encoded = json.dumps(record, ensure_ascii=False)
    existing = set()
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            existing = {line.strip() for line in file if line.strip()}
    if encoded in existing:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(encoded + "\n")


def quiz_sequence(quiz):
    sequence = quiz.get("sequence")
    if isinstance(sequence, int):
        return sequence
    quiz_id = quiz.get("quizId", "")
    match = re.search(r"-daily-(\d+)-", quiz_id)
    if match:
        return int(match.group(1))
    return None


def recent_history(delivered, target_date, policy, target_sequence=None):
    dedupe = policy["deduplication"]
    topic_cutoff = target_date - timedelta(days=dedupe["sameTopicCooldownDays"])
    recent_ids = set()
    recent_topics = set()
    recent_stems = set()

    for quiz_date, quiz in delivered:
        if quiz_date > target_date:
            continue
        sequence = quiz_sequence(quiz)
        if (
            target_sequence is not None
            and quiz_date == target_date
            and sequence is not None
            and sequence >= target_sequence
        ):
            continue
        for question in quiz.get("questions", []):
            recent_ids.add(question["id"])
            recent_stems.add(normalize_stem(question["question"]))
            if topic_cutoff <= quiz_date <= target_date:
                recent_topics.add(question["topic"])
    return recent_ids, recent_topics, recent_stems


def weak_signals(attempts, target_date, policy):
    recent_cutoff = target_date - timedelta(days=policy["recentWrongWindowDays"])
    topic_counter = Counter()
    subject_counter = Counter()
    review_topics = Counter()

    for attempt in attempts:
        attempt_date_text = attempt.get("date")
        if not attempt_date_text:
            continue
        try:
            attempt_date = parse_date(attempt_date_text)
        except ValueError:
            continue
        if not (recent_cutoff <= attempt_date < target_date):
            continue
        subject = attempt.get("subject", "미분류")
        for wrong in attempt.get("wrong", []):
            topic = wrong.get("topic")
            if topic:
                topic_counter[topic] += 1
            subject_counter[subject] += 1
        for review in attempt.get("review", []):
            topic = review.get("topic")
            if topic:
                review_topics[topic] += 1

    return topic_counter, subject_counter, review_topics


def difficulty_penalty(question, selected, policy):
    target_mix = policy["qualityGuards"]["difficultyMix"]
    selected_counts = Counter(q.get("difficulty", 3) for q in selected)
    difficulty = int(question.get("difficulty", 3))
    if difficulty <= 2:
        bucket = "easy"
    elif difficulty == 3:
        bucket = "medium"
    else:
        bucket = "hard"
    if selected_counts[difficulty] >= target_mix.get(bucket, 99):
        return 8
    return 0


def score_candidate(question, selected, subject_targets, topic_counter, subject_counter, review_topics, rng, policy):
    subject_counts = Counter(q["subject"] for q in selected)
    topic_counts = Counter(q["topic"] for q in selected)
    answer_counts = Counter(q["answerIndex"] for q in selected)
    score = 0

    subject_need = subject_targets.get(question["subject"], 0) - subject_counts[question["subject"]]
    score += max(subject_need, 0) * 20
    score += min(subject_counter[question["subject"]], policy["maxExtraQuestionsPerWeakSubject"]) * 10
    score += min(topic_counter[question["topic"]], 3) * 18
    score += min(review_topics[question["topic"]], 2) * 12
    score += int(question.get("difficulty", 3)) * 2
    if question.get("wrongRateBasis"):
        score += 3

    score -= topic_counts[question["topic"]] * 25
    score -= answer_counts[question["answerIndex"]] * 4
    score -= difficulty_penalty(question, selected, policy)
    score += rng.random()
    return score


def can_add(question, selected, policy, allow_partial):
    dedupe = policy["deduplication"]
    guards = policy["qualityGuards"]
    subject_counts = Counter(q["subject"] for q in selected)
    topic_counts = Counter(q["topic"] for q in selected)
    answer_counts = Counter(int(q["answerIndex"]) for q in selected)

    if any(question["id"] == q["id"] for q in selected):
        return False
    if any(question["_normalizedStem"] == q["_normalizedStem"] for q in selected):
        return False
    if subject_counts[question["subject"]] >= dedupe["maxSameSubjectPerDay"] and not allow_partial:
        return False
    if topic_counts[question["topic"]] >= dedupe["maxSameTopicPerDay"] and not allow_partial:
        return False
    if answer_counts[int(question["answerIndex"])] >= guards["answerBalance"]["maxSameAnswerCount"] and not allow_partial:
        return False
    return True


def select_questions(bank, policy, attempts, delivered, mastered_ids, target_date, count, allow_partial, target_sequence=None):
    rng = random.Random(target_date.isoformat())
    subject_targets = dict(policy["defaultSubjectAllocation"])
    recent_ids, recent_topics, recent_stems = recent_history(delivered, target_date, policy, target_sequence)
    topic_counter, subject_counter, review_topics = weak_signals(attempts, target_date, policy)

    strict_pool = [
        q for q in bank
        if q["id"] not in mastered_ids
        and q["id"] not in recent_ids
        and q["_normalizedStem"] not in recent_stems
        and (allow_partial or q["topic"] not in recent_topics or topic_counter[q["topic"]] >= policy["repeatWrongTopicThreshold"])
    ]
    if allow_partial and not strict_pool:
        strict_pool = [q for q in bank if q["id"] not in recent_ids and q["_normalizedStem"] not in recent_stems]
    if allow_partial and not strict_pool:
        strict_pool = list(bank)

    selected = []
    required_subjects = set(subject_targets)

    for subject in required_subjects:
        if len(selected) >= count:
            break
        subject_pool = [q for q in strict_pool if q["subject"] == subject and can_add(q, selected, policy, allow_partial)]
        if not subject_pool and not allow_partial:
            subject_pool = [
                q for q in bank
                if q["subject"] == subject
                and q["id"] not in mastered_ids
                and q["id"] not in recent_ids
                and q["_normalizedStem"] not in recent_stems
                and can_add(q, selected, policy, allow_partial)
            ]
        if not subject_pool:
            continue
        subject_pool.sort(key=lambda q: score_candidate(q, selected, subject_targets, topic_counter, subject_counter, review_topics, rng, policy), reverse=True)
        selected.append(subject_pool[0])

    while len(selected) < count:
        candidates = [q for q in strict_pool if can_add(q, selected, policy, allow_partial)]
        if not candidates:
            if allow_partial:
                break
            raise RuntimeError("정책을 만족하는 후보가 부족합니다. 문제은행을 보강해야 합니다.")
        candidates.sort(key=lambda q: score_candidate(q, selected, subject_targets, topic_counter, subject_counter, review_topics, rng, policy), reverse=True)
        selected.append(candidates[0])

    missing_subjects = sorted(required_subjects - {q["subject"] for q in selected})
    if missing_subjects and not allow_partial:
        raise RuntimeError(f"8과목 최소 1문항 조건을 만족하지 못했습니다: {', '.join(missing_subjects)}")
    if len(selected) != count and not allow_partial:
        raise RuntimeError(f"요청 문항 수를 채우지 못했습니다: {len(selected)} / {count}")

    selected = order_for_exam_flow(selected)
    for question in selected:
        question.pop("_bankFile", None)
        question.pop("_normalizedStem", None)
    return selected, missing_subjects


def order_for_exam_flow(questions):
    def flow_key(question):
        difficulty = int(question.get("difficulty", 3))
        qtype = question.get("type", "")
        text_len = len(question.get("question", ""))
        if difficulty <= 3 and qtype in {"개념구분", "부정형"} and text_len < 180:
            bucket = 0
        elif difficulty >= 5 or qtype in {"계산", "보기조합"}:
            bucket = 2
        else:
            bucket = 1
        return (bucket, difficulty, text_len, question["subject"], question["id"])

    return sorted(questions, key=flow_key)


def today_kst():
    return datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()


def sequence_label(sequence):
    if sequence == 1:
        return "오전"
    if sequence == 2:
        return "저녁"
    return f"{sequence}회"


def sequence_display_date(target_date, sequence):
    if not sequence:
        return target_date.isoformat()
    return f"{target_date.isoformat()} ({sequence_label(sequence)})"


def build_quiz(questions, target_date, allow_partial, missing_subjects, sequence):
    subjects = Counter(q["subject"] for q in questions)
    subject_text = "전과목" if len(subjects) > 1 else (next(iter(subjects)) if subjects else "미분류")
    round_text = f"시험 임박 전과목 {len(questions)}문항"
    if allow_partial:
        round_text = "부분 문제은행 점검용"
    source_years = sorted({str(q.get("year", "")) for q in questions if q.get("year")})
    date_text = target_date.isoformat()
    slug = f"{date_text}-{sequence}" if sequence else date_text
    display_date = sequence_display_date(target_date, sequence)
    quiz_id = f"{date_text}-daily-{sequence}-all-subjects" if sequence else f"{date_text}-daily-all-subjects"
    quiz = {
        "quizId": quiz_id,
        "date": date_text,
        "displayDate": display_date,
        "slug": slug,
        "sequence": sequence,
        "title": "건강운동관리사 데일리 퀴즈",
        "subject": subject_text,
        "round": round_text,
        "timeLimitMinutes": max(8, len(questions) * 1),
        "sourceSummary": f"{', '.join(source_years)}년 문제·정답·해설 검증 로우데이터 기반",
        "generationNote": "검증 로우데이터 기반 생성. answerVerified와 explanationVerified가 모두 true인 문항만 출제 후보에 포함합니다.",
        "missingSubjects": missing_subjects,
        "questions": questions,
    }
    return quiz


def run_script(script_name, *args):
    command = [sys.executable, str(ROOT / "scripts" / script_name), *map(str, args)]
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description="Generate a daily all-subject quiz JSON and optional mobile HTML.")
    parser.add_argument("--date", default=today_kst(), help="Quiz date, YYYY-MM-DD. Defaults to Asia/Seoul today.")
    parser.add_argument("--count", type=int, help="Question count. Defaults to policy dailyQuestionCount.")
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--bank-dir", type=Path, default=VERIFIED_BANK_DIR, help="검증 완료 로우데이터 JSONL 디렉터리")
    parser.add_argument("--attempts", type=Path, default=ATTEMPTS_PATH)
    parser.add_argument("--mastered", type=Path, default=MASTERED_PATH)
    parser.add_argument("--output", type=Path, help="Output quiz JSON path.")
    parser.add_argument("--sequence", type=int, choices=(1, 2), metavar="N", help="Daily sequence: 1=오전, 2=저녁.")
    parser.add_argument("--html", action="store_true", help="Also generate the mobile HTML delivery file.")
    parser.add_argument("--allow-partial", action="store_true", help="검증 로우데이터 안에서만 부분 생성합니다. 미검증 문항은 어떤 경우에도 포함하지 않습니다.")
    parser.add_argument("--skip-validation", action="store_true", help="Skip policy validation after generation.")
    args = parser.parse_args()

    target_date = parse_date(args.date)
    policy_path = args.policy if args.policy.is_absolute() else ROOT / args.policy
    bank_dir = args.bank_dir if args.bank_dir.is_absolute() else ROOT / args.bank_dir
    attempts_path = args.attempts if args.attempts.is_absolute() else ROOT / args.attempts
    mastered_path = args.mastered if args.mastered.is_absolute() else ROOT / args.mastered
    output_stem = f"{target_date.isoformat()}-{args.sequence}-daily" if args.sequence else f"{target_date.isoformat()}-daily"
    output_path = args.output or QUIZ_DIR / f"{output_stem}.json"
    output_path = output_path if output_path.is_absolute() else ROOT / output_path

    policy = read_json(policy_path)
    count = args.count or int(policy["dailyQuestionCount"])
    try:
        bank = load_bank(bank_dir)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if not bank:
        raise SystemExit(
            f"검증 완료 로우데이터가 없습니다: {bank_dir}\n"
            "문제·정답·해설 검증이 끝난 JSONL만 data/verified-question-bank/에 넣은 뒤 출제할 수 있습니다."
        )

    attempts = load_attempts(attempts_path)
    mastered_ids = load_mastered(mastered_path)
    delivered = load_delivered_quizzes(QUIZ_DIR, DELIVERY_HISTORY_PATH, bank)
    try:
        questions, missing_subjects = select_questions(bank, policy, attempts, delivered, mastered_ids, target_date, count, args.allow_partial, args.sequence)
    except RuntimeError as error:
        raise SystemExit(f"생성 중단: {error}") from error
    quiz = build_quiz(questions, target_date, args.allow_partial, missing_subjects, args.sequence)
    write_json(output_path, quiz)
    print(output_path)

    audit_result = run_script("audit_quiz_answers.py", output_path)
    sys.stdout.write(audit_result.stdout)
    sys.stderr.write(audit_result.stderr)
    if audit_result.returncode != 0:
        raise SystemExit(audit_result.returncode)

    if not args.skip_validation and not args.allow_partial:
        result = run_script("validate_quiz_policy.py", output_path)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode != 0:
            raise SystemExit(result.returncode)

    if args.html:
        result = run_script("generate_quiz_html.py", output_path)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode != 0:
            raise SystemExit(result.returncode)

    append_delivery_history(DELIVERY_HISTORY_PATH, quiz)


if __name__ == "__main__":
    main()
