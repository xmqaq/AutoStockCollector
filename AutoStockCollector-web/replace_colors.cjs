const fs = require('fs');
const path = require('path');

const replacements = [
  { regex: /background(-color)?:\s*#fff(fff)?\b/gi, replacement: 'background$1: var(--bg-card)' },
  { regex: /background(-color)?:\s*white\b/gi, replacement: 'background$1: var(--bg-card)' },
  { regex: /background(-color)?:\s*#f5f7fa\b/gi, replacement: 'background$1: var(--bg-soft)' },
  { regex: /background(-color)?:\s*#fafafa\b/gi, replacement: 'background$1: var(--bg-soft)' },
  { regex: /color:\s*#333(333)?\b/gi, replacement: 'color: var(--text-primary)' },
  { regex: /color:\s*#666(666)?\b/gi, replacement: 'color: var(--text-secondary)' },
  { regex: /color:\s*#999(999)?\b/gi, replacement: 'color: var(--text-muted)' },
  { regex: /border(-color)?:\s*(.*?)#ebeef5\b/gi, replacement: 'border$1: $2var(--border-color)' },
  { regex: /border(-color)?:\s*(.*?)#e4e7ed\b/gi, replacement: 'border$1: $2var(--border-color)' },
  { regex: /border(-color)?:\s*(.*?)#dcdfe6\b/gi, replacement: 'border$1: $2var(--border-strong)' },
  { regex: /border(-color)?:\s*(.*?)#eee(eee)?\b/gi, replacement: 'border$1: $2var(--border-color)' },
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
  if (filePath.endsWith('.vue') || filePath.endsWith('.css')) {
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
