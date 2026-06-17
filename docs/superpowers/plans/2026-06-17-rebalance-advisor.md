# 再平衡建议（Rebalance Advisor）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把量化选股产出的目标组合，结合当前持仓和可用资金，换算成具体的买/卖订单清单，用户可逐条或一键写入模拟盘。

**Architecture:** 新增一个纯计算 advisor 函数（权重→股数 + 缓冲带 + 资金校验），一个只读后端接口（实时读持仓/现金/行情后调 advisor），前端在选股结果页加面板调用现成 `/api/paper/trade` 执行。不重建执行/选股逻辑。

**Tech Stack:** Python(Flask, pytest), Vue3 + TypeScript, MongoDB。

## Global Constraints

- A股交易单位：买入股数必须为 100 的整数倍（`shares % 100 == 0`）。
- 费率口径必须与 `TradeEngine._fees()` 一致：`buy_commission_rate` / `sell_commission_rate` / `min_commission` / `stamp_tax_rate`，佣金 `max(min_commission, amount*rate)`，卖出额外扣 `amount*stamp_tax_rate` 印花税。
- 净值口径：`total_value = cash + Σ(持仓 market_value)`，目标权重按净值计。
- 缓冲带：`|diff股数 × price| / total_value < buffer` → 不产出订单。默认 `buffer=0.05`，走接口参数。
- 目标组合 = 最新选股结果的 `portfolio_suggestion.positions`（top5，评分加权）。持有但不在目标集合的 → 清仓卖出。
- 时间统一用 `from utils.helpers import beijing_now`。
- 前端 `strategyPick.ts` 用 `client`，`paper.ts` 用 `request`——各自沿用文件已有 import，勿混。

---

### Task 1: Advisor 纯计算函数

**Files:**
- Create: `AutoStockCollector-manage/modules/ai_selector/advisor.py`
- Test: `AutoStockCollector-manage/tests/test_advisor.py`

**Interfaces:**
- Consumes: 无（纯函数，所有数据由调用方传入）
- Produces:
  ```python
  DEFAULT_FEES = {"buy_commission_rate": 0.0003, "sell_commission_rate": 0.0003,
                  "min_commission": 5.0, "stamp_tax_rate": 0.001}

  def build_rebalance_orders(
      target_positions: list[dict],   # [{code,name,weight(0-100),composite,industry}]
      current_positions: list[dict],  # [{code,name,shares,current_price,market_value}]
      cash: float,
      prices: dict[str, float],       # {code: live_price}，目标+持仓全部
      buffer: float = 0.05,
      fees: dict | None = None,
  ) -> dict:
      # 返回 {"total_value": float, "buffer": float, "orders": [Order...]}
      # Order = {code,name,action("buy"|"sell"),shares,price,
      #          target_weight,current_weight,reason,skipped(bool),skip_reason(str|None)}
  ```

- [ ] **Step 1: 写失败测试**

