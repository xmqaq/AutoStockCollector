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
                    pnl_amount = (price - head["price"]) * matched
                    completed_pairs.append({"pnl_pct": pnl_pct, "pnl_amount": pnl_amount})
                    head["shares"] -= matched
                    remaining -= matched
                buy_queue[code] = [h for h in buy_queue.get(code, []) if h["shares"] > 0]

        # 累计手续费 = 所有成交的佣金 + 印花税（买入只有佣金，卖出含印花税）
        total_fee = sum((t.get("commission") or 0) + (t.get("stamp_tax") or 0) for t in trades)

        total_pairs = len(completed_pairs)
        # 平本（pnl=0）既不算盈也不算亏，但仍计入完成交易次数
        wins = [p for p in completed_pairs if p["pnl_amount"] > 0]
        losses = [p for p in completed_pairs if p["pnl_amount"] < 0]

        win_rate = len(wins) / total_pairs * 100 if total_pairs > 0 else 0
        avg_profit = sum(p["pnl_pct"] for p in wins) / len(wins) if wins else 0
        avg_loss = sum(p["pnl_pct"] for p in losses) / len(losses) if losses else 0
        # 盈亏比 = 总盈利额 / 总亏损额（计入仓位大小），优于"平均盈利%/平均亏损%"
        gross_profit = sum(p["pnl_amount"] for p in wins)
        gross_loss = abs(sum(p["pnl_amount"] for p in losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0

        return {
            "total_trades": total_pairs,
            "win_trades": len(wins),
            "loss_trades": len(losses),
            "win_rate": round(win_rate, 2),
            "avg_profit_pct": round(avg_profit, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "profit_factor": profit_factor,
            "total_fee": round(total_fee, 2),
        }

    def get_nav(self, user_id: str, account) -> List[Dict[str, Any]]:
        """每日净值序列（仅 portfolio_snapshots 缺失时的回退）。

        回放成交并用「最近成交价」给未平仓持仓估值，得到每个交易日末的净值
        （现金 + 持仓市值）。旧实现 nav = cash_after/initial 完全忽略持仓市值，
        导致一买入净值就塌方。这里用成交价估值是近似（无当日收盘价时的兜底），
        但已平仓/最新一笔的净值是精确的。
        """
        trades = list(self._trades.find({"user_id": user_id}, sort=[("traded_at", 1)]))
        account_doc = account.get(user_id)
        if not account_doc or not trades:
            return []

        initial = account_doc["initial_capital"]
        holdings: Dict[str, Dict[str, float]] = {}
        daily_net: Dict[str, float] = {}
        for t in trades:
            code = t.get("code")
            h = holdings.setdefault(code, {"shares": 0, "price": 0.0})
            h["price"] = t.get("price") or h["price"]
            shares = t.get("shares", 0) or 0
            if t.get("action") == "buy":
                h["shares"] += shares
            elif t.get("action") == "sell":
                h["shares"] = max(0, h["shares"] - shares)
            cash = t.get("cash_after", 0)
            market_value = sum(x["shares"] * x["price"] for x in holdings.values())
            date = t["traded_at"][:10]
            daily_net[date] = cash + market_value

        return [
            {
                "date": date,
                "net_value": round(daily_net[date], 2),
                "nav": round(daily_net[date] / initial, 4) if initial > 0 else 1.0,
            }
            for date in sorted(daily_net)
        ]
