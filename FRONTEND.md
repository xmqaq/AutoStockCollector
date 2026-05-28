# AutoStockCollector 前端项目文档

> 适用版本：AutoStockCollector-web（Vue3 重写版）  
> 后端服务：AutoStockCollector-manage，Flask，端口 5555  
> 数据范围：A股历史数据，当前已采集 2026-01-01 ~ 2026-05-28

---

## 一、项目定位

前端是 AutoStockCollector 量化系统的可视化交互入口，核心目标：

1. **可视化展示** 8 类已采集的 A 股历史数据
2. **管控采集任务** 的启动、进度监控、失败重试
3. **触发 AI 分析与策略回测** 并展示结果
4. **管理自选股** 分组与优先级

定位是**个人量化研究工具**，不是实盘交易系统，无需实时行情、无需账户体系。

---

## 二、技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| 框架 | Vue 3 + TypeScript | 组合式 API，类型安全 |
| 构建 | Vite 5 | 开发代理指向 localhost:5555 |
| UI 组件 | Element Plus | 适配数据表格、表单场景 |
| 图表 | ECharts 5 | K线、折线、热力图、仪表盘 |
| HTTP | Axios | 统一封装拦截器 |
| 路由 | Vue Router 4 | |
| 状态 | Pinia | 轻量，适配任务进度全局状态 |
| 时间 | Day.js | |
| 包管理 | pnpm | Node.js 18+ |

### 初始化

```bash
pnpm create vite AutoStockCollector-web --template vue-ts
cd AutoStockCollector-web
pnpm add element-plus @element-plus/icons-vue echarts vue-echarts axios vue-router pinia dayjs
pnpm add -D @types/node unplugin-auto-import unplugin-vue-components
```

### vite.config.ts 代理

```ts
server: {
  port: 5173,
  proxy: {
    '/api': 'http://localhost:5555',
    '/health': 'http://localhost:5555'
  }
}
```

---

## 三、项目结构

```
AutoStockCollector-web/
├── src/
│   ├── api/                  # 接口请求封装
│   │   ├── client.ts         # axios 实例 + 拦截器
│   │   ├── collect.ts        # 采集任务接口
│   │   ├── kline.ts
│   │   ├── stock.ts
│   │   ├── financial.ts
│   │   ├── news.ts
│   │   ├── fundFlow.ts
│   │   ├── dragonTiger.ts
│   │   ├── margin.ts
│   │   ├── sector.ts
│   │   ├── watchlist.ts
│   │   ├── strategy.ts
│   │   ├── backtest.ts
│   │   └── ai.ts
│   ├── components/
│   │   ├── KlineChart/       # ECharts K线图（含技术指标）
│   │   ├── ProgressTable/    # 8类任务进度表格
│   │   └── StockSearch/      # 股票代码搜索输入框
│   ├── views/
│   │   ├── Dashboard/        # 系统总览
│   │   ├── DataMonitor/      # 采集任务监控
│   │   ├── StockDetail/      # 股票详情（K线+财务+资金+新闻）
│   │   ├── DragonTiger/      # 龙虎榜
│   │   ├── MarginTrading/    # 融资融券
│   │   ├── SectorFlow/       # 板块资金流向
│   │   ├── News/             # 新闻舆情
│   │   ├── AIAnalysis/       # AI智能分析
│   │   ├── StrategyBack/     # 策略回测
│   │   └── Watchlist/        # 自选股管理
│   ├── router/index.ts
│   ├── stores/
│   │   └── collectStore.ts   # 采集进度全局状态
│   ├── types/index.ts        # 所有 TS 类型定义
│   ├── utils/
│   │   ├── stockCode.ts      # 股票代码格式转换
│   │   └── format.ts         # 数字/金额/日期格式化
│   └── layouts/
│       └── MainLayout.vue    # 左侧导航 + 顶部栏
```

---

## 四、路由与导航

左侧固定导航栏，整体深色主题。

