# 模拟盘交易功能设计文档

**日期：** 2026-06-02  
**状态：** 已批准

---

## 背景与目标

将现有静态持仓管理模块重构为模拟盘交易系统。用户可基于 AI 买卖建议对模拟账户资金进行操作，系统记录完整交易流水并支持回测分析（胜率、盈亏比等）。

旧的手动录入持仓数据清空，全部改用模拟交易方式建仓。

---

## 数据模型

### `paper_account`（MongoDB 集合，全局唯一一条）

```json
{
  "user_id": "default",
  "initial_capital": 100000.0,
  "cash_balance": 87500.0,
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

- `initial_capital`：用户初始化时设置，不随交易变动
- `cash_balance`：实时现金余额，每笔交易后更新

### `trade_records`（MongoDB 集合，每笔交易一条）

```json
{
  "user_id": "default",
  "code": "SH600000",
  "name": "浦发银行",
  "action": "buy | sell",
  "shares": 500,
  "price": 8.50,
  "amount": 4250.0,
  "commission": 4.25,
  "ai_signal": {
    "action": "买入",
    "reason": "...",
    "composite": 72.5
  },
  "cash_before": 91754.25,
  "cash_after": 87500.0,
  "traded_at": "ISO8601"
}
```

- `commission`：手续费，默认费率 0.1%（commission_rate = 0.001）
- `ai_signal`：触发本次交易时的 AI 建议快照，只记录关键字段
- `cash_before` / `cash_after`：用于净值曲线精确还原

### 持仓（实时聚合，不独立存储）

持仓数据不存入数据库，每次查询时从 `trade_records` 聚合计算：

- `shares_held = Σbuy.shares - Σsell.shares`（按 code 分组，过滤 shares_held > 0）
- `avg_cost`：加权平均买入成本（买入均价，卖出不影响成本）
- `pnl` / `pnl_percent`：结合当前 K 线收盘价实时计算

---

## 后端 API

所有新接口挂载在 Blueprint `/api/paper`，替换现有 `/api/position`。

### 账户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/paper/account` | 获取账户信息 |
| POST | `/api/paper/account/init` | 初始化或重置账户 |

**`POST /api/paper/account/init` 请求体：**
```json
{ "initial_capital": 100000.0 }
```
执行：清空 `trade_records`，重建 `paper_account`。

### 交易执行

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/paper/trade` | 执行模拟买入或卖出 |

**请求体：**
```json
{
  "code": "SH600000",
  "action": "buy | sell",
  "shares": 500,
  "ai_signal": { "action": "买入", "reason": "...", "composite": 72.5 }
}
```

**买入校验流程：**
1. 从 KlineStorage 获取最新收盘价作为成交价
2. 计算 `amount = shares × price`，`commission = amount × 0.001`
3. 校验 `cash_balance >= amount + commission`，不足则返回 400
4. 写入 `trade_records`，更新 `paper_account.cash_balance`

**卖出校验流程：**
1. 聚合当前持仓，校验 `shares_held >= 卖出数量`，不足则返回 400
2. 获取最新收盘价，计算 `amount = shares × price`
3. 写入 `trade_records`，更新 `cash_balance`（加回 amount - commission）

### 持仓查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/paper/positions` | 获取当前持仓列表（聚合计算） |

返回字段：code、name、shares、avg_cost、current_price、market_value、pnl、pnl_percent、position_ratio

### 数据查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/paper/trades` | 交易流水列表（支持分页，默认最近 50 条） |
| GET | `/api/paper/stats` | 回测统计 |
| GET | `/api/paper/nav` | 账户净值曲线数据 |

**`GET /api/paper/stats` 返回：**
```json
{
  "total_trades": 42,
  "win_trades": 28,
  "win_rate": 66.7,
  "avg_profit_pct": 8.3,
  "avg_loss_pct": -4.1,
  "profit_factor": 2.03,
  "total_return_pct": 23.5
}
```

胜负判定：以每笔完整买卖对（FIFO 匹配）为单位，卖出均价 > 买入均价为胜。

**`GET /api/paper/nav` 返回：**
按日期聚合，`net_value = (cash_balance + Σ持仓市值) / initial_capital`，返回时间序列数组。

---

## 前端设计

### 页面结构

`src/views/Position/index.vue` 重构为模拟盘页面，保留路由路径不变。

**顶部账户概览栏（横排）：**
- 初始资金 | 当前现金 | 持仓市值 | 账户净值 | 总收益率
- 右侧"初始化账户"按钮

**主体左侧（span=16）：持仓表**

列：代码、名称、持仓量、成本价、现价、市值、盈亏%、仓位占比、操作

操作列：
- "AI 建议"按钮 → 调用 `AdviceEngine` → 弹出确认框
- 对于有持仓的股票额外显示"手动卖出"按钮（直接填数量，不经过 AI）

**主体右侧（span=8）：四个卡片**
1. 净值曲线（折线图，数据来自 `/api/paper/nav`）
2. 回测统计（胜率、盈亏比、总收益率，来自 `/api/paper/stats`）
3. 交易流水（最近 10 条，含 AI 信号摘要）
4. 持仓分布（现有条形图逻辑保留）

### AI 确认框

**买入确认框（`action` 为买入类）：**
- 展示：股票名称、AI 理由、参考买入区间、当前价、可用现金
- 可编辑：买入数量（默认按可用现金的 20% 计算手数，最小 100 股）
- 实时显示预计金额和手续费

**卖出确认框（`action` 为减仓/卖出类）：**
- 展示：股票名称、AI 理由、当前持仓量、当前价
- 可编辑：卖出数量（默认按 `position_advice` 解析比例预填，如"减仓 50%"→ 预填持仓量的一半）
- 实时显示预计回收金额

### 新增 API 调用层

`src/api/paper.ts` 替换现有 `src/api/position.ts`，封装所有 `/api/paper/*` 接口。

---

## 文件变更范围

### 后端（新增）
- `AutoStockCollector-manage/api/routes/paper_trading.py`
- `AutoStockCollector-manage/modules/paper_trading/account.py`
- `AutoStockCollector-manage/modules/paper_trading/trade_engine.py`
- `AutoStockCollector-manage/modules/paper_trading/stats.py`

### 后端（修改）
- `AutoStockCollector-manage/api/__init__.py`：注册新 Blueprint，移除旧 position Blueprint

### 前端（修改）
- `AutoStockCollector-web/src/views/Position/index.vue`：完整重写
- `AutoStockCollector-web/src/api/position.ts`：替换为 paper.ts（或重命名内容）

### 旧文件（可删除）
- `AutoStockCollector-manage/api/routes/position.py`
- `AutoStockCollector-manage/modules/position/position_manager.py`

---

## 约束与边界

- 成交价固定使用最新 K 线收盘价，不支持限价单
- 手续费率固定 0.1%，不可配置（MVP 阶段）
- 每次买入最小单位 100 股
- 净值曲线精度：按日，不支持日内
- 不支持做空、融资等操作
- 单用户（`user_id = "default"`），不支持多账户
