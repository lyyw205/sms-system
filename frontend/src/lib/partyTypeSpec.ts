/**
 * party_type 도메인 — 프론트 미러 (파티 참여 멤버십 집합).
 *
 * 백엔드 app/services/party_type.py 의 PARTY_JOINED_TYPES 와 값이 일치한다(설계 의도 공유).
 * RoomAssignment / PartyCheckin / SummaryCards 세 페이지의 파티 인원 집계 기준을 한 곳으로 모은다.
 * cross-check: backend/tests/unit/test_party_type_spec_frontend_sync.py 가 백엔드와의 동기를 강제
 * (두 표가 어긋나면 그 테스트가 실패).
 *
 * ⚠️ 담지 않는 것(프론트 고유 또는 별도 의미 → 기존 위치 유지):
 *   - 1차/2차만/둘다 버킷 분해: RoomAssignment 의 '1'/'2'/'2차만' 개별 동등비교는 멤버십이 아니라
 *     전환율·성비용 통계 분해 로직이라 그대로 둔다(이 Set 으로 접으면 분해 의미가 사라짐).
 *   - 일자별 override 해석: 백엔드가 ReservationDailyInfo 를 res.party_type 로 해석해 내려주므로
 *     프론트는 표시만 한다(effective 계산 헬퍼 불필요).
 *   - party3 2차전용 집합({'2','2차만'}): 백엔드 party3_mms 전용, 프론트 소비처 없음.
 */

/** 파티 참여(아무 차수) 표준값. 'X'/'x'(미신청)·'파티' 등 비표준 값은 인원 집계에서 제외. */
export const PARTY_JOINED_TYPES = new Set(['1', '2', '2차만']);

/** effective party_type 이 파티 참여 집합에 드는지 (null/비표준 → false). */
export function isPartyJoined(partyType: string | null | undefined): boolean {
  return partyType != null && PARTY_JOINED_TYPES.has(partyType);
}
