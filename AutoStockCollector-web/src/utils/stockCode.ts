export function normalizeCode(input: string): string {
  const digits = input.replace(/\D/g, '')
  if (digits.length !== 6) return input.toUpperCase()
  if (digits.startsWith('6')) return `SH${digits}`
  if (digits.startsWith('0') || digits.startsWith('3')) return `SZ${digits}`
  return input.toUpperCase()
}

export function formatCodeDisplay(code: string): string {
  return code.replace(/^(SH|SZ)/, '')
}

export function isValidCode(code: string): boolean {
  return /^(SH|SZ)\d{6}$/.test(code)
}