| 菜单 | 路径 | 优先级 |
|------|------|--------|
| 系统总览 | `/` | P0 |
| 采集监控 | `/monitor` | P0 |
| 股票详情 | `/stock/:code` | P0 |
| AI 分析 | `/ai` | P1 |
| 策略回测 | `/backtest` | P1 |
| 龙虎榜 | `/dragon-tiger` | P1 |
| 融资融券 | `/margin` | P1 |
| 板块流向 | `/sector` | P1 |
| 新闻舆情 | `/news` | P1 |
| 自选股 | `/watchlist` | P2 |

---

## 五、功能模块详细需求

### 5.1 系统总览（Dashboard） — P0

**指标卡片（4张）：**

| 卡片 | 数据来源 |
|------|---------|
| 后端服务状态（在线/离线） | `GET /health` |
| 数据采集完成度（X/8 类） | `GET /api/v1/collect/progress_all` |
| 累计采集成功条数 | 同上，汇总 success 字段 |
| 最新新闻条数 | `GET /api/v1/news?limit=1` 的 count |

**8类采集状态表格：**  
调用 `GET /api/v1/collect/progress_all`，展示每类数据的状态徽章、进度条、成功/失败条数、耗时。  
状态颜色：completed=绿，running=蓝（动画），pending=灰，failed=红，cancelled=橙。

**最新新闻（右侧列表）：**  
`GET /api/v1/news?limit=10`，按时间倒序，点击跳转原文链接。

---

### 5.2 采集任务监控（DataMonitor） — P0

每 3 秒自动轮询 `GET /api/v1/collect/progress_all`。

**总进度仪表盘：** ECharts gauge，显示整体完成百分比。

**任务进度表格：** 8 行，每行含进度条（Element Plus Progress）、状态、成功/失败/耗时。

**操作区：**
- 「启动采集」→ Modal 弹窗，DatePicker 填写日期范围（`start_date`/`end_date`），可选勾选具体类型，提交调用 `POST /api/v1/collect/history`
- 「清空数据库」→ 二次确认弹窗，调用 `POST /api/v1/db/clear`（危险操作，红色按钮）

**任务历史列表：**  
`GET /api/v1/tasks?limit=50`，表格展示所有历史任务，支持按状态筛选，单条任务支持重试（`POST /api/v1/task/:id/retry`）和取消（`POST /api/v1/task/:id/cancel`）。

`all_done: true` 时顶部展示绿色横幅。

---

### 5.3 股票详情页（StockDetail） — P0

顶部搜索框，输入代码自动补全 SH/SZ 前缀（见第七节规范）。

**基础信息卡片：**  
`GET /api/v1/stock/:code/info` — 名称、代码、市场、上市日期、总股本、所属行业。

**K线主图：**  
`GET /api/v1/kline/:code?start_date=&end_date=`

- ECharts candlestick + 成交量柱（上下分区 7:3）
- 上涨红 `#ef5350`，下跌绿 `#26a69a`（A股配色）
- dataZoom 缩放，DatePicker.RangePicker 切换区间
- Tooltip：日期、开/高/低/收、成交量、涨跌幅%
- **技术指标叠加（可选显示）：MA5/MA10/MA20 均线**
- 支持前复权/后复权/不复权切换（adjust 参数：qfq/hfq/none）

> ⚠️ 不支持分时图（后端只有日线数据），不支持盘口（无 Level 2 数据）

K线数据字段：

```ts
interface KlineRecord {
  code: string
  date: string        // "2026-01-02"
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number      // 成交额（元）
  change_rate: number // 涨跌幅 %
  turnover_rate: number // 换手率 %
}
```

**财务数据：**  
`GET /api/v1/financial/:code` — 按报告期倒序表格，字段：报告期、营业收入、净利润、每股收益、ROE、净资产。

**资金流向：**  
`GET /api/v1/fund-flow/:code` — 大单流向数据展示。

**相关新闻：**  
`GET /api/v1/news?code=:code&limit=20` — 时间倒序列表。  
> ⚠️ AKShare API 限制每只股票最多返回 10 条，正常现象。

---

### 5.4 龙虎榜（DragonTiger） — P1

