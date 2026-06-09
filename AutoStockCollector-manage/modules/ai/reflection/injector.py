from typing import Any, Dict, Optional
from modules.ai.reflection.evaluator import ReflectionEvaluator


class ReflectionInjector:
    def __init__(self):
        self.evaluator = ReflectionEvaluator()

    def inject(self, prompt: str, stock_code: str) -> str:
        reflection = self.evaluator.get_reflection_for_stock(stock_code)
        if not reflection:
            return prompt

        reflection_text = (
            f"\n\n【上次交易反思】\n"
            f"上次分析时间: {reflection.get('decision_time', 'N/A')}\n"
            f"当时价格: {reflection.get('decision_price', 'N/A')}\n"
            f"当前价格: {reflection.get('current_price', 'N/A')}\n"
            f"实现收益: {reflection.get('realized_return', 0):+.2f}%\n"
            f"判断准确性: {reflection.get('accuracy', 'unknown')}\n"
            f"总结: {reflection.get('summary', '')}\n"
        )
        return prompt + reflection_text
