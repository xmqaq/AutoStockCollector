# AI 助手数据质量与体验优化设计

**日期:** 2026-06-02  
**状态:** 已批准

---

## 背景

当前 AI 助手 `/api/v1/ai/agent-chat` 端点在以下三个维度存在缺陷：

1. **新闻注入为空**：通用新闻无 `code` 字段，DAL 精确查询永远返回 0 条
2. **流式仅支持 OpenAI 兼容 provider**：Anthropic/Gemini 无流式分支，降级为非流式或报错
3. **跨页面无股票上下文**：AIChatFloat 只读 `route.query.code`，Market/Watchlist/DragonTiger 等页面打开 AI 助手时上下文为空

stock_info 字段缺失属于采集数据问题，通过补采解决，不在本次代码改动范围内。

---

## 改动一：新闻关键词兜底查询

### 文件
- `AutoStockCollector-manage/modules/ai/foundation/dal.py`
- `AutoStockCollector-manage/core/storage/mongo_storage.py`

### 设计

在 `NewsStorage` 新增 `search_by_keywords(keywords, limit)` 方法：

```python
def search_by_keywords(self, keywords: list, limit: int = 10) -> list:
    """按关键词列表模糊搜索新闻标题，用于股票名称/代码兜底查询。"""
    if not keywords:
        return []
    or_clauses = []
    for kw in keywords:
        if kw:
            or_clauses.append({"title": {"$regex": kw, "$options": "i"}})
    if not or_clauses:
        return []
    return self.find_many(
        {"$or": or_clauses},
        sort=[("publish_date", -1), ("_updated_at", -1)],
        limit=limit
    )
```

在 `StockDAL.get_stock_bundle()` 里，精确查询无结果时用关键词兜底：

```python
news = self.news_storage.get_latest_news(code=code, limit=news_limit) or []
if not news:
    bare = self._strip_market_prefix(code)          # "SH600000" → "600000"
    name = (info.get("name") or info.get("A股简称") or "").strip()
    keywords = [k for k in [bare, name] if k]
    if keywords:
        news = self.news_storage.search_by_keywords(keywords, limit=news_limit)
```

### 不动的地方
- `NewsStorage.get_latest_news` 签名不变（现有调用兼容）
- 只在 DAL 层加兜底，不改采集逻辑

---

## 改动二：stream_call 支持 Anthropic / Gemini

### 文件
- `AutoStockCollector-manage/modules/ai/foundation/llm_caller.py`

### 设计

将现有 `stream_call` 方法拆成 provider 分支 + 三个私有 generator 方法：

```python
def stream_call(self, provider: str, prompt: str,
                messages: Optional[List[Dict[str, str]]] = None):
    doc = self.key_loader(provider)
    # ... 公共 key/url/model 加载 ...
    p = provider.lower()
    msg_list = messages if messages else [{"role": "user", "content": prompt}]

    if p == "anthropic":
        yield from self._stream_anthropic(base_url, api_key, model, msg_list)
    elif p == "gemini":
        yield from self._stream_gemini(base_url, api_key, model, msg_list)
    else:
        yield from self._stream_openai(base_url, api_key, model, msg_list)  # 现有逻辑提取
```

#### `_stream_anthropic`

- 端点：`POST {base_url}/v1/messages`
- headers：`x-api-key`, `anthropic-version: 2023-06-01`, `anthropic-beta: messages-2023-06-01`
- body：`{"model", "max_tokens": 4096, "stream": true, "system": <system内容>, "messages": <非system消息>}`
- SSE 解析：事件类型 `content_block_delta`，提取 `delta.text`

```python
def _stream_anthropic(self, base_url, api_key, model, msg_list):
    system_parts = [m["content"] for m in msg_list if m.get("role") == "system"]
    user_msgs = [m for m in msg_list if m.get("role") != "system"]
    payload = {
        "model": model, "max_tokens": 4096, "stream": True,
        "messages": user_msgs,
    }
    if system_parts:
        payload["system"] = system_parts[0]
    # urllib SSE 逐行解析，yield delta["text"]
```

