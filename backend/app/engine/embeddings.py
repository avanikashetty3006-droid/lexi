from __future__ import annotations

import math
from functools import lru_cache
from typing import Callable

import numpy as np

from app.config import settings
from app.schemas import Interpretation, SemanticMapPoint

EmbedFn = Callable[[list[str]], np.ndarray]


@lru_cache(maxsize=2)
def _load_sentence_transformer(model_name: str):
    """Lazy-load and cache local sentence-transformers model."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed texts into L2-normalized vectors using the configured SentenceTransformer."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = _load_sentence_transformer(settings.embed_model)
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return np.asarray(vectors, dtype=np.float32)


def cluster_by_cosine(
    embeddings: np.ndarray,
    cosine_threshold: float = 0.80,
) -> list[list[int]]:
    """Cluster normalized embedding vectors using cosine similarity >= threshold."""
    n = embeddings.shape[0]
    if n == 0:
        return []
    if n == 1:
        return [[0]]

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    unit = embeddings / norms
    sim_matrix = unit @ unit.T

    visited = [False] * n
    clusters: list[list[int]] = []

    for i in range(n):
        if visited[i]:
            continue
        component: list[int] = []
        stack = [i]
        visited[i] = True
        while stack:
            curr = stack.pop()
            component.append(curr)
            for j in range(n):
                if not visited[j] and float(sim_matrix[curr, j]) >= cosine_threshold:
                    visited[j] = True
                    stack.append(j)
        clusters.append(sorted(component))
    return clusters


def compute_semantic_entropy(
    clusters: list[list[int]],
    weights: list[float],
) -> float:
    """Compute Shannon semantic entropy (in bits) across semantic clusters."""
    if not clusters or len(clusters) <= 1:
        return 0.0

    total_weight = sum(max(0.0, w) for w in weights)
    if total_weight <= 0.0:
        n_items = sum(len(c) for c in clusters)
        weights = [1.0 / max(1, n_items)] * n_items
        total_weight = 1.0

    entropy = 0.0
    for cluster in clusters:
        cluster_mass = sum(max(0.0, weights[idx]) for idx in cluster) / total_weight
        if cluster_mass > 0.0:
            entropy -= cluster_mass * math.log2(cluster_mass)

    return round(max(0.0, entropy), 4)


def entropy_to_confidence(semantic_entropy: float, n_items: int) -> float:
    """Convert semantic entropy to a normalized [0, 1] confidence score for comparison with vote confidence."""
    if n_items <= 1:
        return 1.0
    max_entropy = math.log2(n_items)
    if max_entropy <= 0.0:
        return 1.0
    score = 1.0 - (semantic_entropy / max_entropy)
    return round(max(0.0, min(1.0, score)), 4)


def project_to_2d_pca(embeddings: np.ndarray) -> list[tuple[float, float]]:
    """Project N embedding vectors to 2D coordinates using centered SVD-based PCA."""
    n = embeddings.shape[0]
    if n == 0:
        return []
    if n == 1:
        return [(0.0, 0.0)]

    centered = embeddings.astype(np.float64) - np.mean(embeddings, axis=0, keepdims=True)
    # Full matrices=False returns Vh of shape (min(n, d), d)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    components = vh[:2]  # up to 2 principal axes
    projected = centered @ components.T

    coords: list[tuple[float, float]] = []
    for row in projected:
        x = float(row[0]) if projected.shape[1] >= 1 else 0.0
        y = float(row[1]) if projected.shape[1] >= 2 else 0.0
        coords.append((round(x, 4), round(y, 4)))
    return coords


def analyze_semantic_space(
    interpretations: list[Interpretation],
    *,
    cosine_threshold: float = 0.80,
    embed_fn: EmbedFn | None = None,
) -> tuple[float, list[SemanticMapPoint]]:
    """
    Embed candidate interpretations, cluster by cosine similarity, compute semantic entropy,
    and project to a 2D PCA semantic map.
    """
    if not interpretations:
        return 0.0, []

    texts = [item.meaning for item in interpretations]
    weights = [item.probability for item in interpretations]

    fn = embed_fn or embed_texts
    vectors = fn(texts)

    clusters = cluster_by_cosine(vectors, cosine_threshold=cosine_threshold)
    semantic_entropy = compute_semantic_entropy(clusters, weights)
    coords = project_to_2d_pca(vectors)

    semantic_map = [
        SemanticMapPoint(
            id=item.id,
            x=coords[idx][0],
            y=coords[idx][1],
            label=item.meaning,
        )
        for idx, item in enumerate(interpretations)
    ]
    return semantic_entropy, semantic_map
