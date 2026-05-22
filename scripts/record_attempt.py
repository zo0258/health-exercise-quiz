#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "results" / "attempts.jsonl"
NOTE_PATH = ROOT / "notes" / "wrong-note.md"
MASTERED_PATH = ROOT / "results" / "mastered.json"
QUIZ_DIR = ROOT / "data" / "quizzes"


def parse_result(text):
    start = "[HEALTH_EXERCISE_RESULT]"
    end = "[/HEALTH_EXERCISE_RESULT]"
    if start not in text or end not in text:
        raise ValueError("결과 블록을 찾지 못했습니다.")

    body = text.split(start, 1)[1].split(end, 1)[0].strip()
    attempt = {"wrong": [], "review": [], "unanswered": [], "answerLog": []}
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("wrong="):
            payload = line.removeprefix("wrong=")
            parts = payload.split("|")
            wrong_item = {"questionId": parts[0]}
            for part in parts[1:]:
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                wrong_item[key] = value
            attempt["wrong"].append(wrong_item)
            continue
        if line.startswith("answerLog="):
            payload = line.removeprefix("answerLog=")
            parts = payload.split("|")
            answer_item = {"questionId": parts[0]}
            for part in parts[1:]:
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                answer_item[key] = value
            attempt["answerLog"].append(answer_item)
            continue
        if line.startswith("review="):
            payload = line.removeprefix("review=")
            parts = payload.split("|")
            review_item = {"questionId": parts[0]}
            for part in parts[1:]:
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                review_item[key] = value
            attempt["review"].append(review_item)
            continue
        if line.startswith("unanswered="):
            payload = line.removeprefix("unanswered=")
            parts = payload.split("|")
            unanswered_item = {"questionId": parts[0]}
            for part in parts[1:]:
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                unanswered_item[key] = value
            attempt["unanswered"].append(unanswered_item)
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            attempt[key] = value

    for number_key in ("score", "total", "answered", "unansweredCount"):
        if number_key in attempt:
            attempt[number_key] = int(attempt[number_key])

    attempt["recordedAt"] = datetime.now().isoformat(timespec="seconds")
    return attempt


def parse_mastered(text):
    start = "[HEALTH_EXERCISE_MASTERED]"
    end = "[/HEALTH_EXERCISE_MASTERED]"
    if start not in text or end not in text:
        return []
    body = text.split(start, 1)[1].split(end, 1)[0].strip()
    mastered = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("mastered="):
            mastered.append(line.split("=", 1)[1].strip())
    return [item for item in mastered if item]


def load_mastered():
    if not MASTERED_PATH.exists():
        return []
    return json.loads(MASTERED_PATH.read_text(encoding="utf-8"))


