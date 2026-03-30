// Shared highlight color definitions and utilities
// Used by GuestContextMenu, RoomAssignment, and TableSettingsModal

export interface ColorPreset {
  key: string;
  label: string;
  hex: string;
}

export interface HighlightStyle {
  bg: string;
  hover: string;
  text?: string;
}

/** 10 preset colors (5 light + 5 dark variants) */
export const COLOR_PRESETS: ColorPreset[] = [
  { key: 'yellow', label: '연노랑', hex: '#FFF8E1' },
  { key: 'pink', label: '연분홍', hex: '#FFE8EE' },
  { key: 'green', label: '연초록', hex: '#E8F5E9' },
  { key: 'blue', label: '연파랑', hex: '#E3F2FD' },
  { key: 'purple', label: '연보라', hex: '#F3E5F5' },
  { key: 'yellow-dark', label: '노랑', hex: '#FFD54F' },
  { key: 'pink-dark', label: '분홍', hex: '#F48FB1' },
  { key: 'green-dark', label: '초록', hex: '#81C784' },
  { key: 'blue-dark', label: '파랑', hex: '#64B5F6' },
  { key: 'purple-dark', label: '보라', hex: '#CE93D8' },
];

/** Tailwind class-based styles for preset colors */
export const PRESET_HIGHLIGHT_STYLES: Record<string, HighlightStyle> = {
  yellow: { bg: 'bg-[#FFF8E1] dark:bg-[#FFF8E1]/15', hover: 'hover:bg-[#FFF0C0] dark:hover:bg-[#FFF8E1]/25' },
  pink: { bg: 'bg-[#FFE8EE] dark:bg-[#FFE8EE]/15', hover: 'hover:bg-[#FFD6E0] dark:hover:bg-[#FFE8EE]/25' },
  green: { bg: 'bg-[#E8F5E9] dark:bg-[#E8F5E9]/15', hover: 'hover:bg-[#D0ECD2] dark:hover:bg-[#E8F5E9]/25' },
  blue: { bg: 'bg-[#E3F2FD] dark:bg-[#E3F2FD]/15', hover: 'hover:bg-[#CFEBFF] dark:hover:bg-[#E3F2FD]/25' },
  purple: { bg: 'bg-[#F3E5F5] dark:bg-[#F3E5F5]/15', hover: 'hover:bg-[#E8D0ED] dark:hover:bg-[#F3E5F5]/25' },
  'yellow-dark': { bg: 'bg-[#FFD54F] dark:bg-[#FFD54F]/25', hover: 'hover:bg-[#FFCA28] dark:hover:bg-[#FFD54F]/35', text: 'text-[#191F28] dark:text-white' },
  'pink-dark': { bg: 'bg-[#F48FB1] dark:bg-[#F48FB1]/25', hover: 'hover:bg-[#F06292] dark:hover:bg-[#F48FB1]/35', text: 'text-[#191F28] dark:text-white' },
  'green-dark': { bg: 'bg-[#81C784] dark:bg-[#81C784]/25', hover: 'hover:bg-[#66BB6A] dark:hover:bg-[#81C784]/35', text: 'text-[#191F28] dark:text-white' },
  'blue-dark': { bg: 'bg-[#64B5F6] dark:bg-[#64B5F6]/25', hover: 'hover:bg-[#42A5F5] dark:hover:bg-[#64B5F6]/35', text: 'text-[#191F28] dark:text-white' },
  'purple-dark': { bg: 'bg-[#CE93D8] dark:bg-[#CE93D8]/25', hover: 'hover:bg-[#BA68C8] dark:hover:bg-[#CE93D8]/35', text: 'text-[#191F28] dark:text-white' },
};

/** Check if hex color is light (luminance > 0.6) for text contrast */
export function isLightColor(hex: string): boolean {
  const c = hex.replace('#', '');
  const r = parseInt(c.slice(0, 2), 16);
  const g = parseInt(c.slice(2, 4), 16);
  const b = parseInt(c.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6;
}

/** Check if a color key is a custom hex color (starts with #) */
export function isCustomHexColor(key: string | null | undefined): key is string {
  return !!key && key.startsWith('#');
}

/** Get inline background style for custom hex colors (dark mode uses alpha) */
export function getCustomBgStyle(hex: string, isDark: boolean): { backgroundColor: string } {
  return { backgroundColor: isDark ? `${hex}26` : hex }; // 26 hex ≈ 15% opacity
}

/** Get text class for custom hex color based on luminance */
export function getCustomTextClass(hex: string): string {
  return isLightColor(hex) ? 'text-[#191F28] dark:text-white' : 'text-white dark:text-white';
}

/** Default row stripe colors */
export const DEFAULT_ROW_COLORS = {
  even: '#FFFFFF',        // bg-white
  odd: '#F8F9FA',         // bg-[#F8F9FA]
  evenDark: '#1E1E24',    // dark:bg-[#1E1E24]
  oddDark: '#17171C',     // dark:bg-[#17171C]
  overbooking: '#FFF8E1', // bg-[#FFF8E1] (non-dorm, ≥2 guests)
  overbookingDark: '#FFF8E1',
};

export interface RowColorSettings {
  even: string;
  odd: string;
  evenDark: string;
  oddDark: string;
  overbooking: string;
  overbookingDark: string;
}

/** Load row colors from localStorage */
export function loadRowColors(): RowColorSettings {
  try {
    const saved = localStorage.getItem('roomAssignment_rowColors');
    if (saved) return { ...DEFAULT_ROW_COLORS, ...JSON.parse(saved) };
  } catch { /* ignore */ }
  return { ...DEFAULT_ROW_COLORS };
}

/** Save row colors to localStorage */
export function saveRowColors(colors: RowColorSettings): void {
  localStorage.setItem('roomAssignment_rowColors', JSON.stringify(colors));
}

/** Default divider colors */
export const DEFAULT_DIVIDER_COLOR = '#D1D5DB';
export const DEFAULT_DIVIDER_COLOR_DARK = '#4E5968';
export const DEFAULT_BORDER_COLOR = '#E5E8EB';
export const DEFAULT_BORDER_COLOR_DARK = '#2C2C34';

/** Common divider color presets for quick selection */
export const DIVIDER_COLOR_PRESETS = [
  '#D1D5DB', // gray (default)
  '#3182F6', // blue
  '#F04452', // red
  '#00C9A7', // green
  '#FF9F00', // orange
  '#7B61FF', // purple
  '#191F28', // dark
];
