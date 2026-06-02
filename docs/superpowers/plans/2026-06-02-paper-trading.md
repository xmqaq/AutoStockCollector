# Paper Trading Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将静态持仓管理重构为模拟盘交易系统，支持基于 AI 信号的买卖操作、交易流水记录和回测统计。

**Architecture:** 新增 `paper_account`（账户）和 `trade_records`（流水）两张 MongoDB 集合，持仓从流水实时聚合计算，不独立存储。后端三个模块（account / trade_engine / stats）各司其职，Flask Blueprint 统一挂载在 `/api/paper`，前端 Position 页面完整重写。

**Tech Stack:** Python 3 / Flask / pymongo / Vue 3 / TypeScript / Element Plus

---

## File Map

### 新建
- `AutoStockCollector-manage/modules/paper_trading/__init__.py`
- `AutoStockCollector-manage/modules/paper_trading/account.py`
- `AutoStockCollector-manage/modules/paper_trading/trade_engine.py`
- `AutoStockCollector-manage/modules/paper_trading/stats.py`
- `AutoStockCollector-manage/api/routes/paper_trading.py`
- `AutoStockCollector-manage/tests/unit/test_paper_trading.py`
- `AutoStockCollector-web/src/api/paper.ts`

### 修改
- `AutoStockCollector-manage/api/routes/__init__.py` — 替换 position_bp 为 paper_bp
- `AutoStockCollector-web/src/views/Position/index.vue` — 完整重写

### 删除（最后一步）
- `AutoStockCollector-manage/api/routes/position.py`
- `AutoStockCollector-manage/modules/position/position_manager.py`

---

## Task 1: PaperAccount 模块

**Files:**
- Create: `AutoStockCollector-manage/modules/paper_trading/__init__.py`
- Create: `AutoStockCollector-manage/modules/paper_trading/account.py`
- Test: `AutoStockCollector-manage/tests/unit/test_paper_trading.py`（第一批测试）

- [ ] **Step 1: 写失败测试（账户初始化与查询）**

新建 `AutoStockCollector-manage/tests/unit/test_paper_trading.py`：

```python
"""模拟盘模块单元测试：mock MongoDB，不依赖真实数据库。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestPaperAccount(unittest.TestCase):
    def _make_account(self):
        with patch("config.database.DatabaseConfig.get_database") as mock_db:
            mock_db.return_value = {
                "paper_account": MagicMock(),
                "trade_records": MagicMock(),
            }
            from modules.paper_trading.account import PaperAccount
            acct = PaperAccount()
            acct._col = MagicMock()
            acct._db = {"trade_records": MagicMock()}
            return acct

    def test_init_sets_cash_equal_to_capital(self):
        acct = self._make_account()
        acct._col.replace_one = MagicMock()
        result = acct.init(100000.0)
        self.assertEqual(result["cash_balance"], 100000.0)
        self.assertEqual(result["initial_capital"], 100000.0)
        self.assertEqual(result["user_id"], "default")

    def test_init_clears_trade_records(self):
        acct = self._make_account()
        acct._col.replace_one = MagicMock()
        acct.init(50000.0)
        acct._db["trade_records"].delete_many.assert_called_once_with({"user_id": "default"})

    def test_get_returns_none_when_not_initialized(self):
        acct = self._make_account()
        acct._col.find_one.return_value = None
        self.assertIsNone(acct.get())

    def test_get_strips_mongo_id(self):
        acct = self._make_account()
        acct._col.find_one.return_value = {
            "_id": "mongo_id",
            "user_id": "default",
            "initial_capital": 100000.0,
            "cash_balance": 90000.0,
        }
        result = acct.get()
        self.assertNotIn("_id", result)
        self.assertEqual(result["cash_balance"], 90000.0)

    def test_update_cash_calls_update_one(self):
        acct = self._make_account()
        acct._col.update_one = MagicMock()
        acct.update_cash("default", 75000.0)
        acct._col.update_one.assert_called_once()
        args = acct._col.update_one.call_args[0]
        self.assertEqual(args[0], {"user_id": "default"})
        self.assertEqual(args[1]["$set"]["cash_balance"], 75000.0)
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_paper_trading.py::TestPaperAccount -v 2>&1 | head -30
```

预期：`ModuleNotFoundError: No module named 'modules.paper_trading'`

- [ ] **Step 3: 创建模块包**

新建 `AutoStockCollector-manage/modules/paper_trading/__init__.py`（空文件）：

```python
```

- [ ] **Step 4: 实现 PaperAccount**

新建 `AutoStockCollector-manage/modules/paper_trading/account.py`：

```python
from datetime import datetime
from typing import Optional, Dict, Any


class PaperAccount:
    def __init__(self):
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        self._col = db["paper_account"]
        self._db = db

    def get(self, user_id: str = "default") -> Optional[Dict[str, Any]]:
        doc = self._col.find_one({"user_id": user_id})
        if doc:
            doc.pop("_id", None)
        return doc

    def init(self, initial_capital: float, user_id: str = "default") -> Dict[str, Any]:
        self._db["trade_records"].delete_many({"user_id": user_id})
        now = datetime.now().isoformat()
        doc = {
            "user_id": user_id,
            "initial_capital": initial_capital,
            "cash_balance": initial_capital,
            "created_at": now,
            "updated_at": now,
        }
        self._col.replace_one({"user_id": user_id}, doc, upsert=True)
        return doc

    def update_cash(self, user_id: str, new_balance: float) -> None:
        self._col.update_one(
            {"user_id": user_id},
            {"$set": {"cash_balance": new_balance, "updated_at": datetime.now().isoformat()}},
        )
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_paper_trading.py::TestPaperAccount -v
```

预期：`5 passed`

- [ ] **Step 6: 提交**

```bash
git add AutoStockCollector-manage/modules/paper_trading/__init__.py \
        AutoStockCollector-manage/modules/paper_trading/account.py \
        AutoStockCollector-manage/tests/unit/test_paper_trading.py
git commit -m "feat(paper): add PaperAccount module with init/get/update_cash"
```

---

## Task 2: TradeEngine 模块

**Files:**
- Create: `AutoStockCollector-manage/modules/paper_trading/trade_engine.py`
- Test: `AutoStockCollector-manage/tests/unit/test_paper_trading.py`（追加 TestTradeEngine）

- [ ] **Step 1: 追加失败测试（TradeEngine）**

在 `tests/unit/test_paper_trading.py` 末尾追加：

