import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const ALLOWED_TAGS = new Set([
  'p', 'br', 'b', 'i', 'em', 'strong', 'a', 'ul', 'ol', 'li',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'code', 'pre', 'blockquote',
  'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'span', 'div',
])

const ALLOWED_ATTRS = new Set(['href', 'target', 'class', 'style'])

function sanitize(node: Node): Node {
  if (node.nodeType === 3) return node
  if (node.nodeType !== 1) return document.createTextNode('')
  const el = node as Element
  const tag = el.tagName.toLowerCase()
  if (!ALLOWED_TAGS.has(tag)) {
    return document.createTextNode(el.textContent || '')
  }
  const clone = document.createElement(tag)
  for (const attr of Array.from(el.attributes)) {
    if (ALLOWED_ATTRS.has(attr.name)) {
      clone.setAttribute(attr.name, attr.value)
    }
  }
  for (const child of Array.from(el.childNodes)) {
    clone.appendChild(sanitize(child))
  }
  return clone
}

function sanitizeHtml(html: string): string {
  const template = document.createElement('template')
  template.innerHTML = html
  const fragment = document.createDocumentFragment()
  for (const child of Array.from(template.content.childNodes)) {
    fragment.appendChild(sanitize(child))
  }
  return fragment.firstChild
    ? (fragment as unknown as Element).innerHTML || ''
    : ''
}

export function renderMd(text: string): string {
  if (!text) return ''
  return sanitizeHtml(marked.parse(text) as string)
}

export { sanitizeHtml }
