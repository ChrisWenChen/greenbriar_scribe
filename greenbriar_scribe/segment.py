"""Segment creation and role classification."""

from __future__ import annotations

from typing import List, Optional

import regex as re

from .clean import merge_lines_into_paragraphs
from .utils import normalize_line


def classify_role(
    text: str,
    avg_size: Optional[float],
    page_median_size: Optional[float],
    page_width: float,
    bbox: Optional[list],
    repeated_headers_footers: set,
    math_hint: bool = False,
) -> str:
    norm = normalize_line(text)
    if not norm:
        return "unknown"
    if norm in repeated_headers_footers:
        return "header"
    math_score = _math_score(norm)
    if math_hint or math_score >= 2:
        if math_score >= 4:
            return "math_complex"
        return "math"
    if _is_list_item(norm):
        return "list_item"
    if _is_table_like(norm):
        return "table_like"
    if avg_size and page_median_size and avg_size > page_median_size * 1.3:
        if len(norm) <= 80:
            return "title"
    if bbox and page_width > 0:
        x0, _, x1, _ = bbox
        width = x1 - x0
        if width / page_width >= 0.7 and len(norm) <= 120:
            return "title"
    return "paragraph"


def split_block_to_paragraphs(text: str) -> List[str]:
    lines = [line for line in text.split("\n")]
    return merge_lines_into_paragraphs(lines)


def _is_list_item(text: str) -> bool:
    return bool(re.match(r"^([\-*•]|\d+\.|\d+\)|[a-zA-Z]\))\s+", text))


def _is_table_like(text: str) -> bool:
    if "  " in text:
        return True
    if re.search(r"\d+\s+\d+\s+\d+", text):
        return True
    if text.count("|") >= 2:
        return True
    return False


def _math_score(text: str) -> int:
    score = 0
    if re.search(r"[_^]\{", text):
        score += 2
    if re.search(r"[=<>±×÷∑∫√∞≈≠≤≥πθλμΩαβγδΔΣ∏∂]", text):
        score += 2
    if re.search(r"\b(sin|cos|tan|log|ln|exp)\b", text):
        score += 1
    if re.search(r"\d+/\d+", text):
        score += 1
    return score
