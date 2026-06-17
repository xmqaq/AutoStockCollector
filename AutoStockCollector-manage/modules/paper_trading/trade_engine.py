from datetime import datetime, time as dtime
from utils.helpers import beijing_now
from typing import Any, Dict, List, Optional, Tuple

COMMISSION_RATE = 0.0003
COMMISSION_MIN = 5.0
STAMP_TAX_RATE = 0.001


def is_trading_time() -> bool:
    now = beijing_now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    morning = dtime(9, 30) <= t <= dtime(11, 30)
    afternoon = dtime(13, 0) <= t <= dtime(15, 0)
    return morning or afternoon


class TradeEngine:
    def __init__(self):
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        self._trades = db["trade_records"]

    def _fetch_tencent_parts(self, code: str) -> Optional[list]:
        """腾讯行情接口，返回字段数组。parts[3]=现价，parts[4]=昨收。"""
        import re
        try:
            import requests as _req
            r = _req.get(
                f"https://qt.gtimg.cn/q={code.lower()}",
                proxies={"http": "", "https": ""},
                timeout=5,
            )
            m = re.search(rf'v_{code.lower()}="([^"]+)"', r.text)
            if m:
                return m.group(1).split("~")
        except Exception:
            pass
        return None

    def _get_realtime_price(self, code: str) -> Optional[float]:
        """腾讯行情接口取实时价，与深度分析模块一致。"""
        parts = self._fetch_tencent_parts(code)
        if parts and len(parts) > 3 and parts[3]:
            try:
                return float(parts[3]) or None
            except ValueError:
                pass
        return None

    def _get_realtime_prev_close(self, code: str) -> Optional[float]:
        """腾讯行情接口取昨收（parts[4]），与现价同源，和券商/东财展示一致。"""
        parts = self._fetch_tencent_parts(code)
        if parts and len(parts) > 4 and parts[4]:
            try:
                return float(parts[4]) or None
            except ValueError:
                pass
        return None

    def _batch_tencent_quotes(self, codes: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
        """一次请求多只股票，返回 {CODE: {"price":现价, "prev_close":昨收}}。

        腾讯行情支持 q=sh600549,sz000001 多股一次拉取，避免每只持仓 2 次串行 HTTP。
        """
        result: Dict[str, Dict[str, Optional[float]]] = {}
        if not codes:
            return result
        import re
        try:
            import requests as _req
            query = ",".join(c.lower() for c in codes)
            r = _req.get(
                f"https://qt.gtimg.cn/q={query}",
                proxies={"http": "", "https": ""},
                timeout=8,
            )
            for code in codes:
                m = re.search(rf'v_{code.lower()}="([^"]+)"', r.text)
                if not m:
                    continue
                parts = m.group(1).split("~")
                if len(parts) > 4:
                    try:
                        price = float(parts[3]) if parts[3] else None
                        prev = float(parts[4]) if parts[4] else None
                    except ValueError:
                        continue
                    result[code] = {"price": price or None, "prev_close": prev or None}
        except Exception:
            pass
        return result

    def _get_db_price(self, code: str) -> Optional[float]:
        try:
            from core.storage.mongo_storage import FundFlowStorage
            storage = FundFlowStorage()
            doc = storage.get_latest_flow(code)
            if doc:
                for field in ('close', 'price', '收盘价'):
                    if doc.get(field):
                        return float(doc[field])
        except Exception:
            pass
        try:
            from core.storage.mongo_storage import KlineStorage
            storage = KlineStorage()
            kline = storage.find_one({"code": code}, sort=[("date", -1)])
            if kline:
                return float(kline.get("close", 0)) or None
        except Exception:
            pass
        return None

    def get_current_price(self, code: str) -> Tuple[Optional[float], str]:
        # 优先尝试腾讯行情（盘中返回实时价，收盘后返回当日收盘价）
        price = self._get_realtime_price(code)
        if price:
            return price, 'realtime' if is_trading_time() else 'close'
        db_price = self._get_db_price(code)
        if db_price:
            return db_price, 'close'
        return None, 'unknown'

    def _get_yesterday_close(self, code: str) -> Optional[float]:
        # 优先用腾讯行情昨收（与现价同源，和券商/东财一致，无需依赖日K入库时机）
        rt = self._get_realtime_prev_close(code)
        if rt and rt > 0:
            return rt
        # 回退到 K 线库。注意：盘中当日日K尚未生成，最新一条即为昨收；
        # 收盘后当日日K已入库，最新一条是今日，需取上一条。
        # 旧逻辑无条件取倒数第二条，盘中会把"前天"当成昨收，今日%变两天累计涨幅。
        try:
            from core.storage.mongo_storage import KlineStorage
            storage = KlineStorage()
            today = beijing_now().strftime("%Y-%m-%d")
            klines = storage.find_many(
                {"code": code}, sort=[("date", -1)], limit=2
            )
            if not klines:
                return None
            latest = klines[0]
            if str(latest.get("date", "")) >= today and len(klines) >= 2:
                return float(klines[1].get("close", 0)) or None
            return float(latest.get("close", 0)) or None
        except Exception:
            pass
        return None

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

    def get_positions(self, user_id: str = "default") -> Tuple[List[Dict[str, Any]], bool]:
        # 按成交时间顺序回放，用「移动加权平均成本法」算持仓成本：
        #   - 买入：股数累加，成本累加「含佣金的 total_cost」（而非仅 amount）；
        #   - 卖出：按当前均价等比例冲减成本（cost × 卖出股数/当前持股）。
        # 旧实现用 buy_amount/buy_shares 的全历史均值，且 amount 不含佣金，
        # 导致「卖出后再以不同价买回」成本算歪、单只盈亏恒少算一笔买入佣金。
        trades = list(self._trades.find({"user_id": user_id}, sort=[("traded_at", 1)]))

        book: Dict[str, Dict[str, Any]] = {}
        for t in trades:
            code = t.get("code")
            if not code:
                continue
            b = book.setdefault(code, {"name": code, "shares": 0, "cost": 0.0})
            if t.get("name"):
                b["name"] = t["name"]
            shares = t.get("shares", 0) or 0
            if t.get("action") == "buy":
                cost = t.get("total_cost")
                if cost is None:
                    amount = t.get("amount")
                    if amount is None:
                        amount = shares * (t.get("price") or 0)
                    cost = amount + (t.get("commission") or 0)
                b["shares"] += shares
                b["cost"] += cost
            elif t.get("action") == "sell":
                if b["shares"] > 0:
                    sell_shares = min(shares, b["shares"])
                    b["cost"] -= b["cost"] * (sell_shares / b["shares"])
                    b["shares"] -= sell_shares

        trading = is_trading_time()
        # 批量拉行情：所有持仓一次 HTTP 取齐现价+昨收，避免逐只 2 次串行请求
        held_codes = [c for c, b in book.items() if b["shares"] > 0]
        quotes = self._batch_tencent_quotes(held_codes)

        positions = []
        for code in held_codes:
            b = book[code]
            shares_held = b["shares"]
            avg_cost = b["cost"] / shares_held if shares_held > 0 else 0

            q = quotes.get(code) or {}
            price = q.get("price")
            price_type = ('realtime' if trading else 'close') if price else None
            if not price or price <= 0:
                # 批量未命中（停牌/接口异常）才回退到单只查询（含 DB 兜底）
                price, price_type = self.get_current_price(code)
            if not price or price <= 0:
                price = avg_cost
                price_type = 'fallback'
            market_value = shares_held * price
            cost_basis = b["cost"]
            pnl = market_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

            yesterday_close = q.get("prev_close")
            if not yesterday_close or yesterday_close <= 0:
                yesterday_close = self._get_yesterday_close(code)
            today_pnl_pct = 0.0
            if yesterday_close and yesterday_close > 0:
                today_pnl_pct = (price - yesterday_close) / yesterday_close * 100

            positions.append({
                "code": code,
                "name": b["name"],
                "shares": shares_held,
                "avg_cost": round(avg_cost, 4),
                "current_price": round(price, 2),
                "market_value": round(market_value, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_pct, 2),
                "today_pnl_percent": round(today_pnl_pct, 2),
                "yesterday_close": round(yesterday_close, 2) if yesterday_close else None,
                "price_type": price_type,
                "position_ratio": 0,
            })

        total_market = sum(p["market_value"] for p in positions)
        for p in positions:
            p["position_ratio"] = round(p["market_value"] / total_market * 100, 2) if total_market > 0 else 0

        return sorted(positions, key=lambda x: x["market_value"], reverse=True), trading

    def buy(
        self,
        user_id: str,
        code: str,
        shares: int,
        ai_signal: Dict[str, Any],
        account,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        if price is None or price <= 0:
            p, _ = self.get_current_price(code)
            if not p or p <= 0:
                raise ValueError(f"无法获取 {code} 的最新价格")
            price = p

        if shares % 100 != 0:
            raise ValueError("买入数量必须为100的整数倍")

        amount = shares * price
        commission = round(max(COMMISSION_MIN, amount * COMMISSION_RATE), 2)
        total_cost = round(amount + commission, 2)

        account_doc = account.get(user_id)
        if not account_doc:
            raise ValueError("账户未初始化，请先设置初始资金")

        cash = account_doc["cash_balance"]
        if cash < total_cost:
            raise ValueError(f"现金不足，需要 {total_cost:.2f} 元，可用 {cash:.2f} 元")

        cash_after = round(cash - total_cost, 2)
        record = {
            "user_id": user_id,
            "code": code,
            "name": self._get_name(code),
            "action": "buy",
            "shares": shares,
            "price": round(price, 4),
            "amount": round(amount, 2),
            "commission": commission,
            "total_cost": total_cost,
            "ai_signal": ai_signal,
            "cash_before": cash,
            "cash_after": cash_after,
            "traded_at": beijing_now().isoformat(),
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
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        pos_list, _ = self.get_positions(user_id)
        pos = next((p for p in pos_list if p["code"] == code), None)
        if not pos:
            raise ValueError(f"未持有 {code}")
        if pos["shares"] < shares:
            raise ValueError(f"持仓不足，当前 {pos['shares']} 股，尝试卖出 {shares} 股")

        if shares % 100 != 0 and shares != pos["shares"]:
            raise ValueError("卖出数量必须为100的整数倍（或全部卖出）")

        if price is None or price <= 0:
            p, _ = self.get_current_price(code)
            if not p or p <= 0:
                raise ValueError(f"无法获取 {code} 的最新价格")
            price = p

        amount = shares * price
        stamp_tax = round(amount * STAMP_TAX_RATE, 2)
        commission = round(max(COMMISSION_MIN, amount * COMMISSION_RATE), 2)
        actual_gain = round(amount - stamp_tax - commission, 2)

        cost_price = pos["avg_cost"]
        profit = round((price - cost_price) * shares - stamp_tax - commission, 2)

        account_doc = account.get(user_id)
        if not account_doc:
            raise ValueError("账户未初始化，请先设置初始资金")
        cash = account_doc["cash_balance"]
        cash_after = round(cash + actual_gain, 2)

        record = {
            "user_id": user_id,
            "code": code,
            "name": pos["name"],
            "action": "sell",
            "shares": shares,
            "price": round(price, 4),
            "amount": round(amount, 2),
            "stamp_tax": stamp_tax,
            "commission": commission,
            "actual_gain": actual_gain,
            "profit": profit,
            "ai_signal": ai_signal,
            "cash_before": cash,
            "cash_after": cash_after,
            "traded_at": beijing_now().isoformat(),
        }
        self._trades.insert_one(record)
        account.update_cash(user_id, cash_after)
        record.pop("_id", None)
        return record
