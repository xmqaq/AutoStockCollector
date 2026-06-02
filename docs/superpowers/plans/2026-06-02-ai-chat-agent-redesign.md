# AI 助手统一 Agent Chat 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AIChatFloat 浮动对话框重构为统一的 agent-chat 接口，实现股票上下文感知、角色数据预注入、动态快捷操作。

**Architecture:** 后端新增 `POST /api/v1/ai/agent-chat` 端点，用 `dal.get_stock_bundle()` + `factors.py` 按角色裁剪注入数据，通过 SSE 流式返回。前端 AIChatFloat 用 `useRoute()` 感知当前股票页面，废弃双路由判断逻辑，统一调用新端点。

**Tech Stack:** Python/Flask (SSE), MongoDB (ai_agents), Vue 3 (Composition API), TypeScript, Element Plus

---

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 修改 | `AutoStockCollector-manage/api/routes/__init__.py` |
| 新增测试 | `AutoStockCollector-manage/tests/unit/test_agent_chat.py` |
| 修改 | `AutoStockCollector-web/src/components/AIChatFloat/index.vue` |

---

## Task 1：后端 — `_build_agent_context()` + `/api/v1/ai/agent-chat` 端点

**Files:**
- Modify: `AutoStockCollector-manage/api/routes/__init__.py`
- Create: `AutoStockCollector-manage/tests/unit/test_agent_chat.py`

- [ ] **Step 1: 先写失败测试**

创建 `AutoStockCollector-manage/tests/unit/test_agent_chat.py`：

```python
import sys
import os
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def make_app():
    from main import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app


class TestAgentChatEndpoint:
    def test_missing_message_returns_400(self):
        app = make_app()
        with app.test_client() as c:
            rv = c.post('/api/v1/ai/agent-chat',
                        json={},
                        content_type='application/json')
            assert rv.status_code == 400
            data = json.loads(rv.data)
            assert data['success'] is False
            assert 'message' in data['error']

    def test_returns_event_stream_content_type(self):
        app = make_app()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.provider = 'test'
        mock_result.raw = '测试回复'

        with app.test_client() as c:
            with patch('modules.ai.foundation.llm_router.LLMRouter.chat_stream',
                       return_value=iter(['测试', '回复'])):
                rv = c.post('/api/v1/ai/agent-chat',
                            json={'message': '你好'},
                            content_type='application/json')
                assert rv.status_code == 200
                assert 'text/event-stream' in rv.content_type

    def test_build_agent_context_technical(self):
        """_build_agent_context 为技术分析师生成正确字段"""
        from api.routes import _build_agent_context

        class FakeBundle:
            code = 'sh600000'
            name = '浦发银行'
            closes = [10.0, 9.8, 9.9, 10.1, 9.7, 9.5, 9.6, 9.8, 10.0, 10.2,
                      10.3, 10.1, 9.9, 9.8, 10.0, 10.2, 10.4, 10.3, 10.1, 9.9]
            volumes = [1e6] * 20
            pe = 8.5
            pb = 0.7
            main_net_inflow = None
            news = []
            roe = ps = gross_margin = debt_ratio = revenue_growth = profit_growth = None

        ctx = _build_agent_context('technical_analyst', FakeBundle(), {'trend': 65, 'volume': 70})
        assert '浦发银行' in ctx
        assert '技术评分' in ctx
        assert 'MA5' in ctx or 'MA20' in ctx

    def test_build_agent_context_no_agent_shows_basic(self):
        from api.routes import _build_agent_context

        class FakeBundle:
            code = 'sh600000'
            name = '浦发银行'
            closes = [10.0, 9.8, 9.9]
            volumes = []
            pe = 8.5
            pb = 0.7
            main_net_inflow = None
            news = []
            roe = ps = gross_margin = debt_ratio = revenue_growth = profit_growth = None

        ctx = _build_agent_context('', FakeBundle(), {})
        assert '浦发银行' in ctx
        assert '10.0' in ctx  # 收盘价出现
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_agent_chat.py -v 2>&1 | head -40
```
期望输出：`FAILED` / `ImportError: cannot import name '_build_agent_context'`

