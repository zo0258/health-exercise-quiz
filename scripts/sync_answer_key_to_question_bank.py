#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANSWER_KEY = ROOT / "data/verification/answer-key-2018-2025.json"
QUESTION_BANK_DIR = ROOT / "data/question-bank"
CANDIDATE_RAW_DIR = ROOT / "data/verification/candidate-raw"
INDEX_TO_CIRCLED = ["①", "②", "③", "④", "⑤"]
PLACEHOLDER_RE = re.compile(r"최종정답 기준 정답은 [①②③④⑤](?:,[①②③④⑤])*입니다\.")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def answer_maps():
    payload = read_json(ANSWER_KEY)
    by_id = {}
    by_source = {}
    for row in payload.get("records", []):
        indexes = sorted(int(value) for value in row.get("officialAnswerIndexes", []))
        if not indexes:
            continue
        by_id[row["id"]] = row
        key = (
            int(row["year"]),
            int(row["session"]),
            str(row.get("form") or "A").upper(),
            int(row["subjectCode"]),
            int(row["questionNo"]),
        )
        by_source[key] = row
    return by_id, by_source


def source_key(question):
    source = question.get("source") or {}
    values = (
        question.get("year") or source.get("year"),
        source.get("session"),
        str(source.get("form") or "A").upper(),
        source.get("subjectCode"),
        source.get("questionNo"),
    )
    if any(value in (None, "") for value in values):
        return None
    return (int(values[0]), int(values[1]), values[2], int(values[3]), int(values[4]))


def official_for(question, by_id, by_source):
    official = by_id.get(question.get("id"))
    by_source_row = by_source.get(source_key(question)) if source_key(question) else None
    if official and by_source_row and official["officialAnswerIndexes"] != by_source_row["officialAnswerIndexes"]:
        raise ValueError(f"{question.get('id')}: id/source 공식정답 불일치")
    return official or by_source_row


def labels(indexes):
    return ",".join(INDEX_TO_CIRCLED[index] for index in indexes)


def sync_question(question, official):
    indexes = sorted(int(value) for value in official["officialAnswerIndexes"])
    changed = []
    if question.get("answerIndex") not in indexes:
        question["answerIndex"] = indexes[0]
        changed.append("answerIndex")
    if question.get("answerIndexes") != indexes:
        question["answerIndexes"] = indexes
        changed.append("answerIndexes")

    evidence = dict(question.get("answerEvidence") or {})
    desired_evidence = {
        "officialAnswerIndexes": indexes,
        "officialAnswer": labels(indexes),
        "basis": official.get("basis") or "KSPO 최종정답 기준",
        "sourceFile": official.get("answerFile"),
        "questionFile": (question.get("source") or {}).get("file"),
        "questionNo": official.get("questionNo"),
    }
    if len(indexes) == 1:
        desired_evidence["officialAnswerIndex"] = indexes[0]
    for key, value in desired_evidence.items():
        if evidence.get(key) != value:
            evidence[key] = value
            changed.append(f"answerEvidence.{key}")
    if evidence != question.get("answerEvidence"):
        question["answerEvidence"] = evidence

    explanation = question.get("explanation")
    if isinstance(explanation, str) and "최종정답 기준 정답은" in explanation:
        updated = PLACEHOLDER_RE.sub(f"최종정답 기준 정답은 {labels(indexes)}입니다.", explanation)
        if updated != explanation:
            question["explanation"] = updated
            changed.append("explanation")

    explanations = question.get("choiceExplanations")
    if isinstance(explanations, list):
        correct = set(indexes)
        touched = False
        for idx, item in enumerate(explanations):
            if isinstance(item, dict):
                verdict = "correct" if idx in correct else "incorrect"
                if item.get("verdict") != verdict:
                    item["verdict"] = verdict
                    touched = True
        if touched:
            changed.append("choiceExplanations.verdict")
    return sorted(set(changed))


def target_files(include_candidates):
    files = sorted(QUESTION_BANK_DIR.glob("kspo-20*.jsonl"))
    if include_candidates:
        files.extend(sorted(CANDIDATE_RAW_DIR.glob("candidate-20*.jsonl")))
    return files


def main():
    parser = argparse.ArgumentParser(description="Sync question-bank answer fields to the normalized official answer key.")
    parser.add_argument("--apply", action="store_true", help="write corrected JSONL files")
    parser.add_argument("--include-candidates", action="store_true", help="also update data/verification/candidate-raw/*.jsonl")
    args = parser.parse_args()

    by_id, by_source = answer_maps()
    summary = {"checked": 0, "changedQuestions": 0, "changedFiles": 0, "files": []}
    for path in target_files(args.include_candidates):
        rows = read_jsonl(path)
        file_changes = []
        for row in rows:
            year = int(row.get("year") or 0)
            if year < 2018 or year > 2025:
                continue
            official = official_for(row, by_id, by_source)
            if not official:
                continue
            summary["checked"] += 1
            changed = sync_question(row, official)
            if changed:
                file_changes.append({"id": row.get("id"), "changed": changed})
        if file_changes:
            summary["changedQuestions"] += len(file_changes)
            summary["changedFiles"] += 1
            summary["files"].append({"file": str(path.relative_to(ROOT)), "changedQuestions": len(file_changes), "changes": file_changes[:50]})
            if args.apply:
                write_jsonl(path, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if file_changes and not args.apply:
        print("dry-run only; rerun with --apply to write changes")


if __name__ == "__main__":
    main()
