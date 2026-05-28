# AutoStockCollector 前端项目文档

> 本文档描述基于现有后端 API（Flask + MongoDB，端口 5555）构建前端数据展示系统的完整规划。

---

## 一、项目背景

后端已完成 8 类 A 股历史数据的采集与存储：

| 数据类型 | MongoDB 集合 | 说明 |
|----------|-------------|------|
| K线数据 | kline | 日线 OHLCV，前复权 |
| 股票基础信息 | stock_info | 名称、市场、行业等 |
| 财务数据 | financial | 按报告期，同花顺数据源 |
| 新闻舆情 | news | 每股最多 10 条（API 上限） |
| 资金流向 | fund_flow | 大单成交明细 |
| 龙虎榜 | dragon_tiger | 按日期范围，东方财富数据源 |
| 板块数据 | block | 板块资金流向 |
| 融资融券 | margin_data | 按日期，交易所数据源 |

后端共 38 个 API 端点，服务地址 `http://localhost:5555`，前缀 `/api/v1`。

---

## 二、技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| 框架 | React 18 + TypeScript | |
| 构建 | Vite | 开发代理指向 localhost:5555 |
| UI 组件 | Ant Design 5.x | 暗色主题 |
| 图表 | ECharts 5.x + echarts-for-react | K线、折线、热力图 |
| HTTP | axios | 统一封装拦截器 |
| 路由 | React Router v6 | |
| 状态 | Zustand | 轻量，不用 Redux |
| 样式 | CSS Modules + Ant Design Token | |
| 包管理 | pnpm | |

### 初始化命令

```bash
pnpm create vite frontend --template react-ts
cd frontend
pnpm add antd @ant-design/icons echarts echarts-for-react axios react-router-dom zustand dayjs
pnpm add -D @types/react @types/react-dom
```

### vite.config.ts 代理配置

```ts
server: {
  proxy: {
    '/api': 'http://localhost:5555',
    '/health': 'http://localhost:5555'
  }
}
```

---

## 三、项目结构

```
frontend/
├── src/
│   ├── api/                # 接口请求封装
│   │   ├── client.ts       # axios 实例
│   │   ├── kline.ts
│   │   ├── stock.ts
│   │   ├── financial.ts
│   │   ├── news.ts
│   │   ├── fundFlow.ts
│   │   ├── dragonTiger.ts
│   │   ├── margin.ts
│   │   ├── sector.ts
│   │   └── collect.ts
│   ├── components/
│   │   ├── KlineChart/     # ECharts K线图封装
│   │   ├── ProgressTable/  # 采集进度表格
│   │   └── StockSearch/    # 股票代码搜索框
│   ├── pages/
│   │   ├── Dashboard/      # 总览仪表盘
│   │   ├── StockDetail/    # 股票详情（K线+财务+新闻）
│   │   ├── DataMonitor/    # 采集任务监控
│   │   ├── DragonTiger/    # 龙虎榜
│   │   ├── MarginTrading/  # 融资融券
│   │   ├── SectorFlow/     # 板块资金流向
│   │   └── News/           # 新闻舆情
│   ├── stores/
│   │   └── collectStore.ts # 采集进度全局状态
│   ├── types/
│   │   └── index.ts        # 所有接口 TS 类型定义
│   └── utils/
│       └── stockCode.ts    # 股票代码格式转换工具
```

---

## 四、路由与导航

左侧固定导航栏（宽 220px），整体深色主题（背景 `#141414`）。

| 菜单项 | 路径 | 对应页面 |
|--------|------|---------|
| 总览仪表盘 | `/` | Dashboard |
| 股票详情 | `/stock/:code` | StockDetail |
| 龙虎榜 | `/dragon-tiger` | DragonTiger |
| 资金流向 | `/fund-flow` | FundFlow |
| 融资融券 | `/margin` | MarginTrading |
| 板块数据 | `/sector` | SectorFlow |
| 新闻舆情 | `/news` | News |
| 采集监控 | `/monitor` | DataMonitor |

---

## 五、页面详细需求

