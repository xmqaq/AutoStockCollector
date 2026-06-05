import numpy as np
from typing import List, Dict, Optional

_SENTIMENT_MAP = {'positive': 1.0, 'neutral': 0.0, 'negative': -1.0}


def calc_avg_sentiment(records: List[Dict]) -> float:
    if not records:
        return 0.0
    scores = []
    for r in records[:5]:
        s = r.get('sentiment', 'neutral')
        if isinstance(s, str):
            scores.append(_SENTIMENT_MAP.get(s, 0.0))
        elif isinstance(s, (int, float)):
            scores.append(float(np.clip(s, -1, 1)))
    return float(np.mean(scores)) if scores else 0.0


def calc_news_heat(records: List[Dict],
                   avg_daily_count: float = 2.0) -> float:
    return len(records) / max(avg_daily_count, 1)


def calc_sentiment_trend(records: List[Dict]) -> Optional[float]:
    if len(records) < 4:
        return None
    half = len(records) // 2
    recent = [r for r in records[:half]]
    older = [r for r in records[half:]]
    recent_score = calc_avg_sentiment(recent)
    older_score = calc_avg_sentiment(older)
    return recent_score - older_score


def batch_sentiment_factors(codes: List[str],
                            news_map: Dict[str, List[Dict]]
                            ) -> Dict[str, Dict[str, float]]:
    result = {}
    for code in codes:
        records = news_map.get(code, [])
        if not records:
            result[code] = {}
            continue
        factors = {}
        factors['sentiment_avg'] = calc_avg_sentiment(records)
        factors['news_heat'] = calc_news_heat(records)
        st = calc_sentiment_trend(records)
        if st is not None:
            factors['sentiment_trend'] = st
        result[code] = factors
    return result
