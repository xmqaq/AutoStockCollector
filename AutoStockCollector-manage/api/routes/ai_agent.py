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
    """确保 ai_agents 集合存在并初始化默认数据"""
    db = _get_db()
    if "ai_agents" not in db.list_collection_names():
        db.create_collection("ai_agents")
        db["ai_agents"].create_index([("id", 1)], unique=True)
        _init_default_agents()


def _init_default_agents():
    """初始化默认 Agent"""
    db = _get_db()
    default_agents = [
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
        }
    ]
    for agent in default_agents:
        db["ai_agents"].update_one({"id": agent["id"]}, {"$set": agent}, upsert=True)


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
    """测试 Agent，可选择传入股票代码通过 HTTP API 获取实时数据进行测试"""
    _ensure_collection()
    from modules.ai.foundation.llm_router import LLMRouter
    import requests

    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    data = request.get_json() or {}
    test_message = data.get("message", "")
    stock_code = data.get("code")

    try:
        router = LLMRouter()

        if stock_code:
            stock_info = {}
            kline_data = []
            fund_flow_data = {}

            try:
                stock_resp = requests.get(
                    f"http://localhost:5173/api/v1/kline/{stock_code}?limit=10",
                    timeout=5
                )
                if stock_resp.status_code == 200:
                    resp_data = stock_resp.json()
                    if isinstance(resp_data, list):
                        kline_data = resp_data
                    else:
                        kline_data = resp_data.get("data", [])
            except Exception:
                pass

            try:
                fund_resp = requests.get(
                    f"http://localhost:5173/api/v1/fund-flow/{stock_code}",
                    timeout=5
                )
                if fund_resp.status_code == 200:
                    fund_flow_data = fund_resp.json().get("data", {})
            except Exception:
                pass

            closes = [k.get("close") for k in kline_data if k.get("close")]
            volumes = [k.get("volume") for k in kline_data if k.get("volume")]
            main_net = fund_flow_data.get('main_net_inflow') or fund_flow_data.get('main_net_inflow_5d', '暂无')

            price_info = f"""
【股票数据】
- 股票代码：{stock_code}
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

        result = router.chat(prompt, use_cache=False)

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
                "error": result.error or "AI 服务暂不可用"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@ai_agent_bp.route("/<agent_id>/analyze", methods=["POST"])
def analyze_with_agent(agent_id: str):
    """使用指定 Agent 分析股票，通过 HTTP API 获取数据"""
    import requests
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
        stock_info = {}
        kline_data = []
        fund_flow_data = {}
        news_data = []

        try:
            stock_resp = requests.get(
                f"http://localhost:5173/api/v1/kline/{stock_code}?limit=10",
                timeout=5
            )
            if stock_resp.status_code == 200:
                resp_data = stock_resp.json()
                if isinstance(resp_data, list):
                    kline_data = resp_data
                else:
                    kline_data = resp_data.get("data", [])
        except:
            pass

        try:
            fund_resp = requests.get(
                f"http://localhost:5173/api/v1/fund-flow/{stock_code}",
                timeout=5
            )
            if fund_resp.status_code == 200:
                fund_flow_data = fund_resp.json().get("data", {})
        except Exception:
            pass

        try:
            news_resp = requests.get(
                f"http://localhost:5173/api/v1/news?code={stock_code}&limit=3",
                timeout=5
            )
            if news_resp.status_code == 200:
                news_data = news_resp.json().get("data", [])
        except:
            pass

        closes = [k.get("close") for k in kline_data if k.get("close")]
        volumes = [k.get("volume") for k in kline_data if k.get("volume")]
        main_net = fund_flow_data.get('main_net_inflow') or fund_flow_data.get('main_net_inflow_5d') or '暂无'
        stock_name = stock_info.get('name', '未知')
        news_titles = [n.get('title', '') for n in news_data[:3] if isinstance(n, dict)]

        price_info = f"""
【股票数据】
- 股票代码：{stock_code}
- 股票名称：{stock_name}
- 近期收盘价（最新10日）：{closes if closes else '暂无数据'}
- 近期成交量（最新10日）：{volumes if volumes else '暂无数据'}
- 市盈率(PE)：{stock_info.get('pe') or '暂无'}
- 市净率(PB)：{stock_info.get('pb') or '暂无'}
- 主力净流入：{main_net}
- 最新新闻：{news_titles}
"""
        prompt = f"""{agent['system_prompt']}

{price_info}

请结合以上数据给出专业的分析和建议。"""

        result = router.chat(prompt, use_cache=False)

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
                "error": result.error or "AI 服务暂不可用"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
