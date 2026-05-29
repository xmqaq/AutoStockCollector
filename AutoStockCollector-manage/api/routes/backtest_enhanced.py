"""
增强回测相关接口
包含：详细回测报告、Equity曲线、交易记录、月度统计
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from typing import Dict, List
import random

backtest_enhanced_bp = Blueprint("backtest_enhanced", __name__, url_prefix="/api/v1/backtest/enhanced")


def generate_mock_equity_curve(days: int = 90, initial_cash: float = 1000000) -> List[Dict]:
    """生成模拟Equity曲线数据"""
    result = []
    value = initial_cash
    for i in range(days):
        date = datetime.now() - timedelta(days=days-i)
        change = (random.random() - 0.45) * 0.02 * value
        value += change
        result.append({
            "date": date.strftime("%Y-%m-%d"),
            "value": round(value, 2),
        })
    return result


def generate_mock_trades(codes: List[str], count: int = 30) -> List[Dict]:
    """生成模拟交易记录"""
    trades = []
    directions = ["buy", "sell"]
    
    for i in range(count):
        direction = random.choice(directions)
        date = datetime.now() - timedelta(days=random.randint(1, 60))
        price = round(random.uniform(10, 100), 2)
        amount = random.randint(100, 1000) * 100
        
        trades.append({
            "date": date.strftime("%Y-%m-%d"),
            "code": random.choice(codes) if codes else "SH600000",
            "type": direction,
            "price": price,
            "amount": amount,
            "pnl": round(random.uniform(-500, 1500), 2) if direction == "sell" else 0,
            "reason": random.choice(["技术金叉", "资金流入", "止盈", "止损", "RSI超买"]),
        })
    
    trades.sort(key=lambda x: x["date"], reverse=True)
    return trades


def generate_mock_monthly_stats() -> List[Dict]:
    """生成模拟月度统计数据"""
    months = ["1月", "2月", "3月", "4月", "5月", "6月"]
    return [
        {"month": m, "return": round(random.uniform(-3, 5), 2)}
        for m in months
    ]


@backtest_enhanced_bp.route("/report", methods=["POST"])
def get_enhanced_report():
    """获取增强版回测报告"""
    data = request.get_json() or {}
    strategy = data.get("strategy", "")
    codes = data.get("codes", ["SH600000"])
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    initial_cash = data.get("initial_cash", 1000000)
    
    equity_curve = generate_mock_equity_curve(90, initial_cash)
    trades = generate_mock_trades(codes, 30)
    monthly_stats = generate_mock_monthly_stats()
    
    final_value = equity_curve[-1]["value"] if equity_curve else initial_cash
    total_return = ((final_value - initial_cash) / initial_cash) * 100
    
    win_trades = [t for t in trades if t["type"] == "sell" and t["pnl"] > 0]
    lose_trades = [t for t in trades if t["type"] == "sell" and t["pnl"] <= 0]
    
    win_rate = len(win_trades) / max(1, len(win_trades) + len(lose_trades)) * 100
    
    return jsonify({
        "success": True,
        "report": {
            "strategy": strategy,
            "codes": codes,
            "start_date": start_date,
            "end_date": end_date,
            "initial_cash": initial_cash,
            "final_value": round(final_value, 2),
            "total_return": round(total_return, 2),
            "annual_return": round(total_return * 365 / 90, 2),
            "max_drawdown": round(random.uniform(3, 8), 2),
            "sharpe_ratio": round(random.uniform(1.0, 2.5), 2),
            "win_rate": round(win_rate, 1),
            "total_trades": len(trades),
            "equity_curve": equity_curve,
            "monthly_stats": monthly_stats,
        },
        "sample_trades": trades[:20],
        "win_stats": {
            "winning": len(win_trades),
            "losing": len(lose_trades),
            "avg_profit": round(random.uniform(1.5, 3.0), 2),
            "avg_loss": round(random.uniform(-2.0, -0.8), 2),
            "profit_loss_ratio": round(random.uniform(1.5, 2.5), 2),
        },
    })


@backtest_enhanced_bp.route("/equity", methods=["POST"])
def get_equity_curve():
    """获取Equity曲线"""
    data = request.get_json() or {}
    initial_cash = data.get("initial_cash", 1000000)
    days = int(data.get("days", 90))
    
    equity_curve = generate_mock_equity_curve(days, initial_cash)
    
    return jsonify({
        "success": True,
        "data": equity_curve,
    })


@backtest_enhanced_bp.route("/trades", methods=["POST"])
def get_trade_history():
    """获取交易历史"""
    data = request.get_json() or {}
    codes = data.get("codes", [])
    limit = int(data.get("limit", 50))
    
    trades = generate_mock_trades(codes, limit)
    
    return jsonify({
        "success": True,
        "count": len(trades),
        "data": trades,
    })


@backtest_enhanced_bp.route("/monthly", methods=["POST"])
def get_monthly_stats():
    """获取月度收益统计"""
    monthly_stats = generate_mock_monthly_stats()
    
    return jsonify({
        "success": True,
        "data": monthly_stats,
    })


@backtest_enhanced_bp.route("/win-rate", methods=["POST"])
def get_win_rate_analysis():
    """获取胜率分析"""
    data = request.get_json() or {}
    codes = data.get("codes", [])
    
    trades = generate_mock_trades(codes, 50)
    sell_trades = [t for t in trades if t["type"] == "sell"]
    
    win_trades = [t for t in sell_trades if t["pnl"] > 0]
    lose_trades = [t for t in sell_trades if t["pnl"] <= 0]
    
    total_pnl = sum(t["pnl"] for t in sell_trades)
    total_win_pnl = sum(t["pnl"] for t in win_trades)
    total_lose_pnl = abs(sum(t["pnl"] for t in lose_trades))
    
    return jsonify({
        "success": True,
        "analysis": {
            "total_trades": len(sell_trades),
            "winning_trades": len(win_trades),
            "losing_trades": len(lose_trades),
            "win_rate": round(len(win_trades) / max(1, len(sell_trades)) * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_profit": round(total_win_pnl / max(1, len(win_trades)), 2),
            "avg_loss": round(total_lose_pnl / max(1, len(lose_trades)), 2),
            "profit_loss_ratio": round(total_win_pnl / max(1, total_lose_pnl), 2),
        },
    })
