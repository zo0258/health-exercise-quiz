# 건강운동관리사 전체 후보 문제은행 자동 감사

## 판정 기준

- auto_reject: 공식 정답/필수 필드/범위/파일 존재/선택지 오염 등 기계 검증 실패
- manual_review: 정답 번호는 기계 검증 가능하나 원문·보기·그림/표·해설·수동승인 검증 필요
- verified_candidate: 기계 검증, 해설 필수 필드, 수동 승인 필드까지 모두 통과

## 요약

| status | count |
|---|---:|
| manual_review | 1044 |
| missing_from_auto_bank | 165 |
| auto_reject | 71 |

## 과목별

| 과목 | auto_reject | manual_review | verified_candidate | missing_from_auto_bank |
|---|---:|---:|---:|---:|
| 건강·체력평가 | 2 | 138 | 0 | 20 |
| 기능해부학 | 32 | 106 | 0 | 22 |
| 병태생리학 | 3 | 137 | 0 | 20 |
| 스포츠심리학 | 1 | 139 | 0 | 20 |
| 운동부하검사 | 2 | 137 | 0 | 21 |
| 운동상해 | 31 | 107 | 0 | 22 |
| 운동생리학 | 0 | 140 | 0 | 20 |
| 운동처방론 | 0 | 140 | 0 | 20 |

## 주요 자동 탈락 사유

| reason | count |
|---|---:|
| candidate_missing | 165 |
| page_footer_or_copyright_contamination | 69 |
| choice_count_not_4 | 2 |

## 주요 수동검수 사유

| reason | count |
|---|---:|
| placeholder_explanation | 1115 |
| external_sources_missing | 1115 |
| choice_explanations_missing | 1115 |
| manual_approval_missing | 1115 |
| source_stem_needs_manual_review | 528 |
| official_source_crop_or_ocr_required | 165 |
| source_text_not_matched | 117 |
| figure_or_table_needs_manual_check | 109 |
| choice_text_needs_manual_review | 79 |
| multi_answer_needs_manual_review | 15 |
