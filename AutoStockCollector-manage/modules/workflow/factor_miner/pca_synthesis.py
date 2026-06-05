"""PCA 因子合成：把高相关的因子群降维成独立的主成分因子。"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


class PCASynthesizer:
    """使用 PCA 将大量因子压缩为少数独立的主成分。

    用法:
        pca = PCASynthesizer(n_components=5)
        pca.fit(factor_matrix, feature_names)
        reduced = pca.transform(factor_matrix)  # 降维后的因子暴露
        pca.explain()  # 输出各主成分的解释方差比
    """

    def __init__(self, n_components: Optional[int] = None,
                 variance_ratio: float = 0.85):
        self.n_components = n_components
        self.variance_ratio = variance_ratio
        self._pca = None
        self._feature_names: List[str] = []
        self._component_names: List[str] = []

    def fit(self, X: np.ndarray, feature_names: List[str]) -> 'PCASynthesizer':
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        X_scaled = StandardScaler().fit_transform(X)
        n_features = X.shape[1]

        n_comp = self.n_components or min(n_features, max(2, n_features // 3))
        pca = PCA(n_components=n_comp, random_state=42)
        pca.fit(X_scaled)

        if self.variance_ratio < 1.0:
            cumsum = np.cumsum(pca.explained_variance_ratio_)
            n_needed = int(np.searchsorted(cumsum, self.variance_ratio) + 1)
            if n_needed < n_comp:
                pca = PCA(n_components=n_needed, random_state=42)
                pca.fit(X_scaled)

        self._pca = pca
        self._feature_names = feature_names
        self._component_names = [
            f'PC{i + 1}' for i in range(pca.n_components_)
        ]
        logger.info(
            f"PCA fitted: {n_features} factors → {pca.n_components_} components, "
            f"explained variance={pca.explained_variance_ratio_.sum():.2%}"
        )
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self._pca is None:
            raise RuntimeError("PCA not fitted. Call fit() first.")
        from sklearn.preprocessing import StandardScaler
        X_scaled = StandardScaler().fit_transform(X)
        return self._pca.transform(X_scaled)

    def explain(self) -> List[Dict[str, Any]]:
        if self._pca is None:
            return []
        result = []
        for i, (ratio, name) in enumerate(
            zip(self._pca.explained_variance_ratio_, self._component_names)
        ):
            # 找出对该主成分贡献最大的前 3 个原始因子
            loadings = self._pca.components_[i]
            top_idx = np.argsort(np.abs(loadings))[-3:][::-1]
            top_features = [
                {
                    'feature': self._feature_names[j],
                    'loading': round(float(loadings[j]), 3),
                }
                for j in top_idx if j < len(self._feature_names)
            ]
            result.append({
                'component': name,
                'explained_variance_ratio': round(float(ratio), 4),
                'cumulative': round(float(np.sum(
                    self._pca.explained_variance_ratio_[:i + 1])), 4),
                'top_features': top_features,
            })
        return result


def auto_select_n_components(
    X: np.ndarray,
    min_ratio: float = 0.80,
    max_components: int = 10,
) -> int:
    """自动选择主成分数，使得累积解释方差 >= min_ratio。"""
    from sklearn.decomposition import PCA
    pca = PCA(n_components=min(X.shape[1], max_components), random_state=42)
    pca.fit(X)
    cumsum = np.cumsum(pca.explained_variance_ratio_)
    n = int(np.searchsorted(cumsum, min_ratio) + 1)
    return min(n, max_components)
