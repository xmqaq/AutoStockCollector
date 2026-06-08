"""
AI Agent 管理相关接口
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Dict, Any

ai_agent_bp = Blueprint("ai_agent", __name__, url_prefix="/api/v1/ai-agents")


def _get_db():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()


def _ensure_collection():
    """确保 ai_agents 集合存在并补全缺失的默认 Agent"""
    db = _get_db()
    if "ai_agents" not in db.list_collection_names():
        db.create_collection("ai_agents")
        db["ai_agents"].create_index([("id", 1)], unique=True)
    _sync_default_agents()


def _sync_default_agents():
    """同步默认 Agent，新增的插入，已存在的更新 system_prompt"""
    db = _get_db()
    for agent in _default_agent_configs():
        db["ai_agents"].update_one(
            {"id": agent["id"]},
            {
                "$set": {"system_prompt": agent["system_prompt"]},
                "$setOnInsert": {
                    k: v for k, v in agent.items() if k != "system_prompt"
                },
            },
            upsert=True,
        )


def _init_default_agents():
    """初始化默认 Agent（全量覆盖，仅首次建库时调用）"""
    db = _get_db()
    for agent in _default_agent_configs():
        db["ai_agents"].update_one({"id": agent["id"]}, {"$set": agent}, upsert=True)


def _default_agent_configs():
    """返回所有默认 Agent 配置"""
    return [
        {
            "id": "market_analyst",
            "name": "市场分析师",
            "description": "分析宏观经济环境和市场整体走势",
            "role": "market_analyst",
            "system_prompt": """你是一位专业的股票市场分析师。你能够访问股票的K线数据（包含近期收盘价、成交量）、资金流向数据、新闻舆情等。

你的分析框架：
1. 【趋势判断】根据近期收盘价变化判断价格趋势（上升/下降/震荡）
2. 【量价分析】结合成交量变化判断市场活跃度和资金参与度
3. 【资金动向】分析主力资金净流入/流出情况
4. 【市场情绪】结合新闻舆情判断市场热点和情绪
5. 【板块联动】判断个股所属板块的整体表现

数据解读原则：
- 收盘价连续上涨且放量 = 强势
- 收盘价上涨但缩量 = 谨慎
- 主力资金净流入 = 机构看好
- 新闻面偏多 = 情绪支撑

请给出简洁专业的分析，重点提示：当前趋势、关键信号、投资建议（买入/观望/回避）。""",
            "temperature": 0.7,
            "max_tokens": 2000,
            "enabled": True,
            "priority": 1,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": "technical_analyst",
            "name": "技术分析师",
            "description": "分析股票价格走势和技术指标信号",
            "role": "technical_analyst",
            "system_prompt": """你是一位专业的技术分析专家。你能够访问股票的K线数据（收盘价、成交量、按时间排序）。

你的技术分析框架：
1. 【均线系统】
   - MA5/MA10/MA20 多头排列 = 短期强势
   - 股价跌破均线支撑 = 警惕
   
2. 【量价配合】
   - 放量上涨 = 健康
   - 缩量上涨 = 乏力
   - 放量下跌 = 恐慌
   - 缩量下跌 = 盘整
   
3. 【趋势判断】
   - 连续上涨：判断是否为加速行情
   - 回调：判断是否为正常调整
   
4. 【买卖信号】
   - 金叉（短期均线上穿长期均线）= 买入信号
   - 死叉 = 卖出信号
   
5. 【支撑压力】
   - 前期高点 = 压力位
   - 前期低点 = 支撑位

请给出具体的技术指标解读，重点：当前趋势信号、关键支撑位/压力位、建议操作。""",
            "temperature": 0.5,
            "max_tokens": 1500,
            "enabled": True,
            "priority": 2,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": "fund_analyst",
            "name": "资金分析师",
            "description": "分析资金流向和大单交易",
            "role": "fund_analyst",
            "system_prompt": """你是一位专业的资金流向分析师。你能够访问股票的成交量数据、资金流向指标等。

