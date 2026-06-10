"""
初始化默认工作流模板到数据库
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.workflow import WorkflowTemplate, WorkflowNode, WorkflowEdge, WorkflowTemplateStorage
from datetime import datetime
from utils.helpers import beijing_now
import uuid


DEFAULT_TEMPLATES = [
    {
        'id': 'template_value',
        'name': '价值投资策略',
        'description': '基于基本面筛选低估值的优质股票',
        'tags': ['价值', '基本面'],
        'category': 'system',
        'nodes': [
            {'id': 'start_1', 'type': 'start', 'label': '起始', 'x': 100, 'y': 200, 'config': {'source': 'all'}},
            {'id': 'filter_pe', 'type': 'filter', 'label': 'PE筛选', 'x': 300, 'y': 200, 'config': {'filter_type': 'pe_range', 'min_pe': 0, 'max_pe': 25}},
            {'id': 'filter_pb', 'type': 'filter', 'label': 'PB筛选', 'x': 500, 'y': 200, 'config': {'filter_type': 'pb_range', 'min_pb': 0, 'max_pb': 3}},
            {'id': 'score_1', 'type': 'score', 'label': '基本面评分', 'x': 700, 'y': 200, 'config': {'score_type': 'fundamental'}},
            {'id': 'end_1', 'type': 'end', 'label': '输出', 'x': 900, 'y': 200, 'config': {'output': 'list', 'top_n': 20}}
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
        'category': 'system',
        'nodes': [
            {'id': 'start_1', 'type': 'start', 'label': '起始', 'x': 100, 'y': 200, 'config': {'source': 'all'}},
            {'id': 'filter_trend', 'type': 'filter', 'label': '趋势筛选', 'x': 300, 'y': 200, 'config': {'filter_type': 'trend', 'trend_type': 'up'}},
            {'id': 'filter_volume', 'type': 'filter', 'label': '成交量筛选', 'x': 500, 'y': 200, 'config': {'filter_type': 'volume_ratio', 'threshold': 1.5}},
            {'id': 'score_1', 'type': 'score', 'label': '技术面评分', 'x': 700, 'y': 200, 'config': {'score_type': 'technical'}},
            {'id': 'end_1', 'type': 'end', 'label': '输出', 'x': 900, 'y': 200, 'config': {'output': 'list', 'top_n': 20}}
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
        'category': 'system',
        'nodes': [
            {'id': 'start_1', 'type': 'start', 'label': '起始', 'x': 100, 'y': 200, 'config': {'source': 'all'}},
            {'id': 'filter_1', 'type': 'filter', 'label': '基础筛选', 'x': 300, 'y': 200, 'config': {'filter_type': 'price_range', 'min_price': 5, 'max_price': 100}},
            {'id': 'score_1', 'type': 'score', 'label': '综合评分', 'x': 500, 'y': 200, 'config': {'score_type': 'weighted', 'weights': {'technical': 0.3, 'fundamental': 0.3, 'sentiment': 0.2, 'fund_flow': 0.2}}},
            {'id': 'ai_1', 'type': 'ai_agent', 'label': 'AI深度分析', 'x': 700, 'y': 200, 'config': {'agent_id': '', 'top_n': 30}},
            {'id': 'end_1', 'type': 'end', 'label': '输出', 'x': 900, 'y': 200, 'config': {'output': 'list', 'top_n': 15}}
        ],
        'edges': [
            {'id': 'e1', 'source': 'start_1', 'target': 'filter_1'},
            {'id': 'e2', 'source': 'filter_1', 'target': 'score_1'},
            {'id': 'e3', 'source': 'score_1', 'target': 'ai_1'},
            {'id': 'e4', 'source': 'ai_1', 'target': 'end_1'}
        ]
    },
    {
        'id': 'template_chanlun',
        'name': '缠论选股策略',
        'description': '基于缠中说禅理论，识别中枢、背驰与三类买卖点',
        'tags': ['缠论', '技术分析', '买卖点'],
        'category': 'system',
        'nodes': [
            {'id': 'start_1', 'type': 'start', 'label': '起始', 'x': 100, 'y': 200, 'config': {'source': 'all'}},
            {'id': 'data_fetch_1', 'type': 'data_fetch', 'label': 'K线数据', 'x': 380, 'y': 200, 'config': {'data_type': 'kline', 'days': 120}},
            {'id': 'chanlun_zs', 'type': 'chanlun_zs', 'label': '中枢识别', 'x': 660, 'y': 200, 'config': {'level': '60min', 'min_bars': 3}},
            {'id': 'chanlun_bc', 'type': 'chanlun_bc', 'label': '背驰判断', 'x': 940, 'y': 200, 'config': {'bc_type': 'divergence', 'threshold': 0.1}},
            {'id': 'chanlun_buy1', 'type': 'chanlun_buy1', 'label': '缠论一买', 'x': 1220, 'y': 200, 'config': {'min_price': 2, 'max_price': 100, 'rsi_oversold': 30, 'kdj_oversold': 20}},
            {'id': 'risk_1', 'type': 'risk_control', 'label': '风控', 'x': 1500, 'y': 200, 'config': {'max_positions': 10, 'max_position_ratio': 0.1, 'exclude_st': True}},
            {'id': 'end_1', 'type': 'end', 'label': '输出', 'x': 1780, 'y': 200, 'config': {'output': 'list', 'top_n': 20}}
        ],
        'edges': [
            {'id': 'e1', 'source': 'start_1', 'target': 'data_fetch_1'},
            {'id': 'e2', 'source': 'data_fetch_1', 'target': 'chanlun_zs'},
            {'id': 'e3', 'source': 'chanlun_zs', 'target': 'chanlun_bc'},
            {'id': 'e4', 'source': 'chanlun_bc', 'target': 'chanlun_buy1'},
            {'id': 'e5', 'source': 'chanlun_buy1', 'target': 'risk_1'},
            {'id': 'e6', 'source': 'risk_1', 'target': 'end_1'}
        ]
    },
    {
        'id': 'template_chanlun_buy1',
        'name': '缠论一买策略',
        'description': '识别缠论第一类买点，抄底策略',
        'tags': ['缠论', '一买', '抄底'],
        'category': 'system',
        'nodes': [
            {'id': 'start_1', 'type': 'start', 'label': '起始', 'x': 100, 'y': 200, 'config': {'source': 'all'}},
            {'id': 'filter_price', 'type': 'filter', 'label': '价格筛选', 'x': 300, 'y': 200, 'config': {'filter_type': 'price_range', 'min_price': 2, 'max_price': 50}},
            {'id': 'data_fetch_1', 'type': 'data_fetch', 'label': 'K线数据', 'x': 500, 'y': 200, 'config': {'data_type': 'kline', 'days': 120}},
            {'id': 'chanlun_zs', 'type': 'chanlun_zs', 'label': '中枢识别', 'x': 700, 'y': 200, 'config': {'level': '60min', 'min_bars': 3}},
            {'id': 'chanlun_bc', 'type': 'chanlun_bc', 'label': '背驰判断', 'x': 900, 'y': 200, 'config': {'bc_type': 'divergence', 'threshold': 0.1}},
            {'id': 'chanlun_buy1', 'type': 'chanlun_buy1', 'label': '缠论一买', 'x': 1100, 'y': 200, 'config': {'min_price': 2, 'max_price': 50, 'rsi_oversold': 30, 'kdj_oversold': 20}},
            {'id': 'risk_1', 'type': 'risk_control', 'label': '风控', 'x': 1300, 'y': 200, 'config': {'max_positions': 5, 'max_position_ratio': 0.1, 'exclude_st': True}},
            {'id': 'end_1', 'type': 'end', 'label': '输出', 'x': 1500, 'y': 200, 'config': {'output': 'list', 'top_n': 10}}
        ],
        'edges': [
            {'id': 'e1', 'source': 'start_1', 'target': 'filter_price'},
            {'id': 'e2', 'source': 'filter_price', 'target': 'data_fetch_1'},
            {'id': 'e3', 'source': 'data_fetch_1', 'target': 'chanlun_zs'},
            {'id': 'e4', 'source': 'chanlun_zs', 'target': 'chanlun_bc'},
            {'id': 'e5', 'source': 'chanlun_bc', 'target': 'chanlun_buy1'},
            {'id': 'e6', 'source': 'chanlun_buy1', 'target': 'risk_1'},
            {'id': 'e7', 'source': 'risk_1', 'target': 'end_1'}
        ]
    },
    {
        'id': 'template_chanlun_buy2',
        'name': '缠论二买策略',
        'description': '识别缠论第二类买点，回调确认策略',
        'tags': ['缠论', '二买', '回调'],
        'category': 'system',
        'nodes': [
            {'id': 'start_1', 'type': 'start', 'label': '起始', 'x': 100, 'y': 200, 'config': {'source': 'all'}},
            {'id': 'filter_volume', 'type': 'filter', 'label': '量能筛选', 'x': 300, 'y': 200, 'config': {'filter_type': 'volume_ratio', 'threshold': 1.2}},
            {'id': 'data_fetch_1', 'type': 'data_fetch', 'label': 'K线数据', 'x': 500, 'y': 200, 'config': {'data_type': 'kline', 'days': 90}},
            {'id': 'chanlun_zs', 'type': 'chanlun_zs', 'label': '中枢识别', 'x': 700, 'y': 200, 'config': {'level': '60min', 'min_bars': 3}},
            {'id': 'chanlun_buy2', 'type': 'chanlun_buy2', 'label': '缠论二买', 'x': 900, 'y': 200, 'config': {}},
            {'id': 'combine_1', 'type': 'combine', 'label': '组合', 'x': 1100, 'y': 200, 'config': {'strategy': 'top_n', 'top_n': 20}},
            {'id': 'end_1', 'type': 'end', 'label': '输出', 'x': 1300, 'y': 200, 'config': {'output': 'list', 'top_n': 15}}
        ],
        'edges': [
            {'id': 'e1', 'source': 'start_1', 'target': 'filter_volume'},
            {'id': 'e2', 'source': 'filter_volume', 'target': 'data_fetch_1'},
            {'id': 'e3', 'source': 'data_fetch_1', 'target': 'chanlun_zs'},
            {'id': 'e4', 'source': 'chanlun_zs', 'target': 'chanlun_buy2'},
            {'id': 'e5', 'source': 'chanlun_buy2', 'target': 'combine_1'},
            {'id': 'e6', 'source': 'combine_1', 'target': 'end_1'}
        ]
    },
    {
        'id': 'template_chanlun_buy3',
        'name': '缠论三买策略',
        'description': '识别缠论第三类买点，突破确认策略',
        'tags': ['缠论', '三买', '突破'],
        'category': 'system',
        'nodes': [
            {'id': 'start_1', 'type': 'start', 'label': '起始', 'x': 100, 'y': 200, 'config': {'source': 'all'}},
            {'id': 'filter_price', 'type': 'filter', 'label': '价格筛选', 'x': 300, 'y': 200, 'config': {'filter_type': 'price_range', 'min_price': 5, 'max_price': 100}},
            {'id': 'data_fetch_1', 'type': 'data_fetch', 'label': 'K线数据', 'x': 500, 'y': 200, 'config': {'data_type': 'kline', 'days': 60}},
            {'id': 'chanlun_zs', 'type': 'chanlun_zs', 'label': '中枢识别', 'x': 700, 'y': 200, 'config': {'level': '60min', 'min_bars': 3}},
            {'id': 'chanlun_buy3', 'type': 'chanlun_buy3', 'label': '缠论三买', 'x': 900, 'y': 200, 'config': {'min_price': 5, 'max_price': 100, 'vol_threshold': 1.5}},
            {'id': 'end_1', 'type': 'end', 'label': '输出', 'x': 1100, 'y': 200, 'config': {'output': 'list', 'top_n': 15}}
        ],
        'edges': [
            {'id': 'e1', 'source': 'start_1', 'target': 'filter_price'},
            {'id': 'e2', 'source': 'filter_price', 'target': 'data_fetch_1'},
            {'id': 'e3', 'source': 'data_fetch_1', 'target': 'chanlun_zs'},
            {'id': 'e4', 'source': 'chanlun_zs', 'target': 'chanlun_buy3'},
            {'id': 'e5', 'source': 'chanlun_buy3', 'target': 'end_1'}
        ]
    }
]


def init_default_templates():
    """初始化默认模板"""
    storage = WorkflowTemplateStorage()
    count = 0

    for tmpl_data in DEFAULT_TEMPLATES:
        existing = storage.get_template(tmpl_data['id'])
        if existing:
            print(f"Template '{tmpl_data['name']}' already exists, skipping...")
            continue

        now = beijing_now().isoformat()
        template = WorkflowTemplate(
            id=tmpl_data['id'],
            name=tmpl_data['name'],
            description=tmpl_data['description'],
            tags=tmpl_data['tags'],
            nodes=[WorkflowNode.from_dict(n) for n in tmpl_data['nodes']],
            edges=[WorkflowEdge.from_dict(e) for e in tmpl_data['edges']],
            is_public=True,
            owner_id=None,
            category=tmpl_data.get('category', 'system'),
            created_at=now,
            updated_at=now
        )

        if storage.save_template(template):
            print(f"Template '{tmpl_data['name']}' created successfully!")
            count += 1
        else:
            print(f"Failed to create template '{tmpl_data['name']}'")

    print(f"\nInitialization complete! {count}/{len(DEFAULT_TEMPLATES)} templates created.")


if __name__ == '__main__':
    init_default_templates()