```python
class TestTradeEngine(unittest.TestCase):
    def _make_engine(self):
        with patch("config.database.DatabaseConfig.get_database") as mock_db:
            mock_db.return_value = {"trade_records": MagicMock()}
            from modules.paper_trading.trade_engine import TradeEngine
            engine = TradeEngine()
            engine._trades = MagicMock()
            return engine

    def _make_account_mock(self, cash=100000.0):
        acct = MagicMock()
        acct.get.return_value = {
            "user_id": "default",
            "initial_capital": 100000.0,
            "cash_balance": cash,
        }
        return acct

    def test_buy_deducts_cash_and_commission(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=10.0)
        engine._get_name = MagicMock(return_value="测试股票")
        engine._trades.insert_one = MagicMock()
        acct = self._make_account_mock(cash=100000.0)

        record = engine.buy("default", "SH600000", 500, {}, acct)

        # amount=5000, commission=5, total_cost=5005
        self.assertAlmostEqual(record["cash_after"], 94995.0, places=2)
        self.assertEqual(record["action"], "buy")
        self.assertEqual(record["shares"], 500)
        acct.update_cash.assert_called_once_with("default", 94995.0)

    def test_buy_raises_when_insufficient_cash(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=10.0)
        engine._get_name = MagicMock(return_value="测试股票")
        acct = self._make_account_mock(cash=100.0)  # only 100, need 5005

        with self.assertRaises(ValueError) as ctx:
            engine.buy("default", "SH600000", 500, {}, acct)
        self.assertIn("现金不足", str(ctx.exception))

    def test_buy_raises_when_price_unavailable(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=0.0)
        engine._get_name = MagicMock(return_value="测试股票")
        acct = self._make_account_mock()

        with self.assertRaises(ValueError) as ctx:
            engine.buy("default", "SH600000", 500, {}, acct)
        self.assertIn("无法获取", str(ctx.exception))

    def test_sell_adds_proceeds_to_cash(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=12.0)
        engine.get_positions = MagicMock(return_value=[
            {"code": "SH600000", "name": "测试股票", "shares": 500}
        ])
        engine._trades.insert_one = MagicMock()
        acct = self._make_account_mock(cash=50000.0)

        record = engine.sell("default", "SH600000", 300, {}, acct)

        # amount=3600, commission=3.6, proceeds=3596.4
        self.assertAlmostEqual(record["cash_after"], 53596.4, places=1)
        self.assertEqual(record["action"], "sell")

    def test_sell_raises_when_shares_insufficient(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=10.0)
        engine.get_positions = MagicMock(return_value=[
            {"code": "SH600000", "name": "测试股票", "shares": 100}
        ])
        acct = self._make_account_mock()

        with self.assertRaises(ValueError) as ctx:
            engine.sell("default", "SH600000", 500, {}, acct)
        self.assertIn("持仓不足", str(ctx.exception))

    def test_sell_raises_when_no_position(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=10.0)
        engine.get_positions = MagicMock(return_value=[])
        acct = self._make_account_mock()

        with self.assertRaises(ValueError) as ctx:
            engine.sell("default", "SH600000", 100, {}, acct)
        self.assertIn("未持有", str(ctx.exception))

    def test_get_positions_aggregates_buy_minus_sell(self):
        engine = self._make_engine()
        engine._trades.aggregate = MagicMock(return_value=[
            {
                "_id": "SH600000",
                "name": "测试股票",
                "buy_shares": 1000,
                "sell_shares": 300,
                "buy_amount": 10000.0,
            }
        ])
        engine._get_price = MagicMock(return_value=11.0)

        positions = engine.get_positions("default")

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["shares"], 700)
        self.assertAlmostEqual(positions[0]["avg_cost"], 10.0, places=4)

    def test_get_positions_excludes_fully_sold(self):
        engine = self._make_engine()
        engine._trades.aggregate = MagicMock(return_value=[
            {
                "_id": "SH600000",
                "name": "测试股票",
                "buy_shares": 500,
                "sell_shares": 500,
                "buy_amount": 5000.0,
            }
        ])
        engine._get_price = MagicMock(return_value=10.0)

        positions = engine.get_positions("default")
        self.assertEqual(len(positions), 0)
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_paper_trading.py::TestTradeEngine -v 2>&1 | head -20
```

预期：`ImportError: cannot import name 'TradeEngine'`

- [ ] **Step 3: 实现 TradeEngine**

新建 `AutoStockCollector-manage/modules/paper_trading/trade_engine.py`：