你的资金分析框架：
1. 【量价关系】
   - 放量上涨：资金推动行情，看多
   - 放量下跌：资金出逃，看空
   - 缩量整理：等待方向选择
   
2. 【资金强度】
   - 连续放量 = 资金持续关注
   - 脉冲式放量 = 短线机会
   - 持续缩量 = 观望信号
   
3. 【对比分析】
   - 与板块平均成交量对比
   - 与历史均量对比
   
4. 【资金信号】
   - 放量突破 = 启动信号
   - 缩量跌破 = 离场信号
   - 平量整理 = 突破前兆

请给出资金面分析，重点：资金活跃度、净流入/流出情况、资金信号提示。""",
            "temperature": 0.6,
            "max_tokens": 1500,
            "enabled": True,
            "priority": 3,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": "fundamental_analyst",
            "name": "基本面分析师",
            "description": "分析公司财务数据和基本面",
            "role": "fundamental_analyst",
            "system_prompt": """你是一位专业的基本面分析师。你能够访问股票的财务数据（PE、PB、PS等指标）。

你的基本面分析框架：
1. 【估值分析】
   - PE（市盈率）：行业对比，判断高低
   - PB（市净率）：破净 = 价值低估信号
   - PS（市销率）：营收倍数
   
2. 【盈利能力】
   - 营收增长情况
   - 净利润趋势
   
3. 【财务健康】
   - 资产负债情况
   - 现金流状况
   
4. 【行业地位】
   - 市场份额
   - 竞争优势
   
5. 【估值判断】
   - 当前估值在历史分位
   - 与行业平均对比
   - 合理估值区间

请给出基本面评估，重点：估值合理性、盈利质量、风险点提示。""",
            "temperature": 0.6,
            "max_tokens": 2000,
            "enabled": True,
            "priority": 4,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": "risk_analyst",
            "name": "风险分析师",
            "description": "识别和评估投资风险",
            "role": "risk_analyst",
            "system_prompt": """你是一位专业的风险控制专家。你能够访问股票的K线数据、财务数据、新闻舆情等。

你的风险分析框架：
1. 【技术风险】
   - 破位下跌 = 技术破位风险
   - 高位放量滞涨 = 主力出货风险
   - 连续下跌 = 趋势转弱风险

2. 【估值风险】
   - PE/PB 显著高于行业 = 估值泡沫风险
   - 涨幅过大 = 回调风险
   - 市盈率为负 = 盈利风险

3. 【流动性风险】
   - 成交量异常萎缩 = 流动性枯竭风险
   - 大单砸盘风险

4. 【消息面风险】
   - 利空新闻影响
   - 行业政策风险
   - 大股东减持风险

5. 【止损建议】
   - 建议止损位设置
   - 仓位管理建议

请给出客观风险评估，重点：主要风险点、风险等级（高/中/低）、止损建议。""",
            "temperature": 0.5,
            "max_tokens": 1500,
            "enabled": True,
            "priority": 5,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": "sentiment_analyst",
            "name": "舆情分析师",
            "description": "分析市场舆情、新闻情绪和社会热度",
            "role": "sentiment_analyst",
            "system_prompt": """你是一位专业的市场舆情分析师。你能够访问股票相关的新闻标题、市场情绪数据等。

你的舆情分析框架：
1. 【新闻情绪】
   - 正面新闻（业绩超预期、政策利好、合同中标）= 情绪支撑
   - 负面新闻（业绩下滑、监管处罚、高管变动）= 情绪压力
   - 中性新闻（行业动态、产品发布）= 关注度提升

2. 【市场热度】
   - 相关新闻数量增多 = 市场关注度上升
   - 连续多日正面报道 = 持续催化
   - 突发负面新闻 = 短期冲击风险

3. 【情绪拐点】
   - 负面新闻出尽 = 可能触底信号
   - 正面新闻密集出现 = 主力拉升配合

