import { readFileSync, writeFileSync } from 'node:fs'

// rgba replacements for <style> blocks (CSS vars / brand-specific values)
// Rule: in style blocks use the new brand blue 21,89,140 (dark bg) or keep same transparency
// Per spec: blue → rgba(21, 89, 140, x) in style; green → rgba(52, 138, 93, x); red → rgba(196, 69, 60, x); orange → rgba(185, 134, 46, x)
const styleRgbaMap = [
  // blue: rgba(64, 158, 255, x) or rgba(64,158,255,x)
  [/rgba\(\s*64\s*,\s*158\s*,\s*255\s*,\s*([^)]+)\)/gi,  (_, a) => `rgba(21, 89, 140, ${a.trim()})`],
  // green: rgba(103, 194, 58, x)
  [/rgba\(\s*103\s*,\s*194\s*,\s*58\s*,\s*([^)]+)\)/gi,   (_, a) => `rgba(52, 138, 93, ${a.trim()})`],
  // red: rgba(245, 108, 108, x)
  [/rgba\(\s*245\s*,\s*108\s*,\s*108\s*,\s*([^)]+)\)/gi,  (_, a) => `rgba(196, 69, 60, ${a.trim()})`],
  // orange: rgba(230, 162, 60, x)
  [/rgba\(\s*230\s*,\s*162\s*,\s*60\s*,\s*([^)]+)\)/gi,   (_, a) => `rgba(185, 134, 46, ${a.trim()})`],
]

// rgba replacements for template/script blocks (use mid-tone hex-space values)
// Per spec: blue → rgba(63,127,174,x); green → rgba(63,157,112,x); red → rgba(208,90,81,x); orange → rgba(201,148,58,x)
const scriptRgbaMap = [
  [/rgba\(\s*64\s*,\s*158\s*,\s*255\s*,\s*([^)]+)\)/gi,  (_, a) => `rgba(63, 127, 174, ${a.trim()})`],
  [/rgba\(\s*103\s*,\s*194\s*,\s*58\s*,\s*([^)]+)\)/gi,   (_, a) => `rgba(63, 157, 112, ${a.trim()})`],
  [/rgba\(\s*245\s*,\s*108\s*,\s*108\s*,\s*([^)]+)\)/gi,  (_, a) => `rgba(208, 90, 81, ${a.trim()})`],
  [/rgba\(\s*230\s*,\s*162\s*,\s*60\s*,\s*([^)]+)\)/gi,   (_, a) => `rgba(201, 148, 58, ${a.trim()})`],
]

const applyMap = (text, map) => {
  for (const [pat, rep] of map) text = text.replace(pat, rep)
  return text
}

const files = [
  'src/components/LLMDialoguePanel/index.vue',
  'src/components/KlineChart/index.vue',
  'src/components/AIChatFloat/index.vue',
  'src/components/SentimentTrend/index.vue',
  'src/components/BatchPick/index.vue',
  'src/components/MultiAgentPanel/index.vue',
  'src/components/MultiAgentPanel/AnalysisPipeline.vue',
  'src/components/MultiAgentPanel/ResearcherAnalysis.vue',
  'src/components/MultiAgentPanel/DebateArena.vue',
  'src/components/MultiAgentPanel/DataCollectionPanel.vue',
  'src/components/AlertNotification/index.vue',
  'src/components/PhilosophyPanel/index.vue',
  'src/components/ProgressTable/index.vue',
  'src/components/ProfitChart/index.vue',
  'src/components/AnalysisProgress/index.vue',
  'src/views/MarginTrading/index.vue',
  'src/views/Workflow/index.vue',
  'src/views/Position/index.vue',
  'src/views/Dashboard/index.vue',
  'src/views/AIAgent/index.vue',
]

for (const file of files) {
  const src = readFileSync(file, 'utf8')
  const idx = src.search(/<style[\s>]/)
  let out
  if (idx === -1) {
    out = applyMap(src, scriptRgbaMap)
  } else {
    out = applyMap(src.slice(0, idx), scriptRgbaMap) + applyMap(src.slice(idx), styleRgbaMap)
  }
  if (out !== src) {
    writeFileSync(file, out)
    console.log('updated', file)
  }
}
