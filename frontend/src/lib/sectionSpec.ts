/**
 * Reservation.section 행동 명세서 — 프론트 미러.
 *
 * 백엔드 app/services/section_registry.py 의 프론트 대응물.
 * label / draggable 은 백엔드 명세서와 값이 일치한다(설계 의도 공유) — cross-check 로 관리.
 *
 * ⚠️ 담지 않는 것(프론트 고유 또는 오버레이와 결합 → 기존 위치 유지):
 *   - zone/버킷 식별자: 프론트는 'pool' 등 자기 네이밍 + room_id/unstable_party/sectionOverrides 오버레이
 *     와 결합되므로 useReservationsData 의 분류 로직에 그대로 둔다.
 *   - zone 색상 / 드롭 accept: zone 컴포넌트 prop.
 *
 * 값은 현재 프론트 하드코딩과 1:1 일치(동작 불변). 새 section 추가 시 이 표 한 줄만.
 */
export interface SectionSpec {
  label: string;
  draggable: boolean;
}

export const SECTION_SPEC: Record<string, SectionSpec> = {
  room: { label: '객실', draggable: true },
  unassigned: { label: '미배정', draggable: true },
  party: { label: '파티만', draggable: true },
  unstable: { label: '언스테이블', draggable: true },
  activity: { label: '액티비티', draggable: false },
};

// NULL/빈값/미지의 section → 'unassigned' 동작 (백엔드 spec_for 와 동일 fallback)
const DEFAULT_SPEC: SectionSpec = SECTION_SPEC.unassigned;

export function specForSection(section: string | null | undefined): SectionSpec {
  return (section && SECTION_SPEC[section]) || DEFAULT_SPEC;
}

/** 드래그 가능 여부 (현재: activity 만 false). cancelled 상태는 별도 오버레이로 호출처에서 처리. */
export function isDraggableSection(section: string | null | undefined): boolean {
  return specForSection(section).draggable;
}

export function sectionLabel(section: string | null | undefined): string {
  return specForSection(section).label;
}
