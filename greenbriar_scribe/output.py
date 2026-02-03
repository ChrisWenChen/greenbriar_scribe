"""Output writers for text and JSONL artifacts."""

from __future__ import annotations

from typing import Iterable, List

from .utils import ensure_dir, json_write, jsonl_write


def write_cleaned_text(path: str, pages_text: List[str]) -> None:
    content = "\n\n\f\n\n".join(pages_text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def write_cleaned_markdown(path: str, markdown: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)


def write_pages_jsonl(path: str, records: Iterable[dict]) -> None:
    jsonl_write(path, records)


def write_segments_jsonl(path: str, records: Iterable[dict]) -> None:
    jsonl_write(path, records)


def write_meta(path: str, meta: dict) -> None:
    json_write(path, meta)


def ensure_out_dir(out_dir: str) -> None:
    ensure_dir(out_dir)