```python
# AutoStockCollector-manage/tests/test_advisor.py
from modules.ai_selector.advisor import build_rebalance_orders


def _orders_by_code(result):
    return {o["code"]: o for o in result["orders"]}


def test_underweight_target_generates_buy_round_lot():
    # 净值 = cash 100000 + 持仓0 = 100000；目标 600519 权重40% → 40000；价 200 → 200股
    res = build_rebalance_orders(
        target_positions=[{"code": "600519", "name": "贵州茅台", "weight": 40.0, "composite": 80, "industry": "白酒"}],
        current_positions=[],
        cash=100000.0,
        prices={"600519": 200.0},
        buffer=0.05,
    )
    o = _orders_by_code(res)["600519"]
    assert o["action"] == "buy"
    assert o["shares"] == 200          # floor(40000/200/100)*100
    assert o["shares"] % 100 == 0
    assert o["skipped"] is False


def test_held_but_not_in_target_is_full_sell():
    res = build_rebalance_orders(
        target_positions=[],
        current_positions=[{"code": "000001", "name": "平安银行", "shares": 500,
                            "current_price": 10.0, "market_value": 5000.0}],
        cash=10000.0,
        prices={"000001": 10.0},
    )
    o = _orders_by_code(res)["000001"]
    assert o["action"] == "sell"
    assert o["shares"] == 500          # 清仓全部
    assert "未入选" in o["reason"] or "清仓" in o["reason"]


def test_buffer_suppresses_small_deviation():
    # 净值100000；目标权重10%→10000→价100→100股；已持100股(market_value 10000)
    # diff=0，且即便差1手也应被5%缓冲带吸收
    res = build_rebalance_orders(
        target_positions=[{"code": "600000", "name": "浦发", "weight": 10.0, "composite": 70, "industry": "银行"}],
        current_positions=[{"code": "600000", "name": "浦发", "shares": 100,
                            "current_price": 100.0, "market_value": 10000.0}],
        cash=90000.0,
        prices={"600000": 100.0},
        buffer=0.05,
    )
    # 持仓不动 → 不产出该票订单
    assert "600000" not in _orders_by_code(res)


def test_insufficient_cash_skips_lowest_priority_buy():
    # 现金只够买高分票，低分票应被跳过并标注
    res = build_rebalance_orders(
        target_positions=[
            {"code": "AAA", "name": "高分", "weight": 50.0, "composite": 90, "industry": "A"},
            {"code": "BBB", "name": "低分", "weight": 50.0, "composite": 60, "industry": "B"},
        ],
        current_positions=[],
        cash=12000.0,                  # 净值=12000，每个目标想要6000
        prices={"AAA": 100.0, "BBB": 100.0},
        buffer=0.0,
    )
    by = _orders_by_code(res)
    # 高分先买（6000+佣金），剩余现金不足再买低分 → 低分 skipped
    assert by["AAA"]["skipped"] is False and by["AAA"]["action"] == "buy"
    assert by["BBB"]["skipped"] is True
    assert "现金不足" in by["BBB"]["skip_reason"]


def test_no_price_target_skipped_not_crash():
    res = build_rebalance_orders(
        target_positions=[{"code": "ZZZ", "name": "停牌", "weight": 30.0, "composite": 75, "industry": "X"}],
        current_positions=[],
        cash=100000.0,
        prices={},                     # 无价
    )
    by = _orders_by_code(res)
    assert by["ZZZ"]["skipped"] is True
    assert "价格" in by["ZZZ"]["skip_reason"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd AutoStockCollector-manage && python -m pytest tests/test_advisor.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'modules.ai_selector.advisor'`

- [ ] **Step 3: 实现 advisor**

