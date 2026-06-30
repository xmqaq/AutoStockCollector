import math
from datetime import datetime, time as dtime
from utils.helpers import beijing_now, is_trading_day, get_market_session
from utils.logger import get_logger
from typing import Any, Dict, List, Optional, Tuple

logger = get_logger(__name__)

COMMISSION_RATE = 0.0003
COMMISSION_MIN = 5.0
STAMP_TAX_RATE = 0.001


def is_trading_time() -> bool:
    """是否处于连续竞价时段（可即时成交）。节假日返回 False。

    集合竞价（9:15-9:25）不算"可即时成交"——按"开盘即按市价成交"策略，
    此时的挂单等 09:30 连续竞价开盘后统一按实时价撮合。
    """
    return get_market_session() == "continuous"


class TradeEngine:
    def __init__(self):
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        self._trades = db["trade_records"]
        self._orders = db["paper_orders"]  # 订单表（pending/filled/cancelled）

    def _fees(self) -> Dict[str, float]:
        """读取平台费率配置；配置不可用时回退到模块默认常量。"""
        try:
            from modules.platform.config import PlatformConfig
            return PlatformConfig().get()
        except Exception:
            return {
                "buy_commission_rate": COMMISSION_RATE,
                "sell_commission_rate": COMMISSION_RATE,
                "min_commission": COMMISSION_MIN,
                "stamp_tax_rate": STAMP_TAX_RATE,
            }

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

        # 当日盈亏用「券商口径的逐日盯市」：当日盈亏 = 现市值 + 当日卖出额 − 当日买入额
        #   − 昨日持仓市值(隔夜股数×昨收)。这样「当天新建仓」的盈亏基准是你的买入价，
        # 而非昨收——否则会把「昨收→你买入价」这段你没吃到的涨幅也算进当日盈亏。
        today = beijing_now().strftime("%Y-%m-%d")

        book: Dict[str, Dict[str, Any]] = {}
        stop_losses: Dict[str, float] = {}
        take_profits: Dict[str, float] = {}
        for t in trades:
            code = t.get("code")
            if not code:
                continue
            b = book.setdefault(code, {
                "name": code, "shares": 0, "cost": 0.0,
                "prev_shares": None, "today_buy_amt": 0.0, "today_sell_amt": 0.0,
                "today_buy_shares": 0,  # T+1：当日买入股数（当日不可卖）
            })
            if t.get("name"):
                b["name"] = t["name"]
            is_today = str(t.get("traded_at", ""))[:10] == today
            # 第一笔「今日成交」前的持股数 = 隔夜持仓（昨收口径的基准股数）
            if is_today and b["prev_shares"] is None:
                b["prev_shares"] = b["shares"]
            shares = t.get("shares", 0) or 0
            amount = t.get("amount")
            if amount is None:
                amount = shares * (t.get("price") or 0)
            if t.get("action") == "buy":
                cost = t.get("total_cost")
                if cost is None:
                    cost = amount + (t.get("commission") or 0)
                b["shares"] += shares
                b["cost"] += cost
                if is_today:
                    b["today_buy_amt"] += amount
                    b["today_buy_shares"] += shares  # T+1 锁定
                sl = t.get("stop_loss")
                tp = t.get("take_profit")
                if sl:
                    stop_losses[code] = float(sl)
                if tp:
                    take_profits[code] = float(tp)
            elif t.get("action") == "sell":
                if b["shares"] > 0:
                    sell_shares = min(shares, b["shares"])
                    b["cost"] -= b["cost"] * (sell_shares / b["shares"])
                    b["shares"] -= sell_shares
                if is_today:
                    b["today_sell_amt"] += amount

        trading = is_trading_time()
        # 批量拉行情：所有持仓一次 HTTP 取齐现价+昨收，避免逐只 2 次串行请求
        held_codes = [c for c, b in book.items() if b["shares"] > 0]
        quotes = self._batch_tencent_quotes(held_codes)

        # T+1 / 挂单冻结：汇总该用户所有 pending 卖出单的股数，作为 frozen_shares。
        # 挂卖单时只校验"可卖份额"，pending 期间这部分股数视为已冻结、不可重复挂卖。
        frozen_by_code: Dict[str, int] = {}
        for o in self._orders.find(
            {"user_id": user_id, "action": "sell", "status": "pending"},
            {"code": 1, "shares": 1, "_id": 0},
        ):
            frozen_by_code[o.get("code", "")] = frozen_by_code.get(o.get("code", ""), 0) + (o.get("shares") or 0)

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

            # 当日盈亏（金额）：逐日盯市口径，当天买入按买入价、隔夜持仓按昨收为基准。
            prev_shares = b["prev_shares"]
            if prev_shares is None:
                prev_shares = shares_held  # 无今日成交 → 全部隔夜持仓
            today_pnl_amount = 0.0
            if yesterday_close and yesterday_close > 0:
                today_pnl_amount = (
                    market_value + b["today_sell_amt"] - b["today_buy_amt"]
                    - prev_shares * yesterday_close
                )

            sl_price = stop_losses.get(code)
            tp_price = take_profits.get(code)
            sl_hit = False
            tp_hit = False
            if sl_price and price and price <= sl_price:
                sl_hit = True
            if tp_price and price and price >= tp_price:
                tp_hit = True

            # T+1：可卖股数 = 总持仓 - 当日买入 - 卖出挂单冻结。
            today_buy = b.get("today_buy_shares", 0)
            frozen_shares = frozen_by_code.get(code, 0)
            available_shares = max(0, shares_held - today_buy - frozen_shares)

            positions.append({
                "code": code,
                "name": b["name"],
                "shares": shares_held,
                "available_shares": available_shares,  # T+1 + 挂单冻结后可卖
                "frozen_shares": frozen_shares,        # 卖出挂单冻结
                "today_buy_shares": today_buy,         # 当日买入（T+1 锁定）
                "avg_cost": round(avg_cost, 4),
                "current_price": round(price, 2),
                "market_value": round(market_value, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_pct, 2),
                "today_pnl_percent": round(today_pnl_pct, 2),
                "today_pnl_amount": round(today_pnl_amount, 2),
                "yesterday_close": round(yesterday_close, 2) if yesterday_close else None,
                "price_type": price_type,
                "position_ratio": 0,
                "stop_loss": round(sl_price, 2) if sl_price else None,
                "take_profit": round(tp_price, 2) if tp_price else None,
                "sl_hit": sl_hit,
                "tp_hit": tp_hit,
            })

        total_market = sum(p["market_value"] for p in positions)
        for p in positions:
            p["position_ratio"] = round(p["market_value"] / total_market * 100, 2) if total_market > 0 else 0

        exited_codes = self._auto_exit_sl_tp(user_id, positions, quotes)
        if exited_codes:
            return self.get_positions(user_id)

        return sorted(positions, key=lambda x: x["market_value"], reverse=True), trading

    def _auto_exit_sl_tp(
        self, user_id: str, positions: List[Dict], quotes: Dict[str, Dict],
    ) -> List[str]:
        """检查所有持仓的 SL/TP，触发则自动市价卖出。返回已平仓的 code 列表。"""
        exited = []
        for pos in positions:
            if pos["shares"] <= 0:
                continue
            code = pos["code"]
            price = pos["current_price"]
            sl_hit = pos.get("sl_hit", False)
            tp_hit = pos.get("tp_hit", False)
            if not sl_hit and not tp_hit:
                continue
            # T+1：自动止损止盈只能平"可卖"份额，当日买入部分不可卖。
            available = pos.get("available_shares", 0)
            if available <= 0:
                logger.info(f"[AutoExit] {code} 触发但 T+1 锁定无可卖份额，跳过")
                continue
            reason = "止损" if sl_hit else "止盈"
            sell_shares = available if available < pos["shares"] else pos["shares"]
            try:
                from modules.paper_trading.account import PaperAccount
                acc = PaperAccount()
                record = self.sell(
                    user_id, code, sell_shares,
                    ai_signal={"source": "pa_auto_exit", "reason": reason},
                    account=acc,
                    price=price,
                    immediate=True,  # 自动交易绕过挂单判断，直接成交
                )
                logger.info(f"[AutoExit] {code} {reason} 触发: {sell_shares}股 @{price}")
                exited.append(code)
            except Exception as e:
                logger.warning(f"[AutoExit] {code} {reason} 失败: {e}")
        return exited

    def _compute_fees(self, action: str, shares: int, price: float) -> Dict[str, float]:
        """计算手续费。买入=佣金；卖出=佣金+印花税。返回 amount/commission/stamp_tax/total_cost/actual_gain。"""
        fees = self._fees()
        amount = shares * price
        if action == "buy":
            commission = round(max(fees["min_commission"], amount * fees["buy_commission_rate"]), 2)
            return {
                "amount": round(amount, 2),
                "commission": commission,
                "stamp_tax": 0.0,
                "total_cost": round(amount + commission, 2),
                "actual_gain": 0.0,
            }
        else:
            stamp_tax = round(amount * fees["stamp_tax_rate"], 2)
            commission = round(max(fees["min_commission"], amount * fees["sell_commission_rate"]), 2)
            actual_gain = round(amount - stamp_tax - commission, 2)
            return {
                "amount": round(amount, 2),
                "commission": commission,
                "stamp_tax": stamp_tax,
                "total_cost": 0.0,
                "actual_gain": actual_gain,
            }

    def _create_order(
        self, user_id: str, code: str, action: str, shares: int,
        ai_signal: Dict[str, Any], account, price: Optional[float] = None,
        stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """创建一条 pending 订单。买入冻结资金，卖出冻结股数（股数冻结由 pending sell
        order 的存在性在 get_positions 回放时体现，无需显式记账）。返回订单文档。"""
        if price is None or price <= 0:
            p, _ = self.get_current_price(code)
            if not p or p <= 0:
                raise ValueError(f"无法获取 {code} 的最新价格")
            price = p

        if shares % 100 != 0:
            raise ValueError("下单数量必须为100的整数倍")

        account_doc = account.get(user_id)
        if not account_doc:
            raise ValueError("账户未初始化，请先设置初始资金")

        name = self._get_name(code) if action == "buy" else None
        now = beijing_now().isoformat()
        order = {
            "user_id": user_id,
            "code": code,
            "name": name,
            "action": action,
            "shares": shares,
            "price": round(price, 4),  # 下单参考价（展示用），成交价以撮合时实时价为准
            "status": "pending",
            "ai_signal": ai_signal,
            "stop_loss": round(stop_loss, 2) if stop_loss else None,
            "take_profit": round(take_profit, 2) if take_profit else None,
            "created_at": now,
            "filled_at": None,
            "filled_price": None,
            "cancel_reason": None,
            "trade_record_id": None,
        }

        if action == "buy":
            # 买入挂单冻结资金：用下单参考价预估冻结额，撮合时按实际价补差。
            fees = self._compute_fees("buy", shares, price)
            frozen = fees["total_cost"]
            available_cash = account.get_available_cash(user_id)
            if available_cash < frozen:
                raise ValueError(f"可用资金不足，需要 {frozen:.2f} 元，可用 {available_cash:.2f} 元（含冻结）")
            account.freeze_cash(user_id, frozen)
            order["frozen_cash"] = frozen
        else:
            # 卖出挂单：校验可卖份额（T+1 + 已挂卖单冻结）。
            pos_list, _ = self.get_positions(user_id)
            pos = next((p for p in pos_list if p["code"] == code), None)
            if not pos:
                raise ValueError(f"未持有 {code}")
            available = pos.get("available_shares", 0)
            if available < shares:
                raise ValueError(
                    f"可卖份额不足，当前可卖 {available} 股（T+1锁定/挂单冻结），尝试卖出 {shares} 股"
                )
            if shares % 100 != 0 and shares != pos["shares"]:
                raise ValueError("卖出数量必须为100的整数倍（或全部卖出）")
            order["name"] = pos["name"]

        result = self._orders.insert_one(order)
        order["_id"] = result.inserted_id
        return order

    def _fill_now(
        self, order: Dict[str, Any], account, price: Optional[float] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """把一条 pending 订单按给定价格（默认取实时价）撮合成交：写 trade_records +
        订单标 filled + 资金从冻结转实扣/到账。force=True 跳过 T+1 校验（自动交易豁免）。"""
        if order.get("status") != "pending":
            raise ValueError(f"订单 {order.get('_id')} 非 pending 状态，无法成交")

        user_id = order["user_id"]
        code = order["code"]
        action = order["action"]
        shares = order["shares"]

        if price is None or price <= 0:
            p, _ = self.get_current_price(code)
            if not p or p <= 0:
                raise ValueError(f"无法获取 {code} 的最新价格")
            price = p

        if action == "sell" and not force:
            # T+1 复核（pending 期间持仓可能变化）：再次校验可卖份额。
            pos_list, _ = self.get_positions(user_id)
            pos = next((p for p in pos_list if p["code"] == code), None)
            if not pos:
                raise ValueError(f"成交失败：已不持有 {code}")
            available = pos.get("available_shares", 0)
            if available < shares:
                raise ValueError(f"成交失败：可卖份额不足（T+1），可卖 {available} 股")

        fees = self._compute_fees(action, shares, price)
        account_doc = account.get(user_id)
        if not account_doc:
            raise ValueError("账户未初始化，请先设置初始资金")
        cash = account_doc["cash_balance"]

        now = beijing_now().isoformat()
        if action == "buy":
            # 先解冻挂单时按参考价冻结的资金，再按实际成交价扣减现金。
            frozen = order.get("frozen_cash") or fees["total_cost"]
            account.unfreeze_cash(user_id, frozen)
            cash_after = round(cash - fees["total_cost"], 2)
            if cash_after < 0:
                # 参考价低于成交价导致资金缺口，回滚冻结并撤单。
                account.freeze_cash(user_id, frozen)
                raise ValueError(f"成交价高于下单价，现金不足，需要 {fees['total_cost']:.2f} 元，可用 {cash:.2f} 元")
            record = {
                "user_id": user_id, "code": code, "name": self._get_name(code),
                "action": "buy", "shares": shares, "price": round(price, 4),
                "amount": fees["amount"], "commission": fees["commission"],
                "total_cost": fees["total_cost"],
                "stop_loss": order.get("stop_loss"), "take_profit": order.get("take_profit"),
                "ai_signal": order.get("ai_signal"),
                "cash_before": cash, "cash_after": cash_after, "traded_at": now,
            }
            self._trades.insert_one(record)
            account.update_cash(user_id, cash_after)
        else:
            cost_price = 0.0
            pos_list, _ = self.get_positions(user_id)
            pos = next((p for p in pos_list if p["code"] == code), None)
            if pos:
                cost_price = pos["avg_cost"]
            profit = round((price - cost_price) * shares - fees["stamp_tax"] - fees["commission"], 2)
            cash_after = round(cash + fees["actual_gain"], 2)
            record = {
                "user_id": user_id, "code": code, "name": order.get("name") or code,
                "action": "sell", "shares": shares, "price": round(price, 4),
                "amount": fees["amount"], "stamp_tax": fees["stamp_tax"],
                "commission": fees["commission"], "actual_gain": fees["actual_gain"],
                "profit": profit, "ai_signal": order.get("ai_signal"),
                "cash_before": cash, "cash_after": cash_after, "traded_at": now,
            }
            self._trades.insert_one(record)
            account.update_cash(user_id, cash_after)

        record.pop("_id", None)
        self._orders.update_one(
            {"_id": order["_id"]},
            {"$set": {
                "status": "filled", "filled_at": now, "filled_price": round(price, 4),
                "trade_record_id": str(record.get("traded_at")),
            }},
        )
        return {"status": "filled", "trade": record, "order_id": str(order["_id"])}

    def _cancel_order(self, order_id: str, reason: str = "用户撤单") -> Dict[str, Any]:
        """撤单：买入解冻资金，卖出无需处理（pending sell 不持币）。"""
        from bson import ObjectId
        try:
            oid = ObjectId(order_id)
        except Exception:
            raise ValueError("无效的订单ID")
        order = self._orders.find_one({"_id": oid})
        if not order:
            raise ValueError("订单不存在")
        if order.get("status") != "pending":
            raise ValueError(f"订单已 {order.get('status')}，无法撤单")

        if order.get("action") == "buy" and order.get("frozen_cash"):
            from modules.paper_trading.account import PaperAccount
            PaperAccount().unfreeze_cash(order["user_id"], order["frozen_cash"])

        self._orders.update_one(
            {"_id": oid},
            {"$set": {"status": "cancelled", "cancel_reason": reason,
                      "filled_at": beijing_now().isoformat()}},
        )
        order["status"] = "cancelled"
        order["cancel_reason"] = reason
        order.pop("_id", None)
        return order

    def _match_pending_orders(self) -> int:
        """盘中撮合：扫所有 pending 单，取实时价成交。返回成交笔数。
        仅在连续竞价时段由 cron 调用；非交易时段直接返回 0。"""
        if not is_trading_time():
            return 0
        from modules.paper_trading.account import PaperAccount
        acc = PaperAccount()
        matched = 0
        orders = list(self._orders.find({"status": "pending"}, sort=[("created_at", 1)]))
        for order in orders:
            try:
                self._fill_now(order, acc)
                matched += 1
                logger.info(f"[Match] 订单 {order['_id']} {order['action']} {order['code']} 成交")
            except Exception as e:
                # 成交失败（资金不足/T+1/取价失败）保持 pending，等下次撮合或收盘清算。
                logger.warning(f"[Match] 订单 {order['_id']} 撮合失败: {e}")
        return matched

    def _market_close_settle(self) -> int:
        """收盘清算：撤所有未成交 pending 单，解冻资金。返回撤单笔数。"""
        orders = list(self._orders.find({"status": "pending"}))
        cancelled = 0
        for order in orders:
            try:
                self._cancel_order(str(order["_id"]), reason="收盘自动撤单（当日未成交）")
                cancelled += 1
            except Exception as e:
                logger.warning(f"[CloseSettle] 订单 {order['_id']} 撤单失败: {e}")
        return cancelled

    def buy(
        self,
        user_id: str,
        code: str,
        shares: int,
        ai_signal: Dict[str, Any],
        account,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        immediate: bool = False,
    ) -> Dict[str, Any]:
        """提交买入订单。

        - immediate=True（自动交易）：建 pending 订单后立即撮合成交，等价旧的"即时成交"。
        - immediate=False（手动下单，API 默认）：连续竞价时段立即成交；非交易时段仅挂单 pending，
          等开盘后由 cron 撮合或收盘清算撤单。
        返回 {status, trade?, order?}。
        """
        order = self._create_order(
            user_id, code, "buy", shares, ai_signal, account,
            price=price, stop_loss=stop_loss, take_profit=take_profit,
        )
        if immediate or is_trading_time():
            return self._fill_now(order, account, price=price)
        order_id = str(order["_id"])
        order.pop("_id", None)
        return {"status": "pending", "order": order, "order_id": order_id}

    def sell(
        self,
        user_id: str,
        code: str,
        shares: int,
        ai_signal: Dict[str, Any],
        account,
        price: Optional[float] = None,
        immediate: bool = False,
        force: bool = False,
    ) -> Dict[str, Any]:
        """提交卖出订单。T+1：当日买入不可卖（force=True 可豁免，仅竞价雷达等自动日内策略用）。

        返回 {status, trade?, order?}。
        """
        order = self._create_order(
            user_id, code, "sell", shares, ai_signal, account, price=price,
        )
        if immediate or is_trading_time():
            return self._fill_now(order, account, price=price, force=force)
        order_id = str(order["_id"])
        order.pop("_id", None)
        return {"status": "pending", "order": order, "order_id": order_id}
