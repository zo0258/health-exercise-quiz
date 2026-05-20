# 건강운동관리사 데일리 퀴즈

건강운동관리사 필기시험 준비용 모바일 퀴즈 생성 프로젝트입니다.

## 바로 풀기

GitHub Pages 배포 후 `index.html`에서 일자별 퀴즈를 선택합니다.

## 매일 생성

```bash
python3 scripts/generate_daily_quiz.py --date YYYY-MM-DD --html
python3 scripts/build_static_site.py --site-dir .
```

## 무비용 운영 구조

이 프로젝트는 별도 유료 서버 없이 운영합니다.

- 공개 화면: GitHub Pages
- 자동화 백엔드: 로컬 Mac / OpenClaw
- 데이터 원본: repo 내부 JSON과 로컬 결과 기록
- 배포: OpenClaw가 정적 페이지를 재생성한 뒤 GitHub Pages로 push

퀴즈 풀이 결과를 반영할 때는 결과 복사 블록을 아래 명령에 전달합니다.

```bash
python3 scripts/publish_result_update.py result.txt
```

이 명령은 풀이 기록을 로컬에 누적하고, 오답노트와 메인 대시보드 상태를 다시 만든 뒤 GitHub Pages에 반영합니다.

## 주요 경로

- `materials/raw/kspo/`: 공식 기출 PDF 원본
- `data/question-bank/`: 추출된 문제은행
- `data/quizzes/`: 일자별 퀴즈 JSON
- `quizzes/`: GitHub Pages용 HTML
- `results/attempts.jsonl`: 로컬 풀이 기록. git에는 올리지 않습니다.
- `data/review/wrong-note.json`: 공개 오답노트 데이터
- `scripts/`: 다운로드, 추출, 생성, 검증 스크립트