- [ ] **Step 3: 在 `api/routes/__init__.py` 中添加 `_build_agent_context()` 辅助函数**

在文件末尾（`get_sector_stocks` 函数之后）追加：

```python
def _build_agent_context(agent_id: str, bundle, scores: dict) -> str:
    """按角色裁剪注入的股票上下文块，供 ai_agent_chat 端点使用。"""
    lines = [f"【{bundle.name or bundle.code} 数据】"]
    closes = list(bundle.closes or [])
    volumes = list(bundle.volumes or [])

    if agent_id == "technical_analyst":
        lines.append(f"近20日收盘价（最新在前）：{[round(c, 2) for c in closes[:20]] if closes else '暂无'}")
        lines.append(f"近20日成交量：{[round(v, 0) for v in volumes[:20]] if volumes else '暂无'}")
        lines.append(f"技术评分：{scores.get('trend', '暂无')}  成交量评分：{scores.get('volume', '暂无')}")
        if len(closes) >= 5:
            lines.append(f"MA5：{round(sum(closes[:5]) / 5, 2)}")
        if len(closes) >= 20:
            lines.append(f"MA20：{round(sum(closes[:20]) / 20, 2)}")

    elif agent_id == "fund_analyst":
        lines.append(f"近10日成交量：{[round(v, 0) for v in volumes[:10]] if volumes else '暂无'}")
        if bundle.main_net_inflow is not None:
            sign = "+" if bundle.main_net_inflow >= 0 else ""
            lines.append(f"主力净流入：{sign}{bundle.main_net_inflow / 1e8:.2f}亿元")
        lines.append(f"资金评分：{scores.get('fund_flow', '暂无')}")

    elif agent_id == "fundamental_analyst":
        lines.append(f"市盈率(TTM)：{bundle.pe or '暂无'}")
        lines.append(f"市净率(PB)：{bundle.pb or '暂无'}")
        lines.append(f"ROE：{bundle.roe or '暂无'}")
        lines.append(f"毛利率：{bundle.gross_margin or '暂无'}")
        lines.append(f"负债率：{bundle.debt_ratio or '暂无'}")
        lines.append(f"营收同比：{bundle.revenue_growth or '暂无'}")
        lines.append(f"净利润同比：{bundle.profit_growth or '暂无'}")
        lines.append(f"基本面评分：{scores.get('valuation', '暂无')}")

    elif agent_id == "sentiment_analyst":
        news = (bundle.news or [])[:5]
        if news:
            lines.append("最近5条新闻：")
            for n in news:
                date = str(n.get("publish_date", ""))[:10]
                lines.append(f"  [{date}] {n.get('title', '')}")
        else:
            lines.append("暂无相关新闻")

    elif agent_id == "market_analyst":
        lines.append(f"近10日收盘价：{[round(c, 2) for c in closes[:10]] if closes else '暂无'}")
        lines.append(f"近10日成交量：{[round(v, 0) for v in volumes[:10]] if volumes else '暂无'}")
        if bundle.main_net_inflow is not None:
            sign = "+" if bundle.main_net_inflow >= 0 else ""
            lines.append(f"主力净流入：{sign}{bundle.main_net_inflow / 1e8:.2f}亿元")
        for n in (bundle.news or [])[:2]:
            lines.append(f"新闻：{n.get('title', '')}")
        lines.append(
            f"综合评分：{scores.get('composite', '暂无')}"
            f"（技术{scores.get('trend', '?')} 基本面{scores.get('valuation', '?')} 资金{scores.get('fund_flow', '?')}）"
        )

    elif agent_id == "risk_analyst":
        lines.append(f"近20日收盘价：{[round(c, 2) for c in closes[:20]] if closes else '暂无'}")
        lines.append(f"PE：{bundle.pe or '暂无'}  PB：{bundle.pb or '暂无'}  ROE：{bundle.roe or '暂无'}")
        if bundle.main_net_inflow is not None:
            sign = "+" if bundle.main_net_inflow >= 0 else ""
            lines.append(f"主力净流入：{sign}{bundle.main_net_inflow / 1e8:.2f}亿元")
        lines.append(
            f"各维度评分 — 技术：{scores.get('trend', '?')}  基本面：{scores.get('valuation', '?')}"
            f"  资金：{scores.get('fund_flow', '?')}  综合：{scores.get('composite', '?')}"
        )
        for n in (bundle.news or [])[:3]:
            lines.append(f"新闻：{n.get('title', '')}")

    else:
        # 无特定角色：显示基础信息
        if closes:
            lines.append(f"近10日收盘价：{[round(c, 2) for c in closes[:10]]}")
        if bundle.pe:
            lines.append(f"PE：{bundle.pe}  PB：{bundle.pb or '暂无'}")

    return "\n".join(lines)
```

