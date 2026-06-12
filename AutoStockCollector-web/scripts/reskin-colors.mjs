import { readFileSync, writeFileSync } from 'node:fs'
import { execSync } from 'node:child_process'

const styleMap = {
  '#409eff': 'var(--el-color-primary)',
  '#67c23a': 'var(--el-color-success)',
  '#f56c6c': 'var(--el-color-danger)',
  '#e6a23c': 'var(--el-color-warning)',
}
const scriptMap = {
  '#409eff': '#3f7fae',
  '#67c23a': '#3f9d70',
  '#f56c6c': '#d05a51',
  '#e6a23c': '#c9943a',
}

const replaceAll = (text, map) => {
  for (const [from, to] of Object.entries(map))
    text = text.replace(new RegExp(from, 'gi'), to)
  return text
}

const files = execSync(
  `grep -rliE '#(409eff|67c23a|f56c6c|e6a23c)' src --include='*.vue' --include='*.ts'`,
  { encoding: 'utf8' }
).trim().split('\n')

for (const file of files) {
  const src = readFileSync(file, 'utf8')
  let out
  if (file.endsWith('.ts')) {
    out = replaceAll(src, scriptMap)
  } else {
    // .vue:按首个 <style 分界,style 段用 var(),其余(template/script)用 hex
    const idx = src.search(/<style[\s>]/)
    out = idx === -1
      ? replaceAll(src, scriptMap)
      : replaceAll(src.slice(0, idx), scriptMap) + replaceAll(src.slice(idx), styleMap)
  }
  if (out !== src) {
    writeFileSync(file, out)
    console.log('updated', file)
  }
}
