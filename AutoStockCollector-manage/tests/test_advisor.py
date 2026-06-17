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
