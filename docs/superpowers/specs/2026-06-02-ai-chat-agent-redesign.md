# AI 助手浮动对话框重构设计

**日期:** 2026-06-02  
**状态:** 已批准

---

## 背景与问题

现有 AIChatFloat 组件存在三个核心缺陷：

1. **路由脆弱**：通过正则检测用户输入是否含 6 位数字来决定调哪个接口，用户必须手动输入股票代码才能触发 agent 分析
2. **缺乏上下文感知**：聊天框不知道用户当前在查看哪只股票
3. **两条独立链路**：`/ai/chat/stream`（通用对话）与 `/ai-agents/{id}/analyze/stream`（agent 分析）割裂，逻辑重复，且后者未使用 `dal.py + factors.py` 的完整数据注入路径

---

## 方案：统一 Agent Chat 接口

### 架构

```
用户 → AIChatFloat
         ├── useRoute() 感知当前股票上下文
         ├── 选择 agent_id（可选）
         └── POST /api/v1/ai/agent-chat
                    ↓
              后端统一处理逻辑
               ├── stock_code 存在 → dal.get_stock_bundle() + factors 评分
               ├── agent_id 存在  → 加载角色 system_prompt + 按角色裁剪上下文
               ├── history 存在   → 多轮对话
               └── → LLMRouter.chat_stream() → SSE
```

---

## 后端设计

### 新接口 `POST /api/v1/ai/agent-chat`

**文件:** `AutoStockCollector-manage/api/routes/__init__.py`（追加在现有 AI 路由区块）

**请求体：**
```json
{
  "message": "帮我分析技术面",
  "agent_id": "technical_analyst",
  "stock_code": "sh600000",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "provider": "deepseek"
}
```
所有字段均可选，`message` 为必填。

**响应格式（SSE）：**
```
data: {"type": "context", "data": {"stock_name": "浦发银行", "has_data": true}}
data: {"type": "content", "data": "分析结果文字片段"}
data: {"type": "done", "data": {"content": "完整回复"}}
data: {"type": "error", "data": "错误信息"}
```

**处理流程：**

```python
def ai_agent_chat():
    # 1. 加载 agent 配置（若有 agent_id）
    agent = db.ai_agents.find_one({"id": agent_id}) or {}
    system_prompt = agent.get("system_prompt", "你是一个A股投资助手。")
    temperature = agent.get("temperature", 0.7)
    max_tokens = agent.get("max_tokens", 2000)

    # 2. 构建股票上下文（若有 stock_code）
    context_block = ""
    if stock_code:
        bundle = dal.get_stock_bundle(stock_code)          # 复用现有 dal.py
        scores = compute_scores(bundle)                     # 复用现有 factors.py
        context_block = _build_context(agent_id, bundle, scores)  # 按角色裁剪

    # 3. 构建 messages
    full_system = system_prompt
    if context_block:
        full_system += "\n\n" + context_block
    messages = [{"role": "system", "content": full_system}]
    messages += history[-10:]
    messages.append({"role": "user", "content": message})

    # 4. 流式调用
    router = LLMRouter()
    if provider:
        router.providers = [provider]
    return Response(generate_stream(router, messages, temperature, max_tokens), ...)
```

### 按角色裁剪上下文 `_build_context(agent_id, bundle, scores)`

| agent_id | 注入内容 |
|---|---|
| `technical_analyst` | closes（20日）、volumes（20日）、trend_score、volume_score、MA5/MA20 提示 |
| `fund_analyst` | volumes（10日）、main_net_inflow、fund_flow_score |
| `fundamental_analyst` | PE/PB/ROE/毛利率/负债率/营收增速/净利润增速、valuation_score |
| `sentiment_analyst` | 最近 5 条新闻标题 + 发布时间 |
| `market_analyst` | closes/volumes（10日）+ fund_flow + 2 条新闻标题 + 综合评分 |
| `risk_analyst` | 全量数据 + 所有分项评分 |
| *(无 agent_id)* | 不注入数据，纯对话 |

### 复用的现有模块（不修改）