```python
# AutoStockCollector-manage/modules/ai_selector/advisor.py
"""再平衡建议：目标组合权重 + 当前持仓 + 现金 → 具体买卖订单清单。

纯计算、无 IO，所有数据由调用方传入，便于单测。
"""
from typing import Any, Dict, List, Optional
import math

DEFAULT_FEES = {
    "buy_commission_rate": 0.0003,
    "sell_commission_rate": 0.0003,
    "min_commission": 5.0,
    "stamp_tax_rate": 0.001,
}


def _buy_cost(amount: float, fees: Dict[str, float]) -> float:
    commission = max(fees["min_commission"], amount * fees["buy_commission_rate"])
    return amount + commission


def _sell_net(amount: float, fees: Dict[str, float]) -> float:
    commission = max(fees["min_commission"], amount * fees["sell_commission_rate"])
    tax = amount * fees["stamp_tax_rate"]
    return amount - commission - tax


def build_rebalance_orders(
    target_positions: List[Dict[str, Any]],
    current_positions: List[Dict[str, Any]],
    cash: float,
    prices: Dict[str, float],
    buffer: float = 0.05,
    fees: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    fees = fees or DEFAULT_FEES
    held = {p["code"]: p for p in current_positions}
    target_codes = {t["code"] for t in target_positions}

    total_value = cash + sum((p.get("market_value") or 0) for p in current_positions)

    sell_orders: List[Dict[str, Any]] = []
    buy_candidates: List[Dict[str, Any]] = []

    def _cur_weight(code: str) -> float:
        mv = (held.get(code, {}).get("market_value") or 0)
        return round(mv / total_value * 100, 2) if total_value > 0 else 0.0

    # ── 1. 持有但不在目标 → 清仓卖出 ──
    for code, hp in held.items():
        if code in target_codes:
            continue
        price = prices.get(code) or hp.get("current_price")
        sell_orders.append({
            "code": code, "name": hp.get("name", code), "action": "sell",
            "shares": hp["shares"], "price": price,
            "target_weight": 0.0, "current_weight": _cur_weight(code),
            "reason": f"未入选目标组合，清仓 {hp['shares']} 股",
            "skipped": False, "skip_reason": None,
        })

    # ── 2. 目标票：算目标股数，与现持做差（含缓冲带） ──
    for t in sorted(target_positions, key=lambda x: -(x.get("composite") or 0)):
        code = t["code"]
        price = prices.get(code)
        cur_shares = held.get(code, {}).get("shares", 0)
        cur_w = _cur_weight(code)
        if not price or price <= 0:
            buy_candidates.append({
                "code": code, "name": t.get("name", code), "action": "buy",
                "shares": 0, "price": price,
                "target_weight": t["weight"], "current_weight": cur_w,
                "reason": "无法取得实时价格", "skipped": True,
                "skip_reason": "无实时价格（停牌或行情接口失败），已跳过",
                "composite": t.get("composite") or 0,
            })
            continue

        target_value = t["weight"] / 100.0 * total_value
        target_shares = int(math.floor(target_value / price / 100) * 100)
        diff = target_shares - cur_shares

        # 缓冲带：调仓金额占净值比 < buffer → 不动
        if total_value > 0 and abs(diff) * price / total_value < buffer:
            continue
        if diff == 0:
            continue

        if diff > 0:
            buy_candidates.append({
                "code": code, "name": t.get("name", code), "action": "buy",
                "shares": diff, "price": price,
                "target_weight": t["weight"], "current_weight": cur_w,
                "reason": f"目标权重 {t['weight']}%，欠配，买入 {diff} 股",
                "skipped": False, "skip_reason": None,
                "composite": t.get("composite") or 0,
            })
        else:
            sell_orders.append({
                "code": code, "name": t.get("name", code), "action": "sell",
                "shares": -diff, "price": price,
                "target_weight": t["weight"], "current_weight": cur_w,
                "reason": f"目标权重 {t['weight']}%，超配，卖出 {-diff} 股",
                "skipped": False, "skip_reason": None,
            })

    # ── 3. 资金校验：先卖释放现金，买单按评分高→低，不够则跳过低优先级 ──
    available = cash + sum(_sell_net(o["shares"] * o["price"], fees)
                           for o in sell_orders if o["price"])
    buy_orders: List[Dict[str, Any]] = []
    for o in buy_candidates:  # 已按 composite 降序（停牌的 shares=0 不耗现金）
        if o["skipped"]:
            buy_orders.append(o)
            continue
        cost = _buy_cost(o["shares"] * o["price"], fees)
        if cost > available:
            o["skipped"] = True
            o["skip_reason"] = f"现金不足（需 {cost:.0f} 元，可用 {available:.0f} 元），已跳过"
        else:
            available -= cost
        buy_orders.append(o)

    orders = sell_orders + buy_orders
    for o in orders:
        o.pop("composite", None)
    return {"total_value": round(total_value, 2), "buffer": buffer, "orders": orders}


if __name__ == "__main__":
    # 冒烟自检
    r = build_rebalance_orders(
        [{"code": "600519", "name": "茅台", "weight": 40.0, "composite": 80, "industry": "白酒"}],
        [], 100000.0, {"600519": 200.0},
    )
    assert r["orders"][0]["shares"] == 200, r
    print("advisor self-check OK")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd AutoStockCollector-manage && python -m pytest tests/test_advisor.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
cd /Users/xiaoming/Downloads/stock
git add AutoStockCollector-manage/modules/ai_selector/advisor.py AutoStockCollector-manage/tests/test_advisor.py
git commit -m "feat(advisor): 再平衡订单纯计算函数（权重→股数+缓冲带+资金校验）"
```

