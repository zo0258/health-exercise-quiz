# 무비용 운영 구조

## 결론

건강운동관리사 데일리 퀴즈는 유료 서버를 두지 않는다. GitHub Pages는 공개 화면을 맡고, OpenClaw가 로컬 자동화 백엔드 역할을 맡는다.

## 구성

| 영역 | 역할 | 비용 |
|---|---|---|
| GitHub Pages | 메인 대시보드, 일자별 퀴즈, 오답노트 공개 | 무료 |
| OpenClaw / Mac | 문제 생성, 결과 반영, 정적 페이지 재생성, git push | 추가 비용 없음 |
| repo JSON | 퀴즈 데이터, 오답노트 공개 데이터 | 무료 |
| 로컬 results | 개인 풀이 기록 원본 | 무료 |

## 운영 흐름

1. OpenClaw가 매일 퀴즈 JSON과 HTML을 생성한다.
2. `scripts/build_static_site.py`가 메인 대시보드와 GitHub Pages 파일을 재생성한다.
3. 변경된 공개 파일만 commit/push 한다.
4. 영희님 또는 배우자가 퀴즈를 풀고 결과 블록을 Telegram으로 보낸다.
5. OpenClaw가 결과 블록을 `scripts/publish_result_update.py`로 반영한다.
6. 오답노트, 풀이완료 배지, 오답반영 배지를 다시 생성해 GitHub Pages에 배포한다.

## 결과 반영 명령

```bash
python3 scripts/publish_result_update.py result.txt
```

표준 입력으로도 받을 수 있다.

```bash
pbpaste | python3 scripts/publish_result_update.py
```

## 공개 대상

- `index.html`
- `wrong-note.html`
- `data/review/wrong-note.json`
- `quizzes/quiz-YYYY-MM-DD.html`
- `data/quizzes/YYYY-MM-DD-daily.json`

## 비공개 유지 대상

- `results/attempts.jsonl`
- `results/mastered.json`
- `notes/wrong-note.md`

이 파일들은 개인 풀이 기록 원본이므로 git에 올리지 않는다. 공개 페이지에는 필요한 상태와 오답노트 데이터만 반영한다.

## 나중에 확장할 때

자동 저장이 꼭 필요해지면 무료 티어만 검토한다.

- Cloudflare Workers
- Firebase 무료 티어
- Google Forms / Sheets

현재 단계에서는 추가 서버보다 로컬 자동화 + GitHub Pages 조합이 관리 포인트가 가장 적다.
