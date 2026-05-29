"""
模型列表拉取模块单元测试
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from modules.ai.models.fetcher import ModelListFetcher, ModelCache


class TestModelCache:
    """ModelCache 缓存测试"""

    def test_cache_set_and_get(self):
        """测试缓存设置和获取"""
        cache = ModelCache(ttl_seconds=3600)
        models = [{'id': 'test-model', 'name': 'Test Model'}]
        cache.set('openai', models)

        result = cache.get('openai')
        assert result == models

    def test_cache_expiration(self):
        """测试缓存过期"""
        cache = ModelCache(ttl_seconds=1)

        cache._cache['openai'] = {
            'models': [{'id': 'test'}],
            '_cached_at': datetime.now() - timedelta(seconds=2)
        }

        result = cache.get('openai')
        assert result is None

    def test_cache_invalidate(self):
        """测试缓存清除"""
        cache = ModelCache()
        cache.set('openai', [{'id': 'test1'}])
        cache.set('anthropic', [{'id': 'test2'}])

        cache.invalidate('openai')
        assert cache.get('openai') is None
        assert cache.get('anthropic') is not None

        cache.invalidate()
        assert cache.get('anthropic') is None

    def test_get_all_cached(self):
        """测试获取所有缓存"""
        cache = ModelCache(ttl_seconds=3600)
        cache.set('openai', [{'id': 'test1'}])
        cache.set('anthropic', [{'id': 'test2'}])

        all_cached = cache.get_all_cached()
        assert 'openai' in all_cached
        assert 'anthropic' in all_cached


class TestModelListFetcher:
    """ModelListFetcher 测试"""

    def test_https_only(self):
        """测试仅允许HTTPS"""
        fetcher = ModelListFetcher()

        with pytest.raises(ValueError, match="Only HTTPS"):
            fetcher._fetch_from_api('openai', 'test-key', 'http://http.example.com')

    def test_api_key_required(self):
        """测试API密钥必填"""
        fetcher = ModelListFetcher()

        with pytest.raises(ValueError, match="API key is required"):
            fetcher._fetch_from_api('openai', '', 'https://api.openai.com')

    def test_unknown_provider(self):
        """测试未知提供商"""
        fetcher = ModelListFetcher()

        with pytest.raises(ValueError, match="Unknown provider"):
            fetcher._fetch_from_api('unknown', 'test-key', None)

    def test_build_headers_anthropic(self):
        """测试Anthropic请求头构建"""
        fetcher = ModelListFetcher()
        headers = fetcher._build_headers('anthropic', 'test-key')

        assert 'Authorization' in headers
        assert 'x-api-key' in headers
        assert headers['anthropic-version'] == '2023-06-01'

    def test_build_headers_others(self):
        """测试其他提供商请求头构建"""
        fetcher = ModelListFetcher()

        for provider in ['openai', 'deepseek', 'moonshot']:
            headers = fetcher._build_headers(provider, 'test-key')
            assert 'Authorization' in headers
            assert headers['Authorization'] == 'Bearer test-key'
            assert 'x-api-key' not in headers

    def test_build_url(self):
        """测试URL构建"""
        fetcher = ModelListFetcher()

        url = fetcher._build_url('https://api.openai.com/v1')
        assert url == 'https://api.openai.com/v1/models'

        url = fetcher._build_url('https://api.openai.com/v1/')
        assert url == 'https://api.openai.com/v1/models'

    def test_parse_response_dict_data(self):
        """测试解析dict格式响应"""
        fetcher = ModelListFetcher()
        data = {
            'data': [
                {'id': 'gpt-4', 'name': 'GPT-4'},
                {'id': 'gpt-3.5', 'name': 'GPT-3.5'}
            ]
        }

        result = fetcher._parse_response(data, 'openai')
        assert len(result) == 2
        assert result[0]['id'] == 'gpt-4'
        assert result[1]['id'] == 'gpt-3.5'

    def test_parse_response_list_format(self):
        """测试解析list格式响应"""
        fetcher = ModelListFetcher()
        data = [
            {'id': 'model-1'},
            {'id': 'model-2'}
        ]

        result = fetcher._parse_response(data, 'openai')
        assert len(result) == 2

    def test_parse_response_empty_data(self):
        """测试解析空数据"""
        fetcher = ModelListFetcher()

        with pytest.raises(ValueError, match="Empty response"):
            fetcher._parse_response({}, 'openai')

    def test_parse_response_empty_list(self):
        """测试解析空列表"""
        fetcher = ModelListFetcher()

        with pytest.raises(ValueError, match="Model list is empty"):
            fetcher._parse_response({'data': []}, 'openai')

    def test_parse_response_invalid_type(self):
        """测试解析无效类型"""
        fetcher = ModelListFetcher()

        with pytest.raises(ValueError, match="Invalid response type"):
            fetcher._parse_response("invalid string", 'openai')

    def test_parse_response_handles_missing_id(self):
        """测试解析时处理缺失ID"""
        fetcher = ModelListFetcher()
        data = {
            'data': [
                {'id': 'valid-model'},
                {'id': None, 'name': 'has-name'},
                {'id': None, 'name': None},
                {}
            ]
        }

        result = fetcher._parse_response(data, 'openai')
        assert len(result) == 2
        assert result[0]['id'] == 'valid-model'

    def test_get_fallback_models(self):
        """测试获取备用模型"""
        fetcher = ModelListFetcher()

        models = fetcher._get_fallback_models('openai')
        assert len(models) > 0
        assert models[0]['id'] == 'gpt-4o-mini'

        unknown_models = fetcher._get_fallback_models('unknown')
        assert unknown_models == []

    def test_get_default_model(self):
        """测试获取默认模型"""
        fetcher = ModelListFetcher()

        assert fetcher.get_default_model('openai') == 'gpt-4o-mini'
        assert fetcher.get_default_model('anthropic') == 'claude-3-5-sonnet-latest'
        assert fetcher.get_default_model('minimax') == 'MiniMax-Text-01'
        assert fetcher.get_default_model('unknown') is None

    def test_invalidate_cache(self):
        """测试缓存失效"""
        fetcher = ModelListFetcher()
        fetcher._cache.set('openai', [{'id': 'test'}])

        fetcher.invalidate_cache('openai')
        assert fetcher._cache.get('openai') is None

    def test_get_cache_status(self):
        """测试获取缓存状态"""
        fetcher = ModelListFetcher()
        fetcher._cache.set('openai', [{'id': 'test'}])

        status = fetcher.get_cache_status()
        assert 'cached_providers' in status
        assert 'cache_ttl' in status
        assert 'openai' in status['cached_providers']


class TestModelListFetcherWithMock:
    """带Mock的API测试"""

    @patch('requests.get')
    def test_fetch_models_success(self, mock_get):
        """测试成功拉取模型"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {'id': 'gpt-4', 'type': 'chat'},
                {'id': 'gpt-3.5', 'type': 'chat'}
            ]
        }
        mock_get.return_value = mock_response

        fetcher = ModelListFetcher()
        models = fetcher.fetch_models('openai', 'test-key')

        assert len(models) == 2
        assert models[0]['id'] == 'gpt-4'

    @patch('requests.get')
    def test_fetch_models_uses_cache(self, mock_get):
        """测试使用缓存"""
        fetcher = ModelListFetcher()
        cached_models = [{'id': 'cached-model'}]
        fetcher._cache.set('openai', cached_models)

        models = fetcher.fetch_models('openai', 'test-key')

        assert models == cached_models
        mock_get.assert_not_called()

    @patch('requests.get')
    def test_fetch_models_api_failure_uses_fallback(self, mock_get):
        """测试API失败时使用备用模型"""
        mock_get.side_effect = Exception("Network error")

        fetcher = ModelListFetcher()
        models = fetcher.fetch_models('openai', 'test-key')

        assert len(models) > 0
        assert mock_get.called

    @patch('requests.get')
    def test_fetch_models_401_returns_fallback(self, mock_get):
        """测试401错误时返回备用模型"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        fetcher = ModelListFetcher()
        models = fetcher.fetch_models('openai', 'invalid-key')

        assert len(models) > 0
        assert models[0]['id'] == 'gpt-4o-mini'

    @patch('requests.get')
    def test_fetch_models_429_returns_fallback(self, mock_get):
        """测试429错误时返回备用模型"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        fetcher = ModelListFetcher()
        models = fetcher.fetch_models('openai', 'test-key')

        assert len(models) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])