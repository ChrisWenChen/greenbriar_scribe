"""Cleaning rules for headers, footers, dehyphenation, and whitespace."""

from __future__ import annotations

from typing import Dict, Iterable, List, Set

import regex as re

from .utils import is_page_number, normalize_line


def detect_header_footer_lines(
    pages_lines: List[List[dict]],
    header_max_lines: int,
    footer_max_lines: int,
    min_repetition_ratio: float,
) -> Set[str]:
    total_pages = len(pages_lines)
    if total_pages == 0:
        return set()
    counts: Dict[str, int] = {}
    for lines in pages_lines:
        if not lines:
            continue
        sorted_lines = sorted(lines, key=lambda l: (l.get("bbox") or [0, 0, 0, 0])[1])
        if len(sorted_lines) <= header_max_lines + footer_max_lines:
            continue
        header_lines = sorted_lines[:header_max_lines]
        footer_lines = sorted_lines[-footer_max_lines:] if footer_max_lines > 0 else []
        for line in header_lines + footer_lines:
            text = normalize_line(line.get("text", ""))
            if not text:
                continue
            counts[text] = counts.get(text, 0) + 1
    threshold = max(2, int(total_pages * min_repetition_ratio + 0.5))
    if total_pages < 2:
        return set()
    repeated = {text for text, count in counts.items() if count >= threshold}
    return repeated


def remove_headers_footers(lines: Iterable[str], repeated: Set[str]) -> List[str]:
    cleaned = []
    for line in lines:
        text = normalize_line(line)
        if text in repeated:
            continue
        cleaned.append(line)
    return cleaned


def remove_page_number_lines(lines: Iterable[str]) -> List[str]:
    cleaned = []
    for line in lines:
        if is_page_number(line):
            continue
        cleaned.append(line)
    return cleaned


def dehyphenate_text(text: str) -> str:
    return re.sub(r"([A-Za-z0-9])-\n([A-Za-z])", r"\1\2", text)


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def merge_lines_into_paragraphs(lines: List[str]) -> List[str]:
    paragraphs: List[str] = []
    buffer: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buffer:
                paragraphs.append(" ".join(buffer).strip())
                buffer = []
            continue
        if _is_list_item(stripped):
            if buffer:
                paragraphs.append(" ".join(buffer).strip())
                buffer = []
            paragraphs.append(stripped)
            continue
        if buffer and _ends_sentence(buffer[-1]):
            paragraphs.append(" ".join(buffer).strip())
            buffer = [stripped]
        else:
            buffer.append(stripped)
    if buffer:
        paragraphs.append(" ".join(buffer).strip())
    return [p for p in paragraphs if p]


def _ends_sentence(line: str) -> bool:
    return bool(re.search(r"[。！？.!?]\s*$", line))


def _is_list_item(text: str) -> bool:
    return bool(re.match(r"^([\-*•]|\d+\.|\d+\)|[a-zA-Z]\))\s+", text))
