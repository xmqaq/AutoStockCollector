export const PRESETS = [
  { value: 'openai',    label: 'OpenAI',                 provider: 'openai',    base_url: 'https://api.openai.com/v1',                         color: '#10a37f' },
  { value: 'anthropic', label: 'Anthropic (Claude)',      provider: 'anthropic', base_url: 'https://api.anthropic.com',                         color: '#d4805a' },
  { value: 'qwen',      label: '通义千问 (Qwen)',          provider: 'qwen',      base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', color: '#5664f5' },
  { value: 'deepseek',  label: 'DeepSeek',                provider: 'deepseek',  base_url: 'https://api.deepseek.com/v1',                       color: '#4b7bf4' },
  { value: 'gemini',    label: 'Google Gemini',           provider: 'gemini',    base_url: 'https://generativelanguage.googleapis.com/v1beta',  color: '#4285f4' },
  { value: 'moonshot',  label: '月之暗面 (Moonshot)',      provider: 'moonshot',  base_url: 'https://api.moonshot.cn/v1',                        color: '#8b5cf6' },
  { value: 'glm',       label: '智谱 AI (GLM)',            provider: 'glm',       base_url: 'https://open.bigmodel.cn/api/paas/v4',             color: '#2563eb' },
  { value: 'doubao',    label: '字节豆包 (Doubao)',         provider: 'doubao',    base_url: 'https://ark.cn-beijing.volces.com/api/v3',          color: '#f59e0b' },
  { value: 'mistral',   label: 'Mistral AI',              provider: 'mistral',   base_url: 'https://api.mistral.ai/v1',                         color: '#f87c56' },
  { value: 'minimax',   label: 'MiniMax',                 provider: 'minimax',   base_url: 'https://api.minimax.io/v1/text/chatcompletion_v2',  color: '#00d4aa' },
  { value: 'cohere',    label: 'Cohere',                  provider: 'cohere',    base_url: 'https://api.cohere.com/v1',                         color: '#39594d' },
  { value: 'agnes',     label: 'Agnes AI',               provider: 'agnes',     base_url: 'https://apihub.agnes-ai.com/v1',                    color: '#8B5CF6' },
  { value: 'custom',    label: '自定义接口',               provider: '',          base_url: '',                                                  color: '#666688' },
]

export const BUILTIN_URLS: Record<string, string> = Object.fromEntries(
  PRESETS.filter(p => p.value !== 'custom').map(p => [p.provider, p.base_url])
)

export const COLOR_MAP: Record<string, string> = Object.fromEntries(
  PRESETS.filter(p => p.value !== 'custom').map(p => [p.provider, p.color])
)

export function providerColor(provider: string): string {
  const lower = provider.toLowerCase()
  for (const [k, v] of Object.entries(COLOR_MAP)) {
    if (lower.includes(k)) return v
  }
  let h = 0
  for (let i = 0; i < provider.length; i++) h = provider.charCodeAt(i) + ((h << 5) - h)
  return `hsl(${Math.abs(h) % 360},50%,52%)`
}

export function isBuiltinUrl(provider: string, url: string): boolean {
  return BUILTIN_URLS[provider] === url
}
