"""Configuration dataclasses for Greenbriar Scribe."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScribeOptions:
    out_dir: str = "."
    doc_id: Optional[str] = None
    enable_ocr: bool = True
    ocr_lang: str = "ch"
    ocr_dpi: int = 250
    use_angle_cls: bool = True
    ocr_workers: int = 2
    max_ocr_pages: Optional[int] = None
    max_pages_ocr: Optional[int] = None
    multicolumn: bool = True
    remove_headers_footers: bool = True
    header_max_lines: int = 3
    footer_max_lines: int = 3
    min_repetition_ratio: float = 0.6
    remove_page_numbers: bool = True
    dehyphenate: bool = True
    normalize_whitespace: bool = True
    merge_paragraphs: bool = True
    mode: str = "local"
    simpletex_token: Optional[str] = None
    simpletex_api_url: str = "https://server.simpletex.cn/api/doc_ocr"
    simpletex_qps: float = 1.0
    simpletex_dpi: int = 150
    simpletex_inline_formula_wrapper: Optional[list] = None
    simpletex_isolated_formula_wrapper: Optional[list] = None
    simpletex_timeout_sec: int = 60
    simpletex_max_retries: int = 2
    export_math_crops: bool = False
    math_crop_dpi: int = 200
    quiet: bool = False
    verbose: bool = False
    log_level: Optional[str] = None
    extra: dict = field(default_factory=dict)
