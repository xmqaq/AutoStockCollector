"""
新闻管理模块
整合新浪财经新闻采集、存储、查询功能
支持多线程并行采集，提升采集速度
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.helpers import beijing_now, call_with_timeout
import re
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from core.storage.mongo_storage import NewsStorage
from utils.logger import get_logger


logger = get_logger(__name__)


class NewsChannel:
    GENERAL = "general"
    RESEARCH = "research"
    FUTURES = "futures"
    NMETAL = "nmetal"


ROLL_CHANNELS = [
    {"cid": "56592", "name": "财经滚动", "type": NewsChannel.GENERAL},
    {"cid": "56978", "name": "机构评论", "type": NewsChannel.RESEARCH},
    {"cid": "56988", "name": "期市要闻", "type": NewsChannel.FUTURES},
    {"cid": "57085", "name": "黄金分析", "type": NewsChannel.NMETAL},
    {"cid": "57088", "name": "白银分析", "type": NewsChannel.NMETAL},
]


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://finance.sina.com.cn/",
}


# akshare 财新接口（stock_news_main_cx）内部不设超时，外部源不响应时会无限阻塞，
# 进而拖死整个新闻采集任务（卡满 1 小时后被调度器/cron 看门狗强杀为"已取消"）。
# 用单独线程包一层硬超时兜底。
_CAIXIN_TIMEOUT_SECONDS = 30


_thread_local = threading.local()


def _get_thread_session() -> requests.Session:
    """获取线程本地的 Session（requests.Session 不是线程安全的）"""
    if not hasattr(_thread_local, "session"):
        session = requests.Session()
        session.headers.update(HEADERS)
        _thread_local.session = session
    return _thread_local.session


class NewsManager:
    def __init__(
        self,
        max_workers: int = 8,
        article_workers: int = 16
    ):
        self.storage = NewsStorage()
        self.max_workers = max_workers
        self.article_workers = article_workers
        self._stats_lock = threading.Lock()
        self._collected_count = 0

    def fetch_article_content(self, url: str) -> tuple:
        """获取新闻文章正文内容和发布时间
        
        Returns:
            tuple: (content: str, publish_date: str)
        """
        if not url or ".shtml" not in url:
            return "", ""
        session = _get_thread_session()
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = "utf-8"
            
            soup = BeautifulSoup(response.text, "html.parser")
            publish_date = ""
            
            meta_time = soup.find("meta", property="article:published_time")
            if meta_time:
                publish_date = meta_time.get("content", "")
            
            if not publish_date:
                meta_time = soup.find("meta", attrs={"name": "publish_time"})
                if meta_time:
                    publish_date = meta_time.get("content", "")
            
            if not publish_date:
                date_span = soup.find("span", class_="date")
                if date_span:
                    publish_date = date_span.get_text(strip=True)
            
            content_div = soup.find("div", class_="article-content")
            if content_div:
                paragraphs = content_div.find_all("p")
                content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                if content:
                    return content, publish_date
            
            article = soup.find("article")
            if article:
                return article.get_text(separator="\n", strip=True), publish_date
            
            for cls in ["art_content", "content", "article-body"]:
                elem = soup.find("div", class_=lambda x: x and cls in str(x))
                if elem:
                    return elem.get_text(separator="\n", strip=True), publish_date
                    
        except Exception as e:
            logger.debug(f"获取文章内容失败 {url}: {e}")
        return "", ""

    def _fetch_articles_batch(
        self,
        urls: List[str]
    ) -> Dict[str, tuple]:
        """批量并行获取文章内容
        
        Args:
            urls: 文章URL列表
            
        Returns:
            {url: (content, publish_date)} 字典
        """
        results = {}
        if not urls:
            return results
            
        with ThreadPoolExecutor(max_workers=self.article_workers) as executor:
            future_to_url = {
                executor.submit(self.fetch_article_content, url): url
                for url in urls
            }
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    results[url] = future.result()
                except Exception as e:
                    logger.debug(f"并行获取文章失败 {url}: {e}")
                    results[url] = ("", "")
        return results

    def _fetch_page(self, cid: str, page: int) -> List[Dict[str, Any]]:
        """获取单页新闻列表（不含正文）"""
        session = _get_thread_session()
        try:
            url = f"https://finance.sina.com.cn/roll/c/{cid}.shtml?page={page}"
            response = session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = "utf-8"
            
            soup = BeautifulSoup(response.text, "html.parser")
            news_items = soup.find_all("li")
            
            records = []
            for item in news_items:
                try:
                    link = item.find("a")
                    if not link:
                        continue
                        
                    title = link.get_text(strip=True)
                    href = link.get("href", "")
                    
                    if not title or len(title) < 10:
                        continue
                        
                    if href.startswith("//"):
                        href = "https:" + href
                    elif href.startswith("/"):
                        href = "https://finance.sina.com.cn" + href
                        
                    # URL 含完整日期（如 /2026-02-05/），span 含时间（如 (02月05日 12:01)）
                    # 日期取 URL，时间取 span，合并得到精确 datetime，无需推断年份
                    publish_date = None
                    url_date_m = re.search(r"/(\d{4}-\d{2}-\d{2})/", href)
                    date_str = url_date_m.group(1) if url_date_m else None

                    time_span = item.find("span")
                    time_str = None
                    if time_span:
                        raw_time = time_span.get_text(strip=True)
                        tm = re.search(r"\(.*?(\d{1,2}):(\d{2})\)", raw_time)
                        if tm:
                            time_str = f"{int(tm.group(1)):02d}:{tm.group(2)}:00"

                    if date_str and time_str:
                        publish_date = f"{date_str} {time_str}"   # 2026-02-05 12:01:00
                    elif date_str:
                        publish_date = f"{date_str} 00:00:00"     # 只有日期，无时间
                    # date_str 都没有则 None

                    record = {
                        "title": title,
                        "url": href,
                        "publish_date": publish_date,
                        "_updated_at": beijing_now(),
                    }
                    records.append(record)
                    
                except Exception:
                    continue
            
            return records
            
        except Exception as e:
            logger.debug(f"获取第{page}页失败: {e}")
            return []

    @staticmethod
    def _is_old_news(publish_date: Optional[str], cutoff: Optional[str]) -> bool:
        """判断新闻是否早于截止时间（已采集过）。
        两端都有精确时间时按时间比较；任一方只有日期则只比较日期部分，
        同日新闻不跳过（靠 upsert 去重），避免因时间精度不同误跳。
        """
        if not cutoff or not publish_date:
            return False
        if len(publish_date) >= 19 and len(cutoff) >= 19:
            return publish_date < cutoff
        return publish_date[:10] < cutoff[:10]

    def collect_channel(
        self,
        cid: str,
        channel_name: str,
        news_type: str,
        max_pages: int = 100,
        with_content: bool = True
    ) -> int:
        """采集指定频道的新闻（增量模式：基于 DB 最新 publish_date 跳过旧新闻，按需停止翻页）"""
        cutoff = self.storage.get_latest_publish_date(channel_name)
        if cutoff:
            logger.info(f"[{channel_name}] 增量采集，DB 最新: {cutoff}")
        else:
            logger.info(f"[{channel_name}] 首次采集，获取{max_pages}页")

        all_records = []
        article_urls = []

        # 逐页采集，整页无新内容时停止翻页
        for page in range(1, max_pages + 1):
            page_records = self._fetch_page(cid, page)
            if not page_records:
                break

            new_on_page = 0
            for record in page_records:
                if self._is_old_news(record.get("publish_date"), cutoff):
                    continue

                record["news_type"] = news_type
                record["channel_name"] = channel_name
                record["source"] = "新浪财经"
                record["_collect_at"] = beijing_now()
                record["_uid"] = f"{channel_name}_{record['title'][:40]}_{record['url'][-40:]}"

                if with_content and ".shtml" in record["url"]:
                    article_urls.append(record["url"])

                all_records.append(record)
                new_on_page += 1

            logger.info(f"[{channel_name}] 第{page}页: {new_on_page}条新增")

            if new_on_page == 0:
                logger.info(f"[{channel_name}] 第{page}页全部为已有新闻，停止翻页")
                break

        if not all_records:
            logger.info(f"[{channel_name}] 无新增新闻")
            return 0

        # 并行获取新文章的正文和发布时间
        if with_content and article_urls:
            logger.info(f"[{channel_name}] 并行获取{len(article_urls)}篇文章正文...")
            content_results = self._fetch_articles_batch(article_urls)

            for record in all_records:
                if record["url"] in content_results:
                    content, article_date = content_results[record["url"]]
                    if content:
                        record["content"] = content
                        record["summary"] = content[:200]
                    if article_date:
                        record["article_date"] = article_date
                        if not record.get("publish_date"):
                            record["publish_date"] = article_date

        # 批量保存
        inserted, updated = self.storage.save_news_batch(all_records)
        saved = inserted + updated
        logger.info(f"[{channel_name}] 新增 {len(all_records)} 条，写入 {saved} 条（新增{inserted}/更新{updated}）")
        return saved

    def collect_all_channels(
        self,
        max_pages_per_channel: int = 100,
        max_workers: Optional[int] = None
    ) -> Dict[str, int]:
        """并行采集所有频道的新闻"""
        if max_workers:
            self.max_workers = max_workers
        
        results = {}
        logger.info(f"开始并行采集 {len(ROLL_CHANNELS)} 个频道，每频道最多 {max_pages_per_channel} 页")
        
        # 使用线程池并行采集不同频道
        with ThreadPoolExecutor(max_workers=len(ROLL_CHANNELS)) as executor:
            future_to_channel = {
                executor.submit(
                    self.collect_channel,
                    cid=channel["cid"],
                    channel_name=channel["name"],
                    news_type=channel["type"],
                    max_pages=max_pages_per_channel
                ): channel["name"]
                for channel in ROLL_CHANNELS
            }
            
            for future in as_completed(future_to_channel):
                channel_name = future_to_channel[future]
                try:
                    count = future.result()
                    results[channel_name] = count
                    logger.info(f"=== [{channel_name}] 共采集: {count}条 ===")
                except Exception as e:
                    logger.error(f"[{channel_name}] 采集失败: {e}")
                    results[channel_name] = 0
        
        return results

    def collect(
        self,
        channels: Optional[List[str]] = None,
        max_pages: int = 100,
        with_content: bool = True,
        max_workers: Optional[int] = None
    ) -> Dict[str, int]:
        """采集新闻（多线程并行版本）
        
        Args:
            channels: 要采集的频道列表，None表示全部
            max_pages: 每个频道采集的页数
            with_content: 是否获取文章正文
            max_workers: 最大线程数（默认8）
            
        Returns:
            各频道采集统计
        """
        if max_workers:
            self.max_workers = max_workers
        
        if channels is None:
            return self.collect_all_channels(max_pages, max_workers)
        
        channel_map = {ch["type"]: ch for ch in ROLL_CHANNELS}
        
        # 过滤有效的频道
        target_channels = [
            channel_map[ch_type] for ch_type in channels
            if ch_type in channel_map
        ]
        
        if not target_channels:
            return {}
        
        results = {}
        logger.info(f"开始并行采集 {len(target_channels)} 个频道")
        
        with ThreadPoolExecutor(max_workers=len(target_channels)) as executor:
            future_to_channel = {
                executor.submit(
                    self.collect_channel,
                    cid=ch["cid"],
                    channel_name=ch["name"],
                    news_type=ch["type"],
                    max_pages=max_pages,
                    with_content=with_content
                ): ch["name"]
                for ch in target_channels
            }
            
            for future in as_completed(future_to_channel):
                channel_name = future_to_channel[future]
                try:
                    count = future.result()
                    results[channel_name] = count
                except Exception as e:
                    logger.error(f"[{channel_name}] 采集失败: {e}")
                    results[channel_name] = 0
        
        return results

    def get_news(
        self,
        news_type: Optional[str] = None,
        channel_name: Optional[str] = None,
        is_breaking: Optional[bool] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取新闻列表"""
        return self.storage.get_latest_news(
            news_type=news_type,
            channel_name=channel_name,
            is_breaking=is_breaking,
            limit=limit
        )

    def get_by_category(self, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        """按分类获取新闻"""
        return self.storage.get_news_by_category(category, limit=limit)

    def get_breaking(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取突发新闻"""
        return self.storage.get_breaking_news(limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.storage.get_news_stats()

    @staticmethod
    def _fetch_caixin_df(timeout: int = _CAIXIN_TIMEOUT_SECONDS):
        """带硬超时地拉取财新数据（akshare 接口无 timeout，外部源挂起会拖死任务）。"""
        import akshare as ak
        return call_with_timeout(ak.stock_news_main_cx, timeout)

    def collect_caixin_news(self) -> int:
        """采集财新最新财经新闻（stock_news_main_cx，~100条）"""
        try:
            df = self._fetch_caixin_df()
            if df is None or df.empty:
                return 0
            records = []
            for _, row in df.iterrows():
                url = str(row.get("url", ""))
                summary = str(row.get("summary", "")).strip()
                tag = str(row.get("tag", "")) or "综合"
                if not summary:
                    continue
                # 财新接口无时间字段，文章页 JS 防爬不可靠，只存日期
                m = re.search(r"/(\d{4}-\d{2}-\d{2})/", url)
                publish_date = m.group(1) if m else beijing_now().strftime("%Y-%m-%d")
                title = (summary[:38] + "…") if len(summary) > 38 else summary
                records.append({
                    "title": title,
                    "content": summary,
                    "summary": summary[:200],
                    "url": url,
                    "publish_date": publish_date,
                    "news_type": "research",
                    "channel_name": tag,
                    "source": "财新",
                    "_collect_at": beijing_now(),
                })
            if records:
                inserted, updated = self.storage.save_news_batch(records)
                saved = inserted + updated
                logger.info(f"[财新] 写入 {saved} 条（新增{inserted}/更新{updated}）")
                return saved
        except Exception as e:
            logger.warning(f"财新新闻采集失败: {e}")
        return 0

    def get_categories(self) -> List[Dict[str, str]]:
        """获取新闻分类列表"""
        return [
            {"id": "general",  "name": "财经滚动", "description": "新浪财经综合滚动新闻"},
            {"id": "research", "name": "机构研报", "description": "机构评论/财新研究"},
            {"id": "futures",  "name": "期市要闻", "description": "期货市场要闻"},
            {"id": "nmetal",   "name": "有色金属", "description": "黄金白银贵金属"},
        ]

    def close(self):
        """关闭连接"""
        # 清理线程本地 session
        if hasattr(_thread_local, "session"):
            try:
                _thread_local.session.close()
            except Exception:
                pass