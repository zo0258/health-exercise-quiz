#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANSWER_KEY = ROOT / "data/verification/answer-key-2018-2025.json"
QUEUE = ROOT / "data/verification/2018-2025-verification-queue.json"
CANDIDATE_DIR = ROOT / "data/verification/candidate-raw"
OUT_JSON = ROOT / "data/verification/candidate-bank-audit.json"
OUT_MD = ROOT / "data/verification/candidate-bank-audit.md"
TEXT_CACHE = ROOT / "data/verification/text-cache"

ALLOWED_YEARS = set(range(2018, 2026))
FIGURE_TERMS = ("<그림>", "<표>", "그래프", "분포도", "심전도", "그림")
FOOTER_CONTAMINATION_TERMS = (
    "건강운동관리사 자격검정",
    "본 문제는 저작권법에",
    "한국스포츠정책과학원",
    "본 제작물에는",
    "대한인쇄문화협회",
    "페이지",
    "쪽",
)
REQUIRED_MANUAL_APPROVAL_FIELDS = (
    "manualApproved",
    "reviewer",
    "reviewedAt",
    "sourceEvidence",
    "choiceExplanationsVerified",
)
PLACEHOLDER_TERMS = (
    "해설 보강 전 기본 문항",
    "최종정답 기준 정답은",
    "정답 기준과 맞지 않는 보기입니다",
    "최종정답 기준에 맞는 보기입니다",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(text):
    return re.sub(r"\s+", "", str(text or "")).lower()


def compact_snippet(text, limit=80):
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value[:limit]


def answer_maps():
    payload = read_json(ANSWER_KEY)
    by_id = {}
    by_source = {}
    for row in payload.get("records", []):
        indexes = sorted(int(value) for value in row.get("officialAnswerIndexes", []))
        by_id[row["id"]] = indexes
        key = (int(row["year"]), int(row["session"]), str(row.get("form") or "A").upper(), int(row["subjectCode"]), int(row["questionNo"]))
        by_source[key] = indexes
    return by_id, by_source


def candidate_rows():
    rows = []
    for path in sorted(CANDIDATE_DIR.glob("*.jsonl")):
        for item in read_jsonl(path):
            item["_candidateFile"] = str(path.relative_to(ROOT))
            rows.append(item)
    return rows


def source_key(question):
    source = question.get("source") or {}
    values = (question.get("year") or source.get("year"), source.get("session"), str(source.get("form") or "A").upper(), source.get("subjectCode"), source.get("questionNo"))
    if any(value in (None, "") for value in values):
        return None
    return (int(values[0]), int(values[1]), values[2], int(values[3]), int(values[4]))


def source_key_from_id(question_id):
    match = re.fullmatch(r"(20\d{2})-(\d)A-(\d{2})-(\d{2})", str(question_id or ""))
    if not match:
        return None
    year, session, subject_code, question_no = match.groups()
    return (int(year), int(session), "A", int(subject_code), int(question_no))


def answer_for(question, by_id, by_source):
    from_id = by_id.get(question.get("id"))
    key = source_key(question)
    from_source = by_source.get(key) if key else None
    if from_id and from_source and from_id != from_source:
        return None, "official_id_source_mismatch"
    return from_id or from_source, None


def has_manual_approval(question):
    if question.get("manualApproved") is not True:
        return False
    if not question.get("reviewer") or not question.get("reviewedAt"):
        return False
    if len(question.get("sourceEvidence") or []) < 1:
        return False
    if question.get("choiceExplanationsVerified") is not True:
        return False
    return True


def pdf_text(path):
    source = ROOT / path
    if not source.exists():
        return None
    TEXT_CACHE.mkdir(parents=True, exist_ok=True)
    cache = TEXT_CACHE / (re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", str(path)) + ".txt")
    if cache.exists() and cache.stat().st_mtime >= source.stat().st_mtime:
        return cache.read_text(encoding="utf-8", errors="ignore")
    result = subprocess.run(["pdftotext", "-layout", str(source), "-"], text=True, capture_output=True)
    if result.returncode != 0:
        return None
    cache.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def source_match(question):
    source = question.get("source") or {}
    file_name = source.get("file")
    if not file_name:
        return "missing_source_file"
    text = pdf_text(file_name)
    if text is None:
        return "source_text_unavailable"
    source_text = norm(text)
    stem = norm(question.get("question"))
    choices = [norm(choice) for choice in question.get("choices") or []]
    if not stem or len(stem) < 8:
        return "question_text_too_short"
    stem_ok = stem[: min(len(stem), 45)] in source_text or stem in source_text
    choice_hits = sum(1 for choice in choices if choice and (choice[: min(len(choice), 25)] in source_text or choice in source_text))
    if not stem_ok and choice_hits < max(2, min(4, len(choices))):
        return "source_text_not_matched"
    if not stem_ok:
        return "source_stem_needs_manual_review"
    if choice_hits < len(choices):
        return "choice_text_needs_manual_review"
    return "matched"


def has_placeholder(question):
    values = [question.get("explanation", ""), question.get("correctRationale", ""), question.get("reviewPoint", "")]
    for item in question.get("choiceExplanations") or []:
        if isinstance(item, dict):
            values.extend([item.get("reason", ""), item.get("trap", ""), item.get("fix", "")])
        else:
            values.append(str(item))
    text = "\n".join(str(value or "") for value in values)
    return any(term in text for term in PLACEHOLDER_TERMS)


def classify_candidate(question, by_id, by_source):
    errors = []
    manual = []
    warnings = []
    year = int(question.get("year") or 0)
    if year not in ALLOWED_YEARS:
        errors.append("year_out_of_scope")
    if not question.get("id"):
        errors.append("missing_id")
    id_source_key = source_key_from_id(question.get("id"))
    actual_source_key = source_key(question)
    if id_source_key and actual_source_key and id_source_key != actual_source_key:
        errors.append("id_source_mismatch")
    choices = question.get("choices") or []
    if len(choices) != 4:
        errors.append("choice_count_not_4")
    normalized_choices = [norm(choice) for choice in choices]
    if any(not choice for choice in normalized_choices):
        errors.append("empty_choice")
    if len(set(normalized_choices)) != len(normalized_choices):
        errors.append("duplicate_choice")
    if any(term in str(question.get("question") or "") for term in FOOTER_CONTAMINATION_TERMS):
        errors.append("page_footer_or_copyright_contamination")
    if any(any(term in str(choice) for term in FOOTER_CONTAMINATION_TERMS) for choice in choices):
        errors.append("page_footer_or_copyright_contamination")
    try:
        answer_index = int(question.get("answerIndex", -1))
    except Exception:
        answer_index = -1
    if answer_index < 0 or answer_index >= len(choices):
        errors.append("answer_index_out_of_range")
    official, answer_error = answer_for(question, by_id, by_source)
    if answer_error:
        errors.append(answer_error)
    if official is None:
        errors.append("official_answer_missing")
    elif answer_index not in official:
        errors.append("answer_mismatch")
    elif len(official) != 1:
        manual.append("multi_answer_needs_manual_review")
    source = question.get("source") or {}
    for key in ("file", "answerFile", "questionNo", "session", "form", "subjectCode"):
        if source.get(key) in (None, ""):
            errors.append(f"source_{key}_missing")
    if source.get("file") and not (ROOT / source["file"]).exists():
        errors.append("source_pdf_missing")
    if source.get("answerFile") and not (ROOT / source["answerFile"]).exists():
        errors.append("answer_file_missing")
    source_status = source_match(question)
    if source_status != "matched":
        manual.append(source_status)
    joined = " ".join([str(question.get("question") or ""), *(str(choice) for choice in choices)])
    if any(term in joined for term in FIGURE_TERMS) and not question.get("images"):
        manual.append("figure_or_table_needs_manual_check")
    if has_placeholder(question):
        manual.append("placeholder_explanation")
    if len(question.get("externalReview", {}).get("sources") or []) < 2:
        manual.append("external_sources_missing")
    if len(question.get("choiceExplanations") or []) != len(choices):
        manual.append("choice_explanations_missing")
    if not has_manual_approval(question):
        manual.append("manual_approval_missing")
    if errors:
        status = "auto_reject"
    elif manual:
        status = "manual_review"
    else:
        status = "verified_candidate"
    return status, errors, manual, warnings


def main():
    parser = argparse.ArgumentParser(description="Audit all health-exercise candidate questions before verified-bank promotion.")
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=OUT_MD)
    args = parser.parse_args()
    by_id, by_source = answer_maps()
    rows = candidate_rows()
    queue = read_json(QUEUE)
    queue_items = queue.get("items", [])
    candidate_by_id = {row.get("id"): row for row in rows}
    results = []
    for item in queue_items:
        question = candidate_by_id.get(item.get("id"))
        if not question:
            results.append({"id": item.get("id"), "year": item.get("year"), "subject": item.get("subject"), "status": "missing_from_auto_bank", "errors": ["candidate_missing"], "manualChecks": ["official_source_crop_or_ocr_required"]})
            continue
        status, errors, manual, warnings = classify_candidate(question, by_id, by_source)
        results.append({"id": question.get("id"), "year": question.get("year"), "subject": question.get("subject"), "topic": question.get("topic"), "priority": item.get("priority"), "status": status, "errors": errors, "manualChecks": manual, "warnings": warnings, "question": compact_snippet(question.get("question")), "candidateFile": question.get("_candidateFile")})
    status_counts = Counter(row["status"] for row in results)
    error_counts = Counter(error for row in results for error in row.get("errors", []))
    manual_counts = Counter(check for row in results for check in row.get("manualChecks", []))
    by_subject = defaultdict(Counter)
    for row in results:
        by_subject[row.get("subject") or "unknown"][row["status"]] += 1
    payload = {"scope": "2018-2025 A형 1280문항", "standard": {"autoReject": "공식 정답/필수 필드/범위/파일 존재/선택지 오염 등 기계 검증 실패", "manualReview": "정답 번호는 기계 검증 가능하나 원문·보기·그림/표·해설·수동승인 검증 필요", "verifiedCandidate": "기계 검증, 해설 필수 필드, 수동 승인 필드까지 모두 통과"}, "requiredManualApprovalFields": list(REQUIRED_MANUAL_APPROVAL_FIELDS), "summary": {"total": len(results), "statusCounts": dict(status_counts), "topErrors": dict(error_counts.most_common(30)), "topManualChecks": dict(manual_counts.most_common(30)), "bySubject": {subject: dict(counter) for subject, counter in sorted(by_subject.items())}}, "items": results}
    out_json = args.out_json if args.out_json.is_absolute() else ROOT / args.out_json
    out_md = args.out_md if args.out_md.is_absolute() else ROOT / args.out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 건강운동관리사 전체 후보 문제은행 자동 감사", "", "## 판정 기준", "", "- auto_reject: 공식 정답/필수 필드/범위/파일 존재/선택지 오염 등 기계 검증 실패", "- manual_review: 정답 번호는 기계 검증 가능하나 원문·보기·그림/표·해설·수동승인 검증 필요", "- verified_candidate: 기계 검증, 해설 필수 필드, 수동 승인 필드까지 모두 통과", "", "## 요약", "", "| status | count |", "|---|---:|"]
    for status, count in status_counts.most_common():
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## 과목별", "", "| 과목 | auto_reject | manual_review | verified_candidate | missing_from_auto_bank |", "|---|---:|---:|---:|---:|"])
    for subject, counter in sorted(by_subject.items()):
        lines.append(f"| {subject} | {counter.get('auto_reject', 0)} | {counter.get('manual_review', 0)} | {counter.get('verified_candidate', 0)} | {counter.get('missing_from_auto_bank', 0)} |")
    lines.extend(["", "## 주요 자동 탈락 사유", "", "| reason | count |", "|---|---:|"])
    for reason, count in error_counts.most_common(20):
        lines.append(f"| {reason} | {count} |")
    lines.extend(["", "## 주요 수동검수 사유", "", "| reason | count |", "|---|---:|"])
    for reason, count in manual_counts.most_common(20):
        lines.append(f"| {reason} | {count} |")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(out_json.relative_to(ROOT))
    print(out_md.relative_to(ROOT))


if __name__ == "__main__":
    main()