4. 【综合判断】
   - 情绪评分（0-100）
   - 正负面比例估算
   - 对股价的短期影响预判

请给出舆情分析，重点：当前情绪倾向、关键新闻影响、情绪对股价的短期影响。""",
            "temperature": 0.7,
            "max_tokens": 1500,
            "enabled": True,
            "priority": 6,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": "bull_analyst",
            "name": "多头分析师",
            "description": "从多头视角挖掘看涨信号和积极因素",
            "role": "bull_analyst",
            "system_prompt": """你是一位坚定的多头分析师，你的使命是从数据中找出一切支持看涨的理由和信号。

你的多头分析框架：
1. 【技术面看涨信号】
   - 均线多头排列（MA5 > MA10 > MA20）= 上升趋势确立
   - MACD金叉或红柱放大 = 动能增强
   - 放量突破关键压力位 = 上涨空间打开
   - RSI在50-70强势区间 = 趋势健康
   - K线形态：W底、头肩底、旗形突破等

2. 【资金面看涨信号】
   - 主力资金持续净流入 = 机构建仓
   - 成交量放大配合上涨 = 价量配合良好
   - 大单买入占比提升 = 大资金看好

3. 【基本面看涨信号】
   - PE/PB处于历史低位 = 估值洼地
   - 营收利润双增长 = 成长性强
   - 行业景气度上升 = 戴维斯双击潜力

4. 【情绪面看涨信号】
   - 政策利好 = 催化剂
   - 行业龙头带动 = 板块效应
   - 业绩预增/超预期 = 基本面支撑

请基于给定数据，以多头视角全面分析，给出：看涨理由（至少3条）、目标价位预测、建议买入区间、仓位建议。请旗帜鲜明地阐述看多观点，但保持客观合理。

最后必须给出一行：综合评分：XX/100（0=完全没有看涨理由，100=极度看涨，反映你作为多头的信心强度）""",
            "temperature": 0.8,
            "max_tokens": 2000,
            "enabled": True,
            "priority": 7,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": "bear_analyst",
            "name": "空头分析师",
            "description": "从空头视角挖掘看跌信号和风险因素",
            "role": "bear_analyst",
            "system_prompt": """你是一位谨慎的空头分析师，你的使命是从数据中找出一切支持看跌的理由和风险信号。

你的空头分析框架：
1. 【技术面看跌信号】
   - 均线空头排列（MA5 < MA10 < MA20）= 下降趋势确立
   - MACD死叉或绿柱放大 = 动能减弱
   - 放量跌破关键支撑位 = 下跌空间打开
   - RSI在30-50弱势区间 = 趋势疲弱
   - K线形态：M顶、头肩顶、下降旗形等

2. 【资金面看跌信号】
   - 主力资金持续净流出 = 机构撤离
   - 放量下跌 = 恐慌出逃
   - 大单卖出占比提升 = 大资金撤离

3. 【基本面看跌信号】
   - PE/PB显著高于行业均值 = 估值泡沫
   - 营收利润下滑 = 基本面恶化
   - 行业景气度下降 = 戴维斯双杀风险

4. 【情绪面看跌信号】
   - 政策利空/监管风险 = 不确定性
   - 负面新闻频出 = 情绪压制
   - 业绩预亏/不及预期 = 盈利风险

请基于给定数据，以空头视角全面分析，给出：看跌理由（至少3条）、目标下跌价位预测、建议止损/回避区间、风险等级。请旗帜鲜明地阐述看空观点，但保持客观合理。

最后必须给出一行：综合评分：XX/100（0=完全没有看跌理由，100=极度看跌，反映你作为空头的信心强度）""",
            "temperature": 0.8,
            "max_tokens": 2000,
            "enabled": True,
            "priority": 8,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": "debate_judge",
            "name": "辩论裁判与风险管控师",
            "description": "综合多空双方观点，评估风险等级，给出最终风险控制建议",
            "role": "debate_judge",
            "system_prompt": """你是一位资深的风险管控专家和辩论裁判。你的职责是审阅多头和空头双方的分析观点，进行客观权衡，并给出最终的风险控制决策。

