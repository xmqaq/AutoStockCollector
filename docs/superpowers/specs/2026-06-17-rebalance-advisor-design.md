# 再平衡建议（Rebalance Advisor）设计

日期：2026-06-17
状态：已批准，待实现计划

## 目标

根据用户当前持仓和可用资金，把量化选股产出的"目标组合"换算成具体的买/卖订单清单，用户可逐条或一键执行（写入模拟盘 paper_trading）。

## 关键决策（已与用户确认）

| 维度 | 选择 |
|------|------|
| 判断逻辑 | 目标组合再平衡（diff 现持仓 vs 目标组合），**不**走逐票止盈止损信号 |
| 换手控制 | 缓冲带阈值：偏离目标 < 阈值（默认 5%）则"持有不动" |
| 执行目标 | 模拟盘 paper_trading（复用 `TradeEngine.buy()/sell()`），**不**接真实券商 |
| 一键粒度 | 逐条确认为主，顶部"全部执行"可全选 |

## 复用现状（不重建）

`strategy_pick` 流水线（`api/routes/strategy_pick.py`）跑完已存入结果：
- `picks` — 入选股的 `composite` 评分、`industry`、维度分。**无现价。**
- `trade_signals` — `_generate_trade_signals()` 产出的定性动作（买入/加仓/持有/减仓/卖出），**无股数**。
- `portfolio_suggestion` — `_build_portfolio_suggestion()` 产出的 top5 **目标权重**（评分加权 + 行业分散），**无股数/金额**。

执行通道现成：`POST /paper/trade`（`api/routes/paper_trading.py:102`）已支持 buy/sell。
实时行情现成：`TradeEngine._batch_tencent_quotes(codes)` 一次拉多只现价。
持仓/现金现成：`TradeEngine.get_positions(uid)`、`PaperAccount.get(uid)`。

**缺口仅三块**：权重→股数换算、缓冲带、把订单接到执行通道。

## 架构

### ① Advisor 函数（新增，纯计算可单测）

文件：`modules/ai_selector/advisor.py`

```
build_rebalance_orders(
    target_positions,   # portfolio_suggestion.positions: [{code,name,weight(%),composite,industry}]
    current_positions,  # get_positions(uid): [{code,name,shares,current_price,market_value}]
    cash,               # account.cash_balance
    prices,             # {code: live_price}（调用方用 _batch_tencent_quotes 拉好传入）
    buffer=0.05,
) -> List[Order]
```

算法：
1. 净值 `total_value = cash + Σ(持仓 market_value)`
2. 每个目标：`目标股数 = floor(weight% × total_value / price / 100) × 100`（A股 100 股整数倍）
3. 持有但不在目标集合 → 清仓卖出（全部 shares）
4. `diff = 目标股数 − 当前股数`
   - `|diff × price| / total_value < buffer` → 持有不动（不产出订单）
   - `diff > 0` → 买入 `diff` 股
   - `diff < 0` → 卖出 `|diff|` 股
5. 资金校验：先排卖单（释放现金），再按 `composite` 高→低排买单；累加买入成本（含 `_fees()` 佣金口径），现金不足时跳过剩余低优先级买单，并在被跳过订单上标注原因。

订单结构：
```
{code, name, action: "buy"|"sell", shares, price,
 target_weight, current_weight, reason, skipped: bool, skip_reason?}
```

无价格（停牌/接口失败）的目标：跳过并标注，不阻断其余订单。

### ② 只读接口（新增）

`GET /strategy-pick/rebalance-advice?buffer=0.05`
- 读最新选股结果的 `portfolio_suggestion`
- 实时取 `get_positions(uid)` + `account.get(uid).cash_balance`
- 用 `_batch_tencent_quotes` 拉目标+持仓全部现价
- 调 `build_rebalance_orders` 返回订单清单 + `total_value`、`buffer`
- **必须实时计算**，不在选股时冻结（现金/股价时刻在变）

### ③ 执行（复用，后端不新增）

- 逐条：前端每行 `执行` 调现成 `POST /paper/trade`（`{code,action,shares,price,ai_signal}`）
- 全部：前端按"先卖后买"顺序循环调 `/paper/trade`（先卖释放现金才够买）

### ④ 前端

选股结果页新增"再平衡建议"面板：
- 订单表格：动作、代码/名称、股数、现价、目标权重/当前权重、reason、被跳过标注
- 每行 `执行` 按钮 + 顶部 `全部执行`
- 执行后刷新持仓/现金

## 数据流

```
最新选股结果.portfolio_suggestion(目标权重)
        +
get_positions(uid)(当前持仓) + account.cash(现金) + _batch_tencent_quotes(现价)
        ↓
build_rebalance_orders(buffer)  ── 缓冲带过滤 + 资金校验
        ↓
订单清单 → 前端表格 → 逐条/全部 → POST /paper/trade → TradeEngine.buy/sell
```

## 错误处理

- 无选股结果：接口返回空清单 + 提示"先跑选股"
- 账户未初始化：沿用 `buy/sell` 现有 `ValueError`，前端提示设置初始资金
- 单只取价失败：该订单跳过并标注，不影响整体
- 现金不足：买单按优先级跳过并标注（非异常）

## 测试

`build_rebalance_orders` 留一个 assert 自检（`__main__` 或 `test_advisor.py`），覆盖：
- 缓冲带抑制小额调仓
- 持有但不在目标 → 清仓
- 欠配 → 买入正确股数（100 整数倍）
- 现金不足 → 低优先级买单被跳过

## 范围外（YAGNI / 二期）

- 逐票止盈止损/风控信号混入（另一条逻辑，需要再加）
- 真实券商下单（零风险先验证再平衡逻辑）
- 缓冲带做进平台配置页（先用接口参数）