def save_mastered(question_ids):
    MASTERED_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASTERED_PATH.write_text(json.dumps(sorted(set(question_ids)), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_attempts():
    if not RESULTS_PATH.exists():
        return []
    attempts = []
    with RESULTS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                attempts.append(json.loads(line))
    return attempts


def load_quiz_for_attempt(attempt):
    quiz_id = attempt.get("quizId")
    attempt_date = attempt.get("date")
    for path in sorted(QUIZ_DIR.glob("*-daily.json")):
        try:
            quiz = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if quiz_id and quiz.get("quizId") == quiz_id:
            return quiz
        if not quiz_id and attempt_date and quiz.get("date") == attempt_date:
            return quiz
    return None


def canonicalize_attempt_answers(attempt):
    if not attempt.get("answerLog"):
        return attempt

    quiz = load_quiz_for_attempt(attempt)
    if not quiz:
        return attempt

    question_map = {question["id"]: question for question in quiz.get("questions", [])}
    old_wrong = {item.get("questionId"): item for item in attempt.get("wrong", [])}
    score = 0
    wrong = []

    for item in attempt.get("answerLog", []):
        question = question_map.get(item.get("questionId"))
        if not question:
            continue
        answer = str(int(question["answerIndex"]) + 1)
        selected = item.get("selected", "none")
        correct = "yes" if selected != "none" and selected == answer else "no"
        item["answer"] = answer
        item["correct"] = correct
        if correct == "yes":
            score += 1
            continue
        if selected != "none":
            previous = old_wrong.get(item.get("questionId"), {})
            wrong.append({
                "questionId": item.get("questionId"),
                "topic": item.get("topic") or question.get("topic", ""),
                "selected": selected,
                "answer": answer,
                "wrongReason": previous.get("wrongReason") or item.get("wrongReason") or "미선택",
                "bookmarked": previous.get("bookmarked") or item.get("bookmarked") or "no",
            })

    unanswered = []
    answered_ids = {item.get("questionId") for item in attempt.get("answerLog", [])}
    for question in quiz.get("questions", []):
        if question["id"] in answered_ids:
            continue
        unanswered.append({
            "questionId": question["id"],
            "topic": question.get("topic", ""),
            "answer": str(int(question["answerIndex"]) + 1),
        })

    attempt["wrong"] = wrong
    attempt["unanswered"] = unanswered
    attempt["score"] = score
    attempt["total"] = len(quiz.get("questions", [])) or attempt.get("total", 0)
    attempt["answered"] = len(attempt.get("answerLog", []))
    attempt["unansweredCount"] = len(unanswered)
    return attempt


def append_attempt(attempt):
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(attempt, ensure_ascii=False) + "\n")


def render_wrong_note(attempts):
    subject_counter = Counter()
    topic_counter = Counter()
    question_counter = Counter()
    reason_counter = Counter()
    review_counter = Counter()
    unanswered_counter = Counter()
    total_score = 0
    total_questions = 0

    recent_wrong = []
    recent_review = []
    for attempt in attempts:
        total_score += int(attempt.get("score", 0))
        total_questions += int(attempt.get("total", 0))
        subject = attempt.get("subject", "미분류")
        for wrong in attempt.get("wrong", []):
            subject_counter[subject] += 1
            topic = wrong.get("topic", "미분류")
            topic_counter[topic] += 1
            question_counter[wrong.get("questionId", "unknown")] += 1
            reason = wrong.get("wrongReason")
            if reason and reason != "미선택":
                reason_counter[reason] += 1
            recent_wrong.append((attempt.get("date", ""), subject, topic, wrong))
        for review in attempt.get("review", []):
            topic = review.get("topic", "미분류")
            review_counter[topic] += 1
            recent_review.append((attempt.get("date", ""), subject, topic, review))
        for unanswered in attempt.get("unanswered", []):
            topic = unanswered.get("topic", "미분류")
            unanswered_counter[topic] += 1

    accuracy = (total_score / total_questions * 100) if total_questions else 0
    lines = [
        "# 건강운동관리사 오답노트",
        "",
        f"- 갱신: {datetime.now().isoformat(timespec='seconds')}",
        f"- 누적 풀이: {len(attempts)}회",
        f"- 누적 정답률: {accuracy:.1f}%",
        "",
        "## 반복 오답 TOP 10",
        ""
    ]

    if topic_counter:
        for topic, count in topic_counter.most_common(10):
            lines.append(f"- {topic}: {count}회")
    else:
        lines.append("- 아직 누적 오답이 없습니다.")

    lines += ["", "## 과목별 오답 수", ""]
    if subject_counter:
        for subject, count in subject_counter.most_common():
            lines.append(f"- {subject}: {count}개")
    else:
        lines.append("- 아직 누적 오답이 없습니다.")

    lines += ["", "## 오답 원인", ""]
    if reason_counter:
        for reason, count in reason_counter.most_common():
            lines.append(f"- {reason}: {count}회")
    else:
        lines.append("- 아직 선택된 오답 원인이 없습니다.")

    lines += ["", "## 최근 오답", ""]
    if recent_wrong:
        for date, subject, topic, wrong in recent_wrong[-20:]:
            selected = wrong.get("selected", "none")
            answer = wrong.get("answer", "")
            reason = wrong.get("wrongReason", "미선택")
            bookmarked = wrong.get("bookmarked", "no")
            lines.append(f"- {date} | {subject} | {topic} | 내 답 {selected} / 정답 {answer} | 이유 {reason} | 다시보기 {bookmarked} | {wrong.get('questionId')}")
    else:
        lines.append("- 아직 누적 오답이 없습니다.")

    lines += ["", "## 다시 볼 문제", ""]
    if recent_review:
        for date, subject, topic, review in recent_review[-20:]:
            lines.append(f"- {date} | {subject} | {topic} | {review.get('questionId')}")
    else:
        lines.append("- 아직 표시된 다시 볼 문제가 없습니다.")

    lines += ["", "## 미응답 주의 영역", ""]
    if unanswered_counter:
        for topic, count in unanswered_counter.most_common(10):
            lines.append(f"- {topic}: {count}회")
    else:
        lines.append("- 아직 누적 미응답이 없습니다.")

    lines += [
        "",
        "## 다음 퀴즈 반영 규칙",
        "",
        "- 반복 오답 TOP 5 topic은 다음 퀴즈 후보에 우선 포함한다.",
        "- 오답 원인이 '문제 잘못 읽음'이면 같은 개념보다 짧은 판별형 문항을 먼저 배정한다.",
        "- 오답 원인이 '계산 실수'이면 같은 공식의 다른 숫자 문제를 배정한다.",
        "- 과목별 오답 수가 많은 과목은 `config/daily-selection-policy.json` 기준으로 추가 배정한다.",
        "- 다시 볼 문제로 표시된 topic은 다음 퀴즈 또는 주간 복습 후보에 포함한다.",
        "- 같은 questionId가 반복되면 같은 문항보다 같은 topic의 유사 문항을 우선 배정한다."
    ]

    NOTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Record a copied quiz result block and update wrong-note.md.")
    parser.add_argument("input", nargs="?", type=Path, help="Text file containing HEALTH_EXERCISE_RESULT block. Reads stdin when omitted.")
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
    mastered = parse_mastered(text)
    if mastered and "[HEALTH_EXERCISE_RESULT]" not in text:
        save_mastered([*load_mastered(), *mastered])
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_wrong_note_site.py")], cwd=ROOT, check=True)
        print(f"mastered: {MASTERED_PATH}")
        return

    attempt = canonicalize_attempt_answers(parse_result(text))
    append_attempt(attempt)
    if mastered:
        save_mastered([*load_mastered(), *mastered])
    attempts = load_attempts()
    render_wrong_note(attempts)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_wrong_note_site.py")], cwd=ROOT, check=True)
    print(f"recorded: {RESULTS_PATH}")
    print(f"wrong-note: {NOTE_PATH}")


if __name__ == "__main__":
    main()
