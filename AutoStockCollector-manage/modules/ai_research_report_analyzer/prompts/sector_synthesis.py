SECTOR_SYNTHESIS_PROMPT = """你是一名资深 A 股行业研究员。以下是近期关于 **{sector}** 板块的 {total} 篇研究报告标题列表。

请分析这批研报，输出 JSON 格式的分析结果。

## 研报标题

{report_titles}

## 输出要求

请严格输出 JSON（只返回 JSON，不要解释）：

```json
{{
  "sector": "{sector}",
  "themes": [
    {{"name": "主题1", "hot": true, "description": "简短的描述"}},
    {{"name": "主题2", "hot": false, "description": "简短的描述"}}
  ],
  "sentiment": "bullish",
  "key_stocks": [
    {{"code": "000000", "name": "公司名", "reason": "被提及的原因"}}
  ],
  "summary": "一段 100-200 字的行业综述",
  "theme_summary": "一段关于主题热度的简要分析"
}}
```

## 字段说明

- **themes**: 研报中反复出现的关键主题/方向，hot=true 表示热度高、被反复提及
- **sentiment**: 整体情绪，bullish（看多）/ bearish（看空）/ neutral（中性）
- **key_stocks**: 被多份研报提及的核心公司（最多 15 只），reason 简要说明看好逻辑
- **summary**: 对该板块的综合研判
- **theme_summary**: 各主题的热度分析和组合关系
"""
