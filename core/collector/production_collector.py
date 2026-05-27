"""
生产级数据采集调度任务
整合所有验证通过的模块，实现稳定的数据采集
"""
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, "/Users/chenyongzhou/CodeBuddy/AutoStockCollector")

from config.database import DatabaseConfig
from core.scheduler.enhanced_scheduler import enhanced_scheduler, EnhancedTaskScheduler
from core.collector.kline_collector import KlineCollector
from core.collector.fund_flow_collector import FundFlowCollector, MarginCollector, DragonTigerCollector
from core.collector.stock_info_collector import StockInfoCollector
from core.collector.financial_collector import FinancialCollector
from core.collector.news_collector import NewsCollector
from core.collector.block_collector import BlockCollector
from core.logs.chain_logger import chain_logger, LogLevel, LogStage
from core.api.api_client import api_client, RetryConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class ProductionDataCollector:
    def __init__(self):
        self.db = DatabaseConfig.get_database()
        self._register_collectors()
        self._setup_api_client()

    def _register_collectors(self):
        self.collectors = {
            "kline": KlineCollector(),
            "fund_flow": FundFlowCollector(),
            "margin": MarginCollector(),
            "stock_info": StockInfoCollector(),
            "financial": FinancialCollector(),
            "news": NewsCollector(),
            "block": BlockCollector(),
            "dragon_tiger": DragonTigerCollector()
        }

        for name, collector in self.collectors.items():
            enhanced_scheduler.register_collector(name, collector)

    def _setup_api_client(self):
        retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            retry_on_timeout=True,
            retry_on_connection_error=True
        )
        api_client.set_retry_config("akshare_stock", retry_config)
        api_client.set_default_timeout(30.0)

    def get_all_stock_codes(self) -> list:
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            codes = []
            for code in df["code"].tolist():
                if str(code).startswith("6"):
                    codes.append(f"SH{code}")
                else:
                    codes.append(f"SZ{code}")
            logger.info(f"获取到 {len(codes)} 只股票")
            return codes
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    def collect_kline_data(self, codes: list, start_date: str, end_date: str) -> Dict[str, Any]:
        request_id = chain_logger.start_chain(
            f"kline_{int(time.time() * 1000)}",
            "kline",
            {"codes_count": len(codes), "start_date": start_date, "end_date": end_date}
        )

        logger.info(f"[{request_id}] 开始采集K线数据: {len(codes)} 只股票")
        start_time = time.time()

        success = 0
        failed = 0
        total_records = 0

        for i, code in enumerate(codes):
            try:
                records = self.collectors["kline"].collect_single(
                    code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq",
                    period="daily"
                )

                if records:
                    total_records += len(records)
                    success += 1
                else:
                    failed += 1

            except Exception as e:
                failed += 1
                logger.error(f"K线采集失败 {code}: {e}")

            if (i + 1) % 100 == 0:
                logger.info(f"  K线进度: {i+1}/{len(codes)} ({100*(i+1)/len(codes):.1f}%) 成功:{success} 失败:{failed}")
                chain_logger.log(
                    LogLevel.INFO,
                    LogStage.API_CALL,
                    request_id,
                    message=f"Progress: {i+1}/{len(codes)}",
                    extra_data={"success": success, "failed": failed}
                )

        duration = time.time() - start_time
        chain_logger.end_chain(
            request_id,
            success=True,
            stats={"success": success, "failed": failed, "records": total_records, "duration": duration}
        )

        logger.info(f"K线采集完成: 成功 {success}, 失败 {failed}, 记录 {total_records}, 耗时 {duration:.1f}秒")
        return {"success": success, "failed": failed, "records": total_records, "duration": duration}

    def collect_fund_flow_data(self, codes: list) -> Dict[str, Any]:
        request_id = chain_logger.start_chain(
            f"fund_flow_{int(time.time() * 1000)}",
            "fund_flow",
            {"codes_count": len(codes)}
        )

        logger.info(f"[{request_id}] 开始采集资金流向数据")
        start_time = time.time()

        success = 0
        failed = 0
        total_records = 0

        for i, code in enumerate(codes[:500]):
            try:
                records = self.collectors["fund_flow"].collect_single(code)
                if records:
                    total_records += len(records)
                    success += 1
            except:
                failed += 1

        duration = time.time() - start_time
        chain_logger.end_chain(
            request_id,
            success=True,
            stats={"success": success, "failed": failed, "records": total_records}
        )

        logger.info(f"资金流向采集完成: 成功 {success}, 失败 {failed}, 记录 {total_records}")
        return {"success": success, "failed": failed, "records": total_records}

    def collect_margin_data(self, start_date: str, end_date: str) -> Dict[str, Any]:
        request_id = chain_logger.start_chain(
            f"margin_{int(time.time() * 1000)}",
            "margin",
            {"start_date": start_date, "end_date": end_date}
        )

        logger.info(f"[{request_id}] 开始采集两融数据")
        start_time = time.time()

        try:
            records = self.collectors["margin"].collect_detailed_margin(
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", "")
            )
            duration = time.time() - start_time
            chain_logger.end_chain(request_id, success=True, stats={"records": len(records)})
            logger.info(f"两融数据采集完成: {len(records)} 条")
            return {"records": len(records), "duration": duration}
        except Exception as e:
            chain_logger.end_chain(request_id, success=False, error_message=str(e))
            logger.error(f"两融数据采集失败: {e}")
            return {"records": 0, "error": str(e)}

    def collect_news_data(self) -> Dict[str, Any]:
        request_id = chain_logger.start_chain(
            f"news_{int(time.time() * 1000)}",
            "news",
            {}
        )

        logger.info(f"[{request_id}] 开始采集新闻数据")
        start_time = time.time()

        try:
            records = self.collectors["news"].collect()
            duration = time.time() - start_time
            chain_logger.end_chain(request_id, success=True, stats={"records": len(records)})
            logger.info(f"新闻数据采集完成: {len(records)} 条")
            return {"records": len(records), "duration": duration}
        except Exception as e:
            chain_logger.end_chain(request_id, success=False, error_message=str(e))
            logger.error(f"新闻数据采集失败: {e}")
            return {"records": 0, "error": str(e)}

    def collect_block_data(self) -> Dict[str, Any]:
        request_id = chain_logger.start_chain(
            f"block_{int(time.time() * 1000)}",
            "block",
            {}
        )

        logger.info(f"[{request_id}] 开始采集板块数据")
        start_time = time.time()

        try:
            records = self.collectors["block"].collect()
            duration = time.time() - start_time
            chain_logger.end_chain(request_id, success=True, stats={"records": len(records)})
            logger.info(f"板块数据采集完成: {len(records)} 条")
            return {"records": len(records), "duration": duration}
        except Exception as e:
            chain_logger.end_chain(request_id, success=False, error_message=str(e))
            logger.error(f"板块数据采集失败: {e}")
            return {"records": 0, "error": str(e)}

    def collect_dragon_tiger_data(self) -> Dict[str, Any]:
        request_id = chain_logger.start_chain(
            f"dragon_tiger_{int(time.time() * 1000)}",
            "dragon_tiger",
            {}
        )

        logger.info(f"[{request_id}] 开始采集龙虎榜数据")
        start_time = time.time()

        try:
            records = self.collectors["dragon_tiger"].collect()
            duration = time.time() - start_time
            chain_logger.end_chain(request_id, success=True, stats={"records": len(records)})
            logger.info(f"龙虎榜数据采集完成: {len(records)} 条")
            return {"records": len(records), "duration": duration}
        except Exception as e:
            chain_logger.end_chain(request_id, success=False, error_message=str(e))
            logger.error(f"龙虎榜数据采集失败: {e}")
            return {"records": 0, "error": str(e)}

    def verify_database(self) -> Dict[str, int]:
        logger.info("验证数据库数据")
        stats = {}
        for coll in ["kline", "fund_flow", "margin_data", "stock_info", "financial", "news", "block", "dragon_tiger"]:
            try:
                stats[coll] = self.db[coll].count_documents({})
            except:
                stats[coll] = 0
        return stats

    def run_full_collection(self):
        logger.info("=" * 80)
        logger.info("开始生产级数据采集调度")
        logger.info(f"时间: {datetime.now()}")
        logger.info("=" * 80)

        codes = self.get_all_stock_codes()
        if not codes:
            logger.error("无法获取股票列表")
            return

        start_time = time.time()
        results = {}

        results["kline"] = self.collect_kline_data(
            codes,
            "2026-05-01",
            datetime.now().strftime("%Y-%m-%d")
        )

        results["fund_flow"] = self.collect_fund_flow_data(codes)

        results["margin"] = self.collect_margin_data("2026-05-01", "2026-05-27")

        results["news"] = self.collect_news_data()

        results["block"] = self.collect_block_data()

        results["dragon_tiger"] = self.collect_dragon_tiger_data()

        db_stats = self.verify_database()

        total_duration = time.time() - start_time

        logger.info("=" * 80)
        logger.info("生产级数据采集完成")
        logger.info(f"总耗时: {total_duration:.1f}秒")
        logger.info("=" * 80)

        for name, result in results.items():
            logger.info(f"  {name}: {result}")

        logger.info("数据库统计:")
        for name, count in db_stats.items():
            logger.info(f"  {name}: {count:,} 条")

        scheduler_stats = enhanced_scheduler.get_scheduler_stats()
        logger.info(f"调度器统计: {scheduler_stats}")

        api_stats = api_client.get_request_stats()
        logger.info(f"API调用统计: {api_stats}")

        return {"results": results, "database": db_stats, "duration": total_duration}


if __name__ == "__main__":
    collector = ProductionDataCollector()
    collector.run_full_collection()