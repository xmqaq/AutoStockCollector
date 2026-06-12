import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

/** LLM 输出 markdown → 经 DOMPurify 消毒的 HTML,供 v-html 使用 */
export function renderMd(text: string): string {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text) as string)
}

/** 自行拼接的 HTML 片段(如 \n→<br> 简易格式化)统一消毒后再 v-html */
export function sanitizeHtml(html: string): string {
  if (!html) return ''
  return DOMPurify.sanitize(html)
}