```python
from datetime import datetime
from typing import Any, Dict, List, Optional

COMMISSION_RATE = 0.001


class TradeEngine:
    def __init__(self):
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        self._trades = db["trade_records"]

    def _get_price(self, code: str) -> float:
        try:
            from core.storage.mongo_storage import KlineStorage
            storage = KlineStorage()
            kline = storage.find_one({"code": code}, sort=[("date", -1)])
            if kline:
                return float(kline.get("close", 0))
        except Exception:
            pass
        return 0.0

    def _get_name(self, code: str) -> str:
        try:
            from core.storage.mongo_storage import StockInfoStorage
            storage = StockInfoStorage()
            info = storage.get_by_code(code)
            if info:
                return info.get("name") or info.get("A股简称") or code
        except Exception:
            pass
        return code

    def get_positions(self, user_id: str = "default") -> List[Dict[str, Any]]:
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$code",
                "name": {"$last": "$name"},
                "buy_shares": {"$sum": {"$cond": [{"$eq": ["$action", "buy"]}, "$shares", 0]}},
                "sell_shares": {"$sum": {"$cond": [{"$eq": ["$action", "sell"]}, "$shares", 0]}},
                "buy_amount": {"$sum": {"$cond": [{"$eq": ["$action", "buy"]}, "$amount", 0]}},
            }},
        ]
        groups = list(self._trades.aggregate(pipeline))

        positions = []
        for g in groups:
            shares_held = g["buy_shares"] - g["sell_shares"]
            if shares_held <= 0:
                continue
            avg_cost = g["buy_amount"] / g["buy_shares"] if g["buy_shares"] > 0 else 0
            price = self._get_price(g["_id"])
            if price <= 0:
                price = avg_cost
            market_value = shares_held * price
            cost_basis = shares_held * avg_cost
            pnl = market_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0
            positions.append({
                "code": g["_id"],
                "name": g["name"],
                "shares": shares_held,
                "avg_cost": round(avg_cost, 4),
                "current_price": price,
                "market_value": round(market_value, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_pct, 2),
                "position_ratio": 0,
            })

        total_market = sum(p["market_value"] for p in positions)
        for p in positions:
            p["position_ratio"] = round(p["market_value"] / total_market * 100, 2) if total_market > 0 else 0

        return sorted(positions, key=lambda x: x["market_value"], reverse=True)

    def buy(
        self,
        user_id: str,
        code: str,
        shares: int,
        ai_signal: Dict[str, Any],
        account,
    ) -> Dict[str, Any]:
        price = self._get_price(code)
        if price <= 0:
            raise ValueError(f"无法获取 {code} 的最新价格")

        amount = shares * price
        commission = round(amount * COMMISSION_RATE, 2)
        total_cost = amount + commission

        account_doc = account.get(user_id)
        if not account_doc:
            raise ValueError("账户未初始化，请先设置初始资金")

        cash = account_doc["cash_balance"]
        if cash < total_cost:
            raise ValueError(f"现金不足，需要 {total_cost:.2f}，可用 {cash:.2f}")

        cash_after = round(cash - total_cost, 2)
        record = {
            "user_id": user_id,
            "code": code,
            "name": self._get_name(code),
            "action": "buy",
            "shares": shares,
            "price": price,
            "amount": round(amount, 2),
            "commission": commission,
            "ai_signal": ai_signal,
            "cash_before": cash,
            "cash_after": cash_after,
            "traded_at": datetime.now().isoformat(),
        }
        self._trades.insert_one(record)
        account.update_cash(user_id, cash_after)
        record.pop("_id", None)
        return record

    def sell(
        self,
        user_id: str,
        code: str,
        shares: int,
        ai_signal: Dict[str, Any],
        account,
    ) -> Dict[str, Any]:
        positions = self.get_positions(user_id)
        pos = next((p for p in positions if p["code"] == code), None)
        if not pos:
            raise ValueError(f"未持有 {code}")
        if pos["shares"] < shares:
            raise ValueError(f"持仓不足，当前 {pos['shares']} 股，尝试卖出 {shares} 股")

        price = self._get_price(code)
        if price <= 0:
            raise ValueError(f"无法获取 {code} 的最新价格")

        amount = shares * price
        commission = round(amount * COMMISSION_RATE, 2)
        proceeds = round(amount - commission, 2)

        account_doc = account.get(user_id)
        cash = account_doc["cash_balance"]
        cash_after = round(cash + proceeds, 2)

        record = {
            "user_id": user_id,
            "code": code,
            "name": pos["name"],
            "action": "sell",
            "shares": shares,
            "price": price,
            "amount": round(amount, 2),
            "commission": commission,
            "ai_signal": ai_signal,
            "cash_before": cash,
            "cash_after": cash_after,
            "traded_at": datetime.now().isoformat(),
        }
        self._trades.insert_one(record)
        account.update_cash(user_id, cash_after)
        record.pop("_id", None)
        return record
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_paper_trading.py::TestTradeEngine -v
```

预期：`8 passed`

- [ ] **Step 5: 提交**

```bash
git add AutoStockCollector-manage/modules/paper_trading/trade_engine.py \
        AutoStockCollector-manage/tests/unit/test_paper_trading.py
git commit -m "feat(paper): add TradeEngine with buy/sell/get_positions"
```

---

## Task 3: PaperStats 模块

**Files:**
- Create: `AutoStockCollector-manage/modules/paper_trading/stats.py`
- Test: `AutoStockCollector-manage/tests/unit/test_paper_trading.py`（追加 TestPaperStats）

- [ ] **Step 1: 追加失败测试（PaperStats）**

在 `tests/unit/test_paper_trading.py` 末尾追加：

```python
class TestPaperStats(unittest.TestCase):
    def _make_stats(self, trades):
        with patch("config.database.DatabaseConfig.get_database") as mock_db:
            mock_db.return_value = {"trade_records": MagicMock()}
            from modules.paper_trading.stats import PaperStats
            s = PaperStats()
            s._trades = MagicMock()
            s._trades.find.return_value = trades
            return s

    def _trade(self, action, code, shares, price, traded_at, cash_after=0):
        return {
            "action": action, "code": code, "shares": shares,
            "price": price, "traded_at": traded_at, "cash_after": cash_after,
        }

    def test_win_rate_100_when_all_profitable(self):
        trades = [
            self._trade("buy", "SH600000", 100, 10.0, "2026-01-01T10:00:00"),
            self._trade("sell", "SH600000", 100, 12.0, "2026-01-10T10:00:00"),
        ]
        s = self._make_stats(trades)
        result = s.get_stats()
        self.assertEqual(result["win_trades"], 1)
        self.assertEqual(result["total_trades"], 1)
        self.assertAlmostEqual(result["win_rate"], 100.0, places=1)

    def test_win_rate_0_when_all_losses(self):
        trades = [
            self._trade("buy", "SH600000", 100, 10.0, "2026-01-01T10:00:00"),
            self._trade("sell", "SH600000", 100, 8.0, "2026-01-10T10:00:00"),
        ]
        s = self._make_stats(trades)
        result = s.get_stats()
        self.assertEqual(result["win_trades"], 0)
        self.assertAlmostEqual(result["win_rate"], 0.0, places=1)

    def test_partial_sell_creates_one_completed_pair(self):
        trades = [
            self._trade("buy", "SH600000", 500, 10.0, "2026-01-01T10:00:00"),
            self._trade("sell", "SH600000", 200, 11.0, "2026-01-05T10:00:00"),
        ]
        s = self._make_stats(trades)
        result = s.get_stats()
        self.assertEqual(result["total_trades"], 1)

    def test_empty_trades_returns_zeros(self):
        s = self._make_stats([])
        result = s.get_stats()
        self.assertEqual(result["total_trades"], 0)
        self.assertEqual(result["win_rate"], 0)
        self.assertEqual(result["profit_factor"], 0)

    def test_nav_returns_sorted_series(self):
        trades = [
            self._trade("buy", "SH600000", 100, 10.0, "2026-01-01T10:00:00", cash_after=99000.0),
            self._trade("sell", "SH600000", 100, 12.0, "2026-01-10T10:00:00", cash_after=101200.0),
        ]
        acct = MagicMock()
        acct.get.return_value = {"initial_capital": 100000.0}
        s = self._make_stats(trades)
        nav = s.get_nav("default", acct)
        self.assertEqual(len(nav), 2)
        self.assertEqual(nav[0]["date"], "2026-01-01")
        self.assertAlmostEqual(nav[1]["nav"], 1.012, places=3)
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_paper_trading.py::TestPaperStats -v 2>&1 | head -20
```

预期：`ImportError: cannot import name 'PaperStats'`

- [ ] **Step 3: 实现 PaperStats**

新建 `AutoStockCollector-manage/modules/paper_trading/stats.py`：