你的裁决框架：
1. 【观点权衡】
   - 多头论点强度（论据充分性、逻辑严密性）
   - 空头论点强度（论据充分性、逻辑严密性）
   - 关键分歧点识别
   - 双方论据的可靠性和时效性

2. 【风险评估矩阵】
   - 技术面风险：趋势、支撑/压力位距离、成交量异常
   - 基本面风险：估值、盈利能力、债务水平
   - 资金面风险：主力动向、流动性
   - 情绪面风险：舆情、政策、事件驱动
   - 综合风险等级评估（低/中低/中/中高/高）

3. 【最终裁决】
   - 倾向判断：偏多/偏空/中性震荡
   - 信心指数（0-100）
   - 方向性建议：买入/持有/减仓/回避

4. 【风险管控建议】
   - 合理仓位比例（基于风险等级）
   - 建仓策略：分批/一次性/观望
   - 止损位设置（具体价位）
   - 止盈位设置（具体价位）
   - 仓位动态调整预案
   - 最大亏损控制建议

请输出最终观点，重点：综合裁决、风险等级（用🔥数量表示，🔥/🔥🔥/🔥🔥🔥/🔥🔥🔥🔥/🔥🔥🔥🔥🔥）、止损止盈价位、仓位建议。""",
            "temperature": 0.5,
            "max_tokens": 2500,
            "enabled": True,
            "priority": 9,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    ]


@ai_agent_bp.route("", methods=["GET"])
def list_agents():
    """获取所有 Agent 列表"""
    _ensure_collection()
    db = _get_db()
    agents = list(db["ai_agents"].find({}, {"_id": 0}).sort("priority", 1))
    return jsonify({"success": True, "data": agents, "count": len(agents)})


@ai_agent_bp.route("", methods=["POST"])
def create_agent():
    """创建新 Agent"""
    _ensure_collection()
    data = request.get_json() or {}
    
    required_fields = ["id", "name", "role", "system_prompt"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"success": False, "error": f"{field} is required"}), 400
    
    db = _get_db()
    existing = db["ai_agents"].find_one({"id": data["id"]})
    if existing:
        return jsonify({"success": False, "error": "Agent ID already exists"}), 400
    
    agent = {
        "id": data["id"],
        "name": data["name"],
        "description": data.get("description", ""),
        "role": data["role"],
        "system_prompt": data["system_prompt"],
        "temperature": data.get("temperature", 0.7),
        "max_tokens": data.get("max_tokens", 2000),
        "enabled": data.get("enabled", True),
        "priority": data.get("priority", 99),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    db["ai_agents"].insert_one(agent)
    agent.pop("_id", None)
    return jsonify({"success": True, "data": agent}), 201


@ai_agent_bp.route("/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    """获取单个 Agent"""
    _ensure_collection()
    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404
    return jsonify({"success": True, "data": agent})


@ai_agent_bp.route("/<agent_id>", methods=["PUT"])
def update_agent(agent_id: str):
    """更新 Agent"""
    _ensure_collection()
    db = _get_db()
    data = request.get_json() or {}
    
    existing = db["ai_agents"].find_one({"id": agent_id})
    if not existing:
        return jsonify({"success": False, "error": "Agent not found"}), 404
    
    update_fields = {}
    allowed_fields = ["name", "description", "role", "system_prompt", "temperature", "max_tokens", "enabled", "priority"]
    for field in allowed_fields:
        if field in data:
            update_fields[field] = data[field]
    
    update_fields["updated_at"] = datetime.now().isoformat()
    
    db["ai_agents"].update_one({"id": agent_id}, {"$set": update_fields})
    updated = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    return jsonify({"success": True, "data": updated})


@ai_agent_bp.route("/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id: str):
    """删除 Agent"""
    _ensure_collection()
    db = _get_db()
    
    result = db["ai_agents"].delete_one({"id": agent_id})
    if result.deleted_count == 0:
        return jsonify({"success": False, "error": "Agent not found"}), 404
    
    return jsonify({"success": True, "message": "Agent deleted"})


@ai_agent_bp.route("/<agent_id>/test", methods=["POST"])
def test_agent(agent_id: str):
    """测试 Agent，可选择传入股票代码从 MongoDB 获取实时数据进行测试"""
    _ensure_collection()
    from modules.ai.foundation.llm_router import LLMRouter

    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    data = request.get_json() or {}
    test_message = data.get("message", "")
    stock_code = data.get("code")

    temperature = float(agent.get("temperature", 0.7))
    max_tokens = int(agent.get("max_tokens", 2000))

    try:
        router = LLMRouter()

        if stock_code:
            kline_data = []
            fund_flow_data = {}
            stock_info = {}

            try:
                from core.storage.mongo_storage import KlineStorage
                kline_storage = KlineStorage()
                kline_data = list(kline_storage.find_many(
                    {"code": stock_code}, sort=[("date", -1)], limit=20
                ))
            except Exception as e:
                logger.warning(f"Failed to fetch kline data for {stock_code}: {e}")

            try:
                from core.storage.mongo_storage import FundFlowStorage
                fund_storage = FundFlowStorage()
                fund_flow_data = fund_storage.get_latest_flow(stock_code) or {}
            except Exception as e:
                logger.warning(f"Failed to fetch fund flow data for {stock_code}: {e}")

            try:
                from core.storage.mongo_storage import StockInfoStorage
                info_storage = StockInfoStorage()
                stock_info = info_storage.get_by_code(stock_code) or {}
            except Exception as e:
                logger.warning(f"Failed to fetch stock info for {stock_code}: {e}")

            closes = [k.get("close") for k in kline_data if k.get("close")]
            volumes = [k.get("volume") for k in kline_data if k.get("volume")]
            main_net = fund_flow_data.get('main_net_inflow') or fund_flow_data.get('main_net_inflow_5d', '暂无')

            price_info = f"""
