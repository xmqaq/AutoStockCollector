import json
import re
from typing import Any, Dict, List, Optional
from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1


class Compressor:
    def __init__(self, max_tokens: int = 128000, threshold: float = 0.8):
        cfg = getattr(Settings, "COMPRESSION_CONFIG", {})
        self.max_tokens = max_tokens or cfg.get("max_tokens", 128000)
        self.threshold = threshold if threshold is not None else cfg.get("threshold", 0.8)
        self.enabled = cfg.get("enabled", True)
        self._layer1_max_trim = cfg.get("layer1_max_trim", 5000)

    def compress(self, text: str) -> str:
        if not self.enabled:
            return text

        budget = int(self.max_tokens * self.threshold)
        current_tokens = estimate_tokens(text)

        if current_tokens <= budget:
            return text

        text = self._layer1_microcompact(text)
        text = self._layer2_context_collapse(text)

        current_tokens = estimate_tokens(text)
        if current_tokens <= budget:
            return text

        text = self._layer3_auto_compact(text, budget)
        return text

    def _layer1_microcompact(self, text: str) -> str:
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        lines = text.split('\n')
        new_lines = []
        trimmed = 0
        for line in lines:
            if len(line) > 500 and trimmed < self._layer1_max_trim:
                line = line[:250] + '...' + line[-50:]
                trimmed += len(line) - 300
            new_lines.append(line)
        return '\n'.join(new_lines)

    def _layer2_context_collapse(self, text: str) -> str:
        price_blocks = re.findall(r'(?:收盘|close|价格)[：:]\s*([\d.,\s]+)', text, re.IGNORECASE)
        if price_blocks:
            collapsed = []
            for block in price_blocks:
                values = [v.strip() for v in re.split(r'[,\s]+', block) if v.strip()]
                if len(values) > 15:
                    first5 = values[:5]
                    last5 = values[-5:]
                    collapsed.append(f"[{', '.join(first5)} ... {', '.join(last5)}](共{len(values)}个)")
            if collapsed:
                text = re.sub(
                    r'(?:收盘|close|价格)[：:]\s*[\d.,\s]{100,}',
                    '收盘价: ' + collapsed[0],
                    text,
                )

        data_sections = re.findall(r'【([^】]+)】\n(.*?)(?=\n【|\Z)', text, re.DOTALL)
        collapsed_sections = []
        for title, content in data_sections:
            lines = content.strip().split('\n')
            if len(lines) > 20:
                kept = lines[:5] + [f'... (省略{len(lines) - 10}行)'] + lines[-5:]
                text = text.replace(content, '\n'.join(kept))

        return text

    def _layer3_auto_compact(self, text: str, budget: int) -> str:
        try:
            from modules.ai.foundation.llm_router import LLMRouter
            router = LLMRouter()
            result = router.chat_quick(
                f"请将以下内容压缩为原始长度的30%左右，保留所有关键信息和数据：\n\n{text}",
                use_cache=False, task_type="compress",
            )
            if result.success and result.raw:
                compressed = result.raw
                if estimate_tokens(compressed) < estimate_tokens(text) * 0.6:
                    return compressed
        except Exception as e:
            logger.warning(f"Layer3 compression failed: {e}")

        lines = text.split('\n')
        if len(lines) > 100:
            kept = lines[:30] + ['...'] + lines[-30:]
            return '\n'.join(kept)
        return text