- `modules/ai/foundation/dal.py` — `get_stock_bundle(code)`
- `modules/ai/foundation/factors.py` — `trend_score`, `volume_score`, `valuation_score`, `fund_flow_score`
- `modules/ai/foundation/llm_router.py` — `LLMRouter.chat_stream()`
- `api/routes/ai_agent.py` — `/ai-agents/{id}/analyze` 接口（MultiAgent 面板继续使用）

---

## 前端设计

### 文件：`AutoStockCollector-web/src/components/AIChatFloat/index.vue`

#### 1. 上下文感知

```ts
import { useRoute } from 'vue-router'
const route = useRoute()

// 从路由 query 读取当前股票代码（/stock-detail?code=sh600000）
const stockContext = computed(() => (route.query.code as string) || '')
const stockName = ref('')  // 通过 /api/v1/stock/{code}/info 异步获取股票名

watch(stockContext, async (code) => {
  if (code) {
    const res = await stockApi.getInfo(code)
    stockName.value = res.data?.data?.name || code
  } else {
    stockName.value = ''
  }
})
```

#### 2. 单一发送函数（替换现有双路由逻辑）

```ts
// 删除：streamChat() 和 streamAgentAnalyze()
// 新增：统一发送
async function handleSend() {
  if (!inputText.value.trim()) return
  const userMsg = inputText.value.trim()
  inputText.value = ''
  messages.value.push({ role: 'user', content: userMsg, time: getTime() })
  
  await streamAgentChat({
    message: userMsg,
    agent_id: selectedAgent.value || undefined,
    stock_code: stockContext.value || undefined,
    history: messages.value.slice(-10, -1).map(m => ({role: m.role, content: m.content})),
    provider: selectedProvider.value || undefined,
  })
}

async function streamAgentChat(params: AgentChatParams) {
  // fetch('/api/v1/ai/agent-chat', ...) → SSE 解析
  // 收到 type=context 事件时更新股票名提示
  // 收到 type=content 时追加文字
  // 收到 type=done/error 时结束
}
```

#### 3. 动态快捷操作

```ts
const quickActions = computed(() => {
  if (stockContext.value) return [
    { label: 'K线走势', prompt: '分析最近的K线走势和关键技术信号' },
    { label: '资金动向', prompt: '分析主力资金流入流出情况' },
    { label: '基本面', prompt: '评估基本面质量和当前估值水平' },
    { label: '风险提示', prompt: '有哪些值得关注的投资风险？' },
  ]
  return [
    { label: '大盘分析', prompt: '分析一下今天的大盘走势' },
    { label: '选股推荐', prompt: '帮我推荐几只值得关注的股票' },
    { label: '风险提示', prompt: '当前市场有什么风险需要注意？' },
  ]
})
```

#### 4. Toolbar 上下文提示条

```html
<!-- 在 agent 选择器右侧 -->
<el-tag
  v-if="stockContext"
  size="small"
  closable
  @close="clearStockContext"
>
  {{ stockName || stockContext }}
</el-tag>
```

---

## 不改动的部分

| 模块 | 说明 |
|---|---|
| `api/routes/ai_agent.py` | MultiAgent 面板继续使用 `/ai-agents/{id}/analyze` |
| `agentStore.ts` | MultiAgent 面板逻辑不变 |
| MongoDB `ai_agents` 集合 | agent 配置完全复用 |
| `llm_router.py` / `llm_caller.py` | 底层调用层不改 |

---

## 验证方案

1. 启动后端，访问 `/stock-detail?code=sh600000`，打开 AI 助手
2. Toolbar 显示"浦发银行"上下文标签
3. 快捷操作变为股票相关 4 个按钮
4. 点击"K线走势" → POST `/api/v1/ai/agent-chat` 携带 stock_code + agent_id
5. 验证 LLM 收到的 prompt 包含真实 K 线数据（不是"暂无数据"）
6. 切换 agent 到"基本面分析师"，发送相同问题，确认注入数据切换为财务数据
7. 清空上下文标签，发送消息，确认退回纯聊天模式
8. 多轮对话：连续发 3 条消息，确认历史正确传递
