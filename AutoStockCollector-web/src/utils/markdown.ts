import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const ALLOWED_TAGS = new Set([
  'p', 'br', 'b', 'i', 'em', 'strong', 'a', 'ul', 'ol', 'li',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'code', 'pre', 'blockquote',
  'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'span', 'div',
])

// 允许的属性：移除 style（可被用于 CSS 数据外泄/点击劫持），href/target/class 保留但做协议白名单
const ALLOWED_ATTRS = new Set(['href', 'target', 'class'])
const SAFE_URL_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:'])

function sanitizeUrl(url: string): string {
  // 阻断 javascript:/data: 等危险协议（LLM 输出可能被研报标题诱导注入）
  const trimmed = (url || '').trim().toLowerCase()
  if (trimmed.startsWith('#') || trimmed.startsWith('/')) return url // 锚点/相对路径放行
  try {
    const proto = new URL(url, 'http://placeholder/').protocol
    return SAFE_URL_PROTOCOLS.has(proto) ? url : ''
  } catch {
    return ''
  }
}

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
    if (!ALLOWED_ATTRS.has(attr.name)) continue
    if (attr.name === 'href') {
      const safe = sanitizeUrl(attr.value)
      if (safe) clone.setAttribute('href', safe)
      // 不安全 href 直接丢弃，不留空属性
    } else {
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
  // 装进一个容器元素再读 innerHTML：DocumentFragment 没有 innerHTML 属性，
  // 旧实现 (fragment as unknown as Element).innerHTML 恒为 undefined，导致任何非空内容都被渲染成空白。
  const container = document.createElement('div')
  for (const child of Array.from(template.content.childNodes)) {
    container.appendChild(sanitize(child))
  }
  return container.innerHTML
}

export function renderMd(text: string): string {
  if (!text) return ''
  return sanitizeHtml(marked.parse(text) as string)
}

export { sanitizeHtml }