---

### Task 2: 再平衡建议接口

**Files:**
- Modify: `AutoStockCollector-manage/api/routes/strategy_pick.py`（在 `get_result` 路由后追加新路由，约 `:847` 之后）

**Interfaces:**
- Consumes: `build_rebalance_orders`（Task 1）、`TradeEngine`（`get_positions`/`_batch_tencent_quotes`/`_fees`）、`PaperAccount`、`_get_result`
- Produces: `GET /api/v1/strategy-pick/rebalance-advice?buffer=0.05`
  返回 `{"success": true, "data": {"total_value", "buffer", "cash", "orders": [...]}}`

- [ ] **Step 1: 写接口**

在 `strategy_pick.py` 的 `get_result` 路由（`:843-847`）之后追加：

```python
@strategy_pick_bp.route("/rebalance-advice", methods=["GET"])
def get_rebalance_advice():
    """根据最新选股结果的目标组合 + 实时持仓/现金，生成再平衡买卖清单。"""
    from modules.ai_selector.advisor import build_rebalance_orders
    from modules.paper_trading.trade_engine import TradeEngine
    from modules.paper_trading.account import PaperAccount

    try:
        buffer = float(request.args.get("buffer", 0.05))
    except (TypeError, ValueError):
        buffer = 0.05

    # admin 映射到 default，兼容旧数据；与 paper_trading._resolve_user_id 同口径
    uid = g.current_user["user_id"] if hasattr(g, "current_user") and g.current_user else "default"
    account = PaperAccount()
    if uid == "admin" and account.get("default"):
        uid = "default"

    result = _get_result()
    targets = (result.get("portfolio_suggestion") or {}).get("positions") or []
    if not targets:
        return jsonify({"success": True, "data": {
            "total_value": 0, "buffer": buffer, "cash": 0, "orders": [],
            "message": "暂无选股结果，请先运行策略选股",
        }})

    engine = TradeEngine()
    positions, _ = engine.get_positions(uid)
    acc = account.get(uid)
    cash = acc["cash_balance"] if acc else 0.0

    codes = list({t["code"] for t in targets} | {p["code"] for p in positions})
    quotes = engine._batch_tencent_quotes(codes)
    prices = {c: (q.get("price") or 0) for c, q in quotes.items() if q.get("price")}
    # 行情接口未命中的持仓，回退到 get_positions 已算出的 current_price
    for p in positions:
        prices.setdefault(p["code"], p.get("current_price") or 0)

    advice = build_rebalance_orders(
        target_positions=targets,
        current_positions=positions,
        cash=cash,
        prices=prices,
        buffer=buffer,
        fees=engine._fees(),
    )
    advice["cash"] = round(cash, 2)
    return jsonify({"success": True, "data": advice})
```

- [ ] **Step 2: 确认 `g` 已导入**

Run: `cd AutoStockCollector-manage && grep -n "^from flask import\|^import flask" api/routes/strategy_pick.py`
Expected: `from flask import Blueprint, jsonify, request, Response, stream_with_context`（**没有 `g`**）。
若无 `g`，把该行改为：

```python
from flask import Blueprint, jsonify, request, Response, stream_with_context, g
```

- [ ] **Step 3: 冒烟启动，确认蓝图注册无语法错**

Run: `cd AutoStockCollector-manage && python -c "from api.routes.strategy_pick import strategy_pick_bp; print([str(r) for r in strategy_pick_bp.deferred_functions and []] or 'import ok')"`
Expected: 打印 `import ok`，无 traceback。

- [ ] **Step 4: 提交**

```bash
cd /Users/xiaoming/Downloads/stock
git add AutoStockCollector-manage/api/routes/strategy_pick.py
git commit -m "feat(strategy-pick): 新增 /rebalance-advice 再平衡建议接口"
```

---

### Task 3: 前端 API 与类型

**Files:**
- Modify: `AutoStockCollector-web/src/api/strategyPick.ts`

**Interfaces:**
- Consumes: 后端 `GET /api/v1/strategy-pick/rebalance-advice`（Task 2）
- Produces: `strategyPickApi.getRebalanceAdvice(buffer?)`、`RebalanceOrder`、`RebalanceAdvice` 类型