- [ ] **Step 4: 在 `api/routes/__init__.py` 中添加 `ai_agent_chat` 端点**

在 `_build_agent_context` 函数之前（文件倒数第二个位置，`get_sector_stocks` 之后）添加：

```python
@api_bp.route("/ai/agent-chat", methods=["POST"])
def ai_agent_chat():
    """统一 Agent Chat：通用聊天 + 角色 agent + 股票数据预注入，SSE 流式返回。
    Body: {message, agent_id?, stock_code?, history?, provider?}
    """
    import json as _json
    from flask import Response
    from modules.ai.foundation.llm_router import LLMRouter

    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    agent_id = (data.get("agent_id") or "").strip()
    stock_code = (data.get("stock_code") or "").strip()
    history = data.get("history") or []
    provider = (data.get("provider") or "").strip()

    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400

    # 1. 加载 agent 配置
    system_prompt = "你是一个专业的A股投资助手，能够提供市场分析和投资建议。"
    temperature = 0.7
    max_tokens = 2000
    if agent_id:
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            agent_doc = db["ai_agents"].find_one({"id": agent_id, "enabled": True})
            if agent_doc:
                system_prompt = agent_doc.get("system_prompt", system_prompt)
                temperature = float(agent_doc.get("temperature", temperature))
                max_tokens = int(agent_doc.get("max_tokens", max_tokens))
        except Exception as e:
            logger.warning(f"Failed to load agent config for {agent_id}: {e}")

    # 2. 构建股票上下文
    context_block = ""
    stock_name = ""
    if stock_code:
        try:
            from modules.ai.foundation.dal import StockDAL
            from modules.ai.foundation.factors import (
                trend_score, volume_score, valuation_score,
                fund_flow_score, composite_score,
            )
            bundle = StockDAL().get_stock_bundle(stock_code)
            stock_name = bundle.name or stock_code

            scores: dict = {}
            if bundle.closes:
                scores["trend"] = round(trend_score(bundle.closes), 1)
                if bundle.volumes:
                    scores["volume"] = round(volume_score(bundle.volumes), 1)
            scores["valuation"] = round(valuation_score(
                bundle.pe, bundle.pb, getattr(bundle, "ps", None),
                bundle.roe, bundle.gross_margin, bundle.debt_ratio,
                bundle.revenue_growth, bundle.profit_growth,
            ), 1)
            scores["fund_flow"] = round(fund_flow_score(bundle.main_net_inflow), 1)
            defined = {k: v for k, v in scores.items() if v is not None}
            total_w = {"trend": 0.25, "volume": 0.10, "valuation": 0.35, "fund_flow": 0.30}
            scores["composite"] = round(composite_score(defined, total_w), 1)

            context_block = _build_agent_context(agent_id, bundle, scores)
        except Exception as e:
            logger.warning(f"Failed to build stock context for {stock_code}: {e}")
            context_block = f"（获取 {stock_code} 数据时出错，请基于通用知识分析）"

    def generate():
        # 先发上下文元信息（前端可用于显示股票名）
        yield f"data: {_json.dumps({'type': 'context', 'data': {'stock_name': stock_name, 'has_data': bool(context_block)}})}\n\n"

        full_system = system_prompt
        if context_block:
            full_system += "\n\n" + context_block

        valid_history = [
            {"role": m["role"], "content": m["content"]}
            for m in history[-10:]
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        msgs = [{"role": "system", "content": full_system}] + valid_history + [{"role": "user", "content": message}]

        try:
            router = LLMRouter()
            if provider:
                router.providers = [provider]

            full_content = ""
            for chunk in router.chat_stream("", messages=msgs):
                if chunk:
                    full_content += chunk
                    yield f"data: {_json.dumps({'type': 'content', 'data': chunk})}\n\n"

            yield f"data: {_json.dumps({'type': 'done', 'data': {'content': full_content}})}\n\n"
        except Exception as e:
            logger.error(f"AI agent chat stream failed: {e}")
            yield f"data: {_json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_agent_chat.py -v
```
期望输出：`4 passed`

