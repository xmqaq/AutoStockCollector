"""因子权重学习：用 ElasticNet 从历史数据中自动学习因子权重。"""

import numpy as np
from typing import List, Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class FactorWeightLearner:
    """使用 ElasticNet 回归学习因子权重。

    用法:
        1. 提供 X (因子暴露矩阵) 和 y (未来收益/排序标签)
        2. fit() 训练模型，返回特征权重
        3. get_weights() 输出正规化后的因子权重 (sum=1)
    """

    def __init__(self, alpha: float = 0.01, l1_ratio: float = 0.5):
        self.alpha = alpha
        self.l1_ratio = l1_ratio
        self._model = None
        self._feature_names: List[str] = []
        self._weights: Dict[str, float] = {}

    def fit(self, X: np.ndarray, y: np.ndarray,
            feature_names: List[str]) -> 'FactorWeightLearner':
        from sklearn.linear_model import ElasticNet
        from sklearn.preprocessing import StandardScaler

        X_scaled = StandardScaler().fit_transform(X)
        model = ElasticNet(
            alpha=self.alpha,
            l1_ratio=self.l1_ratio,
            random_state=42,
            max_iter=10000,
            fit_intercept=True,
        )
        model.fit(X_scaled, y)

        self._model = model
        self._feature_names = feature_names

        total_abs = np.sum(np.abs(model.coef_))
        if total_abs > 0:
            self._weights = {
                name: float(abs(coef) / total_abs)
                for name, coef in zip(feature_names, model.coef_)
            }
        else:
            n = len(feature_names)
            self._weights = {name: 1.0 / n for name in feature_names}

        n_nonzero = np.sum(model.coef_ != 0)
        logger.info(
            f"ElasticNet trained: alpha={self.alpha} l1_ratio={self.l1_ratio} "
            f"nonzero_coefs={n_nonzero}/{len(feature_names)} "
            f"R2={model.score(X_scaled, y):.4f}"
        )
        return self

    def get_weights(self) -> Dict[str, float]:
        return dict(self._weights)

    def get_top_features(self, n: int = 5) -> List[Dict[str, Any]]:
        sorted_w = sorted(self._weights.items(), key=lambda x: x[1], reverse=True)
        return [
            {'feature': name, 'weight': round(w, 4)}
            for name, w in sorted_w[:n]
        ]

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")
        from sklearn.preprocessing import StandardScaler
        X_scaled = StandardScaler().fit_transform(X)
        return self._model.predict(X_scaled)


def learn_weights_from_ic(
    ic_results: Dict[int, List[Dict[str, Any]]],
    default_equal: bool = True,
) -> Dict[str, float]:
    """从多周期 IC 结果中学习权重：IC 越高的因子权重越大。

    Args:
        ic_results: compute_multi_period_ic() 的输出
        default_equal: 当无 IC 数据时是否使用等权
    Returns:
        {factor_name: weight}
    """
    from collections import defaultdict

    factor_ics = defaultdict(list)
    for period, results in ic_results.items():
        for r in results:
            factor_ics[r['factor']].append(r['abs_ic'])

    if not factor_ics:
        return {} if not default_equal else None

    if default_equal:
        # 等权作为兜底
        pass

    # 取每个因子的平均 IC 作为权重
    weights = {}
    total_ic = 0.0
    for fname, ics in factor_ics.items():
        w = float(np.mean(ics))
        if w > 0:
            weights[fname] = w
            total_ic += w

    if total_ic > 0:
        weights = {k: v / total_ic for k, v in weights.items()}

    return weights
