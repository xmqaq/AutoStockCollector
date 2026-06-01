"""
选股工作流执行引擎
"""
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from core.storage.mongo_storage import StockInfoStorage, KlineStorage, FundFlowStorage, NewsStorage
from modules.ai_selector.strategies.base import SelectionResult, RiskLevel
from modules.ai.ai_analyzer import AIAnalyzer
from utils.logger import get_logger


logger = get_logger(__name__)

ProgressCallback = Callable[[str, str, str, float, Optional[Dict[str, Any]]], None]


class WorkflowCancelManager:
    """管理工作流取消状态"""
    _cancelled_executions: Dict[str, bool] = {}

    @classmethod
    def cancel(cls, execution_id: str):
        cls._cancelled_executions[execution_id] = True
        logger.info(f"Execution {execution_id} marked for cancellation")

    @classmethod
    def is_cancelled(cls, execution_id: str) -> bool:
        return cls._cancelled_executions.get(execution_id, False)

    @classmethod
    def clear(cls, execution_id: str):
        cls._cancelled_executions.pop(execution_id, None)


class WorkflowExecutor:
    def __init__(self, workflow_id: str, execution_id: str = "", progress_callback: Optional[ProgressCallback] = None):
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.stock_info = StockInfoStorage()
        self.kline = KlineStorage()
        self.fund_flow = FundFlowStorage()
        self.news = NewsStorage()
        self.financial = None
        self.ai_analyzer = AIAnalyzer()
        self.codes: List[str] = []
        self.results: List[SelectionResult] = []
        self.progress_callback = progress_callback
        self._cancelled = False

    def _get_financial_storage(self):
        if self.financial is None:
            from core.storage.mongo_storage import FinancialStorage
            self.financial = FinancialStorage()
        return self.financial

    def _report_progress(
        self,
        node_id: str,
        node_label: str,
        step: str,
        progress: float,
        detail: Optional[Dict[str, Any]] = None
    ):
        if self.progress_callback:
            try:
                self.progress_callback(node_id, node_label, step, progress, detail)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    def _is_cancelled(self) -> bool:
        if self._cancelled:
            return True
        if self.execution_id and WorkflowCancelManager.is_cancelled(self.execution_id):
            self._cancelled = True
            logger.info(f"Execution {self.execution_id} cancelled via cancel manager")
            return True
        return False

    def execute(self, nodes: List[Dict], edges: List[Dict], params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Starting workflow execution: {self.workflow_id}")
        start_time = datetime.now()
        execution_log: List[Dict[str, Any]] = []

        try:
            self._report_progress("init", "初始化", "正在连接数据库，加载股票池...", 1)
            self._init_codes()
            node_map = {n['id']: n for n in nodes}
            execution_order = self._topological_sort(nodes, edges)
            total_nodes = len(execution_order)

            self._report_progress("start", "初始化", f"加载 {len(self.codes)} 只有效股票", 5)
            start_log = {
                "node": "start",
                "label": "初始化",
                "status": "completed",
                "stocks_count": len(self.codes),
                "message": f"加载 {len(self.codes)} 只有效股票"
            }
            execution_log.append(start_log)

            for idx, node in enumerate(execution_order):
                if self._cancelled or (self.execution_id and WorkflowCancelManager.is_cancelled(self.execution_id)):
                    logger.info(f"Execution {self.execution_id} cancelled, stopping workflow")
                    self._cancelled = True
                    return {
                        "success": False,
                        "workflow_id": self.workflow_id,
                        "error": "Execution cancelled by user",
                        "cancelled": True,
                        "execution_time": datetime.now().isoformat(),
                        "execution_log": execution_log
                    }
                base_progress = 10 + (idx / total_nodes) * 85
                result = self._execute_node(node, node_map, params, base_progress)
                execution_log.append(result)

            duration = (datetime.now() - start_time).total_seconds()
            self._report_progress("end", "完成", f"执行完成，耗时 {duration:.2f}s", 100)
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

    def _execute_node(self, node: Dict, node_map: Dict, params: Dict, base_progress: float = 0) -> Dict[str, Any]:
        node_type = node.get('type')
        node_id = node.get('id')
        node_label = node.get('label')
        node_config = node.get('config', {})
        logger.info(f"Executing node: {node_label} ({node_type})")

        self._report_progress(node_id, node_label, f"开始执行 {node_label}", base_progress)

        try:
            if node_type == 'start':
                self._execute_start_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'filter':
                self._execute_filter_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'score':
                self._execute_score_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'ai_agent':
                self._execute_ai_agent_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'combine':
                self._execute_combine_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'risk_control':
                self._execute_risk_control_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'end':
                self._execute_end_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'data_fetch':
                self._execute_data_fetch_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'technical_indicator':
                self._execute_technical_indicator_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'fundamental_filter':
                self._execute_fundamental_filter_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'market_sentiment':
                self._execute_market_sentiment_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'index_components':
                self._execute_index_components_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'compare':
                self._execute_compare_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'chanlun_zs':  # 缠论中枢识别
                self._execute_chanlun_zs_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'chanlun_bc':  # 缠论背驰判断
                self._execute_chanlun_bc_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'chanlun_buy1':  # 缠论一买
                self._execute_chanlun_buy1_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'chanlun_buy2':  # 缠论二买
                self._execute_chanlun_buy2_node(node_config, params, node_id, node_label, base_progress)
            elif node_type == 'chanlun_buy3':  # 缠论三买
                self._execute_chanlun_buy3_node(node_config, params, node_id, node_label, base_progress)

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

    def _execute_start_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
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
                self.codes = block.get_stocks_by_block_name(sector, 'industry')
        self._report_progress(node_id, node_label, f"已加载 {len(self.codes)} 只股票", base_progress + 5)
        logger.info(f"Start node: loaded {len(self.codes)} codes from {source}")

    def _execute_filter_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        if self._is_cancelled():
            return

        filter_type = config.get('filter_type', 'price_range')
        total = len(self.codes)
        filtered_codes = []
        report_interval = max(1, total // 10)

        for i, code in enumerate(self.codes):
            if self._is_cancelled():
                self.codes = filtered_codes
                return

            if self._check_filter(code, filter_type, config):
                filtered_codes.append(code)
            if (i + 1) % report_interval == 0 or i == total - 1:
                pct = (i + 1) / total * 100
                self._report_progress(
                    node_id, node_label,
                    f"筛选中 {i + 1}/{total}",
                    base_progress + pct * 0.4,
                    {"filtered": len(filtered_codes), "checked": i + 1, "total": total}
                )

        self.codes = filtered_codes
        self._report_progress(node_id, node_label, f"筛选完成: {total} → {len(self.codes)} 只", base_progress + 50)
        logger.info(f"Filter node ({filter_type}): {total} -> {len(filtered_codes)}")

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

        elif filter_type == 'sector':
            sector = config.get('sector', '')
            if not sector:
                return True
            from core.storage.mongo_storage import BlockStorage
            block = BlockStorage()
            stock_blocks = block.get_block_by_code(code, 'industry')
            if not stock_blocks:
                return False
            block_name = stock_blocks.get('block_name', '')
            return block_name == sector

        return True

    def _execute_score_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        if self._is_cancelled():
            return

        score_type = config.get('score_type', 'weighted')
        weights = config.get('weights', {
            'technical': 0.25,
            'fundamental': 0.25,
            'sentiment': 0.25,
            'fund_flow': 0.25
        })

        total = len(self.codes)
        scored_results = []
        report_interval = max(1, total // 10)

        for i, code in enumerate(self.codes):
            if self._is_cancelled():
                self.results = scored_results
                return

            try:
                factors = self._calculate_factors(code)
                score = self._calculate_composite_score(factors, score_type, weights)
                result = self._build_result(code, factors, score)
                scored_results.append(result)
            except Exception as e:
                logger.warning(f"Scoring failed for {code}: {e}")
            if (i + 1) % report_interval == 0 or i == total - 1:
                avg_score = sum(r.score for r in scored_results) / max(len(scored_results), 1)
                self._report_progress(
                    node_id, node_label,
                    f"评分中 {i + 1}/{total} (平均 {avg_score:.1f})",
                    base_progress + (i + 1) / total * 80,
                    {"scored": len(scored_results), "avg_score": avg_score}
                )

        scored_results.sort(key=lambda x: x.score, reverse=True)
        self.results = scored_results
        self._report_progress(node_id, node_label, f"评分完成，共 {len(self.results)} 只", base_progress + 85)
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

    def _execute_ai_agent_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        agent_id = config.get('agent_id', '')
        if not agent_id:
            logger.warning("AI Agent node: no agent_id specified")
            return

        # Fetch agent configuration from MongoDB
        agent_config = None
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            agent_config = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
        except Exception as e:
            logger.warning(f"AI Agent node: failed to load agent {agent_id}: {e}")

        if not agent_config:
            logger.warning(f"AI Agent node: agent {agent_id} not found, falling back to default")
            agent_config = {
                "system_prompt": "你是专业的股票分析师，请分析以下股票数据并给出投资建议。",
                "temperature": 0.7,
                "max_tokens": 2000
            }

        system_prompt = agent_config.get("system_prompt", "")
        temperature = float(agent_config.get("temperature", 0.7))
        max_tokens = int(agent_config.get("max_tokens", 2000))

        top_n = config.get('top_n', 20)
        results_to_analyze = self.results[:top_n] if self.results else []
        total = len(results_to_analyze)

        if not results_to_analyze:
            logger.warning("AI Agent node: no results to analyze")
            return

        from modules.ai.foundation.llm_router import LLMRouter
        router = LLMRouter()

        self._report_progress(node_id, node_label, f"AI Agent [{agent_config.get('name', agent_id)}] 开始分析 {total} 只股票", base_progress + 2)

        for i, result in enumerate(results_to_analyze):
            if self._is_cancelled():
                return
            try:
                # Build per-stock context from real data
                klines = self.kline.find_many({"code": result.code}, sort=[("date", -1)], limit=20)
                closes = [k.get('close', 0) for k in klines if k.get('close')]
                volumes = [k.get('volume', 0) for k in klines if k.get('volume')]

                fund_flow = self.fund_flow.get_latest_flow(result.code)
                main_inflow = fund_flow.get('main_net_inflow', 0) if fund_flow else 0

                stock_context = f"""【股票信息】
代码: {result.code}  名称: {result.name}
综合评分: {result.score:.1f}（技术:{result.technical_score:.0f} 基本面:{result.fundamental_score:.0f} 资金:{result.fund_flow_score:.0f} 舆情:{result.sentiment_score:.0f}）
近期收盘价（最新→历史）: {closes[:10] if closes else '暂无'}
近期成交量: {volumes[:10] if volumes else '暂无'}
主力净流入: {main_inflow}元
系统初步建议: {result.recommendation}

请结合以上数据给出你的专业分析结论（150字以内）。"""

                prompt = f"{system_prompt}\n\n{stock_context}"
                llm_result = router.chat(prompt, use_cache=False)

                if llm_result.success and llm_result.raw:
                    result.metadata[f'ai_{agent_id}_analysis'] = llm_result.raw
                    # Update recommendation based on AI output
                    raw_lower = llm_result.raw
                    if '强烈推荐' in raw_lower or '强力买入' in raw_lower:
                        result.recommendation = '强烈推荐'
                    elif '买入' in raw_lower and '谨慎' not in raw_lower:
                        result.recommendation = '买入'
                    elif '谨慎' in raw_lower or '观望' in raw_lower:
                        result.recommendation = '谨慎买入'
                    elif '回避' in raw_lower or '减持' in raw_lower or '卖出' in raw_lower:
                        result.recommendation = '回避'
                    result.risk_factors = [llm_result.raw[:200]]
                else:
                    logger.warning(f"AI analysis returned no content for {result.code}: {llm_result.error}")

            except Exception as e:
                logger.warning(f"AI Agent analysis failed for {result.code}: {e}")

            if (i + 1) % 3 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"AI分析中 {i + 1}/{total} ({result.code})",
                    base_progress + (i + 1) / max(total, 1) * 80,
                    {"analyzed": i + 1, "total": total, "agent": agent_id}
                )

        self.results.sort(key=lambda x: x.score, reverse=True)
        self._report_progress(node_id, node_label, f"AI分析完成: {len(results_to_analyze)} 只", base_progress + 90)
        logger.info(f"AI Agent node [{agent_id}]: analyzed {len(results_to_analyze)} stocks")

    def _execute_combine_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        strategy = config.get('strategy', 'top_n')
        top_n = config.get('top_n', 20)
        min_score = config.get('min_score', 60.0)
        original_count = len(self.results)

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

        self._report_progress(
            node_id, node_label,
            f"组合完成: {original_count} → {len(self.results)} 只",
            base_progress + 50
        )
        logger.info(f"Combine node ({strategy}): {len(self.results)} stocks")

    def _execute_risk_control_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        max_positions = config.get('max_positions', 10)
        max_position_ratio = config.get('max_position_ratio', 0.1)
        exclude_st = config.get('exclude_st', True)
        exclude_limit_up = config.get('exclude_limit_up', False)
        original_count = len(self.results)

        if exclude_st:
            st_count = len([r for r in self.results if r.name.startswith(('*ST', 'ST'))])
            self.results = [r for r in self.results if not r.name.startswith(('*ST', 'ST'))]
            if st_count > 0:
                self._report_progress(node_id, node_label, f"排除 {st_count} 只ST股票", base_progress + 10)

        if exclude_limit_up:
            change_pcts = params.get('change_pcts', {})
            limit_up_count = len([r for r in self.results if abs(change_pcts.get(r.code, 0)) >= 9.9])
            self.results = [r for r in self.results if abs(change_pcts.get(r.code, 0)) < 9.9]
            if limit_up_count > 0:
                self._report_progress(node_id, node_label, f"排除 {limit_up_count} 只涨停股票", base_progress + 20)

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

        self._report_progress(
            node_id, node_label,
            f"风控完成: {original_count} → {len(self.results)} 只",
            base_progress + 50
        )
        logger.info(f"Risk control node: {len(self.results)} stocks after risk filtering")

    def _execute_end_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        output_type = config.get('output', 'list')
        top_n = config.get('top_n', 10)
        include_reasons = config.get('include_reasons', False)

        self._report_progress(node_id, node_label, f"正在生成结果 (Top {top_n})", base_progress + 20)

        if output_type == 'list':
            self.results = self.results[:top_n]

        if include_reasons:
            for result in self.results:
                result.metadata['reasons'] = self._generate_pick_reason(result)

        self._report_progress(node_id, node_label, f"输出 {len(self.results)} 只股票", base_progress + 40)
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

        current_price = result.metadata.get('current_price') or result.stop_loss / 0.95 if result.stop_loss else 0
        if result.target_price > 0 and current_price > 0:
            profit_ratio = (result.target_price - current_price) / current_price * 100
            reasons.append(f"目标涨幅：{profit_ratio:.1f}%")

        if not reasons:
            reasons.append("符合基本筛选条件")

        return reasons

    def _execute_data_fetch_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        data_type = config.get('data_type', 'kline')
        days = config.get('days', 60)
        limit = config.get('limit', 100)

        fetched_data: Dict[str, Any] = {}
        codes_to_fetch = self.codes[:limit]
        total = len(codes_to_fetch)

        for i, code in enumerate(codes_to_fetch):
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
                financials = self._get_financial_storage().find_many({"code": code}, limit=1)
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
                from core.storage.mongo_storage import KlineStorage
                kline = KlineStorage()
                signals = kline.get_signals(code)
                if signals:
                    fetched_data[code] = {"signals": signals}
            if (i + 1) % 50 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"获取数据 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"fetched": len(fetched_data), "total": total}
                )

        params['fetched_data'] = fetched_data
        self._report_progress(node_id, node_label, f"获取完成: {len(fetched_data)} 条数据", base_progress + 70)
        logger.info(f"Data fetch node ({data_type}): fetched {len(fetched_data)} records")

    def _execute_technical_indicator_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        indicator_type = config.get('indicator_type', 'ma')
        params_str = config.get('params', '5,20,60')
        params_list = [int(p.strip()) for p in params_str.split(',') if p.strip().isdigit()]

        indicator_data: Dict[str, Any] = {}
        total = len(self.codes)

        for i, code in enumerate(self.codes):
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
            if (i + 1) % 100 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"计算指标 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"calculated": len(indicator_data), "total": total}
                )

        params['indicator_data'] = indicator_data
        self._report_progress(node_id, node_label, f"指标计算完成: {len(indicator_data)} 只", base_progress + 70)
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

    def _execute_fundamental_filter_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        filter_type = config.get('filter_type', 'pe')
        operator = config.get('operator', 'lt')
        value = config.get('value', 0)
        min_value = config.get('min_value', 0)
        max_value = config.get('max_value', 0)
        total = len(self.codes)
        filtered_codes = []

        for i, code in enumerate(self.codes):
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
                financials = self._get_financial_storage().find_many({"code": code}, sort=[("report_date", -1)], limit=1)
                if financials:
                    val = financials[0].get('roe', 0)
                    if self._check_operator(val, operator, value, min_value, max_value):
                        match = True

            if match:
                filtered_codes.append(code)
            if (i + 1) % 100 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"筛选中 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"passed": len(filtered_codes), "checked": i + 1, "total": total}
                )

        self.codes = filtered_codes
        self._report_progress(node_id, node_label, f"基本面筛选完成: {total} → {len(self.codes)} 只", base_progress + 70)
        logger.info(f"Fundamental filter node ({filter_type}): {len(self.codes)} stocks passed")

    def _check_operator(self, val: float, operator: str, value: float, min_val: float, max_val: float) -> bool:
        if operator == 'gt':
            return val > value
        elif operator == 'lt':
            return val < value
        elif operator == 'between':
            return min_val <= val <= max_val
        return False

    def _execute_market_sentiment_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        analysis_type = config.get('analysis_type', 'overall')
        threshold = config.get('threshold', 50)
        sentiment_scores: Dict[str, float] = {}
        total = len(self.codes)

        for i, code in enumerate(self.codes):
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
            if (i + 1) % 50 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"分析情绪 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"analyzed": len(sentiment_scores), "total": total}
                )

        hot_codes = [code for code, score in sentiment_scores.items() if score >= threshold]
        if len(hot_codes) < len(self.codes):
            self.codes = hot_codes

        params['sentiment_scores'] = sentiment_scores
        self._report_progress(node_id, node_label, f"情绪分析完成: {len(hot_codes)} 只热点股", base_progress + 70)
        logger.info(f"Market sentiment node ({analysis_type}): {len(self.codes)} hot stocks identified")

    def _execute_index_components_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        index_code = config.get('index_code', '000300.sh')

        self._report_progress(node_id, node_label, f"获取 {index_code} 成分股", base_progress + 10)

        from core.storage.mongo_storage import IndexComponentStorage
        index_storage = IndexComponentStorage()
        components = index_storage.get_components(index_code)

        if components:
            codes = [c.get('code') for c in components if c.get('code')]
            params['index_components'] = {index_code: codes}
            self._report_progress(node_id, node_label, f"加载 {len(codes)} 只成分股", base_progress + 50)
            logger.info(f"Index components node ({index_code}): {len(codes)} stocks loaded")
        else:
            logger.warning(f"Index components node ({index_code}): no components found")

    def _execute_compare_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        compare_type = config.get('compare_type', 'performance')
        ranking = config.get('ranking', 'desc')
        comparison_data: List[Dict[str, Any]] = []
        total = len(self.codes)

        for i, code in enumerate(self.codes):
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
            if (i + 1) % 50 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"对比分析 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"compared": len(comparison_data), "total": total}
                )

        comparison_data.sort(key=lambda x: x.get('value', 0), reverse=(ranking == 'desc'))

        params['comparison_data'] = comparison_data
        self._report_progress(node_id, node_label, f"对比完成: {len(comparison_data)} 只股票", base_progress + 70)
        logger.info(f"Compare node ({compare_type}): compared {len(comparison_data)} stocks")

    def _execute_chanlun_zs_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        """缠论中枢识别节点"""
        level = config.get('level', '60min')  # 级别: 1min, 5min, 15min, 30min, 60min, 日线
        min_bars = config.get('min_bars', 3)  # 中枢区间最少K线数

        zs_data: Dict[str, Any] = {}
        total = len(self.codes)

        for i, code in enumerate(self.codes):
            klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=120)
            if not klines or len(klines) < 30:
                continue

            closes = [k.get('close', 0) for k in klines]
            highs = [k.get('high', 0) for k in klines]
            lows = [k.get('low', 0) for k in klines]

            zs_result = self._find_zhongshu(closes, highs, lows, min_bars)
            if zs_result:
                zs_data[code] = zs_result

            if (i + 1) % 50 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"识别中枢 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"found_zs": len(zs_data), "total": total}
                )

        params['zs_data'] = zs_data
        self._report_progress(node_id, node_label, f"中枢识别完成: {len(zs_data)} 只股票", base_progress + 70)
        logger.info(f"Chanlun ZS node (level={level}): identified {len(zs_data)} stocks with zhongshu")

    def _find_zhongshu(self, closes: List[float], highs: List[float], lows: List[float], min_bars: int) -> Optional[Dict]:
        """寻找缠论中枢"""
        if len(closes) < min_bars * 3:
            return None

        highs_reversed = list(reversed(highs))
        lows_reversed = list(reversed(lows))
        closes_reversed = list(reversed(closes))

        peak_idx = self._find_peaks(highs_reversed, 3)
        trough_idx = self._find_troughs(lows_reversed, 3)

        if len(peak_idx) < 2 or len(trough_idx) < 2:
            return None

        zhongshu = None
        for i in range(len(peak_idx) - 1):
            for j in range(len(trough_idx) - 1):
                p1, p2 = peak_idx[i], peak_idx[i + 1]
                t1, t2 = trough_idx[j], trough_idx[j + 1]

                if p1 < t1 < p2 < t2:
                    zg = max(highs_reversed[p1:p2+1])
                    zd = min(lows_reversed[t1:t2+1])
                    zg = min(zg, zd)
                    zd = max(zg, zd)

                    if zg > zd:
                        zhongshu = {
                            "zg": round(zg, 2),
                            "zd": round(zd, 2),
                            "zz": round((zg + zd) / 2, 2),
                            "gg": round(max(highs_reversed[p1:p2+1]), 2),
                            "dd": round(min(lows_reversed[t1:t2+1]), 2),
                            "start_idx": len(closes) - p2 - 1,
                            "bars": p2 - p1 + 1
                        }
                        break
            if zhongshu:
                break

        return zhongshu

    def _find_peaks(self, data: List[float], window: int) -> List[int]:
        """寻找峰值"""
        peaks = []
        for i in range(window, len(data) - window):
            if all(data[i] >= data[i - j] for j in range(1, window + 1)) and \
               all(data[i] >= data[i + j] for j in range(1, window + 1)):
                peaks.append(i)
        return peaks

    def _find_troughs(self, data: List[float], window: int) -> List[int]:
        """寻找谷值"""
        troughs = []
        for i in range(window, len(data) - window):
            if all(data[i] <= data[i - j] for j in range(1, window + 1)) and \
               all(data[i] <= data[i + j] for j in range(1, window + 1)):
                troughs.append(i)
        return troughs

    def _execute_chanlun_bc_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        """缠论背驰判断节点"""
        bc_type = config.get('bc_type', 'divergence')  # divergence: 背驰,新高新低: new_high_low
        threshold = config.get('threshold', 0.1)

        bc_data: Dict[str, Any] = {}
        total = len(self.codes)

        for i, code in enumerate(self.codes):
            klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=120)
            if not klines or len(klines) < 60:
                continue

            closes = [k.get('close', 0) for k in klines]
            volumes = [k.get('volume', 0) for k in klines]

            if bc_type == 'divergence':
                macd_result = self._calculate_macd(closes)
                dif = macd_result.get('dif', 0)
                dea = macd_result.get('dea', 0)

                prev_difs = []
                prev_deas = []
                for j in range(5, min(20, len(closes))):
                    temp_closes = closes[j:]
                    if len(temp_closes) >= 26:
                        macd_temp = self._calculate_macd(temp_closes)
                        prev_difs.append(macd_temp.get('dif', 0))
                        prev_deas.append(macd_temp.get('dea', 0))

                divergence = False
                if prev_difs and prev_deas:
                    if dif < 0 and all(d < 0 for d in prev_difs):
                        if all(abs(dif) > abs(d) + threshold for d in prev_difs[:-1]):
                            divergence = True
                    elif dif > 0 and all(d > 0 for d in prev_difs):
                        if all(abs(dif) > abs(d) + threshold for d in prev_difs[:-1]):
                            divergence = True

                bc_data[code] = {
                    "divergence": divergence,
                    "dif": round(dif, 4),
                    "dea": round(dea, 0),
                    "type": "bottom" if divergence and dif < 0 else "top" if divergence and dif > 0 else "none"
                }

            if (i + 1) % 50 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"判断背驰 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"bc_found": len([c for c, d in bc_data.items() if d.get('divergence')]), "total": total}
                )

        params['bc_data'] = bc_data
        bc_count = len([d for d in bc_data.values() if d.get('divergence')])
        self._report_progress(node_id, node_label, f"背驰识别完成: {bc_count} 只股票", base_progress + 70)
        logger.info(f"Chanlun BC node (type={bc_type}): found {bc_count} divergences")

    def _execute_chanlun_buy1_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        """缠论第一类买点识别"""
        min_price = config.get('min_price', 2)
        max_price = config.get('max_price', 100)
        rsi_oversold = config.get('rsi_oversold', 30)
        kdj_oversold = config.get('kdj_oversold', 20)

        buy1_data: Dict[str, Any] = {}
        total = len(self.codes)

        for i, code in enumerate(self.codes):
            klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=120)
            if not klines or len(klines) < 60:
                continue

            closes = [k.get('close', 0) for k in klines]
            current_price = closes[0]

            if not (min_price <= current_price <= max_price):
                continue

            macd_data = self._calculate_macd(closes)
            kdj_data = self._calculate_kdj(closes)
            rsi_data = self._calculate_rsi(closes)

            is_buy1 = False
            reasons = []

            if macd_data['dif'] < 0 and macd_data['macd'] > macd_data['dif']:
                is_buy1 = True
                reasons.append("MACD底背驰")

            if kdj_data['j'] < kdj_oversold:
                is_buy1 = True
                reasons.append(f"KDJ超卖(J={kdj_data['j']:.1f})")

            if rsi_data < rsi_oversold:
                is_buy1 = True
                reasons.append(f"RSI超卖({rsi_data:.1f})")

            if is_buy1:
                buy1_data[code] = {
                    "price": round(current_price, 2),
                    "macd": macd_data,
                    "kdj": kdj_data,
                    "rsi": round(rsi_data, 2),
                    "reasons": reasons,
                    "strength": len(reasons)
                }

            if (i + 1) % 50 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"识别一买 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"buy1_found": len(buy1_data), "total": total}
                )

        if buy1_data:
            buy1_data = dict(sorted(buy1_data.items(), key=lambda x: x[1]['strength'], reverse=True))

        params['buy1_data'] = buy1_data
        self._report_progress(node_id, node_label, f"一买识别完成: {len(buy1_data)} 只股票", base_progress + 70)
        logger.info(f"Chanlun Buy1 node: found {len(buy1_data)} first-type buy points")

    def _execute_chanlun_buy2_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        """缠论第二类买点识别"""
        buy1_data = params.get('buy1_data', {})

        buy2_data: Dict[str, Any] = {}
        total = len(self.codes)

        for i, code in enumerate(self.codes):
            klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=120)
            if not klines or len(klines) < 60:
                continue

            closes = [k.get('close', 0) for k in klines]
            current_price = closes[0]

            macd_data = self._calculate_macd(closes)
            kdj_data = self._calculate_kdj(closes)
            ma5 = sum(closes[:5]) / 5
            ma20 = sum(closes[:20]) / 20

            is_buy2 = False
            reasons = []

            if macd_data['dif'] > 0 and macd_data['dea'] > 0:
                is_buy2 = True
                reasons.append("MACD多头排列")

            if ma5 > ma20:
                is_buy2 = True
                reasons.append("均线多头排列")

            if buy1_data.get(code):
                buy1_price = buy1_data[code].get('price', 0)
                if buy1_price > 0 and current_price >= buy1_price * 0.95:
                    is_buy2 = True
                    reasons.append(f"回调不破一买({buy1_price})")

            if kdj_data['k'] > kdj_data['d'] and kdj_data['j'] < 80:
                is_buy2 = True
                reasons.append("KDJ金叉")

            if is_buy2:
                buy2_data[code] = {
                    "price": round(current_price, 2),
                    "macd": macd_data,
                    "kdj": kdj_data,
                    "ma5": round(ma5, 2),
                    "ma20": round(ma20, 2),
                    "reasons": reasons,
                    "strength": len(reasons)
                }

            if (i + 1) % 50 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"识别二买 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"buy2_found": len(buy2_data), "total": total}
                )

        if buy2_data:
            buy2_data = dict(sorted(buy2_data.items(), key=lambda x: x[1]['strength'], reverse=True))

        params['buy2_data'] = buy2_data
        self._report_progress(node_id, node_label, f"二买识别完成: {len(buy2_data)} 只股票", base_progress + 70)
        logger.info(f"Chanlun Buy2 node: found {len(buy2_data)} second-type buy points")

    def _execute_chanlun_buy3_node(self, config: Dict, params: Dict, node_id: str, node_label: str, base_progress: float):
        """缠论第三类买点识别"""
        zs_data = params.get('zs_data', {})
        min_price = config.get('min_price', 5)
        max_price = config.get('max_price', 100)
        vol_threshold = config.get('vol_threshold', 1.5)

        buy3_data: Dict[str, Any] = {}
        total = len(self.codes)

        for i, code in enumerate(self.codes):
            klines = self.kline.find_many({"code": code}, sort=[("date", -1)], limit=120)
            if not klines or len(klines) < 60:
                continue

            closes = [k.get('close', 0) for k in klines]
            volumes = [k.get('volume', 0) for k in klines]
            current_price = closes[0]

            if not (min_price <= current_price <= max_price):
                continue

            macd_data = self._calculate_macd(closes)
            boll_data = self._calculate_boll(closes)

            current_vol = volumes[0]
            avg_vol = sum(volumes[:5]) / 5
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1

            zs = zs_data.get(code)
            is_breakout = False

            if zs:
                upper = zs.get('zg', current_price * 1.1)
                if current_price > upper:
                    is_breakout = True
                    reasons = [f"突破中枢上沿({upper})"]
                else:
                    reasons = []
            else:
                reasons = []

            if boll_data.get('upper', 0) > 0 and current_price > boll_data['upper']:
                is_breakout = True
                reasons.append("突破布林上轨")

            if macd_data['dif'] > 0 and macd_data['dea'] > 0:
                reasons.append("MACD多头")

            if vol_ratio >= vol_threshold:
                reasons.append(f"放量({vol_ratio:.1f}倍)")

            if len(reasons) >= 2:
                buy3_data[code] = {
                    "price": round(current_price, 2),
                    "macd": macd_data,
                    "boll": boll_data,
                    "vol_ratio": round(vol_ratio, 2),
                    "zs": zs,
                    "reasons": reasons,
                    "strength": len(reasons)
                }

            if (i + 1) % 50 == 0 or i == total - 1:
                self._report_progress(
                    node_id, node_label,
                    f"识别三买 {i + 1}/{total}",
                    base_progress + (i + 1) / total * 60,
                    {"buy3_found": len(buy3_data), "total": total}
                )

        if buy3_data:
            buy3_data = dict(sorted(buy3_data.items(), key=lambda x: x[1]['strength'], reverse=True))

        params['buy3_data'] = buy3_data
        self._report_progress(node_id, node_label, f"三买识别完成: {len(buy3_data)} 只股票", base_progress + 70)
        logger.info(f"Chanlun Buy3 node: found {len(buy3_data)} third-type buy points")
