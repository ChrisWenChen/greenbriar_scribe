"""Layout ordering utilities."""

from __future__ import annotations

from typing import List, Tuple


def _kmeans_1d(values: List[float], k: int, iterations: int = 12) -> Tuple[List[int], List[float]]:
    if not values:
        return [], []
    sorted_vals = sorted(values)
    if k == 1:
        centroid = sum(values) / len(values)
        return [0] * len(values), [centroid]
    centroids = [sorted_vals[int(i * (len(sorted_vals) - 1) / (k - 1))] for i in range(k)]
    for _ in range(iterations):
        clusters = [[] for _ in range(k)]
        for v in values:
            idx = min(range(k), key=lambda i: abs(v - centroids[i]))
            clusters[idx].append(v)
        new_centroids = []
        for i in range(k):
            if clusters[i]:
                new_centroids.append(sum(clusters[i]) / len(clusters[i]))
            else:
                new_centroids.append(centroids[i])
        if new_centroids == centroids:
            break
        centroids = new_centroids
    assignments = [min(range(k), key=lambda i: abs(v - centroids[i])) for v in values]
    return assignments, centroids


def _inertia(values: List[float], assignments: List[int], centroids: List[float]) -> float:
    if not values:
        return 0.0
    total = 0.0
    for v, idx in zip(values, assignments):
        total += (v - centroids[idx]) ** 2
    return total


def choose_column_count(x0s: List[float], max_k: int = 3) -> int:
    if len(x0s) < 4:
        return 1
    inertias = []
    for k in range(1, max_k + 1):
        assign, cent = _kmeans_1d(x0s, k)
        inertias.append(_inertia(x0s, assign, cent))
    chosen = 1
    for k in range(1, max_k):
        base = inertias[k - 1]
        next_val = inertias[k]
        improvement = (base - next_val) / base if base > 0 else 0.0
        if improvement >= 0.2:
            chosen = k + 1
        else:
            break
    return chosen


def order_blocks(blocks: List[dict], page_width: float) -> List[dict]:
    if not blocks:
        return []
    title_blocks = []
    regular_blocks = []
    for block in blocks:
        bbox = block.get("bbox")
        if bbox:
            x0, y0, x1, y1 = bbox
            width = x1 - x0
            if page_width > 0 and width / page_width >= 0.7:
                title_blocks.append(block)
                continue
        regular_blocks.append(block)
    title_blocks.sort(key=lambda b: (b.get("bbox") or [0, 0, 0, 0])[1])
    x0s = [b["bbox"][0] for b in regular_blocks if b.get("bbox")]
    if not x0s:
        return title_blocks + regular_blocks
    k = choose_column_count(x0s)
    assignments, centroids = _kmeans_1d(x0s, k)
    columns = {i: [] for i in range(k)}
    idx = 0
    for block in regular_blocks:
        if not block.get("bbox"):
            continue
        columns[assignments[idx]].append(block)
        idx += 1
    for col in columns.values():
        col.sort(key=lambda b: b["bbox"][1])
    ordered_columns = sorted(columns.items(), key=lambda item: centroids[item[0]])
    ordered_blocks = []
    for _, col in ordered_columns:
        ordered_blocks.extend(col)
    return title_blocks + ordered_blocks