- [ ] **Step 6: 手动冒烟测试**

重启服务后：
```bash
# 最小请求（无 agent、无股票）
curl -s -X POST http://localhost:5555/api/v1/ai/agent-chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"你好"}' | head -c 200

# 期望：data: {"type": "context", ...}  data: {"type": "content", ...}

# 缺少 message 返回 400
curl -s -X POST http://localhost:5555/api/v1/ai/agent-chat \
  -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d)"
# 期望：{'success': False, 'error': 'message is required'}
```

- [ ] **Step 7: Commit**

```bash
cd AutoStockCollector-manage
git add api/routes/__init__.py tests/unit/test_agent_chat.py
git commit -m "feat: add unified /api/v1/ai/agent-chat endpoint with per-role data injection"
```

---

## Task 2：前端 — 股票上下文感知 + Toolbar 标签

**Files:**
- Modify: `AutoStockCollector-web/src/components/AIChatFloat/index.vue`（模板 `<div class="toolbar">` 部分 + script 顶部）

- [ ] **Step 1: 更新 script 顶部，添加 `useRoute` 和 `stockApi`**

将当前第 126-128 行替换为：

```typescript
import { ref, nextTick, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ChatDotRound, MagicStick, User, UserFilled } from '@element-plus/icons-vue'
import { aiApi, aiAgentApi, aiKeyApi, type AIAgent, type AIKeyConfig } from '@/api/ai'
import { stockApi } from '@/api/stock'
```

- [ ] **Step 2: 在 `const selectedProvider = ref('')` 之后添加股票上下文 refs**

```typescript
const route = useRoute()
const stockName = ref('')

// 从路由 query 读取当前股票代码（/stock-detail?code=sh600000）
const stockContext = computed(() => (route.query.code as string) || '')

watch(stockContext, async (code) => {
  if (!code) {
    stockName.value = ''
    return
  }
  try {
    const res = await stockApi.getStockInfo(code)
    stockName.value = res.data?.data?.name || code
  } catch {
    stockName.value = code
  }
}, { immediate: true })
```

- [ ] **Step 3: 更新 Toolbar 模板，添加股票上下文标签**

将当前第 20-34 行（`<div class="toolbar">...</div>`）替换为：

```html
<div class="toolbar">
  <el-select v-model="selectedAgent" placeholder="选择分析师" size="small" class="agent-select">
    <el-option
      v-for="agent in agents"
      :key="agent.id"
      :label="agent.name"
      :value="agent.id"
    >
      <div class="agent-option">
        <span>{{ agent.name }}</span>
        <span class="agent-desc">{{ agent.description }}</span>
      </div>
    </el-option>
  </el-select>
  <el-tag
    v-if="stockContext"
    size="small"
    type="success"
    class="stock-context-tag"
    closable
    @close="clearStockContext"
  >
    {{ stockName || stockContext }}
  </el-tag>
</div>
```

- [ ] **Step 4: 在 `clearChat()` 函数之后添加 `clearStockContext()`**

```typescript
function clearStockContext() {
  // 导航到当前路由但去掉 code 参数
  const { code: _removed, ...rest } = route.query
  import('@/router/index').then(({ default: router }) =>
    router.replace({ query: rest })
  )
}
```

