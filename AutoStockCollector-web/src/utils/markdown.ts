import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

function sanitizeBasic(html: string): string {
  if (!html) return ''
  return html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/ on\w+="[^"]*"/gi, '')
    .replace(/ on\w+='[^']*'/gi, '')
    .replace(/javascript:/gi, '')
}

export function renderMd(text: string): string {
  if (!text) return ''
  return sanitizeBasic(marked.parse(text) as string)
}

export function sanitizeHtml(html: string): string {
  if (!html) return ''
  return sanitizeBasic(html)
}