### 5.1 总览仪表盘（`/`）

**指标卡片（4张）：**
- 数据采集完成度：`completed_types / 8`（来自 `GET /api/v1/collect/progress_all`）
- 龙虎榜记录数：取最近一次龙虎榜任务的 success 字段
- 最新新闻条数：`GET /api/v1/news?limit=1` 的 count
- 后端服务状态：`GET /health` 在线/离线

**8类数据采集状态表格：**
调用 `GET /api/v1/collect/progress_all`，展示每类数据的状态、进度条、成功/失败条数、耗时。

**最新新闻列表（右侧）：**
调用 `GET /api/v1/news?limit=10`，按时间倒序，点击跳转原文。

---

### 5.2 股票详情页（`/stock/:code`）

顶部搜索框支持输入纯数字代码（自动补全 SH/SZ 前缀）。

**基础信息卡片：**
`GET /api/v1/stock/:code/info` — 股票名称、代码、所属市场、上市日期、总股本、所属行业

**K线主图：**
`GET /api/v1/kline/:code?start_date=&end_date=`

- ECharts `candlestick` + 成交量柱状图（上下分区比例 7:3）
- 上涨红色 `#ef5350`，下跌绿色 `#26a69a`（A股配色）
- 支持 dataZoom 缩放
- 顶部 DatePicker.RangePicker 切换日期范围
- Tooltip 显示：日期、开/高/低/收、成交量、涨跌幅

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
  amount: number      // 成交额
  change_rate: number // 涨跌幅 %
}
```

**财务数据表格：**
`GET /api/v1/financial/:code` — 按报告期倒序：报告期、营业收入、净利润、每股收益、ROE、净资产

**资金流向：**
`GET /api/v1/fund-flow/:code` — 最新大单数据展示

**相关新闻：**
`GET /api/v1/news?code=:code&limit=20` — 时间倒序列表

---

### 5.3 采集监控页（`/monitor`）

每 3 秒自动轮询 `GET /api/v1/collect/progress_all`。

**顶部：** ECharts gauge 仪表盘，显示整体完成百分比

**中部：** 8 类任务进度表格

| 字段 | 组件 |
|------|------|
| 数据类型 | 文字（中文） |
| 状态 | Ant Design Badge（颜色见下表） |
| 进度 | Ant Design Progress 进度条 |
| 成功/失败 | 数字 |
| 耗时 | HH:MM:SS 格式 |

状态颜色：
```
completed → success（绿）
running   → processing（蓝，动态闪烁）
pending   → default（灰）
failed    → error（红）
cancelled → warning（橙）
```

**底部操作区：**
- 「启动采集」按钮 → Modal 弹窗，DatePicker 填写日期范围，提交调用 `POST /api/v1/collect/history`
- 「清空数据库」按钮 → 二次确认弹窗（危险操作），调用 `POST /api/v1/db/clear`

当 `all_done: true` 时，顶部展示绿色横幅"🎉 所有 8 类数据采集完成"。

---

### 5.4 龙虎榜页（`/dragon-tiger`）

> ⚠️ 依赖后端新增查询接口（见第六节）

- 日期范围筛选（默认最近 30 天）+ 股票代码筛选
- 表格：代码、名称、日期、上榜原因、总成交额、净买入额
- 点击行跳转股票详情页

---

### 5.5 融资融券页（`/margin`）

> ⚠️ 依赖后端新增查询接口（见第六节）

- 日期范围筛选
- 融资余额趋势折线图（ECharts line）
- 表格：代码、日期、融资余额、融资买入额、融券余量、融券卖出量

---

### 5.6 板块数据页（`/sector`）

> ⚠️ 依赖后端新增查询接口（见第六节）

- 板块资金流向 treemap（ECharts treemap）
- 净流入红色，净流出绿色（A股习惯）
- 点击板块展开该板块股票列表

---

### 5.7 新闻舆情页（`/news`）

`GET /api/v1/news?limit=100`

- 支持按股票代码筛选
- 每条新闻：标题、发布时间、来源、摘要（折叠展示）
- 点击跳转原文链接

---

## 六、需后端补充的接口

以下 4 个接口当前后端未实现，前端 P2 阶段暂用 mock 数据，待后端补充后接入：

```
GET /api/v1/dragon-tiger
  query: start_date?, end_date?, code?, limit?
  返回: { success, count, data: [{code, name, date, reason, total_amount, net_buy}] }