```python
from typing import Any, Dict, List


class PaperStats:
    def __init__(self):
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        self._trades = db["trade_records"]

    def get_stats(self, user_id: str = "default") -> Dict[str, Any]:
        trades = list(self._trades.find({"user_id": user_id}, sort=[("traded_at", 1)]))

        buy_queue: Dict[str, List[Dict]] = {}
        completed_pairs: List[Dict] = []

        for t in trades:
            code = t["code"]
            action = t["action"]
            shares = t["shares"]
            price = t["price"]

            if action == "buy":
                buy_queue.setdefault(code, []).append({"shares": shares, "price": price})
            elif action == "sell":
                remaining = shares
                for head in list(buy_queue.get(code, [])):
                    if remaining <= 0:
                        break
                    matched = min(remaining, head["shares"])
                    pnl_pct = (price - head["price"]) / head["price"] * 100 if head["price"] > 0 else 0
                    completed_pairs.append({"pnl_pct": pnl_pct})
                    head["shares"] -= matched
                    remaining -= matched
                buy_queue[code] = [h for h in buy_queue.get(code, []) if h["shares"] > 0]

        total = len(completed_pairs)
        wins = [p for p in completed_pairs if p["pnl_pct"] > 0]
        losses = [p for p in completed_pairs if p["pnl_pct"] <= 0]

        win_rate = len(wins) / total * 100 if total > 0 else 0
        avg_profit = sum(p["pnl_pct"] for p in wins) / len(wins) if wins else 0
        avg_loss = sum(p["pnl_pct"] for p in losses) / len(losses) if losses else 0
        profit_factor = round(abs(avg_profit / avg_loss), 2) if avg_loss != 0 else 0

        return {
            "total_trades": total,
            "win_trades": len(wins),
            "loss_trades": len(losses),
            "win_rate": round(win_rate, 2),
            "avg_profit_pct": round(avg_profit, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "profit_factor": profit_factor,
        }

    def get_nav(self, user_id: str, account) -> List[Dict[str, Any]]:
        trades = list(self._trades.find({"user_id": user_id}, sort=[("traded_at", 1)]))
        account_doc = account.get(user_id)
        if not account_doc or not trades:
            return []

        initial = account_doc["initial_capital"]
        daily_cash: Dict[str, float] = {}
        for t in trades:
            date = t["traded_at"][:10]
            daily_cash[date] = t["cash_after"]

        return [
            {
                "date": date,
                "cash": daily_cash[date],
                "nav": round(daily_cash[date] / initial, 4) if initial > 0 else 1.0,
            }
            for date in sorted(daily_cash)
        ]
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_paper_trading.py::TestPaperStats -v
```

预期：`5 passed`

- [ ] **Step 5: 运行全部 paper 测试**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_paper_trading.py -v
```

预期：`18 passed`（Task 1 + 2 + 3 全部）

- [ ] **Step 6: 提交**

```bash
git add AutoStockCollector-manage/modules/paper_trading/stats.py \
        AutoStockCollector-manage/tests/unit/test_paper_trading.py
git commit -m "feat(paper): add PaperStats with win-rate and NAV calculation"
```

---

## Task 4: Flask Blueprint 与路由注册

**Files:**
- Create: `AutoStockCollector-manage/api/routes/paper_trading.py`
- Modify: `AutoStockCollector-manage/api/routes/__init__.py`（替换 position_bp）

- [ ] **Step 1: 新建 paper_trading Blueprint**

新建 `AutoStockCollector-manage/api/routes/paper_trading.py`：

```python
"""模拟盘交易 API — /api/paper/*"""
from flask import Blueprint, request, jsonify
from utils.logger import get_logger

logger = get_logger(__name__)
paper_bp = Blueprint("paper", __name__, url_prefix="/api/paper")

_account = None
_engine = None
_stats = None


def _lazy_init():
    global _account, _engine, _stats
    if _account is None:
        from modules.paper_trading.account import PaperAccount
        from modules.paper_trading.trade_engine import TradeEngine
        from modules.paper_trading.stats import PaperStats
        _account = PaperAccount()
        _engine = TradeEngine()
        _stats = PaperStats()


@paper_bp.route("/account", methods=["GET"])
def get_account():
    _lazy_init()
    user_id = request.args.get("user_id", "default")
    doc = _account.get(user_id)
    if not doc:
        return jsonify({"success": False, "error": "账户未初始化，请先设置初始资金"}), 404
    return jsonify({"success": True, "data": doc})


@paper_bp.route("/account/init", methods=["POST"])
def init_account():
    _lazy_init()
    data = request.get_json() or {}
    user_id = data.get("user_id", "default")
    try:
        capital = float(data.get("initial_capital", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "initial_capital 必须为数字"}), 400
    if capital <= 0:
        return jsonify({"error": "initial_capital 必须大于 0"}), 400
    doc = _account.init(capital, user_id)
    return jsonify({"success": True, "data": doc})


@paper_bp.route("/trade", methods=["POST"])
def execute_trade():
    _lazy_init()
    data = request.get_json() or {}
    user_id = data.get("user_id", "default")
    code = data.get("code", "").strip()
    action = data.get("action", "").strip()
    ai_signal = data.get("ai_signal", {})

    try:
        shares = int(data.get("shares", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "shares 必须为整数"}), 400

    if not code or not action or shares <= 0:
        return jsonify({"error": "code、action、shares 均为必填项"}), 400

    from utils.helpers import normalize_stock_code_flexible
    code = normalize_stock_code_flexible(code)

    try:
        if action == "buy":
            record = _engine.buy(user_id, code, shares, ai_signal, _account)
        elif action == "sell":
            record = _engine.sell(user_id, code, shares, ai_signal, _account)
        else:
            return jsonify({"error": "action 必须为 buy 或 sell"}), 400
        return jsonify({"success": True, "data": record})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@paper_bp.route("/positions", methods=["GET"])
def get_positions():
    _lazy_init()
    user_id = request.args.get("user_id", "default")
    positions = _engine.get_positions(user_id)
    return jsonify({"success": True, "count": len(positions), "data": positions})


@paper_bp.route("/trades", methods=["GET"])
def get_trades():
    _lazy_init()
    from config.database import DatabaseConfig
    user_id = request.args.get("user_id", "default")
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    db = DatabaseConfig.get_database()
    trades = list(
        db["trade_records"].find({"user_id": user_id}, sort=[("traded_at", -1)], limit=limit)
    )
    for t in trades:
        t.pop("_id", None)
    return jsonify({"success": True, "count": len(trades), "data": trades})


@paper_bp.route("/stats", methods=["GET"])
def get_stats():
    _lazy_init()
    user_id = request.args.get("user_id", "default")
    stats = _stats.get_stats(user_id)
    return jsonify({"success": True, "data": stats})


