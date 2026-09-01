# docs/plans — 계획 문서 인덱스

> 2026-08-31 정리: 완료·폐기된 계획 100건을 [`_archive/`](./_archive/) 로 이동했습니다.
> 여기 남은 것만이 **살아있는 계획**입니다.

## 살아있는 계획

| 문서 | 상태 |
|---|---|
| [`refactor/`](./refactor/README.md) | 🎯 **전면 리팩토링 (코어/모듈 3층 + 관문 강제) — 현재 주 트랙** |
| [`sms-gateway-handoff.md`](./sms-gateway-handoff.md) | 진행 중 — 백엔드 완료(미커밋)/앱 미착수. 리팩토링 편입 = refactor/07 §2 |
| [`stay-semantics-design.md`](./stay-semantics-design.md) | 부분 완료 — 잔여 Phase B·D 는 **refactor P5.5 로 흡수** |
| [`manual-edit-protection-plan.md`](./manual-edit-protection-plan.md) (+step 2건) | 부분 완료 — PR1 완료, PR2(날짜 pin 이주)·PR3(pin 컬럼 제거) 미착수 |
| [`db-schema-baseline.md`](./db-schema-baseline.md) | 착수 대기 — 리팩토링 **완료 후** 별도 프로젝트 1 (Q7) |
| [`db-audit-log.md`](./db-audit-log.md) | 착수 대기 — 리팩토링 **완료 후** 별도 프로젝트 2 (Q13·Q15) |

## _archive/ 에 들어간 것

- **완료된 마이그레이션 패밀리**: mutator(15) · lifecycle(20) · chip-store(10) · sync-sms-tags(2) · split-group(4) · tenant-model-registry(2) — 백엔드 / dndkit(13) · react-query(11) · mobile-layout(6) · reload-removal — 프론트
- **완료된 단독 설계**: delete-soft-cancel(2) · activity-product · party-sales-simplify · twin-capacity · dorm-gender-mix · sms-event-gender-filter · event-schedule-exclude · sms-chip-dropdown · clean-stay-group · reservation-mutator-design 등
- **흡수·폐기**: room-assignment-cleanup-plan / room-assignment-pipeline-design (→ refactor P7 로 흡수) · unified-room-edit-modal-design (SUPERSEDED) · architecture-refactor-00/01 (폐기된 이전 접근)
- docs 루트에 있던 plan-frontend-improvements(04-28) · plan-room-upgrade-review(05-13)

코드 docstring 이 이 문서들을 참조하는 경로는 전부 `docs/plans/_archive/...` 로 일괄 수정했습니다 (2026-08-31).
완료된 계획은 역사 기록이지 할 일이 아닙니다 — **새 작업은 항상 `refactor/` 에서 출발하세요.**
