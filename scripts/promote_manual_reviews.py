#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from verified_question_data import load_verified_bank


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_DIR = ROOT / "data/verification/candidate-raw"
VERIFIED_PATH = ROOT / "data/verified-question-bank/verified-2026-05-25.jsonl"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def load_candidates():
    rows = {}
    for path in sorted(CANDIDATE_DIR.glob("*.jsonl")):
        for row in read_jsonl(path):
            rows[row["id"]] = row
    return rows


def promoted_question(candidate, annotation):
    answer_index = int(candidate["answerIndex"])
    choice_reasons = annotation["choiceReasons"]
    if len(choice_reasons) != len(candidate.get("choices") or []):
        raise ValueError(f"{candidate['id']}: choiceReasons 수 불일치")
    sources = annotation["sources"]
    if len(sources) < 2:
        raise ValueError(f"{candidate['id']}: 해설 출처 2개 미만")
    question = dict(candidate)
    question.update(
        {
            "sourceVerified": True,
            "answerVerified": True,
            "explanationVerified": True,
            "answerStatus": "official_verified",
            "explanationStatus": "cross_checked",
            "parserConfidence": "manual",
            "manualApproved": True,
            "reviewer": annotation.get("reviewer") or "Diana",
            "reviewedAt": annotation["reviewedAt"],
            "sourceEvidence": [
                {
                    "type": "official_question_pdf",
                    "status": "matched_by_candidate_audit",
                    "file": candidate["source"]["file"],
                    "questionNo": candidate["source"]["questionNo"],
                },
                {
                    "type": "official_answer_key",
                    "status": "matched_by_audit_quiz_answers",
                    "file": candidate["source"]["answerFile"],
                    "answerIndexes": candidate["answerEvidence"]["officialAnswerIndexes"],
                },
            ],
            "explanation": annotation["correctRationale"],
            "correctRationale": annotation["correctRationale"],
            "reviewPoint": annotation["reviewPoint"],
            "externalReview": {"sources": sources},
            "explanationSources": sources,
            "choiceExplanationsVerified": True,
            "choiceExplanations": [
                {
                    "choiceIndex": index,
                    "verdict": "correct" if index == answer_index else "incorrect",
                    "reason": reason,
                }
                for index, reason in enumerate(choice_reasons)
            ],
            "verificationTodo": [],
            "bankSource": "공식 KSPO 원문 자동 추출 + 정답키 재대조 + Diana 수동 해설 검수",
            "verified": True,
        }
    )
    return question


def main():
    parser = argparse.ArgumentParser(description="Promote manually reviewed candidates into verified-question-bank.")
    parser.add_argument("annotation_json", type=Path)
    parser.add_argument("--out", type=Path, default=VERIFIED_PATH)
    args = parser.parse_args()

    annotation_path = args.annotation_json if args.annotation_json.is_absolute() else ROOT / args.annotation_json
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    annotations = read_json(annotation_path)
    candidates = load_candidates()
    existing = {row["id"]: row for row in read_jsonl(out_path)}
    promoted = []
    for annotation in annotations["items"]:
        question_id = annotation["id"]
        if question_id not in candidates:
            raise ValueError(f"{question_id}: candidate 없음")
        promoted_question_row = promoted_question(candidates[question_id], annotation)
        existing[question_id] = promoted_question_row
        promoted.append(question_id)
    rows = [existing[key] for key in sorted(existing)]
    write_jsonl(out_path, rows)
    load_verified_bank(out_path.parent)
    print(json.dumps({"promoted": promoted, "verifiedCount": len(rows), "out": str(out_path.relative_to(ROOT))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