@paper_bp.route("/nav", methods=["GET"])
def get_nav():
    _lazy_init()
    user_id = request.args.get("user_id", "default")
    nav = _stats.get_nav(user_id, _account)
    return jsonify({"success": True, "data": nav})
```

- [ ] **Step 2: 更新路由注册，替换 position_bp**

编辑 `AutoStockCollector-manage/api/routes/__init__.py`，将：

```python
    from api.routes.position import position_bp
    ...
    app.register_blueprint(position_bp)
```

改为：

```python
    from api.routes.paper_trading import paper_bp
    ...
    app.register_blueprint(paper_bp)
```

具体：找到 `register_routes` 函数中的第 126 行 `from api.routes.position import position_bp` 删除，替换为 `from api.routes.paper_trading import paper_bp`；找到第 135 行 `app.register_blueprint(position_bp)` 替换为 `app.register_blueprint(paper_bp)`。

- [ ] **Step 3: 验证服务器能启动**

```bash
cd AutoStockCollector-manage
python -c "from api import create_app; app = create_app(); print('OK')"
```

预期：输出 `OK`，无 ImportError。

- [ ] **Step 4: 提交**

```bash
git add AutoStockCollector-manage/api/routes/paper_trading.py \
        AutoStockCollector-manage/api/routes/__init__.py
git commit -m "feat(paper): add Flask Blueprint and replace position routes"
```

---

## Task 5: 前端 API 层

**Files:**
- Create: `AutoStockCollector-web/src/api/paper.ts`
- Modify: `AutoStockCollector-web/src/api/position.ts`（替换内容，让原有引用不报错）

- [ ] **Step 1: 新建 paper.ts**

新建 `AutoStockCollector-web/src/api/paper.ts`：

```typescript
import request from './client'

export interface PaperAccount {
  user_id: string
  initial_capital: number
  cash_balance: number
  created_at: string
  updated_at: string
}

export interface PaperPosition {
  code: string
  name: string
  shares: number
  avg_cost: number
  current_price: number
  market_value: number
  pnl: number
  pnl_percent: number
  position_ratio: number
}

export interface TradeRecord {
  user_id: string
  code: string
  name: string
  action: 'buy' | 'sell'
  shares: number
  price: number
  amount: number
  commission: number
  ai_signal: {
    action?: string
    reason?: string
    composite?: number
  }
  cash_before: number
  cash_after: number
  traded_at: string
}

export interface PaperStats {
  total_trades: number
  win_trades: number
  loss_trades: number
  win_rate: number
  avg_profit_pct: number
  avg_loss_pct: number
  profit_factor: number
}

export interface NavPoint {
  date: string
  cash: number
  nav: number
}

export interface AiSignal {
  action?: string
  reason?: string
  composite?: number
  buy_zone?: string
  stop_loss?: string
  position_advice?: string
}

export const paperApi = {
  async getAccount(): Promise<PaperAccount | null> {
    try {
      const res = await request.get<{ data: PaperAccount }>('/api/paper/account')
      return res.data?.data ?? null
    } catch {
      return null
    }
  },

  async initAccount(initialCapital: number): Promise<PaperAccount> {
    const res = await request.post<{ data: PaperAccount }>('/api/paper/account/init', {
      initial_capital: initialCapital,
    })
    return res.data.data
  },

  async getPositions(): Promise<PaperPosition[]> {
    const res = await request.get<{ data: PaperPosition[] }>('/api/paper/positions')
    return res.data?.data ?? []
  },

  async executeTrade(payload: {
    code: string
    action: 'buy' | 'sell'
    shares: number
    ai_signal?: AiSignal
  }): Promise<TradeRecord> {
    const res = await request.post<{ data: TradeRecord }>('/api/paper/trade', payload)
    return res.data.data
  },

  async getTrades(limit = 10): Promise<TradeRecord[]> {
    const res = await request.get<{ data: TradeRecord[] }>(`/api/paper/trades?limit=${limit}`)
    return res.data?.data ?? []
  },

  async getStats(): Promise<PaperStats> {
    const res = await request.get<{ data: PaperStats }>('/api/paper/stats')
    return res.data?.data ?? {
      total_trades: 0, win_trades: 0, loss_trades: 0,
      win_rate: 0, avg_profit_pct: 0, avg_loss_pct: 0, profit_factor: 0,
    }
  },

  async getNav(): Promise<NavPoint[]> {
    const res = await request.get<{ data: NavPoint[] }>('/api/paper/nav')
    return res.data?.data ?? []
  },

  async getAiAdvice(code: string, cost?: number, position?: number): Promise<AiSignal> {
    const params = new URLSearchParams({ code })
    if (cost != null) params.set('cost', String(cost))
    if (position != null) params.set('position', String(position))
    const res = await request.get<{ advice: AiSignal }>(`/api/v1/advice?${params}`)
    return res.data?.advice ?? {}
  },
}
```

- [ ] **Step 2: 更新 position.ts，重定向至 paper.ts**

将 `AutoStockCollector-web/src/api/position.ts` 内容完全替换为：

```typescript
// 模拟盘重构后，持仓接口已迁移至 paper.ts
// 此文件保留以免历史引用报错，直接重导出 paperApi
export { paperApi as positionApi, paperApi } from './paper'
export type { PaperPosition as Position } from './paper'
```

- [ ] **Step 3: 提交**

```bash
git add AutoStockCollector-web/src/api/paper.ts \
        AutoStockCollector-web/src/api/position.ts
