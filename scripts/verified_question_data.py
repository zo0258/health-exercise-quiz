#!/usr/bin/env python3
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIED_BANK_DIR = ROOT / "data" / "verified-question-bank"
ALLOWED_SOURCE_YEARS = set(range(2018, 2026))
ALLOWED_ANSWER_STATUS = {"official_verified", "manual_verified"}
ALLOWED_EXPLANATION_STATUS = {"reviewed", "cross_checked"}
ALLOWED_CONFIDENCE = {"high", "manual"}
MIN_EXTERNAL_REVIEW_SOURCES = 2
FOOTER_CONTAMINATION_TERMS = (
    "건강운동관리사 자격검정",
    "본 문제는 저작권법에",
    "한국스포츠정책과학원",
    "본 제작물에는",
    "대한인쇄문화협회",
    "페이지",
    "쪽",
)
REQUIRED_MANUAL_APPROVAL_FIELDS = ("manualApproved", "reviewer", "reviewedAt", "sourceEvidence", "choiceExplanationsVerified")
PLACEHOLDER_PATTERNS = (
    "해설 보강 전 기본 문항",
    "최종정답 기준 정답은",
    "정답 기준과 맞지 않는 보기입니다",
    "최종정답 기준에 맞는 보기입니다",
)


def read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_no} JSONL 파싱 실패: {error}") from error
    return rows


def normalized_stem(text):
    return "".join(str(text or "").split()).lower()


def public_error_prefix(question, path=None):
    question_id = question.get("id", "id없음")
    if path:
        return f"{path}:{question_id}"
    return question_id


def has_placeholder_explanation(question):
    values = [
        question.get("explanation", ""),
        question.get("correctRationale", ""),
        question.get("reviewPoint", ""),
    ]
    for item in question.get("choiceExplanations") or []:
        if isinstance(item, dict):
            values.extend([item.get("reason", ""), item.get("trap", ""), item.get("fix", "")])
        else:
            values.append(str(item))
    joined = "\n".join(str(value or "") for value in values)
    return any(pattern in joined for pattern in PLACEHOLDER_PATTERNS)


def official_answer_index(question):
    evidence = question.get("answerEvidence") or {}
    values = evidence.get("officialAnswerIndexes")
    if values is not None:
        return [int(value) for value in values]
    value = evidence.get("officialAnswerIndex")
    if value is not None:
        return [int(value)]
    label = str(evidence.get("officialAnswer") or "").strip()
    circled = {"①": 0, "②": 1, "③": 2, "④": 3, "⑤": 4}
    if any(mark in label for mark in circled):
        return [circled[mark] for mark in re.findall(r"[①②③④⑤]", label)]
    if re.fullmatch(r"[1-5]", label):
        return [int(label) - 1]
    raise ValueError("answerEvidence.officialAnswerIndexes 또는 officialAnswer 누락")


def external_review_sources(question):
    review = question.get("externalReview") or {}
    sources = review.get("sources") or question.get("explanationSources") or []
    return [source for source in sources if source]


def validate_choice_explanations(question):
    choices = question.get("choices") or []
    explanations = question.get("choiceExplanations") or []
    answer_index = int(question.get("answerIndex", -1))
    errors = []
    if len(explanations) != len(choices):
        errors.append(f"choiceExplanations 수 불일치: {len(explanations)} / {len(choices)}")
        return errors

    correct_count = 0
    for index, item in enumerate(explanations):
        if not isinstance(item, dict):
            errors.append(f"choiceExplanations[{index}] 객체 아님")
            continue
        verdict = item.get("verdict")
        if index == answer_index and verdict != "correct":
            errors.append(f"정답 선택지 verdict 불일치: {index + 1}")
        if index != answer_index and verdict != "incorrect":
            errors.append(f"오답 선택지 verdict 불일치: {index + 1}")
        if verdict == "correct":
            correct_count += 1
        if not str(item.get("reason") or "").strip():
            errors.append(f"선택지 해설 누락: {index + 1}")
    if correct_count != 1:
        errors.append(f"correct verdict 수 불일치: {correct_count}")
    return errors


