export function normalizeCode(input: string): string {
  const digits = input.replace(/[^0-9]/g, '');
  if (digits.startsWith('6')) return `SH${digits}`;
  if (digits.startsWith('0') || digits.startsWith('3')) return `SZ${digits}`;
  return input.toUpperCase();
}

export function fmtAmount(n: number): string {
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`;
  return n.toLocaleString();
}

export function fmtPercent(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export const RISE_COLOR = '#ef5350';
export const FALL_COLOR = '#26a69a';
export const FLAT_COLOR = '#9e9e9e';