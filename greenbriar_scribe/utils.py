"""Utility helpers for Greenbriar Scribe."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict
from typing import Iterable, Optional


def setup_logger(quiet: bool = False, verbose: bool = False, log_level: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger("greenbriar_scribe")
    if logger.handlers:
        return logger
    level = logging.INFO
    if quiet:
        level = logging.WARNING
    if verbose:
        level = logging.DEBUG
    if log_level:
        level = getattr(logging, log_level.upper(), level)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def remove_whitespace(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def normalize_line(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_page_number(text: str) -> bool:
    stripped = normalize_line(text)
    if not stripped:
        return False
    if re.fullmatch(r"\d{1,4}", stripped):
        return True
    if re.fullmatch(r"(?i)page\s+\d+(\s*/\s*\d+)?", stripped):
        return True
    return False


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def jsonl_write(path: str, records: Iterable[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def json_write(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def dataclass_to_dict(obj) -> dict:
    return asdict(obj)


def segment_id(doc_id: str, page: int, index: int) -> str:
    return f"{doc_id}-p{page:03d}-s{index:03d}"


def safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def markdown_to_text(md: str) -> str:
    import regex as re

    text = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"\\$\\$.*?\\$\\$", " ", text, flags=re.DOTALL)
    text = re.sub(r"\\$.*?\\$", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\\[.*?\\]\\(.*?\\)", " ", text)
    text = re.sub(r"#+\\s+", "", text)
    text = re.sub(r"\\*\\*|__|\\*|_", "", text)
    text = re.sub(r"\\s+", " ", text)
    return text.strip()