git commit -m "feat(paper): add frontend paper API layer"
```

---

## Task 6: 前端持仓页面重写

**Files:**
- Modify: `AutoStockCollector-web/src/views/Position/index.vue`（完整重写）

- [ ] **Step 1: 重写 Position/index.vue**

将 `AutoStockCollector-web/src/views/Position/index.vue` 全部内容替换为：

```vue
<template>
  <div class="paper-trading">
    <!-- 顶部账户概览 -->
    <el-card shadow="never" class="account-bar" v-loading="accountLoading">
      <div class="account-overview" v-if="account">
        <div class="account-stat">
          <div class="stat-label">初始资金</div>
          <div class="stat-value">{{ formatAmount(account.initial_capital) }}</div>
        </div>
        <div class="account-stat">
          <div class="stat-label">当前现金</div>
          <div class="stat-value">{{ formatAmount(account.cash_balance) }}</div>
        </div>
        <div class="account-stat">
          <div class="stat-label">持仓市值</div>
          <div class="stat-value text-primary">{{ formatAmount(totalMarketValue) }}</div>
        </div>
        <div class="account-stat">
          <div class="stat-label">账户净值</div>
          <div class="stat-value" :class="totalReturn >= 0 ? 'text-rise' : 'text-fall'">
            {{ formatAmount(account.cash_balance + totalMarketValue) }}
          </div>
        </div>
        <div class="account-stat">
          <div class="stat-label">总收益率</div>
          <div class="stat-value" :class="totalReturn >= 0 ? 'text-rise' : 'text-fall'">
            {{ formatPercent(totalReturn) }}
          </div>
        </div>
        <el-button size="small" @click="showInitDialog = true">初始化账户</el-button>
      </div>
      <div v-else class="no-account">
        <span>尚未初始化账户</span>
        <el-button type="primary" size="small" @click="showInitDialog = true">立即初始化</el-button>
      </div>
    </el-card>

    <el-row :gutter="16" style="margin-top: 12px">
      <!-- 左侧：持仓表 -->
      <el-col :span="16">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>当前持仓</span>
              <el-button type="primary" size="small" @click="showBuyDialog = true">
                手动买入
              </el-button>
            </div>
          </template>
          <el-table :data="positions" stripe size="small" v-loading="posLoading">
            <el-table-column prop="code" label="代码" width="100" align="center">
              <template #default="{ row }">
                <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
                  {{ row.code }}
                </router-link>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="90" align="center" show-overflow-tooltip />
            <el-table-column prop="shares" label="持仓量" width="80" align="center" />
            <el-table-column label="成本价" width="80" align="center">
              <template #default="{ row }">{{ row.avg_cost.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="现价" width="80" align="center">
              <template #default="{ row }">{{ row.current_price.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="市值" width="90" align="center">
              <template #default="{ row }">{{ formatAmount(row.market_value) }}</template>
            </el-table-column>
            <el-table-column label="盈亏%" width="90" align="center">
              <template #default="{ row }">
                <span :class="row.pnl_percent >= 0 ? 'text-rise' : 'text-fall'">
                  {{ formatPercent(row.pnl_percent) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="占比" width="70" align="center">
              <template #default="{ row }">{{ row.position_ratio.toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button type="primary" size="small" text @click="fetchAiAdvice(row, 'buy')">
                  AI 建议
                </el-button>
                <el-button type="warning" size="small" text @click="openManualSell(row)">
                  卖出
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!posLoading && positions.length === 0" description="暂无持仓" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 右侧：统计卡片 -->
      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <template #header><span>净值曲线</span></template>
          <ProfitChart :data="navChartData" title="" chart-height="200px" />
        </el-card>

        <el-card shadow="never" class="section-card" style="margin-top: 12px">
          <template #header><span>回测统计</span></template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="总交易次数">{{ stats.total_trades }}</el-descriptions-item>
            <el-descriptions-item label="胜率">
              <span :class="stats.win_rate >= 50 ? 'text-rise' : 'text-fall'">
                {{ stats.win_rate.toFixed(1) }}%
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="平均盈利">
              <span class="text-rise">+{{ stats.avg_profit_pct.toFixed(2) }}%</span>
            </el-descriptions-item>
            <el-descriptions-item label="平均亏损">
              <span class="text-fall">{{ stats.avg_loss_pct.toFixed(2) }}%</span>
            </el-descriptions-item>
            <el-descriptions-item label="盈亏比" :span="2">{{ stats.profit_factor.toFixed(2) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="section-card" style="margin-top: 12px">
          <template #header><span>最近交易</span></template>
          <div class="trade-list">
            <div v-for="t in recentTrades" :key="t.traded_at" class="trade-item">
              <div class="trade-header">
                <span class="trade-code">{{ t.code }} {{ t.name }}</span>
                <el-tag size="small" :type="t.action === 'buy' ? 'success' : 'danger'">
                  {{ t.action === 'buy' ? '买入' : '卖出' }}
                </el-tag>
              </div>
              <div class="trade-detail">
                {{ t.shares }} 股 @ {{ t.price.toFixed(2) }}
                <span class="trade-time">{{ t.traded_at.slice(0, 10) }}</span>
              </div>
              <div v-if="t.ai_signal?.action" class="trade-signal">
                AI: {{ t.ai_signal.action }}
              </div>
            </div>
            <el-empty v-if="recentTrades.length === 0" description="暂无记录" :image-size="40" />
          </div>
        </el-card>

        <el-card shadow="never" class="section-card" style="margin-top: 12px">
          <template #header><span>持仓分布</span></template>
          <div v-if="positions.length > 0" class="distribution-chart">
            <div v-for="p in positions" :key="p.code" class="distribution-item">
              <div class="dist-info">
                <span class="dist-label">{{ p.code }}</span>
                <span class="dist-percent">{{ p.position_ratio.toFixed(1) }}%</span>
              </div>
              <div class="dist-bar-container">
                <div class="dist-bar" :style="{ width: p.position_ratio + '%' }" />
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="40" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 初始化账户对话框 -->
    <el-dialog v-model="showInitDialog" title="初始化模拟账户" width="400px">
      <el-form label-width="100px">
        <el-form-item label="初始资金">
          <el-input-number v-model="initCapital" :min="1000" :step="10000" style="width: 100%" />
        </el-form-item>
        <div class="dialog-warn">注意：初始化将清空所有交易记录和持仓！</div>
      </el-form>
      <template #footer>
        <el-button @click="showInitDialog = false">取消</el-button>
        <el-button type="primary" :loading="initLoading" @click="doInitAccount">确认初始化</el-button>
      </template>
    </el-dialog>

    <!-- 手动买入对话框 -->
    <el-dialog v-model="showBuyDialog" title="手动买入" width="420px">
      <el-form label-width="100px">
        <el-form-item label="股票代码">
          <el-input v-model="buyForm.code" placeholder="如 SH600000" />
        </el-form-item>
        <el-form-item label="买入数量">
          <el-input-number v-model="buyForm.shares" :min="100" :step="100" style="width: 100%" />
        </el-form-item>
        <div class="dialog-info" v-if="account">可用现金：{{ formatAmount(account.cash_balance) }}</div>
      </el-form>
      <template #footer>
        <el-button @click="showBuyDialog = false">取消</el-button>
        <el-button type="primary" :loading="tradeLoading" @click="doManualBuy">确认买入</el-button>
      </template>
    </el-dialog>

    <!-- AI 买入确认框 -->
    <el-dialog v-model="showAiBuyDialog" title="AI 买入建议" width="480px">
      <div class="ai-advice-panel" v-if="aiAdvice">
        <div class="advice-row">
          <span class="advice-label">建议操作</span>
          <el-tag type="success">{{ aiAdvice.action }}</el-tag>
        </div>
        <div class="advice-row" v-if="aiAdvice.reason">
          <span class="advice-label">理由</span>
          <span class="advice-text">{{ aiAdvice.reason }}</span>
        </div>
        <div class="advice-row" v-if="aiAdvice.buy_zone">
          <span class="advice-label">参考区间</span>
          <span class="advice-text">{{ aiAdvice.buy_zone }}</span>
        </div>
        <el-divider />
        <el-form label-width="100px">
          <el-form-item label="当前价">{{ tradeTarget?.current_price?.toFixed(2) ?? '—' }}</el-form-item>
          <el-form-item label="可用现金">{{ formatAmount(account?.cash_balance ?? 0) }}</el-form-item>
          <el-form-item label="买入数量">
            <el-input-number v-model="tradeShares" :min="100" :step="100" style="width: 100%" />
          </el-form-item>
          <el-form-item label="预计金额">
            <span class="text-primary">
              {{ formatAmount((tradeTarget?.current_price ?? 0) * tradeShares) }}
            </span>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="showAiBuyDialog = false">取消</el-button>
        <el-button type="primary" :loading="tradeLoading" @click="doAiTrade('buy')">确认买入</el-button>
      </template>
    </el-dialog>

    <!-- AI 卖出 / 手动卖出确认框 -->
    <el-dialog v-model="showSellDialog" :title="aiAdvice ? 'AI 卖出建议' : '卖出确认'" width="480px">
      <div class="ai-advice-panel" v-if="aiAdvice">
        <div class="advice-row">
          <span class="advice-label">建议操作</span>
          <el-tag type="danger">{{ aiAdvice.action }}</el-tag>
        </div>
        <div class="advice-row" v-if="aiAdvice.reason">
          <span class="advice-label">理由</span>
          <span class="advice-text">{{ aiAdvice.reason }}</span>
        </div>
        <el-divider />
      </div>
      <el-form label-width="100px">
        <el-form-item label="股票">{{ tradeTarget?.code }} {{ tradeTarget?.name }}</el-form-item>
        <el-form-item label="当前持仓">{{ tradeTarget?.shares }} 股</el-form-item>
        <el-form-item label="当前价">{{ tradeTarget?.current_price?.toFixed(2) ?? '—' }}</el-form-item>
        <el-form-item label="卖出数量">
          <el-input-number
            v-model="tradeShares"
            :min="100"
            :max="tradeTarget?.shares ?? 0"
            :step="100"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="预计回收">
          <span class="text-primary">
            {{ formatAmount((tradeTarget?.current_price ?? 0) * tradeShares) }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSellDialog = false">取消</el-button>
        <el-button type="danger" :loading="tradeLoading" @click="doAiTrade('sell')">确认卖出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paperApi, type PaperAccount, type PaperPosition, type TradeRecord, type PaperStats, type NavPoint, type AiSignal } from '@/api/paper'
import ProfitChart from '@/components/ProfitChart/index.vue'

const accountLoading = ref(false)
const posLoading = ref(false)
const initLoading = ref(false)
const tradeLoading = ref(false)
const aiLoading = ref(false)

const account = ref<PaperAccount | null>(null)
const positions = ref<PaperPosition[]>([])
const recentTrades = ref<TradeRecord[]>([])
const stats = ref<PaperStats>({
  total_trades: 0, win_trades: 0, loss_trades: 0,
  win_rate: 0, avg_profit_pct: 0, avg_loss_pct: 0, profit_factor: 0,
})
const navData = ref<NavPoint[]>([])

const showInitDialog = ref(false)
const showBuyDialog = ref(false)
const showAiBuyDialog = ref(false)
const showSellDialog = ref(false)

const initCapital = ref(100000)
const buyForm = ref({ code: '', shares: 100 })
const tradeTarget = ref<PaperPosition | null>(null)
const tradeShares = ref(100)
const aiAdvice = ref<AiSignal | null>(null)

const totalMarketValue = computed(() =>
  positions.value.reduce((s, p) => s + p.market_value, 0)
)

const totalReturn = computed(() => {
  if (!account.value || account.value.initial_capital === 0) return 0
  const netValue = account.value.cash_balance + totalMarketValue.value
  return (netValue - account.value.initial_capital) / account.value.initial_capital * 100
})

const navChartData = computed(() =>
  navData.value.map(n => ({ date: n.date, value: n.nav * (account.value?.initial_capital ?? 100000), cost: account.value?.initial_capital ?? 100000 }))
)

function formatAmount(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

function formatPercent(v: number): string {
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

async function loadAll() {
  accountLoading.value = true
  posLoading.value = true
  try {
    const [acct, pos, trades, st, nav] = await Promise.all([
      paperApi.getAccount(),
      paperApi.getPositions(),
      paperApi.getTrades(10),
      paperApi.getStats(),
      paperApi.getNav(),
    ])
    account.value = acct
    positions.value = pos
    recentTrades.value = trades
    stats.value = st
    navData.value = nav
  } finally {
    accountLoading.value = false
    posLoading.value = false
  }
}

async function doInitAccount() {
  if (initCapital.value <= 0) return
  try {
    await ElMessageBox.confirm(
      `确认将模拟账户初始资金设为 ${formatAmount(initCapital.value)}？所有持仓和交易记录将被清空！`,
      '初始化确认',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  initLoading.value = true
  try {
    await paperApi.initAccount(initCapital.value)
    ElMessage.success('账户初始化成功')
    showInitDialog.value = false
    loadAll()
  } catch {
    ElMessage.error('初始化失败')
  } finally {
    initLoading.value = false
  }
}

async function fetchAiAdvice(pos: PaperPosition, intent: 'buy' | 'sell') {
  aiAdvice.value = null
  tradeTarget.value = pos
  aiLoading.value = true

  // 默认买入数量：按可用现金 20% 估算
  if (intent === 'buy' && account.value) {
    const budget = account.value.cash_balance * 0.2
    const estimatedShares = Math.floor(budget / (pos.current_price || 1) / 100) * 100
    tradeShares.value = Math.max(100, estimatedShares)
  } else if (intent === 'sell') {
    tradeShares.value = Math.floor(pos.shares * 0.5 / 100) * 100 || 100
  }

  try {
    const advice = await paperApi.getAiAdvice(pos.code, pos.avg_cost, pos.position_ratio / 100)
    aiAdvice.value = advice

    const actionLower = (advice.action ?? '').toLowerCase()
    const isSellSignal = actionLower.includes('卖') || actionLower.includes('减仓') || actionLower.includes('清仓')

    // 尝试解析 position_advice 中的卖出比例
    if (intent === 'sell' && advice.position_advice) {
      const match = advice.position_advice.match(/(\d+)\s*%/)
      if (match) {
        const ratio = parseInt(match[1]) / 100
        tradeShares.value = Math.max(100, Math.floor(pos.shares * ratio / 100) * 100)
      }
    }

    if (isSellSignal || intent === 'sell') {
      showSellDialog.value = true
    } else {
      showAiBuyDialog.value = true
    }
  } catch {
    ElMessage.error('获取 AI 建议失败')
  } finally {
    aiLoading.value = false
  }
}

function openManualSell(pos: PaperPosition) {
  tradeTarget.value = pos
  aiAdvice.value = null
  tradeShares.value = pos.shares
  showSellDialog.value = true
}

async function doManualBuy() {
  if (!buyForm.value.code || buyForm.value.shares <= 0) {
    ElMessage.warning('请填写股票代码和数量')
    return
  }
  tradeLoading.value = true
  try {
    await paperApi.executeTrade({ code: buyForm.value.code, action: 'buy', shares: buyForm.value.shares })
    ElMessage.success('买入成功')
    showBuyDialog.value = false
    buyForm.value = { code: '', shares: 100 }
    loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error ?? '买入失败')
  } finally {
    tradeLoading.value = false
  }
}

async function doAiTrade(action: 'buy' | 'sell') {
  if (!tradeTarget.value || tradeShares.value <= 0) return
  tradeLoading.value = true
  try {
    await paperApi.executeTrade({
      code: tradeTarget.value.code,
      action,
      shares: tradeShares.value,
      ai_signal: aiAdvice.value ?? undefined,
    })
    ElMessage.success(action === 'buy' ? '买入成功' : '卖出成功')
    showAiBuyDialog.value = false
    showSellDialog.value = false
    loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error ?? '交易失败')
  } finally {
    tradeLoading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.paper-trading { display: flex; flex-direction: column; gap: 0; }

.account-bar { background: #1f1f1f; border: 1px solid #2c2c2c; }
.account-overview { display: flex; align-items: center; gap: 32px; flex-wrap: wrap; }
.account-stat { display: flex; flex-direction: column; gap: 4px; }
.stat-label { font-size: 12px; color: #909399; }
.stat-value { font-size: 16px; font-weight: 600; color: #e5eaf3; }
.no-account { display: flex; align-items: center; gap: 12px; color: #909399; }

.section-card { background: #1f1f1f; border: 1px solid #2c2c2c; }
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c; padding: 12px 16px;
  color: #e5eaf3; font-size: 14px; font-weight: 600;
}
.card-header { display: flex; justify-content: space-between; align-items: center; }

.stock-link { color: #409eff; text-decoration: none; }
.stock-link:hover { text-decoration: underline; }

.text-rise { color: #ef5350; }
.text-fall { color: #26a69a; }
.text-primary { color: #409eff; }

.trade-list { display: flex; flex-direction: column; gap: 8px; max-height: 240px; overflow-y: auto; }
.trade-item { padding: 8px 10px; background: #2c2c2c; border-radius: 4px; }
.trade-header { display: flex; justify-content: space-between; align-items: center; }
.trade-code { font-size: 13px; font-weight: 600; color: #e5eaf3; }
.trade-detail { font-size: 12px; color: #909399; margin-top: 4px; display: flex; justify-content: space-between; }
.trade-time { color: #606266; }
.trade-signal { font-size: 11px; color: #e6a23c; margin-top: 2px; }

.distribution-chart { display: flex; flex-direction: column; gap: 8px; }
.distribution-item { display: flex; flex-direction: column; gap: 4px; }
.dist-info { display: flex; justify-content: space-between; font-size: 12px; }
.dist-label { color: #e5eaf3; }
.dist-percent { color: #909399; }
.dist-bar-container { height: 6px; background: #2c2c2c; border-radius: 3px; overflow: hidden; }
.dist-bar { height: 100%; background: #409eff; border-radius: 3px; transition: width 0.3s ease; }

.ai-advice-panel { margin-bottom: 8px; }
.advice-row { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 8px; }
.advice-label { font-size: 12px; color: #909399; min-width: 60px; padding-top: 2px; }
.advice-text { font-size: 13px; color: #e5eaf3; line-height: 1.5; }

.dialog-warn { color: #f56c6c; font-size: 12px; margin-top: 8px; padding-left: 100px; }
.dialog-info { color: #909399; font-size: 12px; margin-top: 4px; padding-left: 100px; }
</style>
```

- [ ] **Step 2: 提交**

```bash
git add AutoStockCollector-web/src/views/Position/index.vue
git commit -m "feat(paper): rewrite Position page as paper trading UI"
```

---

## Task 7: 清理旧文件

**Files:**
- Delete: `AutoStockCollector-manage/api/routes/position.py`
- Delete: `AutoStockCollector-manage/modules/position/position_manager.py`

- [ ] **Step 1: 确认旧文件已无引用**

```bash
cd AutoStockCollector-manage
grep -r "from api.routes.position import\|from modules.position import" --include="*.py" .
```

预期：无输出（已在 Task 4 替换）。

- [ ] **Step 2: 删除旧文件**

```bash
rm AutoStockCollector-manage/api/routes/position.py
rm AutoStockCollector-manage/modules/position/position_manager.py
```

- [ ] **Step 3: 再次验证启动**

```bash
cd AutoStockCollector-manage
python -c "from api import create_app; app = create_app(); print('OK')"
```

预期：`OK`

- [ ] **Step 4: 运行全量测试**

```bash
cd AutoStockCollector-manage
python -m pytest tests/unit/test_paper_trading.py -v
```

预期：`18 passed`

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "chore: remove deprecated position module and routes"
```

---

## 自查摘要

| 规格要求 | 覆盖任务 |
|---|---|
| `paper_account` + `trade_records` 数据模型 | Task 1, 2 |
| 初始化账户、清空流水 | Task 1 |
| 买入校验（现金、价格） | Task 2 |
| 卖出校验（持仓量） | Task 2 |
| 持仓从流水聚合（avg_cost、pnl） | Task 2 |
| 胜率、盈亏比统计（FIFO 匹配） | Task 3 |
| 净值曲线数据 | Task 3 |
| 全部 7 个 `/api/paper` 接口 | Task 4 |
| 旧 position_bp 替换 | Task 4 |
| 前端 paper.ts API 层 | Task 5 |
| 持仓页面完整重写 | Task 6 |
| AI 买入/卖出确认框（含预填比例） | Task 6 |
| 顶部账户概览栏 | Task 6 |
| 回测统计卡片 | Task 6 |
| 旧文件清理 | Task 7 |