【股票数据】
- 股票代码：{stock_code}
- 股票名称：{stock_info.get('name', '未知')}
- 近期收盘价：{closes[:10] if closes else '暂无数据'}
- 近期成交量：{volumes[:10] if volumes else '暂无数据'}
- PE：{stock_info.get('pe') or '暂无'}
- PB：{stock_info.get('pb') or '暂无'}
- 主力净流入：{main_net}
"""
            prompt = f"""{agent['system_prompt']}

{price_info}

用户问题: {test_message or '请分析这只股票'}
"""
        else:
            prompt = f"""{agent['system_prompt']}

用户问题: {test_message or '请简单介绍一下你自己'}
"""

        result = router.chat(prompt, use_cache=False,
                             temperature=temperature, max_tokens=max_tokens)

        if result.success:
            return jsonify({
                "success": True,
                "data": {
                    "content": result.raw,
                    "provider": result.provider
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": result.error or "AI 服务暂不可用，请检查 AI Keys 配置"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@ai_agent_bp.route("/compare", methods=["POST"])
def compare_stocks():
    """多股对比分析"""
    data = request.get_json() or {}
    codes = data.get("codes", [])

    if not codes or len(codes) < 2:
        return jsonify({"success": False, "error": "至少需要2个股票代码"}), 400

    if len(codes) > 10:
        return jsonify({"success": False, "error": "最多支持10个股票对比"}), 400

    try:
        from core.storage.mongo_storage import KlineStorage, StockInfoStorage, FundFlowStorage

        kline_storage = KlineStorage()
        stock_info_storage = StockInfoStorage()
        fund_storage = FundFlowStorage()

        comparison = []

        for code in codes:
            try:
                klines = list(kline_storage.find_many(
                    {"code": code},
                    sort=[("date", -1)],
                    limit=30
                ))

                stock_info = stock_info_storage.get_by_code(code) or {}
                fund_flow = fund_storage.get_latest_flow(code) or {}

                closes = [k.get("close") for k in klines if k.get("close")]
                volumes = [k.get("volume") for k in klines if k.get("volume")]

                price_change = 0
                if len(closes) >= 2:
                    price_change = ((closes[0] - closes[-1]) / closes[-1]) * 100 if closes[-1] else 0

                avg_volume = sum(volumes) / len(volumes) if volumes else 0

                comparison.append({
                    "code": code,
                    "name": stock_info.get("name", code),
                    "price": closes[0] if closes else 0,
                    "price_change": round(price_change, 2),
                    "pe": stock_info.get("pe") or stock_info.get("pe_ttm") or None,
                    "pb": stock_info.get("pb") or None,
                    "market_cap": stock_info.get("market_cap") or None,
                    "volume": avg_volume,
                    "main_net_inflow": fund_flow.get("main_net_inflow") or 0,
                    "close_prices": closes[:10] if closes else []
                })
            except Exception as e:
                logger.warning(f"Failed to fetch data for {code}: {e}")
                comparison.append({
                    "code": code,
                    "name": code,
                    "error": str(e)
                })

        return jsonify({
            "success": True,
            "data": {
                "stocks": comparison,
                "count": len(comparison)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@ai_agent_bp.route("/batch-analyze", methods=["POST"])
def batch_analyze():
    """批量分析多个股票"""
    from modules.ai.foundation.llm_router import LLMRouter
    data = request.get_json() or {}
    codes = data.get("codes", [])
    agent_id = data.get("agent_id", "technical_analyst")

    if not codes or len(codes) > 20:
        return jsonify({"success": False, "error": "最多支持20个股票"}), 400

    _ensure_collection()
    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    results = []
    for code in codes:
        try:
            from core.storage.mongo_storage import KlineStorage, StockInfoStorage
            kline_storage = KlineStorage()
            stock_info_storage = StockInfoStorage()

            klines = list(kline_storage.find_many(
                {"code": code},
                sort=[("date", -1)],
                limit=10
            ))
            stock_info = stock_info_storage.get_by_code(code) or {}

            closes = [k.get("close") for k in klines if k.get("close")]
            stock_name = stock_info.get("name", code)

            price_info = f"""