#### `_stream_gemini`

- 端点：`POST {base_url}/models/{model}:streamGenerateContent?key={api_key}`
- body：`{"contents": [...], "generationConfig": {"temperature": 0.7}}`
- 响应：ndjson，每行 JSON，提取 `candidates[0].content.parts[0].text`

```python
def _stream_gemini(self, base_url, api_key, model, msg_list):
    role_map = {"user": "user", "assistant": "model", "system": "user"}
    contents = [{"role": role_map.get(m["role"], "user"),
                 "parts": [{"text": m["content"]}]} for m in msg_list]
    # urllib 分行读取 ndjson，yield text chunk
```

#### `_stream_openai`（提取自现有 stream_call 逻辑，不改行为）

- 现有逻辑原封不动移入此方法

---

## 改动三：全局股票上下文 Pinia Store

### 文件
- 新建：`AutoStockCollector-web/src/stores/stockContextStore.ts`
- 修改：`AutoStockCollector-web/src/views/Watchlist/index.vue`
- 修改：`AutoStockCollector-web/src/views/DragonTiger/index.vue`
- 修改：`AutoStockCollector-web/src/views/Market/index.vue`
- 修改：`AutoStockCollector-web/src/views/StockDetail/index.vue`
- 修改：`AutoStockCollector-web/src/components/AIChatFloat/index.vue`

### Store 定义

```typescript
// stores/stockContextStore.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useStockContextStore = defineStore('stockContext', () => {
  const currentCode = ref('')
  const currentName = ref('')

  function setStock(code: string, name = '') {
    currentCode.value = code
    currentName.value = name || code
  }

  function clear() {
    currentCode.value = ''
    currentName.value = ''
  }

  return { currentCode, currentName, setStock, clear }
})
```

### 各页面改动（每处一行）

**StockDetail**（`loadStock` 函数里，已有 `currentCode.value = code`，在其后加）：
```typescript
stockContextStore.setStock(code, stockInfo.value?.name || code)
```

**Watchlist**（`goToStock` 或点击行时）：
```typescript
stockContextStore.setStock(code)
```

**DragonTiger**（`goToStock` 函数里）：
```typescript
stockContextStore.setStock(code)
```

**Market**（点击自选行情股票跳转前）：
```typescript
stockContextStore.setStock(code)
```

### AIChatFloat 读取 Store

```typescript
import { useStockContextStore } from '@/stores/stockContextStore'
const stockContextStore = useStockContextStore()

// 原来：
const stockContext = computed(() => (route.query.code as string) || '')

// 改为：store 优先，URL query 兜底
const stockContext = computed(
  () => stockContextStore.currentCode || (route.query.code as string) || ''
)

// stockName 读 store（有则用，无则 watch 自动 fetch）
watch(stockContext, async (code) => {
  if (!code) { stockName.value = ''; return }
  if (stockContextStore.currentName && stockContextStore.currentCode === code) {
    stockName.value = stockContextStore.currentName  // 直接复用，不用再请求
    return
  }
  // 否则走原有 stockApi.getStockInfo 请求
})
```

---

## 验证方案

### A. 新闻注入
```bash
python3 -c "
from modules.ai.foundation.dal import StockDAL
b = StockDAL().get_stock_bundle('SH600000')
print('news count:', len(b.news))
print('news[0]:', b.news[0].get('title') if b.news else 'empty')
"
```
期望：`news count > 0`

### B. 流式多 provider
```bash
# 测试 Anthropic 流式（需要有效 key）
curl -X POST http://localhost:5555/api/v1/ai/agent-chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"你好","provider":"anthropic"}' | head -c 200
# 期望：出现 data: {"type":"content",...} 事件流
```

### C. 全局 Store
1. 在 Watchlist 页点击某只股票 → 打开 AI 助手 → Toolbar 显示对应股票标签 ✓
2. 在 DragonTiger 页点击代码 → AI 助手标签更新 ✓
3. 切换到无股票页面 → AI 助手标签不消失（store 保留最后上下文）✓
