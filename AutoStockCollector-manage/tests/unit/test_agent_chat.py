import sys
import os
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def make_app():
    from main import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app


class TestAgentChatEndpoint:
    def test_missing_message_returns_400(self):
        app = make_app()
        with app.test_client() as c:
            rv = c.post('/api/v1/ai/agent-chat',
                        json={},
                        content_type='application/json')
            assert rv.status_code == 400
            data = json.loads(rv.data)
            assert data['success'] is False
            assert 'message' in data['error']

    def test_returns_event_stream_content_type(self):
        app = make_app()
        with app.test_client() as c:
            with patch('modules.ai.foundation.llm_router.LLMRouter.chat_stream',
                       return_value=iter(['测试', '回复'])):
                rv = c.post('/api/v1/ai/agent-chat',
                            json={'message': '你好'},
                            content_type='application/json')
                assert rv.status_code == 200
                assert 'text/event-stream' in rv.content_type

    def test_build_agent_context_technical(self):
        """_build_agent_context 为技术分析师生成正确字段"""
        from api.routes import _build_agent_context

        class FakeBundle:
            code = 'sh600000'
            name = '浦发银行'
            closes = [10.0, 9.8, 9.9, 10.1, 9.7, 9.5, 9.6, 9.8, 10.0, 10.2,
                      10.3, 10.1, 9.9, 9.8, 10.0, 10.2, 10.4, 10.3, 10.1, 9.9]
            volumes = [1e6] * 20
            pe = 8.5
            pb = 0.7
            main_net_inflow = None
            news = []
            roe = ps = gross_margin = debt_ratio = revenue_growth = profit_growth = None

        ctx = _build_agent_context('technical_analyst', FakeBundle(), {'trend': 65, 'volume': 70})
        assert '浦发银行' in ctx
        assert '技术评分' in ctx
        assert 'MA5' in ctx or 'MA20' in ctx

    def test_build_agent_context_no_agent_shows_basic(self):
        from api.routes import _build_agent_context

        class FakeBundle:
            code = 'sh600000'
            name = '浦发银行'
            closes = [10.0, 9.8, 9.9]
            volumes = []
            pe = 8.5
            pb = 0.7
            main_net_inflow = None
            news = []
            roe = ps = gross_margin = debt_ratio = revenue_growth = profit_growth = None

        ctx = _build_agent_context('', FakeBundle(), {})
        assert '浦发银行' in ctx
        assert '10.0' in ctx
