const fs = require('fs');
const path = require('path');

const replacements = [
  // 1. 布局与滚动条问题 (高度计算冲突)
  { regex: /min-height:\s*100vh;/g, replacement: 'height: 100%;' },
  { regex: /height:\s*100vh;/g, replacement: 'height: 100%;' },
  { regex: /min-height:\s*calc\(100vh[^)]+\);/g, replacement: 'height: 100%;' },
  { regex: /height:\s*calc\(100vh[^)]+\);/g, replacement: 'height: 100%;' },

  // 2. 硬编码的语义颜色 (未随主题切换)
  { regex: /#f56c6c/gi, replacement: 'var(--el-color-danger)' },
  { regex: /#ef5350/gi, replacement: 'var(--el-color-danger)' },
  { regex: /#67c23a/gi, replacement: 'var(--el-color-success)' },
  { regex: /#26a69a/gi, replacement: 'var(--el-color-success)' },
  { regex: /#e6a23c/gi, replacement: 'var(--el-color-warning)' },
  { regex: /#909399/gi, replacement: 'var(--text-muted)' },
  { regex: /#a8abb2/gi, replacement: 'var(--text-muted)' },
  { regex: /#303133/gi, replacement: 'var(--text-primary)' },
  { regex: /#606266/gi, replacement: 'var(--text-secondary)' },
  { regex: /#ffd700/gi, replacement: 'var(--el-color-warning)' },
  { regex: /#e0e0e0/gi, replacement: 'var(--text-secondary)' },

  // 3. 不兼容暗色的透明度背景 (RGBA)
  // 黑色半透明 -> 转换为柔和背景变量
  { regex: /rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.0[1-4]\s*\)/g, replacement: 'var(--bg-hover-subtle)' },
  { regex: /rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.1\s*\)/g, replacement: 'var(--bg-hover)' },
  { regex: /rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.2\s*\)/g, replacement: 'var(--border-color)' },
  // 白色半透明 -> 转换为柔和背景变量
  { regex: /rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.2\s*\)/g, replacement: 'var(--bg-hover)' },
  { regex: /rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.02\s*\)/g, replacement: 'var(--bg-hover-subtle)' },
  { regex: /rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.8\s*\)/g, replacement: 'var(--bg-overlay)' },
  { regex: /rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.4\s*\)/g, replacement: 'var(--text-muted)' },

  // 4. 特殊的硬编码背景色
  { regex: /#1e1e1e/gi, replacement: 'var(--bg-deep)' },
  { regex: /#fdfbf7/gi, replacement: 'var(--bg-card)' },
];

function walkDir(dir, callback) {
  fs.readdirSync(dir).forEach(f => {
    let dirPath = path.join(dir, f);
    let isDirectory = fs.statSync(dirPath).isDirectory();
    isDirectory ? walkDir(dirPath, callback) : callback(path.join(dir, f));
  });
}

let changedFiles = 0;

walkDir('/Users/admin/Desktop/xiangmu/stock/AutoStockCollector-web/src', function(filePath) {
  if (filePath.endsWith('.vue')) {
    let content = fs.readFileSync(filePath, 'utf8');
    let originalContent = content;
    
    replacements.forEach(rule => {
      content = content.replace(rule.regex, rule.replacement);
    });
    
    if (content !== originalContent) {
      fs.writeFileSync(filePath, content, 'utf8');
      console.log('Updated:', filePath);
      changedFiles++;
    }
  }
});

console.log(`Done. Changed ${changedFiles} files.`);