`GET /api/v1/dragon_tiger?start_date=&end_date=&code=&limit=100`

- 日期范围筛选（默认最近 30 天）+ 股票代码可选筛选
- 表格：代码、名称、日期、上榜原因、总成交额、净买入额
- 点击行跳转股票详情页

字段：

```ts
interface DragonTigerRecord {
  code: string
  name: string
  date: string
  reason: string
  total_amount: number
  net_buy: number
}
```

---

### 5.5 融资融券（MarginTrading） — P1

`GET /api/v1/margin?start_date=&end_date=&code=&limit=100`

- 日期范围筛选 + 股票代码可选筛选
- 融资余额趋势折线图（ECharts line，按日期排序）
- 表格：代码、日期、融资余额、融资买入额、融券余量、融券卖出量

字段：

```ts
interface MarginRecord {
  code: string
  date: string
  rz_balance: number   // 融资余额
  rz_buy: number       // 融资买入额
  rq_volume: number    // 融券余量
  rq_sell: number      // 融券卖出量
}
```

---

### 5.6 板块资金流向（SectorFlow） — P1

`GET /api/v1/sector` + `GET /api/v1/sector/:name/stocks`

- 板块热力 treemap（ECharts treemap），净流入红，净流出绿
- 点击板块展开该板块成分股列表（涨跌幅 + 净流向）

字段：

```ts
interface SectorRecord {
  name: string
  type: string
  net_flow: number
  change_rate: number
}
```

---

### 5.7 新闻舆情（News） — P1

`GET /api/v1/news?limit=100&code=`

- 股票代码筛选（可选）
- 列表展示：标题、发布时间、来源、摘要（折叠）
- 点击跳转原文链接

> ⚠️ 每只股票最多 10 条，这是 AKShare API 上限，非 bug。

---

### 5.8 AI 智能分析（AIAnalysis） — P1

`POST /api/v1/ai/analyze` — body: `{ code, type }`

- 输入股票代码，选择分析类型（comprehensive/technical/fundamental）
- 展示 AI 评分（0-100）、研判结论、核心逻辑、风险提示
- 支持导出分析报告（前端生成 Markdown/PDF）
- 结果本地缓存（Pinia + localStorage），避免重复请求

> ⚠️ 目前后端 AI 为单模型分析，不支持多模型并行对比

---

### 5.9 策略回测（StrategyBack） — P1

`GET /api/v1/strategy/list` + `POST /api/v1/backtest`

- 策略模板列表展示（调 strategy/list）
- 回测参数配置：时间区间、初始资金、股票代码列表、止损止盈比例
- 提交回测调 `POST /api/v1/backtest`
- 结果展示：总收益率、年化收益率、最大回撤、胜率、夏普比率
- ECharts 折线图展示收益曲线与回撤曲线

---

### 5.10 自选股管理（Watchlist） — P2

| 操作 | 接口 |
|------|------|
| 查询自选股列表 | `GET /api/v1/watchlist?user_id=default` |
| 添加自选股 | `POST /api/v1/watchlist` |
| 删除自选股 | `DELETE /api/v1/watchlist/:code` |
| 查询分组 | `GET /api/v1/watchlist/groups` |

- 标的增删、分组管理
- 点击股票跳转详情页
- 支持对自选股批量触发 AI 分析

---

## 六、后端 API 完整清单

