"""
新闻管理模块
整合新浪财经新闻采集、存储、查询功能
支持多线程并行采集，提升采集速度
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
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
                        
                    time_elem = item.find("span", class_="time")
                    publish_date = time_elem.get_text(strip=True) if time_elem else ""
                    
                    record = {
                        "title": title,
                        "url": href,
                        "publish_date": publish_date,
                        "_updated_at": datetime.now(),
                    }
                    records.append(record)
                    
                except Exception:
                    continue
            
            return records
            
        except Exception as e:
            logger.debug(f"获取第{page}页失败: {e}")
            return []

    def collect_channel(
        self,
        cid: str,
        channel_name: str,
        news_type: str,
        max_pages: int = 100,
        with_content: bool = True
    ) -> int:
        """采集指定频道的新闻（多线程并行）"""
        # 1. 并行获取所有页面
        logger.info(f"[{channel_name}] 开始并行获取{max_pages}页列表...")
        
        page_records_map = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, 8)) as executor:
            future_to_page = {
                executor.submit(self._fetch_page, cid, page): page
                for page in range(1, max_pages + 1)
            }
            
            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    records = future.result()
                    if records:
                        page_records_map[page] = records
                    else:
                        # 没有数据，取消未完成的任务
                        for f in future_to_page:
                            if not f.done():
                                f.cancel()
                        break
                except Exception as e:
                    logger.debug(f"第{page}页异常: {e}")
        
        if not page_records_map:
            logger.warning(f"[{channel_name}] 无数据")
            return 0
        
        # 2. 按页顺序合并记录
        all_records = []
        article_urls = []
        
        for page in sorted(page_records_map.keys()):
            page_records = page_records_map[page]
            
            for record in page_records:
                record["news_type"] = news_type
                record["channel_name"] = channel_name
                record["source"] = "新浪财经"
                record["_collect_at"] = datetime.now()
                record["_uid"] = f"{channel_name}_{record['title'][:40]}_{record['url'][-40:]}"
                
                if with_content and ".shtml" in record["url"]:
                    article_urls.append(record["url"])
                
                all_records.append(record)
            
            logger.info(f"[{channel_name}] 第{page}页: {len(page_records)}条")
        
        # 3. 并行获取所有文章的正文和发布时间
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
                        # 同步到 publish_date，避免 publish_date 为空字符串
                        if not record.get("publish_date"):
                            record["publish_date"] = article_date
        
        # 4. 批量保存
        if all_records:
            self.storage.save_news_batch(all_records)
            logger.info(f"[{channel_name}] 总计采集 {len(all_records)} 条")
        
        return len(all_records)

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

    def get_categories(self) -> List[Dict[str, str]]:
        """获取新闻分类列表"""
        return [
            {"id": "general", "name": "财经滚动", "description": "新浪财经综合滚动新闻"},
            {"id": "research", "name": "机构评论", "description": "机构研究评论"},
            {"id": "futures", "name": "期市要闻", "description": "期货市场要闻"},
            {"id": "nmetal", "name": "贵金属", "description": "黄金白银分析"},
        ]

    def close(self):
        """关闭连接"""
        # 清理线程本地 session
        if hasattr(_thread_local, "session"):
            try:
                _thread_local.session.close()
            except Exception:
                pass