- [ ] **Step 1: 加方法**

在 `strategyPickApi` 对象内、`getHistory` 之后（`:45` 前的 `},` 之后）追加：

```typescript
  /** 获取再平衡建议（基于最新选股结果 + 实时持仓/现金） */
  getRebalanceAdvice(buffer = 0.05) {
    return client.get<{ success: boolean; data: RebalanceAdvice }>(
      '/api/v1/strategy-pick/rebalance-advice', { params: { buffer } },
    )
  },
```

- [ ] **Step 2: 加类型**

在文件末尾的接口定义区追加：

```typescript
export interface RebalanceOrder {
  code: string
  name: string
  action: 'buy' | 'sell'
  shares: number
  price: number | null
  target_weight: number
  current_weight: number
  reason: string
  skipped: boolean
  skip_reason: string | null
}

export interface RebalanceAdvice {
  total_value: number
  buffer: number
  cash: number
  orders: RebalanceOrder[]
  message?: string
}
```

- [ ] **Step 3: 类型检查通过**

Run: `cd AutoStockCollector-web && npx vue-tsc --noEmit`
Expected: 无报错（或仅与本次无关的既有报错）。

- [ ] **Step 4: 提交**

```bash
cd /Users/xiaoming/Downloads/stock
git add AutoStockCollector-web/src/api/strategyPick.ts
git commit -m "feat(web): strategyPick 新增 getRebalanceAdvice 与再平衡类型"
```

---

### Task 4: 前端再平衡面板

**Files:**
- Modify: `AutoStockCollector-web/src/views/StrategyPick/index.vue`

**Interfaces:**
- Consumes: `strategyPickApi.getRebalanceAdvice`（Task 3）、`paperApi.executeTrade`（现成，`src/api/paper.ts:135`）
- Produces: 无（页面组件）

- [ ] **Step 1: 引入 API 与状态**

在 `<script setup>` 顶部确认/补充 import（沿用文件现有风格）：

```typescript
import { strategyPickApi, type RebalanceOrder, type RebalanceAdvice } from '@/api/strategyPick'
import { paperApi } from '@/api/paper'
import { ref } from 'vue'
```

在已有响应式状态附近新增：

```typescript
const rebalance = ref<RebalanceAdvice | null>(null)
const rebalanceLoading = ref(false)
const executing = ref<Record<string, boolean>>({})

async function loadRebalance() {
  rebalanceLoading.value = true
  try {
    const res = await strategyPickApi.getRebalanceAdvice(0.05)
    rebalance.value = res.data.data
  } finally {
    rebalanceLoading.value = false
  }
}

async function execOne(o: RebalanceOrder) {
  if (o.skipped || !o.price) return
  executing.value[o.code] = true
  try {
    await paperApi.executeTrade({
      code: o.code, action: o.action, shares: o.shares,
      price: o.price, ai_signal: { reason: o.reason, position_advice: '再平衡建议' },
    })
    await loadRebalance()   // 执行后刷新清单（现金/持仓已变）
  } catch (e: any) {
    window.alert(`执行失败：${e?.response?.data?.error || e?.message || e}`)
  } finally {
    executing.value[o.code] = false
  }
}

async function execAll() {
  if (!rebalance.value) return
  // 先卖后买：卖出释放现金才够买
  const ordered = [...rebalance.value.orders].sort(
    (a, b) => (a.action === 'sell' ? 0 : 1) - (b.action === 'sell' ? 0 : 1),
  )
  for (const o of ordered) {
    if (o.skipped || !o.price) continue
    await execOne(o)
  }
}
```

- [ ] **Step 2: 加面板模板**

在选股结果展示区（`portfolio_suggestion` 相关块附近）追加一个面板。按文件现有 UI 库风格实现，结构如下（示例为通用 Element Plus 风格，按本仓既有组件替换）：

