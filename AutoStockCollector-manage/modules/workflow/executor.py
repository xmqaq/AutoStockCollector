"""
选股工作流执行引擎
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.storage.mongo_storage import StockInfoStorage, KlineStorage, FundFlowStorage, NewsStorage
from modules.ai_selector.strategies.base import SelectionResult, RiskLevel
from modules.ai.ai_analyzer import AIAnalyzer
from utils.logger import get_logger


logger = get_logger(__name__)


class WorkflowExecutor:
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.stock_info = StockInfoStorage()
        self.kline = KlineStorage()
        self.fund_flow = FundFlowStorage()
        self.news = NewsStorage()
        self.ai_analyzer = AIAnalyzer()
        self.codes: List[str] = []
        self.results: List[SelectionResult] = []

    def execute(self, nodes: List[Dict], edges: List[Dict], params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Starting workflow execution: {self.workflow_id}")
        start_time = datetime.now()
        execution_log: List[Dict[str, Any]] = []

        try:
            self._init_codes()
            node_map = {n['id']: n for n in nodes}
            execution_order = self._topological_sort(nodes, edges)

            start_log = {
                "node": "start",
                "label": "初始化",
                "status": "completed",
                "stocks_count": len(self.codes),
                "message": f"加载 {len(self.codes)} 只有效股票"
            }
            execution_log.append(start_log)

            for node in execution_order:
                result = self._execute_node(node, node_map, params)
                execution_log.append(result)

            duration = (datetime.now() - start_time).total_seconds()
            return {
                "success": True,
                "workflow_id": self.workflow_id,
                "result_count": len(self.results),
                "duration": duration,
                "results": [r.to_dict() for r in self.results],
                "execution_time": datetime.now().isoformat(),
                "execution_log": execution_log
            }
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "success": False,
                "workflow_id": self.workflow_id,
                "error": str(e),
                "execution_time": datetime.now().isoformat(),
                "execution_log": execution_log
            }

    def _init_codes(self):
        all_codes = self.stock_info.distinct("code")
        valid_codes = []
        for code in all_codes:
            info = self.stock_info.get_by_code(code)
            if info:
                name = info.get("name", "")
                if not any(name.startswith(p) for p in ["*ST", "ST", "PT", "退市"]):
                    status = info.get("status", "")
                    if status not in ("退市", "delisted"):
                        valid_codes.append(code)
        self.codes = valid_codes
        logger.info(f"Initialized {len(self.codes)} valid stock codes")

    def _topological_sort(self, nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
        in_degree = {n['id']: 0 for n in nodes}
        graph = {n['id']: [] for n in nodes}

        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source and target:
                in_degree[target] = in_degree.get(target, 0) + 1
                graph[source].append(target)

        queue = [nid for nid, degree in in_degree.items() if degree == 0]
        sorted_nodes = []

        node_map = {n['id']: n for n in nodes}
        while queue:
            node_id = queue.pop(0)
            sorted_nodes.append(node_map[node_id])
            for neighbor in graph[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return sorted_nodes

    def _execute_node(self, node: Dict, node_map: Dict, params: Dict) -> Dict[str, Any]:
        node_type = node.get('type')
        node_id = node.get('id')
        node_label = node.get('label')
        node_config = node.get('config', {})
        logger.info(f"Executing node: {node_label} ({node_type})")

        try:
            if node_type == 'start':
                self._execute_start_node(node_config, params)
            elif node_type == 'filter':
                self._execute_filter_node(node_config, params)
            elif node_type == 'score':
                self._execute_score_node(node_config, params)
            elif node_type == 'ai_agent':
                self._execute_ai_agent_node(node_config, params)
            elif node_type == 'combine':
                self._execute_combine_node(node_config, params)
            elif node_type == 'risk_control':
                self._execute_risk_control_node(node_config, params)
            elif node_type == 'end':
                self._execute_end_node(node_config, params)
            elif node_type == 'data_fetch':
                self._execute_data_fetch_node(node_config, params)
            elif node_type == 'technical_indicator':
                self._execute_technical_indicator_node(node_config, params)
            elif node_type == 'fundamental_filter':
                self._execute_fundamental_filter_node(node_config, params)
            elif node_type == 'market_sentiment':
                self._execute_market_sentiment_node(node_config, params)
            elif node_type == 'index_components':
                self._execute_index_components_node(node_config, params)
            elif node_type == 'compare':
                self._execute_compare_node(node_config, params)

            return {
                "node": node_id,
                "label": node_label,
                "type": node_type,
                "status": "completed",
                "stocks_count": len(self.codes) if node_type in ('start', 'filter') else len(self.results),
                "message": self._get_node_result_message(node_type, node_config)
            }
        except Exception as e:
            logger.error(f"Node {node_id} execution failed: {e}")
            return {
                "node": node_id,
                "label": node_label,
                "type": node_type,
                "status": "failed",
                "stocks_count": 0,
                "message": f"执行失败: {str(e)}"
            }

    def _get_node_result_message(self, node_type: str, config: Dict) -> str:
        if node_type == 'start':
            return f"从数据源加载股票"
        elif node_type == 'filter':
            filter_type = config.get('filter_type', 'unknown')
            return f"筛选 ({filter_type})"
        elif node_type == 'score':
            score_type = config.get('score_type', 'unknown')
            return f"评分 ({score_type})"
        elif node_type == 'ai_agent':
            agent_id = config.get('agent_id', 'default')
            top_n = config.get('top_n', 20)
            return f"AI分析 (前{top_n}只)"
        elif node_type == 'combine':
            strategy = config.get('strategy', 'unknown')
            return f"组合 ({strategy})"
        elif node_type == 'risk_control':
            return "风险控制"
        elif node_type == 'end':
            return "输出结果"
        elif node_type == 'data_fetch':
            data_type = config.get('data_type', 'kline')
            return f"获取数据 ({data_type})"
        elif node_type == 'technical_indicator':
            indicator = config.get('indicator_type', 'ma')
            return f"计算指标 ({indicator})"
        elif node_type == 'fundamental_filter':
            ftype = config.get('filter_type', 'pe')
            return f"基本面筛选 ({ftype})"
        elif node_type == 'market_sentiment':
            atype = config.get('analysis_type', 'overall')
            return f"市场情绪 ({atype})"
        elif node_type == 'index_components':
            index_code = config.get('index_code', '000300.sh')
            return f"指数成分 ({index_code})"
        elif node_type == 'compare':
            ctype = config.get('compare_type', 'performance')
            return f"对比分析 ({ctype})"
        return ""

    def _execute_start_node(self, config: Dict, params: Dict):
        source = config.get('source', 'all')
        if source == 'watchlist':
            from core.storage.mongo_storage import WatchlistStorage
            watchlist = WatchlistStorage()
            watch_codes = watchlist.get_user_watchlist('default')
            self.codes = [w.get('code') for w in watch_codes if w.get('code')]
        elif source == 'sector':
            sector = config.get('sector', '')
            if sector:
                from core.storage.mongo_storage import BlockStorage
                block = BlockStorage()
                block_stocks = block.get_blocks_by_type('industry')
                self.codes = [s.get('code') for s in block_stocks if s.get('code') == sector]
        logger.info(f"Start node: loaded {len(self.codes)} codes from {source}")

    def _execute_filter_node(self, config: Dict, params: Dict):
        filter_type = config.get('filter_type', 'price_range')
        filtered_codes = []

        for code in self.codes:
            if self._check_filter(code, filter_type, config):
                filtered_codes.append(code)

        logger.info(f"Filter node ({filter_type}): {len(self.codes)} -> {len(filtered_codes)}")
        self.codes = filtered_codes

    def _check_filter(self, code: str, filter_type: str, config: Dict) -> bool:
        if filter_type == 'price_range':
            klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=1)
            if not klines:
                return False
            price = klines[0].get('close', 0)
            min_price = config.get('min_price', 0)
            max_price = config.get('max_price', float('inf'))
            return min_price <= price <= max_price

        elif filter_type == 'volume_ratio':
            klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=20)
            if len(klines) < 5:
                return False
            current_vol = klines[0].get('volume', 0)
            avg_vol = sum(k.get('volume', 0) for k in klines[:5]) / 5
            ratio = current_vol / avg_vol if avg_vol > 0 else 0
            threshold = config.get('threshold', 1.5)
            return ratio >= threshold

        elif filter_type == 'pe_range':
            info = self.stock_info.get_by_code(code)
            if not info:
                return False
            pe = info.get('pe', 0) or 0
            min_pe = config.get('min_pe', 0)
            max_pe = config.get('max_pe', float('inf'))
            return min_pe <= pe <= max_pe

        elif filter_type == 'pb_range':
            info = self.stock_info.get_by_code(code)
            if not info:
                return False
            pb = info.get('pb', 0) or 0
            min_pb = config.get('min_pb', 0)
            max_pb = config.get('max_pb', float('inf'))
            return min_pb <= pb <= max_pb

        elif filter_type == 'trend':
            klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=20)
            if len(klines) < 20:
                return False
            current = klines[0].get('close', 0)
            ma20 = sum(k.get('close', 0) for k in klines[:20]) / 20
            trend_type = config.get('trend_type', 'up')
            if trend_type == 'up':
                return current > ma20
            else:
                return current < ma20

        elif filter_type == 'fund_flow':
            flow = self.fund_flow.get_latest_flow(code)
            if not flow:
                return False
            main_inflow = flow.get('main_net_inflow', 0)
            threshold = config.get('threshold', 0)
            direction = config.get('direction', 'positive')
            if direction == 'positive':
                return main_inflow > threshold
            else:
                return main_inflow < -threshold

        elif filter_type == 'market_cap':
            info = self.stock_info.get_by_code(code)
            if not info:
                return False
            market_cap = info.get('total_mv', 0) or 0
            if not market_cap:
                market_cap = info.get('market_cap', 0) or 0
            min_cap = config.get('min_cap', 0) * 1e8
            max_cap = config.get('max_cap', float('inf')) * 1e8
            return min_cap <= market_cap <= max_cap

        elif filter_type == 'exclude_st':
            info = self.stock_info.get_by_code(code)
            if not info:
                return True
            name = info.get('name', '')
            return not any(name.startswith(p) for p in ['*ST', 'ST', 'PT', '退市'])

        elif filter_type == 'news_sentiment':
            news = self.news.get_latest_news(code=code, limit=20)
            if not news:
                return True
            positive_keywords = ["增长", "盈利", "突破", "利好", "创新", "合作", "升级", "扩张"]
            negative_keywords = ["亏损", "下跌", "减持", "利空", "违规", "风险", "诉讼", "处罚"]
            positive_count = sum(1 for n in news if any(kw in (n.get('title', '') + n.get('content', '')) for kw in positive_keywords))
            negative_count = sum(1 for n in news if any(kw in (n.get('title', '') + n.get('content', '')) for kw in negative_keywords))
            total = positive_count + negative_count
            if total == 0:
                return True
            min_positive_ratio = config.get('min_positive_ratio', 0.5)
            return (positive_count / total) >= min_positive_ratio

        return True

    def _execute_score_node(self, config: Dict, params: Dict):
        score_type = config.get('score_type', 'weighted')
        weights = config.get('weights', {
            'technical': 0.25,
            'fundamental': 0.25,
            'sentiment': 0.25,
            'fund_flow': 0.25
        })

        scored_results = []
        for code in self.codes:
            try:
                factors = self._calculate_factors(code)
                score = self._calculate_composite_score(factors, score_type, weights)
                result = self._build_result(code, factors, score)
                scored_results.append(result)
            except Exception as e:
                logger.warning(f"Scoring failed for {code}: {e}")

        scored_results.sort(key=lambda x: x.score, reverse=True)
        self.results = scored_results
        logger.info(f"Score node ({score_type}): scored {len(self.results)} stocks")

    def _calculate_factors(self, code: str) -> Dict[str, float]:
        factors = {}

        klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=60)
        if klines:
            closes = [k.get('close', 0) for k in klines]
            volumes = [k.get('volume', 0) for k in klines]
            current = closes[0]

            ma5 = sum(closes[:5]) / 5 if len(closes) >= 5 else current
            ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else current
            ma60 = sum(closes[:60]) / 60 if len(closes) >= 60 else current

            factors['current_price'] = current
            factors['ma5'] = ma5
            factors['ma20'] = ma20
            factors['ma60'] = ma60
            factors['ma5_trend'] = 1 if current > ma5 else -1
            factors['ma20_trend'] = 1 if current > ma20 else -1
            factors['ma60_trend'] = 1 if current > ma60 else -1
            factors['trend'] = 1 if current > ma20 else -1

            if len(closes) >= 2 and closes[1] > 0:
                factors['change_pct'] = (current - closes[1]) / closes[1] * 100
            else:
                factors['change_pct'] = 0

            avg_vol = sum(volumes) / len(volumes) if volumes else 1
            factors['volume_ratio'] = volumes[0] / avg_vol if avg_vol > 0 else 1

            factors['technical_score'] = self._calculate_technical_score(factors)

        info = self.stock_info.get_by_code(code)
        if info:
            factors['name'] = info.get('name', '')
            factors['pe'] = info.get('pe', 0) or 0
            factors['pb'] = info.get('pb', 0) or 0
            factors['market_cap'] = info.get('total_mv', 0) or info.get('market_cap', 0) or 0
            factors['fundamental_score'] = self._calculate_fundamental_score(info)
        else:
            factors['name'] = ''
            factors['pe'] = 0
            factors['pb'] = 0
            factors['market_cap'] = 0
            factors['fundamental_score'] = 50.0

        flow = self.fund_flow.get_latest_flow(code)
        if flow:
            main_inflow = flow.get('main_net_inflow', 0)
            super_inflow = flow.get('super_net_inflow', 0)
            big_inflow = flow.get('big_net_inflow', 0)
            factors['main_inflow'] = main_inflow
            factors['super_inflow'] = super_inflow
            factors['big_inflow'] = big_inflow
            total_inflow = main_inflow + super_inflow + big_inflow
            factors['fund_flow_score'] = min(100, 50 + total_inflow / 1e7) if total_inflow > 0 else max(0, 50 + total_inflow / 1e7)
        else:
            factors['main_inflow'] = 0
            factors['super_inflow'] = 0
            factors['big_inflow'] = 0
            factors['fund_flow_score'] = 50.0

        news = self.news.get_latest_news(code=code, limit=20)
        factors['sentiment_score'] = self._calculate_sentiment_score(news)

        return factors

    def _calculate_technical_score(self, factors: Dict[str, float]) -> float:
        score = 50.0

        ma5_trend = factors.get('ma5_trend', 0)
        ma20_trend = factors.get('ma20_trend', 0)
        ma60_trend = factors.get('ma60_trend', 0)

        if ma5_trend > 0:
            score += 10
        else:
            score -= 10

        if ma20_trend > 0:
            score += 10
        else:
            score -= 10

        if ma60_trend > 0:
            score += 10
        else:
            score -= 10

        change_pct = factors.get('change_pct', 0)
        if change_pct > 3:
            score += 10
        elif change_pct < -3:
            score -= 10

        vol_ratio = factors.get('volume_ratio', 1)
        if vol_ratio > 1.5:
            score += 10
        elif vol_ratio < 0.7:
            score -= 5

        return max(0, min(100, score))

    def _calculate_fundamental_score(self, info: Dict[str, Any]) -> float:
        score = 50.0
        pe = info.get('pe') or 0
        if pe and 5 < pe < 25:
            score += 15

        pb = info.get('pb') or 0
        if pb and 0.5 < pb < 3:
            score += 10

        return max(0, min(100, score))

    def _calculate_sentiment_score(self, news: List[Dict[str, Any]]) -> float:
        if not news:
            return 50.0

        positive_keywords = ["增长", "盈利", "突破", "利好", "创新", "合作"]
        negative_keywords = ["亏损", "下跌", "减持", "利空", "违规", "风险"]

        positive_count = 0
        negative_count = 0

        for n in news:
            text = (n.get('title', '') + n.get('content', ''))
            for kw in positive_keywords:
                if kw in text:
                    positive_count += 1
                    break
            for kw in negative_keywords:
                if kw in text:
                    negative_count += 1
                    break

        total = positive_count + negative_count
        if total == 0:
            return 50.0

        return (positive_count / total) * 100

    def _calculate_composite_score(self, factors: Dict[str, float], score_type: str, weights: Dict[str, float]) -> float:
        if score_type == 'weighted':
            technical = factors.get('technical_score', 50.0)
            fundamental = factors.get('fundamental_score', 50.0)
            sentiment = factors.get('sentiment_score', 50.0)
            fund_flow = factors.get('fund_flow_score', 50.0)

            return (
                technical * weights.get('technical', 0.25) +
                fundamental * weights.get('fundamental', 0.25) +
                sentiment * weights.get('sentiment', 0.25) +
                fund_flow * weights.get('fund_flow', 0.25)
            )
        elif score_type == 'technical':
            return factors.get('technical_score', 50.0)
        elif score_type == 'fundamental':
            return factors.get('fundamental_score', 50.0)
        elif score_type == 'fund_flow':
            return factors.get('fund_flow_score', 50.0)
        elif score_type == 'sentiment':
            return factors.get('sentiment_score', 50.0)
        else:
            return factors.get('technical_score', 50.0)

    def _build_result(self, code: str, factors: Dict[str, float], score: float) -> SelectionResult:
        current_price = factors.get("current_price", 0)

        recommendation = "观望"
        risk_level = RiskLevel.MEDIUM

        if score >= 75:
            recommendation = "强烈推荐"
            risk_level = RiskLevel.LOW
        elif score >= 65:
            recommendation = "买入"
            risk_level = RiskLevel.MEDIUM
        elif score >= 55:
            recommendation = "谨慎买入"
            risk_level = RiskLevel.MEDIUM
        elif score <= 35:
            recommendation = "回避"
            risk_level = RiskLevel.HIGH

        stop_loss = current_price * 0.95 if current_price > 0 else 0
        target_price = current_price * 1.15 if current_price > 0 else 0

        return SelectionResult(
            code=code,
            name=factors.get("name", ""),
            score=score,
            technical_score=factors.get("technical_score", 50.0),
            fundamental_score=factors.get("fundamental_score", 50.0),
            sentiment_score=factors.get("sentiment_score", 50.0),
            fund_flow_score=factors.get("fund_flow_score", 50.0),
            recommendation=recommendation,
            risk_level=risk_level,
            stop_loss=stop_loss,
            target_price=target_price,
            support_levels=[stop_loss],
            resistance_levels=[target_price],
            risk_factors=[],
            strategy=self.workflow_id
        )

    def _execute_ai_agent_node(self, config: Dict, params: Dict):
        agent_id = config.get('agent_id', '')
        if not agent_id:
            logger.warning("AI Agent node: no agent_id specified")
            return

        top_n = config.get('top_n', 20)
        results_to_analyze = self.results[:top_n] if self.results else []

        for result in results_to_analyze:
            try:
                analysis = self.ai_analyzer.analyze_stock(result.code)
                if analysis:
                    if analysis.get('scores', {}).get('composite'):
                        result.score = analysis['scores']['composite']
                    if analysis.get('llm', {}).get('recommendation'):
                        result.recommendation = analysis['llm']['recommendation']
                    if analysis.get('llm', {}).get('risk_factors'):
                        result.risk_factors = analysis['llm']['risk_factors']
            except Exception as e:
                logger.warning(f"AI Agent analysis failed for {result.code}: {e}")

        self.results.sort(key=lambda x: x.score, reverse=True)
        logger.info(f"AI Agent node: analyzed {len(results_to_analyze)} stocks with agent {agent_id}")

    def _execute_combine_node(self, config: Dict, params: Dict):
        strategy = config.get('strategy', 'top_n')
        top_n = config.get('top_n', 20)
        min_score = config.get('min_score', 60.0)

        if strategy == 'top_n':
            self.results = self.results[:top_n]
        elif strategy == 'min_score':
            self.results = [r for r in self.results if r.score >= min_score]
        elif strategy == 'diversify':
            max_per_sector = config.get('max_per_sector', 3)
            max_per_market_cap = config.get('max_per_market_cap', 5)

            sector_counts = {}
            market_cap_counts = {'large': 0, 'medium': 0, 'small': 0}
            diversified = []

            for result in self.results:
                if len(diversified) >= top_n:
                    break

                sector = result.metadata.get('sector', 'default')
                market_cap = result.metadata.get('market_cap', 0)

                if market_cap > 500e8:
                    cap_category = 'large'
                elif market_cap > 100e8:
                    cap_category = 'medium'
                else:
                    cap_category = 'small'

                can_add = True

                if sector_counts.get(sector, 0) >= max_per_sector:
                    can_add = False

                if market_cap_counts.get(cap_category, 0) >= max_per_market_cap:
                    can_add = False

                if can_add:
                    diversified.append(result)
                    sector_counts[sector] = sector_counts.get(sector, 0) + 1
                    market_cap_counts[cap_category] = market_cap_counts.get(cap_category, 0) + 1

            self.results = diversified
        elif strategy == 'weighted':
            weights = config.get('weights', {
                'technical': 0.25,
                'fundamental': 0.25,
                'fund_flow': 0.25,
                'sentiment': 0.25
            })

            for result in self.results:
                weighted_score = (
                    result.technical_score * weights.get('technical', 0.25) +
                    result.fundamental_score * weights.get('fundamental', 0.25) +
                    result.fund_flow_score * weights.get('fund_flow', 0.25) +
                    result.sentiment_score * weights.get('sentiment', 0.25)
                )
                result.score = weighted_score

            self.results.sort(key=lambda x: x.score, reverse=True)
            self.results = self.results[:top_n]

        logger.info(f"Combine node ({strategy}): {len(self.results)} stocks")

    def _execute_risk_control_node(self, config: Dict, params: Dict):
        max_positions = config.get('max_positions', 10)
        max_position_ratio = config.get('max_position_ratio', 0.1)
        exclude_st = config.get('exclude_st', True)
        exclude_limit_up = config.get('exclude_limit_up', False)

        if exclude_st:
            original_count = len(self.results)
            self.results = [r for r in self.results if not r.name.startswith(('*ST', 'ST'))]
            logger.info(f"Risk control: excluded {original_count - len(self.results)} ST stocks")

        if exclude_limit_up:
            original_count = len(self.results)
            change_pcts = params.get('change_pcts', {})
            self.results = [r for r in self.results if abs(change_pcts.get(r.code, 0)) < 9.9]
            logger.info(f"Risk control: excluded {original_count - len(self.results)} limit-up stocks")

        base_ratio = min(max_position_ratio, 1.0 / max(len(self.results), 1))

        risk_scores = []
        for result in self.results:
            risk_score = 50.0

            if result.risk_level.value == 'high':
                risk_score += 20
            elif result.risk_level.value == 'medium':
                risk_score += 10

            if result.score < 60:
                risk_score += 10

            risk_scores.append(risk_score)

        for i, result in enumerate(self.results):
            if risk_scores[i] > 60:
                result.position_ratio = base_ratio * 0.5
            else:
                result.position_ratio = base_ratio

        if len(self.results) > max_positions:
            self.results = self.results[:max_positions]

        logger.info(f"Risk control node: {len(self.results)} stocks after risk filtering")

    def _execute_end_node(self, config: Dict, params: Dict):
        output_type = config.get('output', 'list')
        top_n = config.get('top_n', 10)
        include_reasons = config.get('include_reasons', False)

        if output_type == 'list':
            self.results = self.results[:top_n]

        if include_reasons:
            for result in self.results:
                result.metadata['reasons'] = self._generate_pick_reason(result)

        logger.info(f"End node: workflow completed with {len(self.results)} results")

    def _generate_pick_reason(self, result) -> List[str]:
        reasons = []

        if result.technical_score >= 70:
            reasons.append(f"技术面表现优秀（评分：{result.technical_score:.1f}）")

        if result.fundamental_score >= 70:
            reasons.append(f"基本面质量良好（评分：{result.fundamental_score:.1f}）")

        if result.fund_flow_score >= 70:
            reasons.append(f"资金面呈现净流入（评分：{result.fund_flow_score:.1f}）")

        if result.sentiment_score >= 65:
            reasons.append(f"舆情信息偏正面（评分：{result.sentiment_score:.1f}）")

        if result.score >= 75:
            reasons.append("综合评分达到强势区域")
        elif result.score >= 65:
            reasons.append("综合评分处于中等偏上")

        if result.recommendation == "强烈推荐":
            reasons.append("系统给出强烈买入建议")
        elif result.recommendation == "买入":
            reasons.append("系统给出买入建议")

        if result.stop_loss > 0:
            reasons.append(f"建议止损位：{result.stop_loss:.2f}元")

        if result.target_price > 0 and result.current_price > 0:
            profit_ratio = (result.target_price - result.current_price) / result.current_price * 100
            reasons.append(f"目标涨幅：{profit_ratio:.1f}%")

        if not reasons:
            reasons.append("符合基本筛选条件")

        return reasons

    def _execute_data_fetch_node(self, config: Dict, params: Dict):
        data_type = config.get('data_type', 'kline')
        days = config.get('days', 60)
        limit = config.get('limit', 100)

        fetched_data: Dict[str, Any] = {}

        for code in self.codes[:limit]:
            if data_type == 'kline':
                klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=days)
                if klines:
                    fetched_data[code] = {
                        "kline": [k.to_dict() if hasattr(k, 'to_dict') else k for k in klines]
                    }
            elif data_type == 'realtime':
                info = self.stock_info.get_by_code(code)
                if info:
                    fetched_data[code] = {"info": info}
            elif data_type == 'financial':
                financials = self.financial.find_many({"code": code}, limit=1)
                if financials:
                    fetched_data[code] = {"financial": financials[0]}
            elif data_type == 'fund_flow':
                fund_flow = self.fund_flow.find_many({"code": code}, limit=1)
                if fund_flow:
                    fetched_data[code] = {"fund_flow": fund_flow[0]}
            elif data_type == 'sentiment':
                sentiment = self.news.get_sentiment_trend(code, days)
                if sentiment:
                    fetched_data[code] = {"sentiment": sentiment}
            elif data_type == 'signals':
                from core.storage.kline_storage import KlineStorage
                kline = KlineStorage()
                signals = kline.get_signals(code)
                if signals:
                    fetched_data[code] = {"signals": signals}

        params['fetched_data'] = fetched_data
        logger.info(f"Data fetch node ({data_type}): fetched {len(fetched_data)} records")

    def _execute_technical_indicator_node(self, config: Dict, params: Dict):
        indicator_type = config.get('indicator_type', 'ma')
        params_str = config.get('params', '5,20,60')
        params_list = [int(p.strip()) for p in params_str.split(',') if p.strip().isdigit()]

        indicator_data: Dict[str, Any] = {}

        for code in self.codes:
            klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=60)
            if not klines:
                continue

            closes = [k.get('close', 0) for k in klines]
            volumes = [k.get('volume', 0) for k in klines]

            if indicator_type == 'ma':
                ma_values = {}
                for period in params_list:
                    if len(closes) >= period:
                        ma_values[f'ma{period}'] = sum(closes[:period]) / period
                indicator_data[code] = {"ma": ma_values}
            elif indicator_type == 'ema':
                ema_values = {}
                for period in params_list:
                    if len(closes) >= period:
                        ema_values[f'ema{period}'] = self._calculate_ema(closes, period)
                indicator_data[code] = {"ema": ema_values}
            elif indicator_type == 'macd':
                macd_data = self._calculate_macd(closes)
                indicator_data[code] = {"macd": macd_data}
            elif indicator_type == 'kdj':
                kdj_data = self._calculate_kdj(closes)
                indicator_data[code] = {"kdj": kdj_data}
            elif indicator_type == 'rsi':
                rsi_data = self._calculate_rsi(closes)
                indicator_data[code] = {"rsi": rsi_data}
            elif indicator_type == 'boll':
                boll_data = self._calculate_boll(closes)
                indicator_data[code] = {"boll": boll_data}

        params['indicator_data'] = indicator_data
        logger.info(f"Technical indicator node ({indicator_type}): calculated {len(indicator_data)} records")

    def _calculate_ema(self, data: List[float], period: int) -> float:
        if len(data) < period:
            return 0
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _calculate_macd(self, closes: List[float], fast=12, slow=26, signal=9) -> Dict[str, float]:
        if len(closes) < slow:
            return {"dif": 0, "dea": 0, "macd": 0}

        ema_fast = self._calculate_ema(closes, fast)
        ema_slow = self._calculate_ema(closes, slow)
        dif = ema_fast - ema_slow
        dea = dif * 0.9 + dif * 0.1
        macd = (dif - dea) * 2

        return {"dif": dif, "dea": dea, "macd": macd}

    def _calculate_kdj(self, closes: List[float], period: int = 9) -> Dict[str, float]:
        if len(closes) < period:
            return {"k": 50, "d": 50, "j": 50}

        low_prices = closes[-period:]
        high_prices = closes[-period:]
        rsv = (closes[-1] - min(low_prices)) / (max(high_prices) - min(low_prices) + 0.0001) * 100

        k = 0.67 * 50 + 0.33 * rsv
        d = 0.67 * 50 + 0.33 * k
        j = 3 * k - 2 * d

        return {"k": k, "d": d, "j": j}

    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50

        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [c if c > 0 else 0 for c in changes[-period:]]
        losses = [-c if c < 0 else 0 for c in changes[-period:]]

        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_boll(self, closes: List[float], period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        if len(closes) < period:
            return {"upper": 0, "middle": 0, "lower": 0}

        recent = closes[:period]
        middle = sum(recent) / period

        variance = sum((x - middle) ** 2 for x in recent) / period
        std = variance ** 0.5

        return {
            "upper": middle + std_dev * std,
            "middle": middle,
            "lower": middle - std_dev * std
        }

    def _execute_fundamental_filter_node(self, config: Dict, params: Dict):
        filter_type = config.get('filter_type', 'pe')
        operator = config.get('operator', 'lt')
        value = config.get('value', 0)
        min_value = config.get('min_value', 0)
        max_value = config.get('max_value', 0)

        filtered_codes = []
        for code in self.codes:
            info = self.stock_info.get_by_code(code)
            if not info:
                continue

            match = False
            if filter_type == 'pe':
                val = info.get('pe', 0)
                if self._check_operator(val, operator, value, min_value, max_value):
                    match = True
            elif filter_type == 'pb':
                val = info.get('pb', 0)
                if self._check_operator(val, operator, value, min_value, max_value):
                    match = True
            elif filter_type == 'roe':
                financials = self.financial.find_many({"code": code}, sort=[("report_date", -1)], limit=1)
                if financials:
                    val = financials[0].get('roe', 0)
                    if self._check_operator(val, operator, value, min_value, max_value):
                        match = True

            if match:
                filtered_codes.append(code)

        self.codes = filtered_codes
        logger.info(f"Fundamental filter node ({filter_type}): {len(self.codes)} stocks passed")

    def _check_operator(self, val: float, operator: str, value: float, min_val: float, max_val: float) -> bool:
        if operator == 'gt':
            return val > value
        elif operator == 'lt':
            return val < value
        elif operator == 'between':
            return min_val <= val <= max_val
        return False

    def _execute_market_sentiment_node(self, config: Dict, params: Dict):
        analysis_type = config.get('analysis_type', 'overall')
        threshold = config.get('threshold', 50)

        sentiment_scores: Dict[str, float] = {}

        for code in self.codes:
            if analysis_type == 'overall':
                sentiment = self.news.get_sentiment_trend(code, 7)
                if sentiment:
                    sentiment_scores[code] = sentiment.get('current_score', 50)
            elif analysis_type == 'hot_sectors':
                sentiment = self.news.get_sentiment_trend(code, 1)
                if sentiment:
                    sentiment_scores[code] = sentiment.get('current_score', 50)
            elif analysis_type == 'news_impact':
                sentiment = self.news.get_sentiment_trend(code, 3)
                if sentiment:
                    sentiment_scores[code] = sentiment.get('current_score', 50)

        hot_codes = [code for code, score in sentiment_scores.items() if score >= threshold]
        if len(hot_codes) < len(self.codes):
            self.codes = hot_codes

        params['sentiment_scores'] = sentiment_scores
        logger.info(f"Market sentiment node ({analysis_type}): {len(self.codes)} hot stocks identified")

    def _execute_index_components_node(self, config: Dict, params: Dict):
        index_code = config.get('index_code', '000300.sh')

        from core.storage.mongo_storage import IndexComponentStorage
        index_storage = IndexComponentStorage()
        components = index_storage.get_components(index_code)

        if components:
            codes = [c.get('code') for c in components if c.get('code')]
            params['index_components'] = {index_code: codes}
            logger.info(f"Index components node ({index_code}): {len(codes)} stocks loaded")
        else:
            logger.warning(f"Index components node ({index_code}): no components found")

    def _execute_compare_node(self, config: Dict, params: Dict):
        compare_type = config.get('compare_type', 'performance')
        ranking = config.get('ranking', 'desc')

        comparison_data: List[Dict[str, Any]] = []

        for code in self.codes:
            info = self.stock_info.get_by_code(code)
            if not info:
                continue

            item = {"code": code, "name": info.get('name', '')}

            if compare_type == 'price':
                klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=1)
                if klines:
                    item["value"] = klines[0].get('close', 0)
            elif compare_type == 'performance':
                klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=2)
                if len(klines) >= 2:
                    change = (klines[0].get('close', 0) - klines[1].get('close', 0)) / klines[1].get('close', 1) * 100
                    item["value"] = change
            elif compare_type == 'valuation':
                val = info.get('pe', 0)
                if val == 0:
                    val = info.get('pb', 0) * 10
                item["value"] = val
            elif compare_type == 'fund_flow':
                fund_flow = self.fund_flow.find_many({"code": code}, limit=1)
                if fund_flow:
                    item["value"] = fund_flow[0].get('main_net_inflow', 0)

            if "value" in item:
                comparison_data.append(item)

        comparison_data.sort(key=lambda x: x.get('value', 0), reverse=(ranking == 'desc'))

        params['comparison_data'] = comparison_data
        logger.info(f"Compare node ({compare_type}): compared {len(comparison_data)} stocks")
