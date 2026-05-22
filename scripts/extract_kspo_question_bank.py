#!/usr/bin/env python3
import argparse
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "question-bank" / "kspo-2023-a.jsonl"
HWP5TXT = Path.home() / "Library" / "Python" / "3.13" / "bin" / "hwp5txt"
HWP5HTML = Path.home() / "Library" / "Python" / "3.13" / "bin" / "hwp5html"

SESSION_SUBJECTS = {
    1: [
        ("운동생리학", 70),
        ("건강·체력평가", 71),
        ("운동처방론", 72),
        ("운동부하검사", 73),
    ],
    2: [
        ("운동상해", 74),
        ("기능해부학", 75),
        ("병태생리학", 76),
        ("스포츠심리학", 77),
    ],
}

CIRCLED_TO_INDEX = {"①": 0, "②": 1, "③": 2, "④": 3, "⑤": 4}
HANGUL_TO_INDEX = {"가": 0, "나": 1, "다": 2, "라": 3, "마": 4}
INDEX_TO_CIRCLED = ["①", "②", "③", "④", "⑤"]


def run_pdftotext(path):
    result = subprocess.run(
        ["pdftotext", "-raw", str(path), "-"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def run_hwp5txt(path):
    if not HWP5TXT.exists():
        raise SystemExit(f"hwp5txt를 찾지 못했습니다: {HWP5TXT}")
    result = subprocess.run(
        [str(HWP5TXT), str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def run_hwp5html_text(path):
    if not HWP5HTML.exists():
        raise SystemExit(f"hwp5html을 찾지 못했습니다: {HWP5HTML}")
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "html"
        subprocess.run(
            [str(HWP5HTML), "--output", str(output_dir), str(path)],
            check=True,
            text=True,
            capture_output=True,
        )
        index = output_dir / "index.xhtml"
        raw = index.read_text(encoding="utf-8", errors="ignore")
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = raw.replace("\r", "\n")
    return compact_spaces(raw)


def extract_text(path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return run_pdftotext(path)
    if suffix == ".hwp":
        return run_hwp5txt(path)
    raise ValueError(f"지원하지 않는 원본 형식입니다: {path}")


def normalize_subject_text(text):
    return re.sub(r"[\s･·․\.\-_/\(\)（）]", "", text)


def compact_spaces(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def answer_tokens(text):
    tokens = []
    for token in re.findall(r"[①②③④⑤]|(?<![가-힣])[가나다라마](?![가-힣])", text):
        if token in CIRCLED_TO_INDEX:
            tokens.append(CIRCLED_TO_INDEX[token])
        else:
            tokens.append(HANGUL_TO_INDEX[token])
    return tokens


def subject_answer_rows_from_text(text):
    rows = {}
    subjects = SESSION_SUBJECTS[1] + SESSION_SUBJECTS[2]
    for idx, (subject, _code) in enumerate(subjects):
        subject_norm = normalize_subject_text(subject)
        next_subject_norm = normalize_subject_text(subjects[idx + 1][0]) if idx + 1 < len(subjects) else None
        pattern = re.compile(re.escape(subject_norm))
        normalized = normalize_subject_text(text)
        match = pattern.search(normalized)
        if not match:
            continue

        # Work on original text from an approximate position. The normalized
        # offset is not byte-equivalent, so locate the visible subject again.
        original_match = re.search(re.escape(subject).replace("·", r"[·\s]*"), text)
        if not original_match:
            original_match = re.search(subject.replace("·", r".{0,5}"), text)
        if not original_match:
            continue
        start = original_match.end()
        end = len(text)
        if next_subject_norm:
            next_match = re.search(subjects[idx + 1][0].replace("·", r".{0,5}"), text[start:])
            if next_match:
                end = start + next_match.start()
        tokens = answer_tokens(text[start:end])
        if len(tokens) >= 20:
            rows[subject] = tokens[:20]
    return rows


def session_answer_rows_from_text(text):
    session_matches = list(re.finditer(r"(\d)\s*교시\s*정답", text))
    if not session_matches:
        return None

    parsed = {}
    for idx, match in enumerate(session_matches):
        session = int(match.group(1))
        if session not in SESSION_SUBJECTS:
            continue
        start = match.end()
        end = session_matches[idx + 1].start() if idx + 1 < len(session_matches) else len(text)
        section = text[start:end]
        rows = []
        for line in section.splitlines():
            tokens = answer_tokens(line)
            if len(tokens) == 20:
                rows.append(tokens)
        if len(rows) >= 4:
            parsed[(session, "A")] = rows[:4]
        if len(rows) >= 8:
            parsed[(session, "B")] = rows[4:8]

    if (1, "A") in parsed or (2, "A") in parsed:
        return parsed
    return None


def parse_answer_rows(answer_path):
    if answer_path.suffix.lower() == ".hwp":
        text = run_hwp5html_text(answer_path)
    else:
        text = run_pdftotext(answer_path)

    session_rows = session_answer_rows_from_text(text)
    if session_rows:
        result = {}
        for session in (1, 2):
            for form in ("A", "B"):
                key = (session, form)
                if key in session_rows:
                    result[key] = session_rows[key]
        return result

    form_sections = {}
    form_matches = list(re.finditer(r"건강\s*[\(（]\s*([ABＡＢ]|A|B|에이|비)\s*[형型]", text))
    if form_matches:
        for idx, match in enumerate(form_matches):
            marker = match.group(1)
            form = "A" if marker in {"A", "Ａ", "에이"} else "B"
            start = match.end()
            end = form_matches[idx + 1].start() if idx + 1 < len(form_matches) else len(text)
            form_sections[form] = text[start:end]
    else:
        form_sections["A"] = text

    subject_rows = {"A": {}, "B": {}}
    for form, section in form_sections.items():
        rows = subject_answer_rows_from_text(section)
        if len(rows) >= 8:
            subject_rows[form] = rows

    if len(subject_rows["A"]) < 8:
        rows = []
        for line in text.splitlines():
            tokens = answer_tokens(line)
            if len(tokens) == 20:
                rows.append(tokens)
        if len(rows) >= 16:
            subject_rows["A"] = {subject: rows[idx] for idx, (subject, _code) in enumerate(SESSION_SUBJECTS[1] + SESSION_SUBJECTS[2])}
            subject_rows["B"] = {subject: rows[idx + 8] for idx, (subject, _code) in enumerate(SESSION_SUBJECTS[1] + SESSION_SUBJECTS[2])}
        elif len(rows) >= 8:
            subject_rows["A"] = {subject: rows[idx] for idx, (subject, _code) in enumerate(SESSION_SUBJECTS[1] + SESSION_SUBJECTS[2])}

    if len(subject_rows["A"]) < 8:
        tokens = answer_tokens(text)
        # Some final-answer PDFs render as subject names followed by answers on
        # separate lines. When a form marker exists, the first 160 answers are A.
        if len(tokens) >= 160:
            subject_rows["A"] = {
                subject: tokens[idx * 20 : (idx + 1) * 20]
                for idx, (subject, _code) in enumerate(SESSION_SUBJECTS[1] + SESSION_SUBJECTS[2])
            }
            if len(tokens) >= 320:
                subject_rows["B"] = {
                    subject: tokens[160 + idx * 20 : 160 + (idx + 1) * 20]
                    for idx, (subject, _code) in enumerate(SESSION_SUBJECTS[1] + SESSION_SUBJECTS[2])
                }

    if len(subject_rows["A"]) < 8:
        raise ValueError(f"정답 행을 충분히 찾지 못했습니다: {answer_path} ({len(subject_rows['A'])}과목)")

    result = {}
    for session in (1, 2):
        for form in ("A", "B"):
            form_rows = subject_rows.get(form) or {}
            if not form_rows and form == "B":
                continue
            result[(session, form)] = []
            for subject, _code in SESSION_SUBJECTS[session]:
                if subject not in form_rows:
                    raise ValueError(f"정답 행을 찾지 못했습니다: {answer_path} {form}형 {subject}")
                result[(session, form)].append(form_rows[subject])
    return result


def find_subject_ranges(text, session):
    ranges = []
    line_start = 0
    lines = []
    for line in text.splitlines(keepends=True):
        lines.append((line_start, line))
        line_start += len(line)

    for subject, code in SESSION_SUBJECTS[session]:
        normalized_subject = normalize_subject_text(subject)
        position = None
        for start, line in lines:
            normalized_line = normalize_subject_text(line)
            has_code_marker = bool(re.search(rf"[\(（]\s*{code}\s*[\)）]", line))
            if normalized_subject in normalized_line and (has_code_marker or "◆" in line):
                position = start
                break
        if position is None:
            raise ValueError(f"과목 위치를 찾지 못했습니다: {subject}")
        ranges.append((position, subject, code))

    ranges.sort()
    sections = []
    for idx, (start, subject, code) in enumerate(ranges):
        end = ranges[idx + 1][0] if idx + 1 < len(ranges) else len(text)
        sections.append((subject, code, text[start:end]))
    return sections


def split_question_blocks(section_text):
    matches = list(re.finditer(r"(?m)^(20|1\d|[1-9])\.(?=\s|<|[A-Za-z가-힣'‘])\s*", section_text))
    blocks = []
    for idx, match in enumerate(matches):
        question_no = int(match.group(1))
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section_text)
        if 1 <= question_no <= 20:
            blocks.append((question_no, section_text[start:end]))
    return blocks


def parse_question_block(block):
    block = compact_spaces(block)
    marker_matches = list(re.finditer(r"[①②③④⑤]", block))
    marker_type = "circled"
    if len(marker_matches) < 4:
        marker_matches = list(re.finditer(r"(?m)(?<![가-힣])([가나다라마])\.\s*", block))
        marker_type = "hangul"
    if len(marker_matches) < 4:
        return None

    first_choice = marker_matches[0].start()
    stem = re.sub(r"^\d{1,2}\.\s*", "", block[:first_choice]).strip()
    choices = []
    selected_choice_matches = marker_matches[:5]
    for idx, match in enumerate(selected_choice_matches):
        start = match.end()
        end = selected_choice_matches[idx + 1].start() if idx + 1 < len(selected_choice_matches) else len(block)
        choice_text = block[start:end].strip()
        choice_text = re.sub(r"\s+", " ", choice_text)
        choices.append(choice_text)

    if marker_type == "hangul" and len(choices) > 4 and not choices[4]:
        choices = choices[:4]
    if not stem or len(choices) < 4 or any(not choice for choice in choices[:4]):
        return None
    return stem, choices[:5]


def infer_type(stem):
    if "계산" in stem or "추정" in stem or "구하" in stem:
        return "계산"
    if "옳은 것으로만" in stem or "모두 고른" in stem:
        return "보기조합"
    if "괄호" in stem:
        return "빈칸"
    if "옳지 않은" in stem or "바르지" in stem or "아닌" in stem:
        return "부정형"
    return "개념구분"


def infer_difficulty(stem, qtype):
    score = 3
    if qtype in {"보기조합", "계산"}:
        score += 1
    if len(stem) > 160:
        score += 1
    if "<표>" in stem or "<그림>" in stem:
        score += 1
    return min(score, 5)


def infer_topic(subject, stem):
    text = re.sub(r"<[^>]+>", "", stem)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"에서|으로|에 대한|에 관한|의 |가 |은 |는 |을 |를 ", " ", text)
    text = re.sub(r"[^0-9A-Za-z가-힣·･\s]", " ", text)
    words = [word for word in text.split() if len(word) > 1]
    if not words:
        return subject
    return " ".join(words[:2])[:24]


def build_question(year, session, form, subject, code, question_no, stem, choices, answer_index, question_path, answer_path):
    qtype = infer_type(stem)
    topic = infer_topic(subject, stem)
    answer_label = INDEX_TO_CIRCLED[answer_index] if answer_index < len(INDEX_TO_CIRCLED) else str(answer_index + 1)
    return {
        "id": f"{year}-{session}{form}-{code}-{question_no:02d}",
        "year": year,
        "subject": subject,
        "topic": topic,
        "type": qtype,
        "difficulty": infer_difficulty(stem, qtype),
        "trap": f"{topic} 관련 조건과 보기 표현을 섞어 판단하는 문항",
        "question": stem,
        "choices": choices,
        "answerIndex": answer_index,
        "explanation": f"최종정답 기준 정답은 {answer_label}입니다. 해설 보강 전 기본 문항이므로, 틀린 경우 문제 조건과 각 보기의 핵심 용어를 원문 기준으로 다시 확인하세요.",
        "source": {
            "file": str(question_path.relative_to(ROOT)),
            "answerFile": str(answer_path.relative_to(ROOT)),
            "questionNo": question_no,
            "session": session,
            "form": form,
            "subjectCode": code,
        },
        "wrongRateBasis": "고오답 추정",
        "verified": True,
        "bankSource": "공식 KSPO 원문 자동 추출 후 정답 매칭",
    }


def extract_session(year, session, form, question_path, answer_path, answers):
    text = extract_text(question_path)
    extracted = []
    seen_ids = set()
    answer_rows = answers[(session, form)]

    for subject_index, (subject, code, section) in enumerate(find_subject_ranges(text, session)):
        subject_answers = answer_rows[subject_index]
        for question_no, block in split_question_blocks(section):
            parsed = parse_question_block(block)
            if not parsed:
                continue
            stem, choices = parsed
            answer_index = subject_answers[question_no - 1]
            if answer_index >= len(choices):
                continue
            question = build_question(year, session, form, subject, code, question_no, stem, choices, answer_index, question_path, answer_path)
            if question["id"] in seen_ids:
                continue
            seen_ids.add(question["id"])
            extracted.append(question)
    return extracted


def find_question_file(base, year, session, form):
    candidates = []
    session_texts = [f"{session}교시", f"{session} 교시"]
    form_texts = [f"{form}형", f"{form} 형"]
    for directory_name in ("questions", "questions_and_draft_answer"):
        directory = base / directory_name
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() not in {".pdf", ".hwp"}:
                continue
            name = path.name
            if not any(value in name for value in session_texts):
                continue
            if any(value in name for value in form_texts):
                return path
            candidates.append(path)
    if form == "A" and candidates:
        return candidates[0]
    raise FileNotFoundError(f"{year}년 {session}교시 {form}형 문제 파일을 찾지 못했습니다.")


def find_answer_file(base):
    directories = ["final_answer", "final_answer_notice", "draft_answer", "questions_and_draft_answer"]
    keywords = ["최종", "정답", "답안", "정답가안"]
    candidates = []
    for directory_name in directories:
        directory = base / directory_name
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() not in {".pdf", ".hwp"}:
                continue
            if any(keyword in path.name for keyword in keywords):
                candidates.append(path)
    if not candidates:
        raise FileNotFoundError(f"정답 파일을 찾지 못했습니다: {base}")
    candidates.sort(key=lambda path: (0 if "final" in str(path.parent) or "최종" in path.name else 1, path.name))
    return candidates[0]


def extract_year(year, form, output):
    base = ROOT / "materials" / "raw" / "kspo" / str(year)
    answer_path = find_answer_file(base)
    try:
        answers = parse_answer_rows(answer_path)
    except ValueError:
        fallback = None
        for candidate in sorted((base / "questions_and_draft_answer").glob("*정답*")) if (base / "questions_and_draft_answer").exists() else []:
            if candidate != answer_path and candidate.suffix.lower() in {".pdf", ".hwp"}:
                fallback = candidate
                break
        if not fallback:
            raise
        answer_path = fallback
        answers = parse_answer_rows(answer_path)

    questions = []
    for session in (1, 2):
        question_path = find_question_file(base, year, session, form)
        questions.extend(extract_session(year, session, form, question_path, answer_path, answers))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for question in questions:
            file.write(json.dumps(question, ensure_ascii=False) + "\n")
    return questions, answer_path


def main():
    parser = argparse.ArgumentParser(description="Extract KSPO health exercise question bank from official source files.")
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--form", default="A", choices=["A", "B"])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--all-years", action="store_true", help="Extract A-form banks for 2015-2025.")
    args = parser.parse_args()

    targets = range(2015, 2026) if args.all_years else [args.year]
    for year in targets:
        output = args.output
        if args.all_years:
            output = ROOT / "data" / "question-bank" / f"kspo-{year}-a.jsonl"
        questions, answer_path = extract_year(year, args.form, output)
        subject_counts = {}
        for question in questions:
            subject_counts[question["subject"]] = subject_counts.get(question["subject"], 0) + 1

        print(output)
        print(f"answer={answer_path.relative_to(ROOT)}")
        print(f"questions={len(questions)}")
        for subject, _code in SESSION_SUBJECTS[1] + SESSION_SUBJECTS[2]:
            print(f"{subject}={subject_counts.get(subject, 0)}")


if __name__ == "__main__":
    main()