```vue
<div class="rebalance-panel" v-if="result">
  <div class="rebalance-head">
    <span>再平衡建议（缓冲带 5%）</span>
    <el-button size="small" :loading="rebalanceLoading" @click="loadRebalance">生成建议</el-button>
    <el-button size="small" type="primary"
               :disabled="!rebalance || !rebalance.orders.length"
               @click="execAll">全部执行</el-button>
  </div>
  <div v-if="rebalance?.message" class="rebalance-empty">{{ rebalance.message }}</div>
  <el-table v-else-if="rebalance" :data="rebalance.orders" size="small">
    <el-table-column label="动作">
      <template #default="{ row }">
        <el-tag :type="row.action === 'buy' ? 'danger' : 'success'">
          {{ row.action === 'buy' ? '买入' : '卖出' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="股票">
      <template #default="{ row }">{{ row.name }}（{{ row.code }}）</template>
    </el-table-column>
    <el-table-column prop="shares" label="股数" />
    <el-table-column prop="price" label="现价" />
    <el-table-column label="目标/当前权重">
      <template #default="{ row }">{{ row.target_weight }}% / {{ row.current_weight }}%</template>
    </el-table-column>
    <el-table-column prop="reason" label="说明" show-overflow-tooltip />
    <el-table-column label="操作">
      <template #default="{ row }">
        <el-button v-if="!row.skipped" size="small"
                   :loading="executing[row.code]" @click="execOne(row)">执行</el-button>
        <el-tooltip v-else :content="row.skip_reason || ''">
          <el-tag type="info">已跳过</el-tag>
        </el-tooltip>
      </template>
    </el-table-column>
  </el-table>
</div>
```

> 注：本仓 UI 组件以 `StrategyPick/index.vue` 现有写法为准，若用的不是 Element Plus，按既有 `portfolio_suggestion` 表格的同款组件替换标签，逻辑（`loadRebalance`/`execOne`/`execAll`）不变。

- [ ] **Step 3: 类型检查 + 构建**

Run: `cd AutoStockCollector-web && npx vue-tsc --noEmit && npm run build`
Expected: 构建成功。

- [ ] **Step 4: 浏览器验证（Playwright + mock，勿连真库）**

按 [[project_local_env_prod_db]] 约束，用 Playwright 拦截 `/api/v1/strategy-pick/rebalance-advice` 和 `/api/paper/trade` 返回 mock 数据：
- 校验面板渲染订单行、买/卖标签正确
- 点"执行"触发对 `/api/paper/trade` 的 POST（mock 200）
- 点"全部执行"按"先卖后买"顺序发起请求
- `skipped` 行显示"已跳过"且无执行按钮

- [ ] **Step 5: 提交**

```bash
cd /Users/xiaoming/Downloads/stock
git add AutoStockCollector-web/src/views/StrategyPick/index.vue
git commit -m "feat(web): 选股结果页新增再平衡建议面板（逐条/全部一键执行）"
```

---

## Self-Review

**Spec coverage:**
- 权重→股数换算 → Task 1 ✅
- 缓冲带 → Task 1（`test_buffer_suppresses_small_deviation`）✅
- 持有但不在目标→清仓 → Task 1（`test_held_but_not_in_target_is_full_sell`）✅
- 资金校验先卖后买、不够跳过 → Task 1 + Task 4 `execAll` 排序 ✅
- 实时算（不冻结） → Task 2 接口每次实时读持仓/现金/行情 ✅
- 逐条 + 全部执行 → Task 4 ✅
- 复用 `/paper/trade` 执行 → Task 4（`paperApi.executeTrade`）✅
- 无价跳过不崩 → Task 1（`test_no_price_target_skipped_not_crash`）✅
- 无选股结果提示 → Task 2（`message` 字段）✅

**Placeholder scan:** 无 TBD/TODO，所有代码步骤含完整代码。

**Type consistency:** `build_rebalance_orders` 签名在 Task 1 定义、Task 2 调用一致；Order 字段（code/name/action/shares/price/target_weight/current_weight/reason/skipped/skip_reason）在 advisor、后端、前端 `RebalanceOrder` 三处一致；`paperApi.executeTrade` 参数与 `paper.ts:135` 实际签名一致。
