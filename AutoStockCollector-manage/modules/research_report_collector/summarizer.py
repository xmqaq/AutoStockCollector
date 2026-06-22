"""PDF text extraction + AI-powered research report summarization."""
import io
import re
import time
import requests
import pdfplumber
from typing import Optional, Dict, Any
from datetime import datetime
from core.storage.mongo_storage import ResearchReportStorage
from modules.ai.foundation.llm_router import LLMRouter
from utils.logger import get_logger

logger = get_logger(__name__)

_SUMMARIZE_PROMPT = """你是一位专业的金融/证券研究分析助理。
下面是一份券商研究报告的全文（OCR/PDF提取文本，可能有部分格式混乱或缺失）。

请详细分析并输出一份结构化的摘要，包括以下部分（每个部分用中文）：

## 核心观点
概括该报告的核心结论和推荐意见。

## 关键论据
列出支撑核心观点的 3-5 个主要论据或逻辑链条。

## 盈利预测与估值
提取报告中的财务预测数据（营收、净利润、EPS等）和估值判断。

## 风险提示
列出报告中提示的主要风险因素。

## 投资建议
报告给出的具体投资建议（评级、目标价等）。

---
报告标题：{title}
报告原文：
{text}"""

_MAX_SUMMARIZE_PER_RUN = 50
_SUMMARIZE_DELAY = 12


def extract_pdf_text(pdf_url: str, max_chars: int = 12000) -> str:
    """Download PDF from URL and extract text using pdfplumber."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(pdf_url, headers=headers, timeout=30)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        logger.warning(f"[Summarizer] Failed to download PDF {pdf_url}: {e}")
        raise

    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text.strip())
                if sum(len(t) for t in text_parts) >= max_chars:
                    break
    except Exception as e:
        logger.warning(f"[Summarizer] Failed to extract text from PDF: {e}")
        raise

    raw = "\n".join(text_parts)
    cleaned = re.sub(r"\s+", " ", raw).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
    return cleaned


def generate_abstract(title: str, text: str) -> str:
    """Call LLM to generate structured abstract from extracted text."""
    prompt = _SUMMARIZE_PROMPT.format(title=title, text=text)
    try:
        router = LLMRouter()
        result = router.chat(prompt, use_cache=False, max_tokens=2048, temperature=0.3)
        if result.success and result.raw:
            return result.raw.strip()
        else:
            logger.error(f"[Summarizer] LLM call failed: {result.error}")
            return ""
    except Exception as e:
        logger.error(f"[Summarizer] LLM error: {e}")
        return ""


def summarize_report(report_id: str, pdf_url: str, title: str) -> Optional[str]:
    """Full pipeline: extract PDF text -> LLM summary -> store in DB -> return."""
    try:
        logger.info(f"[Summarizer] Summarizing report: {title}")
        text = extract_pdf_text(pdf_url)
        if not text or len(text) < 100:
            logger.warning(f"[Summarizer] Extracted text too short ({len(text)} chars), skipping")
            return None

        abstract = generate_abstract(title, text)
        if not abstract:
            return None

        storage = ResearchReportStorage()
        storage.collection.update_one(
            {"report_id": report_id},
            {"$set": {"generated_abstract": abstract, "summarized_at": datetime.now().isoformat()}},
        )
        logger.info(f"[Summarizer] Saved generated abstract for {report_id}")
        return abstract
    except Exception as e:
        logger.error(f"[Summarizer] summarize_report error: {e}")
        return None


def summarize_pending_reports(max_reports: int = _MAX_SUMMARIZE_PER_RUN, delay: float = _SUMMARIZE_DELAY) -> Dict[str, Any]:
    """Scan reports without generated_abstract and summarize them with rate limiting."""
    storage = ResearchReportStorage()
    pending = list(storage.collection.find(
        {"generated_abstract": {"$exists": False}},
        {"report_id": 1, "title": 1, "info_code": 1, "date": 1},
        sort=[("date", -1)],
        limit=max_reports,
    ))
    if not pending:
        logger.info("[Summarizer] No pending reports to summarize")
        return {"success": True, "summarized": 0, "total": 0}

    logger.info(f"[Summarizer] Found {len(pending)} pending reports to summarize")
    success_count = 0
    for i, report in enumerate(pending):
        report_id = report.get("report_id", "")
        title = report.get("title", "")
        info_code = report.get("info_code", "")
        if not info_code:
            continue

        pdf_url = f"https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
        try:
            result = summarize_report(report_id, pdf_url, title)
            if result:
                success_count += 1
                logger.info(f"[Summarizer] [{i+1}/{len(pending)}] OK: {title[:30]}")
            else:
                logger.warning(f"[Summarizer] [{i+1}/{len(pending)}] FAIL: {title[:30]}")
        except Exception as e:
            logger.error(f"[Summarizer] [{i+1}/{len(pending)}] ERROR: {e}")

        if i < len(pending) - 1:
            time.sleep(delay)

    return {
        "success": True,
        "total": len(pending),
        "summarized": success_count,
    }
