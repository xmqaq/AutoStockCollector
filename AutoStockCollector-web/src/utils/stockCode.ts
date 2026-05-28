export function normalizeCode(input: string): string {
  const trimmed = input.trim().toUpperCase();

  if (trimmed.startsWith('SH') || trimmed.startsWith('SZ')) {
    return trimmed;
  }

  if (trimmed.includes('.')) {
    const parts = trimmed.split('.');
    if (parts.length === 2) {
      const [digits, suffix] = parts;
      if (suffix === 'SH' || suffix === 'SZ' || suffix === 'SHANGHAI' || suffix === 'S') {
        return `SH${digits}`;
      }
      if (suffix === 'SZ' || suffix === 'SZ' || suffix === 'SHENZHEN') {
        return `SZ${digits}`;
      }
    }
  }

  const digitsOnly = trimmed.replace(/\D/g, '');
  if (digitsOnly.length === 6) {
    if (digitsOnly.startsWith('6')) {
      return `SH${digitsOnly}`;
    }
    if (digitsOnly.startsWith('0') || digitsOnly.startsWith('3')) {
      return `SZ${digitsOnly}`;
    }
  }

  return input.toUpperCase();
}

export function formatCodeDisplay(code: string): string {
  return code.replace(/^(SH|SZ)/, '');
}

export function isValidCode(code: string): boolean {
  return /^(SH|SZ)\d{6}$/.test(code);
}