- [ ] **Step 5: 在 `<style scoped>` 中添加标签样式**

在 `.toolbar` 规则之后添加：

```css
.stock-context-tag {
  flex-shrink: 0;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

- [ ] **Step 6: 手动验证**

访问 `/stock-detail?code=sh600000`，打开 AI 助手，确认 Toolbar 显示绿色"浦发银行"标签，点击 × 后标签消失。

- [ ] **Step 7: Commit**

```bash
cd AutoStockCollector-web
git add src/components/AIChatFloat/index.vue
git commit -m "feat: AIChatFloat - add route-based stock context detection and toolbar badge"
```

---

## Task 3：前端 — 替换双路由为统一 `streamAgentChat()`

**Files:**
- Modify: `AutoStockCollector-web/src/components/AIChatFloat/index.vue`（script 中的发送函数）

- [ ] **Step 1: 删除 `streamChat()` 函数（第 245-301 行）**

删除整个 `async function streamChat(text: string) { ... }` 函数。

- [ ] **Step 2: 删除 `streamAgentAnalyze()` 函数（第 303-355 行）**

删除整个 `async function streamAgentAnalyze(agentId: string, stockCode: string) { ... }` 函数。

- [ ] **Step 3: 添加新的 `streamAgentChat()` 函数**

在 `async function sendQuickAction` 之前添加：

```typescript
interface AgentChatParams {
  message: string
  agent_id?: string
  stock_code?: string
  history?: Array<{ role: string; content: string }>
  provider?: string
}

async function streamAgentChat(params: AgentChatParams) {
  const msgIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '', time: getTime() })
  scrollToBottom()

  try {
    const response = await fetch('/api/v1/ai/agent-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })

    if (!response.ok || !response.body) {
      messages.value[msgIndex].content = '请求失败，请稍后重试'
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const evt = JSON.parse(line.slice(6))
          if (evt.type === 'content' && evt.data) {
            messages.value[msgIndex].content += evt.data
            scrollToBottom()
          } else if (evt.type === 'error' && evt.data) {
            messages.value[msgIndex].content = `错误：${evt.data}`
          }
        } catch {
          // 忽略不完整 SSE 行
        }
      }
    }

    if (!messages.value[msgIndex].content) {
      messages.value[msgIndex].content = '抱歉，AI助手暂时无法回复'
    }
  } catch (e: any) {
    messages.value[msgIndex].content = `请求失败: ${e.message || '请稍后重试'}`
  } finally {
    loading.value = false
    scrollToBottom()
  }
}
```

- [ ] **Step 4: 替换 `handleSend()` 函数（第 225-243 行）**

用以下内容替换整个 `handleSend` 函数：

```typescript
async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text, time: getTime() })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  const history = messages.value
    .slice(0, -1)   // 排除刚推入的用户消息
    .slice(-10)
    .map(m => ({ role: m.role, content: m.content }))

  await streamAgentChat({
    message: text,
    agent_id: selectedAgent.value || undefined,
    stock_code: stockContext.value || undefined,
    history,
    provider: selectedProvider.value || undefined,
  })
}
```

- [ ] **Step 5: 确认 TypeScript 无错误**

```bash
cd AutoStockCollector-web
npx tsc --noEmit
```
期望：无输出（零错误）

- [ ] **Step 6: 手动验证核心流程**

1. 打开 AI 助手（无股票上下文）→ 发送"你好" → 收到流式回复 ✓
2. 访问 `/stock-detail?code=sh600000` → 打开 AI 助手 → 选择"技术分析师" → 发送"分析一下" → 确认回复中包含均线/K线相关内容（不是"暂无数据"）✓
3. 切换 agent 到"基本面分析师" → 发送"基本面如何" → 确认回复包含 PE/ROE 数据 ✓
4. 发送多条消息，确认历史正确保留 ✓

- [ ] **Step 7: Commit**

```bash
cd AutoStockCollector-web
git add src/components/AIChatFloat/index.vue
git commit -m "feat: AIChatFloat - replace dual routing with unified streamAgentChat()"
```

---

## Task 4：前端 — 动态快捷操作

**Files:**
- Modify: `AutoStockCollector-web/src/components/AIChatFloat/index.vue`

- [ ] **Step 1: 将静态 `quickActions` 替换为 computed**

将当前第 160-164 行（`const quickActions = [...]`）替换为：

```typescript
const quickActions = computed(() => {
  if (stockContext.value) {
    return [
      { label: 'K线走势', prompt: '分析最近的K线走势和关键技术信号' },
      { label: '资金动向', prompt: '分析主力资金流入流出情况' },
      { label: '基本面', prompt: '评估基本面质量和当前估值水平' },
      { label: '风险提示', prompt: '有哪些值得关注的投资风险？' },
    ]
  }
  return [
    { label: '大盘分析', prompt: '分析一下今天的大盘走势' },
    { label: '选股推荐', prompt: '帮我推荐几只值得关注的股票' },
    { label: '风险提示', prompt: '当前市场有什么风险需要注意？' },
  ]
})
```

- [ ] **Step 2: 确认模板中 `quickActions` 遍历无需改动**

模板中已经是 `v-for="action in quickActions"`，computed 返回数组，无需改动模板。

- [ ] **Step 3: 手动验证**

1. 无股票上下文：快捷按钮显示"大盘分析 / 选股推荐 / 风险提示" ✓
2. 访问 `/stock-detail?code=sh600000`：按钮切换为"K线走势 / 资金动向 / 基本面 / 风险提示" ✓
3. 清空上下文标签：按钮恢复为通用 3 个 ✓

- [ ] **Step 4: TypeScript 检查**

```bash
cd AutoStockCollector-web
npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
cd AutoStockCollector-web
git add src/components/AIChatFloat/index.vue
git commit -m "feat: AIChatFloat - dynamic quick actions based on stock context"
```

---

## Task 5：端到端集成验证

**Files:** 无代码修改，仅验证

- [ ] **Step 1: 重启后端**

```bash
pkill -f "python3 main.py" 2>/dev/null
cd AutoStockCollector-manage && python3 main.py &
sleep 4
curl -s http://localhost:5555/health
# 期望：{"status": "ok", ...}
```

- [ ] **Step 2: 验证端点基础功能**

```bash
# 纯聊天（无 agent、无股票）
curl -s -X POST http://localhost:5555/api/v1/ai/agent-chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"请用一句话介绍自己"}' | grep -o '"type":"[^"]*"' | head -5
# 期望出现: "type":"context"  "type":"content"  "type":"done"

