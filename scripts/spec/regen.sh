#!/usr/bin/env bash
# 전수조사 문서 재생성 — 코드가 바뀌면 이걸 돌린다.
#
#   backend/app/**.py  ─┐
#                       ├─▶ functions/*.yaml  ─┐
#   (기계 추출)          │                      ├─▶ 함수명세/*.md + _진행률.md
#                       │   semantics/*.yaml ──┘   (사람이 쓴 의미 + 골격)
#                       │   ← 손으로 편집하는 유일한 곳
#                       │
#                       ├─▶ variables/01~04.yaml ─┐
#                       │   variables/10-domain-axes.yaml (손편집) ─┴─▶ 변수명세/*.md
#                       │
#                       └─▶ 코어도출/요약.md (확산도 계산)
#
# functions/ · variables/01~04 · 함수명세/ · 변수명세/ · 코어도출/ 은 .gitignore 대상이다.
# 직접 고치지 말 것 — 다음 실행에 덮어써진다.
#
# 사용: bash scripts/spec/regen.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

python3 scripts/spec/extract_functions.py
python3 scripts/spec/extract_variables.py
python3 scripts/spec/merge_functions.py
python3 scripts/spec/render_variables.py
python3 scripts/spec/derive_core.py

echo
echo "완료. 진행률: docs/plans/refactor/함수명세/_진행률.md"
echo "커버리지가 100% 미만이면 새 모듈에 semantics/*.yaml 항목을 추가해야 한다."
