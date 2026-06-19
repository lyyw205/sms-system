import { GuestZone, type GuestZoneProps } from './GuestZone';
import { MobileGuestZone } from './MobileGuestZone';
import { useIsMobile } from '../../../../hooks/use-mobile';

type WrapperProps = Omit<
  GuestZoneProps,
  'title' | 'titleColorClass' | 'accept' | 'zoneId' | 'nextZoneId' | 'hoverBgClass' | 'emptyMessage' | 'emptyMessageColorClass' | 'rowZone'
>;

/**
 * 액티비티 zone 래퍼 — 정보 행(드롭 비활성, 객실 배정 대상 아님), 청록(#00C9A7) 테마.
 * rowZone='activity' 를 고정 전달해 GuestRow 가 3번째 컬럼을 액티비티 모드로 렌더.
 */
export function ActivityZone(props: WrapperProps) {
  const isMobile = useIsMobile();
  const Zone = isMobile ? MobileGuestZone : GuestZone;
  return (
    <Zone
      title="액티비티"
      titleColorClass="text-[#00C9A7] dark:text-[#00C9A7]"
      accept={false}
      hideWhenEmpty
      hoverBgClass="bg-[#00C9A7]/5 dark:bg-[#00C9A7]/8"
      emptyMessage=""
      emptyMessageColorClass="text-[#00C9A7] dark:text-[#00C9A7]"
      rowZone="activity"
      {...props}
    />
  );
}
