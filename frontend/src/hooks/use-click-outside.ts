import { useEffect, type RefObject } from 'react'

/**
 * 지정 ref 영역 바깥 클릭(또는 Escape 키)을 감지해 handler 호출.
 *
 * - mousedown 사용: click 보다 일찍 발화해 메뉴 안 다른 컴포넌트가 stopPropagation 해도
 *   바깥 영역이 비교적 정확히 잡힘.
 * - touchstart 동시 등록: 모바일 바깥 탭 감지.
 * - active=false 면 리스너 미등록 (드롭다운이 닫혀있을 땐 비용 0).
 */
export function useClickOutside(
  ref: RefObject<HTMLElement | null>,
  handler: () => void,
  active: boolean = true,
  options?: { closeOnEscape?: boolean }
) {
  const closeOnEscape = options?.closeOnEscape ?? true

  useEffect(() => {
    if (!active) return

    const onPointer = (e: MouseEvent | TouchEvent) => {
      const el = ref.current
      if (!el) return
      const target = e.target as Node | null
      if (target && el.contains(target)) return
      handler()
    }

    const onKey = (e: KeyboardEvent) => {
      if (closeOnEscape && e.key === 'Escape') handler()
    }

    document.addEventListener('mousedown', onPointer)
    document.addEventListener('touchstart', onPointer, { passive: true })
    if (closeOnEscape) document.addEventListener('keydown', onKey)

    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('touchstart', onPointer)
      if (closeOnEscape) document.removeEventListener('keydown', onKey)
    }
  }, [ref, handler, active, closeOnEscape])
}
