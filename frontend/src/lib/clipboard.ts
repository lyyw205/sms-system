/**
 * 클립보드 복사 헬퍼.
 *
 * navigator.clipboard.writeText 는 secure context(HTTPS·localhost)에서만 동작한다.
 * 운영 nginx 가 HTTP(80)로 떠 있을 수 있어(이 경우 navigator.clipboard === undefined),
 * 구형 execCommand('copy') 폴백을 함께 둔다. 개발(localhost)은 secure context 라
 * 표준 API 로 동작하지만, 운영에서 조용히 깨지는 것을 막기 위해 폴백은 필수다.
 *
 * @returns 복사 성공 여부 (호출측에서 toast 등 피드백 처리)
 */
export async function copyTextToClipboard(text: string): Promise<boolean> {
  // 1) 표준 Async Clipboard API (secure context 필요)
  if (
    typeof navigator !== 'undefined' &&
    navigator.clipboard &&
    typeof window !== 'undefined' &&
    window.isSecureContext
  ) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 권한 거부 / 포커스 상실 등 → 아래 폴백으로 진행
    }
  }

  // 2) execCommand('copy') 폴백 (insecure context / 구형 브라우저)
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    // 화면 밖 배치 + 스크롤 점프 방지
    ta.style.position = 'fixed';
    ta.style.top = '-9999px';
    ta.style.left = '-9999px';
    ta.setAttribute('readonly', '');
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}