【股票数据】
- 股票代码：{code}
- 股票名称：{stock_name}
- 近期收盘价：{closes if closes else '暂无数据'}
- 市盈率(PE)：{stock_info.get('pe') or '暂无'}
- 市净率(PB)：{stock_info.get('pb') or '暂无'}
"""
            prompt = f"""{agent['system_prompt']}

{price_info}

请给出简短的分析结论（100字以内）。"""

            router = LLMRouter()
            result = router.chat(prompt, use_cache=False)

            results.append({
                "code": code,
                "name": stock_name,
                "success": result.success,
                "content": result.raw if result.success else result.error,
                "provider": result.provider if result.success else None
            })
        except Exception as e:
            results.append({
                "code": code,
                "success": False,
                "error": str(e)
            })

    return jsonify({
        "success": True,
        "data": {
            "results": results,
            "total": len(codes),
            "success_count": sum(1 for r in results if r.get("success"))
        }
    })


@ai_agent_bp.route("/<agent_id>/analyze/stream", methods=["POST"])
def analyze_with_agent_stream(agent_id: str):
    """使用指定 Agent 分析股票，流式响应"""
    from flask import Response
    import json

    _ensure_collection()
    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    data = request.get_json() or {}
    stock_code = data.get("code")

    if not stock_code:
        return jsonify({"success": False, "error": "code is required"}), 400

    def generate():
        try:
            router = LLMRouter()
            kline_data = []
            fund_flow_data = {}
            news_data = {}
            stock_info = {}

            try:
                from core.storage.mongo_storage import KlineStorage
                kline_storage = KlineStorage()
                kline_data = list(kline_storage.find_many(
                    {"code": stock_code},
                    sort=[("date", -1)],
                    limit=30
                ))
                yield f"data: {json.dumps({'type': 'progress', 'data': 20})}\n\n"
            except Exception as e:
                logger.warning(f"Failed to fetch kline data: {e}")

            try:
                from core.storage.mongo_storage import FundFlowStorage
                fund_storage = FundFlowStorage()
                fund_flow_data = fund_storage.get_latest_flow(stock_code) or {}
                yield f"data: {json.dumps({'type': 'progress', 'data': 30})}\n\n"
            except Exception as e:
                logger.warning(f"Failed to fetch fund flow data: {e}")

            try:
                from core.storage.mongo_storage import NewsStorage
                news_storage = NewsStorage()
                news_data = list(news_storage.find_many(
                    {"related_codes": stock_code},
                    sort=[("published_at", -1)],
                    limit=5
                ))
                yield f"data: {json.dumps({'type': 'progress', 'data': 40})}\n\n"
            except Exception as e:
                logger.warning(f"Failed to fetch news data: {e}")

            try:
                from core.storage.mongo_storage import StockInfoStorage
                stock_info_storage = StockInfoStorage()
                stock_info = stock_info_storage.get_by_code(stock_code) or {}
                yield f"data: {json.dumps({'type': 'progress', 'data': 50})}\n\n"
            except Exception as e:
                logger.warning(f"Failed to fetch stock info: {e}")

            closes = [k.get("close") for k in kline_data if k.get("close")]
            volumes = [k.get("volume") for k in kline_data if k.get("volume")]
            main_net = fund_flow_data.get('main_net_inflow') or fund_flow_data.get('main_net_inflow_5d') or '暂无'
            stock_name = stock_info.get('name', '未知')
            pe = stock_info.get('pe') or stock_info.get('pe_ttm') or '暂无'
            pb = stock_info.get('pb') or '暂无'
            news_titles = [n.get('title', '') for n in news_data[:3] if isinstance(n, dict)]

            price_info = f"""
