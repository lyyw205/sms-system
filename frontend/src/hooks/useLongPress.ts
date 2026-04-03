import { useRef, useEffect, useCallback } from 'react';
import type React from 'react';

/** CSS styles to apply on elements that use long-press (prevent native touch behaviors) */
export const TOUCH_STYLE: React.CSSProperties = {
  touchAction: 'manipulation',
  WebkitUserSelect: 'none',
  userSelect: 'none',
  WebkitTouchCallout: 'none',
} as React.CSSProperties;

interface UseLongPressOptions {
  /** Called when long-press triggers (≥ delay ms) */
  onLongPress: (e: React.PointerEvent, resId: number) => void;
  /** Called on short tap (< delay ms). Receives the original touch target for manual focus/click compensation. */
  onShortTap?: (target: HTMLElement, e: React.PointerEvent, resId: number, showGrip: boolean) => void;
  /** Long-press delay in ms (default: 500) */
  delay?: number;
  /** Movement threshold to cancel long-press in px (default: 10) */
  moveThreshold?: number;
  /** Disable long-press detection */
  disabled?: boolean;
}

interface LongPressHandlers {
  onPointerDownCapture: (e: React.PointerEvent) => void;
  onPointerMoveCapture: (e: React.PointerEvent) => void;
  onPointerUpCapture: (e: React.PointerEvent) => void;
  onPointerCancelCapture: () => void;
}

/**
 * Custom hook for touch long-press detection with short-tap compensation.
 *
 * Uses capture-phase pointer events so the parent intercepts before child inputs.
 * Calls preventDefault() on pointerdown for touch to block native text selection,
 * then compensates with manual focus/click on short tap via onShortTap callback.
 */
export function useLongPress({
  onLongPress,
  onShortTap,
  delay = 500,
  moveThreshold = 10,
  disabled = false,
}: UseLongPressOptions) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const triggered = useRef(false);
  const startPos = useRef<{ x: number; y: number } | null>(null);
  const target = useRef<HTMLElement | null>(null);

  // Ref-back the callbacks to avoid stale closures in the 500ms timeout
  const onLongPressRef = useRef(onLongPress);
  onLongPressRef.current = onLongPress;
  const onShortTapRef = useRef(onShortTap);
  onShortTapRef.current = onShortTap;

  // Suppress native context menu right after long-press triggers our custom one (mount-once)
  useEffect(() => {
    const suppress = (e: Event) => {
      if (triggered.current) {
        e.preventDefault();
        triggered.current = false;
      }
    };
    document.addEventListener('contextmenu', suppress, true);
    return () => document.removeEventListener('contextmenu', suppress, true);
  }, []);

  const rowEl = useRef<HTMLElement | null>(null);
  const lockedInput = useRef<HTMLElement | null>(null);

  const restoreTouchAction = useCallback(() => {
    if (rowEl.current) {
      rowEl.current.style.touchAction = '';
      rowEl.current = null;
    }
    if (lockedInput.current) {
      lockedInput.current.style.touchAction = '';
      lockedInput.current = null;
    }
  }, []);

  const cleanup = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    restoreTouchAction();
    startPos.current = null;
    target.current = null;
  }, [restoreTouchAction]);

  /**
   * Returns capture-phase pointer event handlers bound to a specific row.
   * Usage: `<div {...handlers(res.id, showGrip)}>`
   */
  const handlers = useCallback((resId: number, showGrip = false): LongPressHandlers => ({
    onPointerDownCapture: (e: React.PointerEvent) => {
      if (e.pointerType === 'mouse') return;
      if (disabled) return;
      const el = e.target as HTMLElement;
      if (el.closest('button, a, select, [role="button"], [data-interactive]')) return;

      e.preventDefault();
      // Immediately blur input to prevent cursor flash during long-press wait
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
        el.blur();
      }
      triggered.current = false;
      target.current = el;
      startPos.current = { x: e.clientX, y: e.clientY };

      // Temporarily lock touch-action to none on both row and target element
      // Input elements have their own touch handling that overrides parent's touch-action
      const row = (e.currentTarget as HTMLElement);
      row.style.touchAction = 'none';
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
        el.style.touchAction = 'none';
        lockedInput.current = el;
      }
      rowEl.current = row;

      const pointerEvent = e;
      timer.current = setTimeout(() => {
        triggered.current = true;
        target.current = null;
        restoreTouchAction();
        if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
        window.getSelection()?.removeAllRanges();
        if (navigator.vibrate) navigator.vibrate(50);
        onLongPressRef.current(pointerEvent, resId);
      }, delay);
    },

    onPointerMoveCapture: (e: React.PointerEvent) => {
      if (!timer.current || !startPos.current) return;
      const dx = e.clientX - startPos.current.x;
      const dy = e.clientY - startPos.current.y;
      if (Math.abs(dx) > moveThreshold || Math.abs(dy) > moveThreshold) {
        cleanup();
      }
    },

    onPointerUpCapture: (e: React.PointerEvent) => {
      if (timer.current) {
        clearTimeout(timer.current);
        timer.current = null;
      }
      restoreTouchAction();
      // Short tap compensation: restore focus/click that preventDefault blocked
      if (!triggered.current && target.current && onShortTapRef.current) {
        onShortTapRef.current(target.current, e, resId, showGrip);
      } else if (triggered.current) {
        // Long-press was triggered — prevent browser from focusing the input on touch-up
        e.preventDefault();
        if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
      }
      startPos.current = null;
      target.current = null;
    },

    onPointerCancelCapture: () => {
      cleanup();
    },
  }), [disabled, delay, moveThreshold, cleanup, restoreTouchAction]);

  return { handlers };
}
