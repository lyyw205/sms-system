/**
 * stayLogic.ts — 투숙 기간(당일 vs 숙박) 프론트 단일 로직.
 *
 * 백엔드 app/services/stay_logic.py 의 프론트 대응물. 반열림 규약 `[check_in, check_out)`:
 * 체크아웃일은 박이 아님, NULL/빈값/co==ci = 당일 1박.
 * 흩어진 FE 사본(useGuestMove `diff>1`, useStayGroup `co!==ci`, GuestRow `<2`)을 한 곳으로.
 *
 * ⚠️ drift-guard: 프론트 테스트 러너(vitest) 미설치라 자동 동기검증 없음 —
 *    백엔드 stay_logic.py / docs/plans/stay-semantics-design.md §1 을 단일 사양으로 보고 cross-ref 로 관리.
 *    (향후 vitest 도입 시 공유 fixture 기반 drift-guard 추가 — 설계 §8.)
 *
 * ⚠️ isMultiNight 의 stay_group_id 분기는 "날짜 함수"가 아니라 네이버 그룹축 —
 *    날짜만으로 정의하면 split 그룹 멤버의 교차일 드래그가 풀리므로 OR-절 그대로 보존.
 */
import dayjs from 'dayjs';

/** 박수 = max(1, (check_out - check_in) 일수). NULL/빈값 → 1. 백엔드 stay_nights 미러.
 *  (GuestRow/MobileGuestRow 의 배지 분모는 표시 결합도가 높아 후속 migration 대상.) */
export function stayNights(checkIn?: string | null, checkOut?: string | null): number {
  if (!checkIn || !checkOut) return 1;
  return Math.max(1, dayjs(checkOut).diff(dayjs(checkIn), 'day'));
}

/** 연박(2박+) 여부. stay_group_id(네이버 그룹축)면 무조건 true, 아니면 (co-ci)일수 > 1. */
export function isMultiNight(res: {
  stay_group_id?: string | null;
  check_in_date?: string | null;
  check_out_date?: string | null;
}): boolean {
  if (res.stay_group_id) return true;
  if (res.check_in_date && res.check_out_date) {
    return dayjs(res.check_out_date).diff(dayjs(res.check_in_date), 'day') > 1;
  }
  return false;
}

/** chain next 슬롯 = 연박이면 check_out, 당일(ci===co 또는 빈값)이면 ci+1. 백엔드 "1박=ci" 규약과 정합. */
export function nextCheckinDate(res: { check_in_date: string; check_out_date?: string | null }): string {
  return (res.check_out_date && res.check_out_date !== res.check_in_date)
    ? res.check_out_date
    : dayjs(res.check_in_date).add(1, 'day').format('YYYY-MM-DD');
}