【股票数据】
- 股票代码：{stock_code}
- 股票名称：{stock_name}
- 近期收盘价（最新10日）：{closes[:10] if closes else '暂无数据'}
- 近期成交量（最新10日）：{volumes[:10] if volumes else '暂无数据'}
- 市盈率(PE)：{pe}
- 市净率(PB)：{pb}
- 主力净流入：{main_net}
- 最新新闻：{news_titles}
"""
            prompt = f"""{agent['system_prompt']}

{price_info}

请结合以上数据给出专业的分析和建议。"""

            yield f"data: {json.dumps({'type': 'progress', 'data': 60, 'message': '开始AI分析...'})}\n\n"

            full_content = ""
            try:
                for chunk in router.chat_stream(prompt, use_cache=False):
                    if chunk:
                        full_content += chunk
                        yield f"data: {json.dumps({'type': 'content', 'data': chunk})}\n\n"

                yield f"data: {json.dumps({'type': 'done', 'data': {'content': full_content}})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@ai_agent_bp.route("/history", methods=["GET"])
def get_agent_history():
    """获取Agent执行历史记录"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    agent_id = request.args.get("agent_id", "")
    stock_code = request.args.get("code", "")

    db = _get_db()
    query = {}
    if agent_id:
        query["agent_id"] = agent_id
    if stock_code:
        query["stock_code"] = stock_code

    total = db["ai_analysis_history"].count_documents(query)
    skip = (page - 1) * page_size

    records = list(
        db["ai_analysis_history"]
        .find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    return jsonify({
        "success": True,
        "data": {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size
        }
    })


@ai_agent_bp.route("/history", methods=["POST"])
def save_agent_history():
    """保存Agent执行记录"""
    db = _get_db()
    data = request.get_json() or {}

    if "agent_id" not in data or "stock_code" not in data:
        return jsonify({"success": False, "error": "agent_id and stock_code are required"}), 400

    record = {
        "agent_id": data.get("agent_id"),
        "stock_code": data.get("stock_code"),
        "stock_name": data.get("stock_name", ""),
        "content": data.get("content", ""),
        "score": data.get("score"),
        "recommendation": data.get("recommendation"),
        "provider": data.get("provider", ""),
        "duration_ms": data.get("duration_ms", 0),
        "created_at": datetime.now().isoformat()
    }

    result = db["ai_analysis_history"].insert_one(record)

    return jsonify({
        "success": True,
        "data": {"id": str(result.inserted_id)}
    })


@ai_agent_bp.route("/<agent_id>/analyze", methods=["POST"])
def analyze_with_agent(agent_id: str):
    """使用指定 Agent 分析股票"""
    from modules.ai.foundation.llm_router import LLMRouter
    _ensure_collection()
    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    data = request.get_json() or {}
    stock_code = data.get("code")

    if not stock_code:
        return jsonify({"success": False, "error": "code is required"}), 400

    try:
        router = LLMRouter()
        kline_data = []
        fund_flow_data = {}
        news_data = []

        try:
            from core.storage.mongo_storage import KlineStorage, FundFlowStorage, NewsStorage, StockInfoStorage
            kline_storage = KlineStorage()
            kline_data = list(kline_storage.find_many(
                {"code": stock_code},
                sort=[("date", -1)],
                limit=30
            ))
        except Exception as e:
            logger.warning(f"Failed to fetch kline data: {e}")

        try:
            from core.storage.mongo_storage import FundFlowStorage
            fund_storage = FundFlowStorage()
            fund_flow_data = fund_storage.get_latest_flow(stock_code) or {}
        except Exception as e:
            logger.warning(f"Failed to fetch fund flow data: {e}")

        try:
            from core.storage.mongo_storage import NewsStorage
            news_storage = NewsStorage()
            news_data = list(news_storage.find_many(
                {"related_codes": stock_code},
                sort=[("published_at", -1)],
                limit=5
            ))
        except Exception as e:
            logger.warning(f"Failed to fetch news data: {e}")

        try:
            from core.storage.mongo_storage import StockInfoStorage
            stock_info_storage = StockInfoStorage()
            stock_info = stock_info_storage.get_by_code(stock_code) or {}
        except Exception as e:
            logger.warning(f"Failed to fetch stock info: {e}")
            stock_info = {}

        closes = [k.get("close") for k in kline_data if k.get("close")]
        volumes = [k.get("volume") for k in kline_data if k.get("volume")]
        main_net = fund_flow_data.get('main_net_inflow') or fund_flow_data.get('main_net_inflow_5d') or '暂无'
        stock_name = stock_info.get('name', '未知')
        pe = stock_info.get('pe') or stock_info.get('pe_ttm') or '暂无'
        pb = stock_info.get('pb') or '暂无'
        news_titles = [n.get('title', '') for n in news_data[:3] if isinstance(n, dict)]

        price_info = f"""
【股票数据】
- 股票代码：{stock_code}
- 股票名称：{stock_name}
- 近期收盘价（最新10日）：{closes[:10] if closes else '暂无数据'}
- 近期成交量（最新10日）：{volumes[:10] if volumes else '暂无数据'}
- 市盈率(PE)：{pe}
- 市净率(PB)：{pb}
- 主力净流入：{main_net}
- 最新新闻：{news_titles}
"""
        prompt = f"""{agent['system_prompt']}

{price_info}

请结合以上数据给出专业的分析和建议。"""

        temperature = float(agent.get("temperature", 0.7))
        max_tokens = int(agent.get("max_tokens", 2000))
        result = router.chat(prompt, use_cache=False,
                             temperature=temperature, max_tokens=max_tokens)

        if result.success:
            return jsonify({
                "success": True,
                "data": {
                    "content": result.raw,
                    "provider": result.provider
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": result.error or "AI 服务暂不可用，请检查 AI Keys 配置"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