```
# 基础
GET  /health

# 任务管理
GET  /api/v1/tasks                    ?status=&limit=
POST /api/v1/task/create
GET  /api/v1/task/:id
POST /api/v1/task/:id/start
POST /api/v1/task/:id/cancel
POST /api/v1/task/:id/retry
GET  /api/v1/scheduler/stats

# 采集控制
POST /api/v1/collect/history          {start_date, end_date, task_types?}
GET  /api/v1/collect/progress_all
POST /api/v1/db/clear                 {collections?}

# K线
GET  /api/v1/kline/:code              ?start_date=&end_date=
GET  /api/v1/kline/:code/latest

# 股票信息
GET  /api/v1/stock/:code/info

# 财务
GET  /api/v1/financial/:code          ?report_date=

# 新闻
GET  /api/v1/news                     ?code=&limit=

# 资金流向
GET  /api/v1/fund-flow/:code

# 龙虎榜
GET  /api/v1/dragon_tiger             ?start_date=&end_date=&code=&limit=

# 融资融券
GET  /api/v1/margin                   ?start_date=&end_date=&code=&limit=

# 板块
GET  /api/v1/sector
GET  /api/v1/sector/:name/stocks

# 自选股
GET  /api/v1/watchlist                ?user_id=&group_id=
POST /api/v1/watchlist
DELETE /api/v1/watchlist/:code
GET  /api/v1/watchlist/groups

# 策略与回测
GET  /api/v1/strategy/list
POST /api/v1/strategy/:name/run
POST /api/v1/backtest

# AI 分析
POST /api/v1/ai/analyze               {code, type}

# 数据校验
POST /api/v1/validation/:data_type
GET  /api/v1/validation/report
GET  /api/v1/validation/gaps
```

---

## 七、通用开发规范

### 股票代码格式

后端使用 `SH{6位}` / `SZ{6位}` 格式，前端输入框自动转换：

```ts
// src/utils/stockCode.ts
export function normalizeCode(input: string): string {
  const digits = input.replace(/\D/g, '')
  if (digits.length !== 6) return input.toUpperCase()
  if (digits.startsWith('6')) return `SH${digits}`
  if (digits.startsWith('0') || digits.startsWith('3')) return `SZ${digits}`
  return input.toUpperCase()
}
```

### 数字格式化

```ts
// src/utils/format.ts
export const RISE_COLOR = '#ef5350'   // 上涨红（A股）
export const FALL_COLOR = '#26a69a'   // 下跌绿（A股）
export const FLAT_COLOR = '#9e9e9e'

export function fmtAmount(n: number): string {
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return n.toLocaleString()
}

export function fmtChange(rate: number): string {
  const sign = rate >= 0 ? '+' : ''
  return `${sign}${rate.toFixed(2)}%`
}
```

### API 响应格式

后端统一返回格式：

```ts
interface ApiResponse<T> {
  success: boolean
  data?: T
  count?: number
  error?: string
  timestamp: string
}
```

### 异常处理

- 接口 `success: false` 时 Element Plus Message 全局提示
- 网络超时/断开时显示"后端服务未启动"提示，不崩溃
- 数据为空时显示 Empty 空态组件，不显示报错

---

## 八、已知数据限制（开发时需注意）

| 限制 | 说明 |
|------|------|
| 新闻条数上限 | 每只股票最多 10 条，AKShare API 限制，无法突破 |
| 无分时图数据 | 后端只采集日线，不要开发分时图功能 |
| 无盘口数据 | 无 Level 2 行情，不要开发盘口深度功能 |
| 无实时行情 | 历史数据最新到采集日期，无实时价格推送 |
| 无大宗交易 | 该类数据未采集 |
| 板块数据为快照 | sector 是采集时的快照，非实时 |

---

## 九、开发优先级

| 阶段 | 页面 | 说明 |
|------|------|------|
| P0（先做） | Dashboard、DataMonitor、StockDetail | 核心路径，后端接口全部就绪 |
| P1（次之） | AIAnalysis、StrategyBack、DragonTiger、Margin、SectorFlow、News | 需要对应查询接口已就绪 |
| P2（最后） | Watchlist | 功能完整但优先级低 |

---

## 十、部署

### 开发启动

```bash
cd AutoStockCollector-web
pnpm install
pnpm dev          # 访问 http://localhost:5173
```

### 生产构建

```bash
pnpm build        # 输出 dist/
# 用 Nginx 托管 dist/，配置 /api 反向代理到 Flask:5555
```

### 免责声明

系统所有 AI 分析结论、选股策略、回测结果**仅用于量化技术研究与数据参考，不构成任何投资建议**，用户需自行承担交易风险。前台页面需在显眼位置永久展示此声明。
