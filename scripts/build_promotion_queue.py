#!/usr/bin/env python3
import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_JSON = ROOT / "data/verification/candidate-bank-audit.json"
CANDIDATE_DIR = ROOT / "data/verification/candidate-raw"
VERIFIED_BANK_DIR = ROOT / "data/verified-question-bank"
OUT_DIR = ROOT / "data/verification"
SUBJECT_ORDER = [
    "운동생리학",
    "건강·체력평가",
    "운동처방론",
    "운동부하검사",
    "운동상해",
    "기능해부학",
    "병태생리학",
    "스포츠심리학",
]
HARD_MANUAL_CHECKS = {
    "source_stem_needs_manual_review",
    "source_text_not_matched",
    "figure_or_table_needs_manual_check",
    "choice_text_needs_manual_review",
    "official_source_crop_or_ocr_required",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_candidates():
    rows = {}
    for path in sorted(CANDIDATE_DIR.glob("*.jsonl")):
        for row in read_jsonl(path):
            row["_candidateFile"] = str(path.relative_to(ROOT))
            rows[row["id"]] = row
    return rows


def load_verified_ids():
    ids = set()
    for path in sorted(VERIFIED_BANK_DIR.glob("*.jsonl")):
        for row in read_jsonl(path):
            if row.get("id"):
                ids.add(row["id"])
    return ids


def answer_symbol(index):
    labels = ["①", "②", "③", "④", "⑤"]
    if isinstance(index, int) and 0 <= index < len(labels):
        return labels[index]
    return None


def status_for(audit_row, verified_ids):
    if audit_row["id"] in verified_ids:
        return "verified_bank"
    if audit_row["status"] == "auto_reject":
        return "blocked_machine_reject"
    if audit_row["status"] == "missing_from_auto_bank":
        return "blocked_missing_candidate"
    checks = set(audit_row.get("manualChecks") or [])
    if checks & HARD_MANUAL_CHECKS:
        return "needs_source_review"
    return "explanation_review"


def blocker_for(audit_row):
    if audit_row["status"] == "auto_reject":
        return ",".join(audit_row.get("errors") or ["auto_reject"])
    if audit_row["status"] == "missing_from_auto_bank":
        return "candidate_missing"
    checks = set(audit_row.get("manualChecks") or [])
    hard = sorted(checks & HARD_MANUAL_CHECKS)
    if hard:
        return ",".join(hard)
    return "external_sources_and_choice_explanations_needed"


def queue_item(audit_row, candidate, verified_ids):
    source = candidate.get("source") if candidate else {}
    return {
        "id": audit_row["id"],
        "state": status_for(audit_row, verified_ids),
        "blocker": blocker_for(audit_row),
        "subject": audit_row.get("subject") or (candidate or {}).get("subject"),
        "year": audit_row.get("year") or (candidate or {}).get("year"),
        "topic": audit_row.get("topic") or (candidate or {}).get("topic"),
        "type": (candidate or {}).get("type"),
        "difficulty": (candidate or {}).get("difficulty"),
        "answerIndex": (candidate or {}).get("answerIndex"),
        "answerSymbol": answer_symbol((candidate or {}).get("answerIndex")),
        "questionNo": source.get("questionNo"),
        "session": source.get("session"),
        "form": source.get("form"),
        "subjectCode": source.get("subjectCode"),
        "sourceFile": source.get("file"),
        "answerFile": source.get("answerFile"),
        "manualChecks": audit_row.get("manualChecks") or [],
        "sourceEvidenceNeeded": [
            "official_question_pdf",
            "official_answer_key",
            "external_explanation_sources_2",
            "choice_explanations",
            "manual_approval",
        ],
        "reviewer": None,
        "reviewedAt": None,
        "nextAction": next_action(status_for(audit_row, verified_ids)),
    }


def next_action(state):
    if state == "verified_bank":
        return "출제 가능. 중복 출제 정책만 확인"
    if state == "explanation_review":
        return "해설 출처 2개, 선택지별 해설, 수동승인 필드 작성"
    if state == "needs_source_review":
        return "원문/보기/OCR/그림·표 대조 후 explanation_review 재분류"
    if state == "blocked_machine_reject":
        return "자동 탈락 사유 복구 가능성 점수화 후 별도 처리"
    if state == "blocked_missing_candidate":
        return "원문 OCR/crop 후 candidate 생성"
    return "확인 필요"


def build_queue(limit_per_subject):
    audit = read_json(AUDIT_JSON)
    candidates = load_candidates()
    verified_ids = load_verified_ids()
    rows = [queue_item(row, candidates.get(row["id"]), verified_ids) for row in audit["items"]]

    first_pass = []
    by_subject = defaultdict(list)
    for row in rows:
        if row["state"] == "explanation_review":
            by_subject[row["subject"]].append(row)
    for subject in SUBJECT_ORDER:
        subject_rows = sorted(
            by_subject.get(subject, []),
            key=lambda row: (row.get("year") or 0, row.get("difficulty") or 0, row["id"]),
            reverse=True,
        )
        first_pass.extend(subject_rows[:limit_per_subject])

    summary = {
        "date": date.today().isoformat(),
        "stateModel": ["raw_candidate", "machine_passed", "explanation_review", "manual_approved", "verified_bank"],
        "totalAuditItems": len(rows),
        "stateCounts": dict(Counter(row["state"] for row in rows)),
        "verifiedCount": len(verified_ids),
        "firstPassCount": len(first_pass),
        "bySubjectFirstPass": dict(Counter(row["subject"] for row in first_pass)),
        "bySubjectExplanationReview": dict(Counter(row["subject"] for row in rows if row["state"] == "explanation_review")),
    }
    return {"summary": summary, "items": rows, "firstPass": first_pass}


def write_markdown(path, payload):
    summary = payload["summary"]
    lines = [
        "# 건강운동관리사 승격검수 큐",
        "",
        "## 요약",
        "",
        f"- verified-bank: {summary['verifiedCount']}문항",
        f"- 1차 승격검수 대상: {summary['firstPassCount']}문항",
        "",
        "| state | count |",
        "|---|---:|",
    ]
    for state, count in summary["stateCounts"].items():
        lines.append(f"| {state} | {count} |")
    lines.extend(["", "## 과목별 1차 대상", "", "| 과목 | explanation_review | first_pass |", "|---|---:|---:|"])
    for subject in SUBJECT_ORDER:
        lines.append(
            f"| {subject} | {summary['bySubjectExplanationReview'].get(subject, 0)} | {summary['bySubjectFirstPass'].get(subject, 0)} |"
        )
    lines.extend(["", "## 1차 승격검수 대상", "", "| id | state | 과목 | 주제 | 정답 | blocker | nextAction |", "|---|---|---|---|---|---|---|"])
    for row in payload["firstPass"]:
        topic = str(row.get("topic") or "").replace("|", "/")
        lines.append(
            f"| {row['id']} | {row['state']} | {row.get('subject')} | {topic} | {row.get('answerSymbol') or ''} | {row.get('blocker')} | {row.get('nextAction')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build a reproducible verified-bank promotion queue.")
    parser.add_argument("--limit-per-subject", type=int, default=10)
    parser.add_argument("--json", type=Path, default=OUT_DIR / f"promotion-queue-{date.today().isoformat()}.json")
    parser.add_argument("--md", type=Path, default=OUT_DIR / f"promotion-queue-{date.today().isoformat()}.md")
    args = parser.parse_args()

    payload = build_queue(args.limit_per_subject)
    json_path = args.json if args.json.is_absolute() else ROOT / args.json
    md_path = args.md if args.md.is_absolute() else ROOT / args.md
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(json_path.relative_to(ROOT))
    print(md_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
