import React, { useRef, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Undo2, Music, Trash2, Link2, X } from 'lucide-react';

interface GuestContextMenuProps {
  position: { x: number; y: number };
  targetCount: number;
  currentSection: 'room' | 'unassigned' | 'party';
  hasStayGroup: boolean;
  onMoveToPool: () => void;
  onMoveToParty: () => void;
  onDelete: () => void;
  onLinkStayGroup: () => void;
  onSetColor: (color: string | null) => void;
  onClose: () => void;
}

const COLOR_PRESETS: { key: string; label: string; bg: string }[] = [
  { key: 'yellow', label: '노랑', bg: '#FFF8E1' },
  { key: 'pink',   label: '분홍', bg: '#FFE8EE' },
  { key: 'green',  label: '초록', bg: '#E8F5E9' },
  { key: 'blue',   label: '파랑', bg: '#E3F2FD' },
  { key: 'purple', label: '보라', bg: '#F3E5F5' },
];

export default function GuestContextMenu({
  position,
  targetCount,
  currentSection,
  hasStayGroup,
  onMoveToPool,
  onMoveToParty,
  onDelete,
  onLinkStayGroup,
  onSetColor,
  onClose,
}: GuestContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [adjusted, setAdjusted] = useState<{ x: number; y: number }>(position);

  useEffect(() => {
    if (!menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let x = position.x;
    let y = position.y;
    if (x + rect.width > vw - 8) x = vw - rect.width - 8;
    if (y + rect.height > vh - 8) y = vh - rect.height - 8;
    if (x < 8) x = 8;
    if (y < 8) y = 8;
    setAdjusted({ x, y });
  }, [position]);

  const plural = targetCount > 1 ? ` (${targetCount}명)` : '';

  const items: { icon: React.ReactNode; label: string; onClick: () => void; disabled: boolean; danger?: boolean }[] = [
    {
      icon: <Undo2 className="h-4 w-4" />,
      label: `미배정으로 이동${plural}`,
      onClick: onMoveToPool,
      disabled: currentSection === 'unassigned',
    },
    {
      icon: <Music className="h-4 w-4" />,
      label: `파티만으로 이동${plural}`,
      onClick: onMoveToParty,
      disabled: currentSection === 'party',
    },
    {
      icon: <Link2 className="h-4 w-4" />,
      label: hasStayGroup ? '연박 해제' : '연박 묶기',
      onClick: onLinkStayGroup,
      disabled: false,
    },
  ];

  return createPortal(
    <div
      ref={menuRef}
      style={{ position: 'fixed', left: adjusted.x, top: adjusted.y, zIndex: 10000 }}
      className="w-48 rounded-xl border border-[#E5E8EB] dark:border-gray-800 bg-white dark:bg-[#1E1E24] shadow-lg py-1 animate-in fade-in zoom-in-95 duration-100"
      onContextMenu={(e) => e.preventDefault()}
    >
      {items.map((item, i) => (
        <button
          key={i}
          onClick={(e) => { e.stopPropagation(); if (!item.disabled) item.onClick(); }}
          disabled={item.disabled}
          className={`w-full px-3 py-2 text-body flex items-center gap-2 transition-colors ${
            item.disabled
              ? 'text-[#B0B8C1] dark:text-[#4E5968] cursor-not-allowed'
              : 'text-[#191F28] dark:text-white hover:bg-[#F2F4F6] dark:hover:bg-[#2C2C34] cursor-pointer'
          }`}
        >
          {item.icon}
          {item.label}
        </button>
      ))}

      <div className="border-t border-[#E5E8EB] dark:border-gray-800 my-1" />

      <div className="px-3 py-1.5 flex items-center gap-1.5">
        {COLOR_PRESETS.map((preset) => (
          <button
            key={preset.key}
            title={preset.label}
            onClick={(e) => { e.stopPropagation(); onSetColor(preset.key); }}
            className="w-5 h-5 rounded-full border border-gray-300 dark:border-gray-600 cursor-pointer hover:scale-110 transition-transform flex-shrink-0"
            style={{ backgroundColor: preset.bg }}
          />
        ))}
        <button
          title="색상 해제"
          onClick={(e) => { e.stopPropagation(); onSetColor(null); }}
          className="w-5 h-5 rounded-full border border-dashed border-gray-300 dark:border-gray-600 cursor-pointer hover:scale-110 transition-transform flex items-center justify-center flex-shrink-0"
        >
          <X className="h-2.5 w-2.5 text-[#8B95A1]" />
        </button>
      </div>

      <div className="border-t border-[#E5E8EB] dark:border-gray-800 my-1" />

      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="w-full px-3 py-2 text-body flex items-center gap-2 text-[#F04452] hover:bg-[#FFF0F0] dark:hover:bg-[#F04452]/10 cursor-pointer transition-colors"
      >
        <Trash2 className="h-4 w-4" />
        게스트 삭제{plural}
      </button>
    </div>,
    document.body,
  );
}
