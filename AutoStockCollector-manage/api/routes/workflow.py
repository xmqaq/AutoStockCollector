"""
选股工作流API路由
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from modules.workflow import Workflow, WorkflowStorage, WorkflowExecutor, WorkflowNode, WorkflowEdge
from utils.logger import get_logger


logger = get_logger(__name__)

workflow_bp = Blueprint('workflow', __name__, url_prefix='/api/v1/workflow')
workflow_storage = WorkflowStorage()


@workflow_bp.route('', methods=['GET'])
def list_workflows():
    """获取所有工作流"""
    try:
        enabled = request.args.get('enabled')
        enabled_filter = None if enabled is None else enabled.lower() == 'true'

        workflows = workflow_storage.list_workflows(enabled=enabled_filter)
        return jsonify({
            'success': True,
            'data': [w.to_dict() for w in workflows]
        })
    except Exception as e:
        logger.error(f"List workflows failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>', methods=['GET'])
def get_workflow(workflow_id):
    """获取单个工作流"""
    try:
        workflow = workflow_storage.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404

        return jsonify({
            'success': True,
            'data': workflow.to_dict()
        })
    except Exception as e:
        logger.error(f"Get workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('', methods=['POST'])
def create_workflow():
    """创建新工作流"""
    try:
        data = request.get_json()
        workflow_id = data.get('id') or str(uuid.uuid4())

        workflow = Workflow(
            id=workflow_id,
            name=data.get('name', 'New Workflow'),
            description=data.get('description', ''),
            nodes=[WorkflowNode.from_dict(n) if isinstance(n, dict) else n for n in data.get('nodes', [])],
            edges=[WorkflowEdge.from_dict(e) if isinstance(e, dict) else e for e in data.get('edges', [])],
            enabled=data.get('enabled', True),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            tags=data.get('tags', [])
        )

        if workflow_storage.save_workflow(workflow):
            return jsonify({
                'success': True,
                'data': workflow.to_dict()
            }), 201
        else:
            return jsonify({'success': False, 'error': 'Failed to save workflow'}), 500

    except Exception as e:
        logger.error(f"Create workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>', methods=['PUT'])
def update_workflow(workflow_id):
    """更新工作流"""
    try:
        data = request.get_json()
        workflow = workflow_storage.get_workflow(workflow_id)

        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404

        if 'name' in data:
            workflow.name = data['name']
        if 'description' in data:
            workflow.description = data['description']
        if 'nodes' in data:
            workflow.nodes = data['nodes']
        if 'edges' in data:
            workflow.edges = data['edges']
        if 'enabled' in data:
            workflow.enabled = data['enabled']
        if 'tags' in data:
            workflow.tags = data['tags']

        workflow.updated_at = datetime.now().isoformat()

        if workflow_storage.save_workflow(workflow):
            return jsonify({
                'success': True,
                'data': workflow.to_dict()
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to save workflow'}), 500

    except Exception as e:
        logger.error(f"Update workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>', methods=['DELETE'])
def delete_workflow(workflow_id):
    """删除工作流"""
    try:
        if workflow_storage.delete_workflow(workflow_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404
    except Exception as e:
        logger.error(f"Delete workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/run', methods=['POST'])
def run_workflow(workflow_id):
    """执行工作流"""
    try:
        workflow = workflow_storage.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404

        if not workflow.enabled:
            return jsonify({'success': False, 'error': 'Workflow is disabled'}), 400

        params = request.get_json() or {}

        executor = WorkflowExecutor(workflow_id)
        nodes = [n.to_dict() if hasattr(n, 'to_dict') else n for n in workflow.nodes]
        edges = [e.to_dict() if hasattr(e, 'to_dict') else e for e in workflow.edges]

        result = executor.execute(nodes, edges, params)

        workflow_storage.update_last_run(workflow_id)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Run workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/templates', methods=['GET'])
def get_templates():
    """获取工作流模板"""
    templates = [
        {
            'id': 'template_value',
            'name': '价值投资策略',
            'description': '基于基本面筛选低估值的优质股票',
            'tags': ['价值', '基本面'],
            'nodes': [
                {
                    'id': 'start_1',
                    'type': 'start',
                    'label': '起始',
                    'x': 100,
                    'y': 200,
                    'config': {'source': 'all'}
                },
                {
                    'id': 'filter_pe',
                    'type': 'filter',
                    'label': 'PE筛选',
                    'x': 300,
                    'y': 200,
                    'config': {
                        'filter_type': 'pe_range',
                        'min_pe': 0,
                        'max_pe': 25
                    }
                },
                {
                    'id': 'filter_pb',
                    'type': 'filter',
                    'label': 'PB筛选',
                    'x': 500,
                    'y': 200,
                    'config': {
                        'filter_type': 'pb_range',
                        'min_pb': 0,
                        'max_pb': 3
                    }
                },
                {
                    'id': 'score_1',
                    'type': 'score',
                    'label': '基本面评分',
                    'x': 700,
                    'y': 200,
                    'config': {
                        'score_type': 'fundamental'
                    }
                },
                {
                    'id': 'end_1',
                    'type': 'end',
                    'label': '输出',
                    'x': 900,
                    'y': 200,
                    'config': {
                        'output': 'list',
                        'top_n': 20
                    }
                }
            ],
            'edges': [
                {'id': 'e1', 'source': 'start_1', 'target': 'filter_pe'},
                {'id': 'e2', 'source': 'filter_pe', 'target': 'filter_pb'},
                {'id': 'e3', 'source': 'filter_pb', 'target': 'score_1'},
                {'id': 'e4', 'source': 'score_1', 'target': 'end_1'}
            ]
        },
        {
            'id': 'template_momentum',
            'name': '动量策略',
            'description': '基于技术面筛选强势股票',
            'tags': ['动量', '技术面'],
            'nodes': [
                {
                    'id': 'start_1',
                    'type': 'start',
                    'label': '起始',
                    'x': 100,
                    'y': 200,
                    'config': {'source': 'all'}
                },
                {
                    'id': 'filter_trend',
                    'type': 'filter',
                    'label': '趋势筛选',
                    'x': 300,
                    'y': 200,
                    'config': {
                        'filter_type': 'trend',
                        'trend_type': 'up'
                    }
                },
                {
                    'id': 'filter_volume',
                    'type': 'filter',
                    'label': '成交量筛选',
                    'x': 500,
                    'y': 200,
                    'config': {
                        'filter_type': 'volume_ratio',
                        'threshold': 1.5
                    }
                },
                {
                    'id': 'score_1',
                    'type': 'score',
                    'label': '技术面评分',
                    'x': 700,
                    'y': 200,
                    'config': {
                        'score_type': 'technical'
                    }
                },
                {
                    'id': 'end_1',
                    'type': 'end',
                    'label': '输出',
                    'x': 900,
                    'y': 200,
                    'config': {
                        'output': 'list',
                        'top_n': 20
                    }
                }
            ],
            'edges': [
                {'id': 'e1', 'source': 'start_1', 'target': 'filter_trend'},
                {'id': 'e2', 'source': 'filter_trend', 'target': 'filter_volume'},
                {'id': 'e3', 'source': 'filter_volume', 'target': 'score_1'},
                {'id': 'e4', 'source': 'score_1', 'target': 'end_1'}
            ]
        },
        {
            'id': 'template_ai',
            'name': 'AI智能选股',
            'description': '结合AI Agent进行智能分析',
            'tags': ['AI', '智能'],
            'nodes': [
                {
                    'id': 'start_1',
                    'type': 'start',
                    'label': '起始',
                    'x': 100,
                    'y': 200,
                    'config': {'source': 'all'}
                },
                {
                    'id': 'filter_1',
                    'type': 'filter',
                    'label': '基础筛选',
                    'x': 300,
                    'y': 200,
                    'config': {
                        'filter_type': 'price_range',
                        'min_price': 5,
                        'max_price': 100
                    }
                },
                {
                    'id': 'score_1',
                    'type': 'score',
                    'label': '综合评分',
                    'x': 500,
                    'y': 200,
                    'config': {
                        'score_type': 'weighted',
                        'weights': {
                            'technical': 0.3,
                            'fundamental': 0.3,
                            'sentiment': 0.2,
                            'fund_flow': 0.2
                        }
                    }
                },
                {
                    'id': 'ai_1',
                    'type': 'ai_agent',
                    'label': 'AI深度分析',
                    'x': 700,
                    'y': 200,
                    'config': {
                        'agent_id': '',
                        'top_n': 30
                    }
                },
                {
                    'id': 'end_1',
                    'type': 'end',
                    'label': '输出',
                    'x': 900,
                    'y': 200,
                    'config': {
                        'output': 'list',
                        'top_n': 15
                    }
                }
            ],
            'edges': [
                {'id': 'e1', 'source': 'start_1', 'target': 'filter_1'},
                {'id': 'e2', 'source': 'filter_1', 'target': 'score_1'},
                {'id': 'e3', 'source': 'score_1', 'target': 'ai_1'},
                {'id': 'e4', 'source': 'ai_1', 'target': 'end_1'}
            ]
        }
    ]

    return jsonify({
        'success': True,
        'data': templates
    })


@workflow_bp.route('/node-types', methods=['GET'])
def get_node_types():
    """获取支持的节点类型"""
    node_types = {
        'start': {
            'type': 'start',
            'label': '起始节点',
            'description': '定义工作流的起始点和数据来源',
            'icon': 'play',
            'config_schema': {
                'source': {
                    'type': 'select',
                    'label': '数据源',
                    'options': [
                        {'value': 'all', 'label': '全部股票'},
                        {'value': 'watchlist', 'label': '自选股'},
                        {'value': 'sector', 'label': '板块'}
                    ],
                    'default': 'all'
                },
                'sector': {
                    'type': 'text',
                    'label': '板块名称',
                    'show_if': {'field': 'source', 'value': 'sector'}
                }
            }
        },
        'filter': {
            'type': 'filter',
            'label': '筛选节点',
            'description': '根据条件筛选股票',
            'icon': 'filter',
            'config_schema': {
                'filter_type': {
                    'type': 'select',
                    'label': '筛选类型',
                    'options': [
                        {'value': 'price_range', 'label': '价格区间'},
                        {'value': 'volume_ratio', 'label': '成交量放大'},
                        {'value': 'pe_range', 'label': 'PE范围'},
                        {'value': 'pb_range', 'label': 'PB范围'},
                        {'value': 'trend', 'label': '趋势筛选'},
                        {'value': 'fund_flow', 'label': '资金流向'},
                        {'value': 'sector', 'label': '板块筛选'},
                        {'value': 'market_cap', 'label': '市值筛选'},
                        {'value': 'news_sentiment', 'label': '舆情筛选'}
                    ],
                    'default': 'price_range'
                },
                'min_price': {'type': 'number', 'label': '最低价', 'show_if': {'field': 'filter_type', 'value': 'price_range'}},
                'max_price': {'type': 'number', 'label': '最高价', 'show_if': {'field': 'filter_type', 'value': 'price_range'}},
                'threshold': {'type': 'number', 'label': '阈值', 'show_if': {'field': 'filter_type', 'value': ['volume_ratio', 'fund_flow']}},
                'direction': {'type': 'select', 'label': '方向', 'options': [{'value': 'positive', 'label': '正向'}, {'value': 'negative', 'label': '负向'}], 'show_if': {'field': 'filter_type', 'value': 'fund_flow'}},
                'min_pe': {'type': 'number', 'label': '最小PE', 'show_if': {'field': 'filter_type', 'value': 'pe_range'}},
                'max_pe': {'type': 'number', 'label': '最大PE', 'show_if': {'field': 'filter_type', 'value': 'pe_range'}},
                'min_pb': {'type': 'number', 'label': '最小PB', 'show_if': {'field': 'filter_type', 'value': 'pb_range'}},
                'max_pb': {'type': 'number', 'label': '最大PB', 'show_if': {'field': 'filter_type', 'value': 'pb_range'}},
                'trend_type': {'type': 'select', 'label': '趋势类型', 'options': [{'value': 'up', 'label': '上涨'}, {'value': 'down', 'label': '下跌'}], 'show_if': {'field': 'filter_type', 'value': 'trend'}}
            }
        },
        'score': {
            'type': 'score',
            'label': '评分节点',
            'description': '对股票进行多维度评分',
            'icon': 'star',
            'config_schema': {
                'score_type': {
                    'type': 'select',
                    'label': '评分类型',
                    'options': [
                        {'value': 'weighted', 'label': '加权评分'},
                        {'value': 'technical', 'label': '技术面评分'},
                        {'value': 'fundamental', 'label': '基本面评分'},
                        {'value': 'fund_flow', 'label': '资金流评分'},
                        {'value': 'sentiment', 'label': '舆情评分'}
                    ],
                    'default': 'weighted'
                },
                'weights': {
                    'type': 'object',
                    'label': '评分权重',
                    'show_if': {'field': 'score_type', 'value': 'weighted'},
                    'properties': {
                        'technical': {'type': 'number', 'label': '技术面权重', 'default': 0.25},
                        'fundamental': {'type': 'number', 'label': '基本面权重', 'default': 0.25},
                        'sentiment': {'type': 'number', 'label': '舆情权重', 'default': 0.25},
                        'fund_flow': {'type': 'number', 'label': '资金流权重', 'default': 0.25}
                    }
                }
            }
        },
        'ai_agent': {
            'type': 'ai_agent',
            'label': 'AI Agent节点',
            'description': '使用AI Agent进行深度分析',
            'icon': 'robot',
            'config_schema': {
                'agent_id': {
                    'type': 'select',
                    'label': '选择Agent',
                    'options': [],
                    'load_from': '/api/v1/ai-agents'
                },
                'top_n': {'type': 'number', 'label': '分析前N只', 'default': 20}
            }
        },
        'combine': {
            'type': 'combine',
            'label': '组合节点',
            'description': '合并和优化选股结果',
            'icon': 'collection',
            'config_schema': {
                'strategy': {
                    'type': 'select',
                    'label': '组合策略',
                    'options': [
                        {'value': 'top_n', 'label': '取前N名'},
                        {'value': 'min_score', 'label': '最低分过滤'},
                        {'value': 'diversify', 'label': '分散配置'}
                    ],
                    'default': 'top_n'
                },
                'top_n': {'type': 'number', 'label': '数量', 'default': 20, 'show_if': {'field': 'strategy', 'value': ['top_n', 'min_score']}},
                'min_score': {'type': 'number', 'label': '最低分', 'default': 60, 'show_if': {'field': 'strategy', 'value': 'min_score'}}
            }
        },
        'risk_control': {
            'type': 'risk_control',
            'label': '风控节点',
            'description': '应用风险控制规则',
            'icon': 'shield',
            'config_schema': {
                'max_positions': {'type': 'number', 'label': '最大持仓数', 'default': 10},
                'max_position_ratio': {'type': 'number', 'label': '单只最大比例', 'default': 0.1},
                'exclude_st': {'type': 'boolean', 'label': '排除ST股票', 'default': True}
            }
        },
        'end': {
            'type': 'end',
            'label': '结束节点',
            'description': '输出选股结果',
            'icon': 'stop',
            'config_schema': {
                'output': {
                    'type': 'select',
                    'label': '输出类型',
                    'options': [
                        {'value': 'list', 'label': '列表'},
                        {'value': 'export', 'label': '导出'}
                    ],
                    'default': 'list'
                },
                'top_n': {'type': 'number', 'label': '输出数量', 'default': 10}
            }
        },
        'data_fetch': {
            'type': 'data_fetch',
            'label': '数据获取节点',
            'description': '从多种数据源获取股票数据',
            'icon': 'database',
            'config_schema': {
                'data_type': {
                    'type': 'select',
                    'label': '数据类型',
                    'options': [
                        {'value': 'kline', 'label': 'K线数据'},
                        {'value': 'realtime', 'label': '实时行情'},
                        {'value': 'financial', 'label': '财务数据'},
                        {'value': 'fund_flow', 'label': '资金流向'},
                        {'value': 'sentiment', 'label': '舆情数据'},
                        {'value': 'dragon_tiger', 'label': '龙虎榜'},
                        {'value': 'margin', 'label': '融资融券'},
                        {'value': 'signals', 'label': '交易信号'}
                    ],
                    'default': 'kline'
                },
                'days': {'type': 'number', 'label': '历史天数', 'default': 60, 'show_if': {'field': 'data_type', 'value': ['kline', 'sentiment']}},
                'limit': {'type': 'number', 'label': '数据条数', 'default': 100}
            }
        },
        'technical_indicator': {
            'type': 'technical_indicator',
            'label': '技术指标节点',
            'description': '计算技术分析指标',
            'icon': 'line-chart',
            'config_schema': {
                'indicator_type': {
                    'type': 'select',
                    'label': '指标类型',
                    'options': [
                        {'value': 'ma', 'label': '均线(MA)'},
                        {'value': 'ema', 'label': '指数均线(EMA)'},
                        {'value': 'macd', 'label': 'MACD'},
                        {'value': 'kdj', 'label': 'KDJ'},
                        {'value': 'rsi', 'label': 'RSI'},
                        {'value': 'boll', 'label': '布林带(BOLL)'},
                        {'value': 'volume', 'label': '成交量指标'}
                    ],
                    'default': 'ma'
                },
                'params': {
                    'type': 'text',
                    'label': '参数配置',
                    'placeholder': '如: 5,20,60',
                    'show_if': {'field': 'indicator_type', 'value': ['ma', 'ema']}
                }
            }
        },
        'fundamental_filter': {
            'type': 'fundamental_filter',
            'label': '基本面筛选节点',
            'description': '基于财务指标进行筛选',
            'icon': 'reading',
            'config_schema': {
                'filter_type': {
                    'type': 'select',
                    'label': '财务指标',
                    'options': [
                        {'value': 'pe', 'label': '市盈率(PE)'},
                        {'value': 'pb', 'label': '市净率(PB)'},
                        {'value': 'roe', 'label': '净资产收益率(ROE)'},
                        {'value': 'revenue_growth', 'label': '营收增长率'},
                        {'value': 'profit_growth', 'label': '净利润增长率'},
                        {'value': 'gross_margin', 'label': '毛利率'},
                        {'value': 'net_margin', 'label': '净利率'},
                        {'value': 'debt_ratio', 'label': '资产负债率'}
                    ],
                    'default': 'pe'
                },
                'operator': {
                    'type': 'select',
                    'label': '比较运算符',
                    'options': [
                        {'value': 'gt', 'label': '大于'},
                        {'value': 'lt', 'label': '小于'},
                        {'value': 'between', 'label': '区间'}
                    ],
                    'default': 'lt'
                },
                'value': {'type': 'number', 'label': '阈值'},
                'min_value': {'type': 'number', 'label': '最小值', 'show_if': {'field': 'operator', 'value': 'between'}},
                'max_value': {'type': 'number', 'label': '最大值', 'show_if': {'field': 'operator', 'value': 'between'}}
            }
        },
        'market_sentiment': {
            'type': 'market_sentiment',
            'label': '市场情绪节点',
            'description': '分析市场整体情绪和热点',
            'icon': 'chat-line-square',
            'config_schema': {
                'analysis_type': {
                    'type': 'select',
                    'label': '分析类型',
                    'options': [
                        {'value': 'overall', 'label': '整体情绪'},
                        {'value': 'hot_sectors', 'label': '热点板块'},
                        {'value': 'capital_flow', 'label': '资金流向'},
                        {'value': 'news_impact', 'label': '新闻影响'}
                    ],
                    'default': 'overall'
                },
                'threshold': {'type': 'number', 'label': '情绪阈值', 'default': 50}
            }
        },
        'index_components': {
            'type': 'index_components',
            'label': '指数成分节点',
            'description': '获取指定指数的成分股',
            'icon': 'collection',
            'config_schema': {
                'index_code': {
                    'type': 'select',
                    'label': '指数',
                    'options': [
                        {'value': '000300.sh', 'label': '沪深300'},
                        {'value': '000905.sh', 'label': '中证500'},
                        {'value': '000001.sh', 'label': '上证指数'},
                        {'value': '399001.sz', 'label': '深证成指'},
                        {'value': '399006.sz', 'label': '创业板指'}
                    ],
                    'default': '000300.sh'
                }
            }
        },
        'compare': {
            'type': 'compare',
            'label': '对比分析节点',
            'description': '对比多只股票的指标数据',
            'icon': 'data-analysis',
            'config_schema': {
                'compare_type': {
                    'type': 'select',
                    'label': '对比维度',
                    'options': [
                        {'value': 'price', 'label': '价格对比'},
                        {'value': 'performance', 'label': '涨跌幅对比'},
                        {'value': 'valuation', 'label': '估值对比'},
                        {'value': 'fund_flow', 'label': '资金流向对比'}
                    ],
                    'default': 'performance'
                },
                'ranking': {
                    'type': 'select',
                    'label': '排序方式',
                    'options': [
                        {'value': 'asc', 'label': '升序'},
                        {'value': 'desc', 'label': '降序'}
                    ],
                    'default': 'desc'
                }
            }
        }
    }

    return jsonify({
        'success': True,
        'data': node_types
    })