GET /api/v1/margin
  query: start_date?, end_date?, code?, limit?
  返回: { success, count, data: [{code, date, rz_balance, rz_buy, rq_volume, rq_sell}] }

GET /api/v1/sector/list
  返回: { success, data: [{name, type, net_flow, change_rate}] }

GET /api/v1/sector/:name/stocks
  返回: { success, data: [{code, name, change_rate, net_flow}] }
```

---

## 七、通用规范

### 股票代码格式转换

```ts
// src/utils/stockCode.ts
export function normalizeCode(input: string): string {
  const digits = input.replace(/[^0-9]/g, '')
  if (digits.startsWith('6')) return `SH${digits}`
  if (digits.startsWith('0') || digits.startsWith('3')) return `SZ${digits}`
  return input.toUpperCase()
}
```

### 数字格式化

```ts
// 万/亿单位格式化
export function fmtAmount(n: number): string {
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return n.toLocaleString()
}
```

### 颜色规范（A股）

```ts
export const RISE_COLOR  = '#ef5350'  // 上涨红
export const FALL_COLOR  = '#26a69a'  // 下跌绿
export const FLAT_COLOR  = '#9e9e9e'  // 平盘灰
```

---

## 八、开发优先级

| 优先级 | 页面 | 依赖接口 | 状态 |
|--------|------|---------|------|
| P0 | 采集监控页 `/monitor` | progress_all, collect/history, db/clear | 可立即开发 |
| P0 | 股票详情 K线图 `/stock/:code` | kline, stock/info, financial, news | 可立即开发 |
| P1 | 总览仪表盘 `/` | progress_all, news | 可立即开发 |
| P1 | 新闻舆情 `/news` | news | 可立即开发 |
| P2 | 龙虎榜 `/dragon-tiger` | 待后端补充 | 先 mock |
| P2 | 融资融券 `/margin` | 待后端补充 | 先 mock |
| P2 | 板块数据 `/sector` | 待后端补充 | 先 mock |

---

## 九、现有后端 API 完整清单

```
# 健康检查
GET  /health

# 数据采集控制
POST /api/v1/collect/history          body: {start_date, end_date, task_types?}
GET  /api/v1/collect/progress_all
POST /api/v1/db/clear                 body: {collections?}

# 任务管理
GET  /api/v1/tasks                    query: {status?, limit?}
POST /api/v1/task/create
GET  /api/v1/task/:task_id
POST /api/v1/task/:task_id/start
POST /api/v1/task/:task_id/cancel
POST /api/v1/task/:task_id/retry
GET  /api/v1/scheduler/stats

# K线
GET  /api/v1/kline/:code              query: {start_date?, end_date?}
GET  /api/v1/kline/:code/latest

# 股票基础信息
GET  /api/v1/stock/:code/info
GET  /api/v1/stock/:code/indices

# 财务
GET  /api/v1/financial/:code          query: {report_date?}

# 新闻
GET  /api/v1/news                     query: {code?, limit?}

# 资金流向
GET  /api/v1/fund-flow/:code

# 指数
POST /api/v1/collect/index
GET  /api/v1/index/:index_code/components

# 自选股
GET  /api/v1/watchlist                query: {user_id?, group_id?}
POST /api/v1/watchlist
DELETE /api/v1/watchlist/:code
GET  /api/v1/watchlist/groups

# 策略 & 回测 & AI（后期集成）
GET  /api/v1/strategy/list
POST /api/v1/strategy/:name/run
POST /api/v1/backtest
POST /api/v1/ai/analyze

# 数据校验
POST /api/v1/validation/:data_type
GET  /api/v1/validation/report
GET  /api/v1/validation/gaps
```