# 带股票上下文 + 技术分析师
curl -s -X POST http://localhost:5555/api/v1/ai/agent-chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"分析一下","agent_id":"technical_analyst","stock_code":"sh600000"}' \
  | grep -o '"type":"[^"]*"' | head -5

# 缺少 message
curl -s -X POST http://localhost:5555/api/v1/ai/agent-chat \
  -H 'Content-Type: application/json' -d '{}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['success'] is False; print('OK: 400 validated')"
```

- [ ] **Step 3: 浏览器全流程测试**

启动前端（如需）：
```bash
cd AutoStockCollector-web && pnpm dev &
```

测试路径：
1. 访问 `http://localhost:5173/stock-detail?code=sh600000`
2. 右下角出现 AI助手 按钮 → 点击打开
3. Toolbar 显示绿色"浦发银行"标签
4. 快捷按钮为：K线走势 / 资金动向 / 基本面 / 风险提示
5. 选择"技术分析师" → 点击"K线走势" → 等待流式回复 → 确认内容包含均线/K线数据（不是"暂无数据"）
6. 切换"基本面分析师" → 点击"基本面" → 确认包含 PE/ROE 数据
7. 点击标签上的 × → 标签消失 → 快捷按钮变为通用 3 个
8. 发送"你好" → 普通聊天模式正常回复
9. 连续发 3 条消息 → 确认多轮对话历史正确保留

- [ ] **Step 4: 运行全部后端单元测试确认无回归**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -20
```
期望：所有原有测试仍通过，`test_agent_chat.py` 新增 4 个通过。