def validate_verified_question(question, path=None):
    errors = []
    prefix = public_error_prefix(question, path)
    year = question.get("year")
    if int(year or 0) not in ALLOWED_SOURCE_YEARS:
        errors.append(f"{prefix}: 출제범위 밖 연도: {year}")

    choices = question.get("choices") or []
    answer_index = int(question.get("answerIndex", -1))
    if not question.get("id"):
        errors.append(f"{prefix}: id 누락")
    if not str(question.get("question") or "").strip():
        errors.append(f"{prefix}: 문제 본문 누락")
    if len(choices) != 4:
        errors.append(f"{prefix}: 4지선다 보기 수 불일치: {len(choices)}")
    normalized_choices = [normalized_stem(choice) for choice in choices]
    if any(not choice for choice in normalized_choices):
        errors.append(f"{prefix}: 빈 선택지 포함")
    if len(set(normalized_choices)) != len(normalized_choices):
        errors.append(f"{prefix}: 중복 선택지 포함")
    if any(term in str(question.get("question") or "") for term in FOOTER_CONTAMINATION_TERMS):
        errors.append(f"{prefix}: 페이지/저작권 문구가 문제 본문에 섞임")
    if any(any(term in str(choice) for term in FOOTER_CONTAMINATION_TERMS) for choice in choices):
        errors.append(f"{prefix}: 페이지/저작권 문구가 선택지에 섞임")
    if answer_index < 0 or answer_index >= len(choices):
        errors.append(f"{prefix}: answerIndex 범위 오류: {answer_index}")

    if question.get("sourceVerified") is not True:
        errors.append(f"{prefix}: sourceVerified가 true가 아님")
    if question.get("answerVerified") is not True:
        errors.append(f"{prefix}: answerVerified가 true가 아님")
    if question.get("explanationVerified") is not True:
        errors.append(f"{prefix}: explanationVerified가 true가 아님")
    if question.get("answerStatus") not in ALLOWED_ANSWER_STATUS:
        errors.append(f"{prefix}: answerStatus 미검증: {question.get('answerStatus')}")
    if question.get("explanationStatus") not in ALLOWED_EXPLANATION_STATUS:
        errors.append(f"{prefix}: explanationStatus 미검증: {question.get('explanationStatus')}")
    if question.get("parserConfidence") not in ALLOWED_CONFIDENCE:
        errors.append(f"{prefix}: parserConfidence 낮음/누락: {question.get('parserConfidence')}")
    if question.get("manualApproved") is not True:
        errors.append(f"{prefix}: manualApproved가 true가 아님")
    if not str(question.get("reviewer") or "").strip():
        errors.append(f"{prefix}: reviewer 누락")
    if not str(question.get("reviewedAt") or "").strip():
        errors.append(f"{prefix}: reviewedAt 누락")
    if len(question.get("sourceEvidence") or []) < 1:
        errors.append(f"{prefix}: sourceEvidence 누락")
    if question.get("choiceExplanationsVerified") is not True:
        errors.append(f"{prefix}: choiceExplanationsVerified가 true가 아님")

    try:
        if answer_index not in official_answer_index(question):
            errors.append(f"{prefix}: answerEvidence 공식 정답과 answerIndex 불일치")
    except Exception as error:
        errors.append(f"{prefix}: 공식 정답 근거 누락: {error}")

    source = question.get("source") or {}
    for key in ("file", "answerFile", "questionNo", "session", "form", "subjectCode"):
        if source.get(key) in (None, ""):
            errors.append(f"{prefix}: source.{key} 누락")
    evidence = question.get("answerEvidence") or {}
    for key in ("basis", "sourceFile", "questionFile", "questionNo"):
        if evidence.get(key) in (None, ""):
            errors.append(f"{prefix}: answerEvidence.{key} 누락")

    if has_placeholder_explanation(question):
        errors.append(f"{prefix}: placeholder 해설 잔존")
    if not str(question.get("correctRationale") or "").strip():
        errors.append(f"{prefix}: correctRationale 누락")
    if not str(question.get("reviewPoint") or "").strip():
        errors.append(f"{prefix}: reviewPoint 누락")
    source_count = len(external_review_sources(question))
    if source_count < MIN_EXTERNAL_REVIEW_SOURCES:
        errors.append(f"{prefix}: 외부 대조 출처 부족: {source_count} / {MIN_EXTERNAL_REVIEW_SOURCES}")

    for error in validate_choice_explanations(question):
        errors.append(f"{prefix}: {error}")
    return errors


def load_verified_bank(bank_dir=VERIFIED_BANK_DIR):
    bank_dir = Path(bank_dir)
    bank = []
    seen = set()
    errors = []
    for path in sorted(bank_dir.glob("*.jsonl")):
        rel_path = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        for question in read_jsonl(path):
            question_id = question.get("id")
            if question_id in seen:
                errors.append(f"{rel_path}:{question_id}: 중복 questionId")
                continue
            seen.add(question_id)
            item_errors = validate_verified_question(question, rel_path)
            if item_errors:
                errors.extend(item_errors)
                continue
            question["_bankFile"] = str(rel_path)
            question["_normalizedStem"] = normalized_stem(question["question"])
            bank.append(question)
    if errors:
        preview = "\n".join(errors[:80])
        extra = f"\n...외 {len(errors) - 80}건" if len(errors) > 80 else ""
        raise ValueError(f"검증 로우데이터 오류로 출제를 중단합니다.\n{preview}{extra}")
    return bank
