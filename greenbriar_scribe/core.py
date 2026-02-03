"""Core Scribe pipeline."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import fitz

from . import clean as clean_mod
from . import extract as extract_mod
from . import layout as layout_mod
from . import ocr as ocr_mod
from . import segment as segment_mod
from . import simpletex as simpletex_mod
from .options import ScribeOptions
from .output import (
    ensure_out_dir,
    write_cleaned_markdown,
    write_cleaned_text,
    write_meta,
    write_pages_jsonl,
    write_segments_jsonl,
)
from .utils import (
    dataclass_to_dict,
    is_page_number,
    markdown_to_text,
    normalize_line,
    remove_whitespace,
    segment_id,
    setup_logger,
)


@dataclass
class CleanResult:
    cleaned_txt_path: str
    cleaned_md_path: Optional[str]
    segments_jsonl_path: str
    pages_jsonl_path: str
    meta_json_path: str
    meta: dict


class Scribe:
    def __init__(self) -> None:
        self.logger = setup_logger()

    def process_pdf(self, path: str, options: Optional[ScribeOptions] = None) -> CleanResult:
        opts = options or ScribeOptions()
        self.logger = setup_logger(opts.quiet, opts.verbose, opts.log_level)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Input PDF not found: {path}")

        doc_id = opts.doc_id or os.path.splitext(os.path.basename(path))[0]
        ensure_out_dir(opts.out_dir)

        warnings: List[str] = []
        errors: List[str] = []

        mode = opts.mode or "local"
        if mode not in {"local", "simpletex_markdown", "auto"}:
            warnings.append(f"Unknown mode {mode}, falling back to local.")
            mode = "local"

        if mode == "simpletex_markdown" and not simpletex_mod.is_simpletex_available():
            raise RuntimeError("SimpleTex dependencies missing; install extras and retry.")

        if mode == "simpletex_markdown" and not opts.simpletex_token:
            raise RuntimeError("SimpleTex token missing; pass simpletex_token or --simpletex-token.")

        if mode == "auto" and not simpletex_mod.is_simpletex_available():
            warnings.append("SimpleTex dependencies missing; falling back to local.")
            mode = "local"

        if mode == "auto" and not opts.simpletex_token:
            warnings.append("SimpleTex token missing; falling back to local.")
            mode = "local"

        ocr_enabled = opts.enable_ocr
        if ocr_enabled and not ocr_mod.is_ocr_available():
            warnings.append("PaddleOCR not available; OCR disabled.")
            ocr_enabled = False

        try:
            doc = fitz.open(path)
        except Exception as exc:
            raise RuntimeError(f"Failed to open PDF: {path}") from exc

        if mode == "auto" and opts.simpletex_token and simpletex_mod.is_simpletex_available() and not ocr_enabled:
            warnings.append("Auto mode switched to SimpleTex because OCR is disabled.")
            mode = "simpletex_markdown"

        if mode == "simpletex_markdown":
            return self._process_simpletex(path, opts, doc_id, warnings, errors)

        pages_data: List[dict] = []
        ocr_images: List = []
        ocr_indices: List[int] = []
        max_ocr_pages = opts.max_ocr_pages if opts.max_ocr_pages is not None else opts.max_pages_ocr
        ocr_pages_used = 0
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            page_width = float(page.rect.width)
            page_dict = extract_mod.extract_page_dict(page)
            page_text = extract_mod.extract_page_text(page_dict)
            blocks, stats = extract_mod.extract_blocks(page_dict)
            lines = extract_mod.extract_lines(page_dict)
            scanned = len(remove_whitespace(page_text)) < 15
            if stats.get("text_blocks", 0) <= 1 and stats.get("image_blocks", 0) > 0:
                scanned = True
            source_mode = "extract:text"
            confidence = None
            if scanned and ocr_enabled:
                if max_ocr_pages is None or ocr_pages_used < max_ocr_pages:
                    try:
                        ocr_images.append(ocr_mod.render_page_array(page, dpi=opts.ocr_dpi))
                        ocr_indices.append(page_index)
                        source_mode = "ocr:pending"
                        ocr_pages_used += 1
                    except Exception as exc:
                        warnings.append(f"OCR render failed on page {page_index + 1}: {exc}")
                        source_mode = "extract:failed_ocr"
                else:
                    warnings.append(f"OCR skipped after max_ocr_pages on page {page_index + 1}.")
                    source_mode = "extract:failed_ocr"
            elif scanned and not ocr_enabled:
                warnings.append(f"OCR disabled; scanned page {page_index + 1} extracted as text.")
                source_mode = "extract:failed_ocr"
            pages_data.append(
                {
                    "page": page_index + 1,
                    "page_width": page_width,
                    "text": page_text,
                    "blocks": blocks,
                    "lines": lines,
                    "source_mode": source_mode,
                    "confidence": confidence,
                }
            )
            self.logger.info(
                "page %s mode=%s chars=%s",
                page_index + 1,
                source_mode,
                len(page_text or ""),
            )

        if ocr_images:
            start = time.time()
            try:
                results = ocr_mod.ocr_images_parallel(
                    ocr_images,
                    lang=opts.ocr_lang,
                    use_angle_cls=opts.use_angle_cls,
                    workers=opts.ocr_workers,
                )
                for (ocr_text, confidence, ocr_blocks), page_index in zip(results, ocr_indices):
                    pages_data[page_index]["text"] = ocr_text
                    pages_data[page_index]["blocks"] = ocr_blocks
                    pages_data[page_index]["lines"] = [
                        {"text": line, "bbox": None} for line in ocr_text.split("\n") if line
                    ]
                    pages_data[page_index]["source_mode"] = "ocr:paddle"
                    pages_data[page_index]["confidence"] = confidence
                self.logger.info("OCR batch time %.2fs", time.time() - start)
            except Exception as exc:
                warnings.append(f"OCR parallel failed: {exc}")
                for page_index in ocr_indices:
                    pages_data[page_index]["source_mode"] = "extract:failed_ocr"

        repeated_lines = set()
        if opts.remove_headers_footers:
            pages_lines = []
            for page in pages_data:
                lines = [line for line in page["lines"] if line.get("bbox")]
                pages_lines.append(lines)
            repeated_lines = clean_mod.detect_header_footer_lines(
                pages_lines,
                opts.header_max_lines,
                opts.footer_max_lines,
                opts.min_repetition_ratio,
            )

        segments: List[dict] = []
        pages_records: List[dict] = []
        pages_text: List[str] = []

        for page in pages_data:
            page_num = page["page"]
            page_width = page["page_width"]
            blocks = page["blocks"]
            if opts.multicolumn and any(b.get("bbox") for b in blocks):
                blocks = layout_mod.order_blocks(blocks, page_width)
            font_sizes = [b.get("avg_size") for b in blocks if b.get("avg_size")]
            font_sizes_sorted = sorted(font_sizes)
            median_size = None
            if font_sizes_sorted:
                mid = len(font_sizes_sorted) // 2
                median_size = font_sizes_sorted[mid]
            page_paragraphs: List[str] = []
            segment_index = 1
            for block in blocks:
                text = block.get("text", "")
                if not text:
                    continue
                lines = text.split("\n")
                if opts.remove_headers_footers and repeated_lines:
                    lines = [line for line in lines if normalize_line(line) not in repeated_lines]
                if opts.remove_page_numbers:
                    lines = [line for line in lines if not is_page_number(normalize_line(line))]
                text = "\n".join(lines)
                if not text.strip():
                    continue
                norm_text = clean_mod.normalize_whitespace(text) if opts.normalize_whitespace else text
                if opts.dehyphenate:
                    text = clean_mod.dehyphenate_text(text)
                paragraphs = segment_mod.split_block_to_paragraphs(text) if opts.merge_paragraphs else [text]
                for paragraph in paragraphs:
                    if opts.normalize_whitespace:
                        paragraph = clean_mod.normalize_whitespace(paragraph)
                    if not paragraph:
                        continue
                    role = segment_mod.classify_role(
                        paragraph,
                        block.get("avg_size"),
                        median_size,
                        page_width,
                        block.get("bbox"),
                        repeated_lines,
                        block.get("math_hint", False),
                    )
                    if role == "math_complex" and opts.export_math_crops and block.get("bbox"):
                        self._export_math_crop(doc, page_num, block.get("bbox"), opts, doc_id, segment_index)
                    segments.append(
                        {
                            "doc_id": doc_id,
                            "page": page_num,
                            "segment_id": segment_id(doc_id, page_num, segment_index),
                            "role": role,
                            "bbox": block.get("bbox"),
                            "text": paragraph,
                            "source_mode": page["source_mode"],
                            "confidence": page.get("confidence"),
                        }
                    )
                    page_paragraphs.append(paragraph)
                    segment_index += 1
            page_text_clean = "\n\n".join(page_paragraphs).strip()
            pages_text.append(page_text_clean)
            pages_records.append(
                {
                    "doc_id": doc_id,
                    "page": page_num,
                    "text": page_text_clean,
                    "source_mode": page["source_mode"],
                }
            )

        cleaned_txt_path = os.path.join(opts.out_dir, f"{doc_id}.cleaned.txt")
        cleaned_md_path = None
        segments_jsonl_path = os.path.join(opts.out_dir, f"{doc_id}.segments.jsonl")
        pages_jsonl_path = os.path.join(opts.out_dir, f"{doc_id}.pages.jsonl")
        meta_json_path = os.path.join(opts.out_dir, f"{doc_id}.meta.json")

        meta = {
            "doc_id": doc_id,
            "input_pdf": os.path.abspath(path),
            "pages": len(pages_data),
            "page_modes": [p["source_mode"] for p in pages_data],
            "ocr_enabled": ocr_enabled,
            "ocr_backend": "paddleocr" if ocr_enabled else None,
            "mode": mode,
            "options": dataclass_to_dict(opts),
            "warnings": warnings,
            "errors": errors,
        }

        write_cleaned_text(cleaned_txt_path, pages_text)
        write_segments_jsonl(segments_jsonl_path, segments)
        write_pages_jsonl(pages_jsonl_path, pages_records)
        write_meta(meta_json_path, meta)

        return CleanResult(
            cleaned_txt_path=cleaned_txt_path,
            cleaned_md_path=cleaned_md_path,
            segments_jsonl_path=segments_jsonl_path,
            pages_jsonl_path=pages_jsonl_path,
            meta_json_path=meta_json_path,
            meta=meta,
        )

    def _process_simpletex(
        self,
        path: str,
        opts: ScribeOptions,
        doc_id: str,
        warnings: List[str],
        errors: List[str],
    ) -> CleanResult:
        if not simpletex_mod.is_simpletex_available():
            raise RuntimeError("SimpleTex dependencies missing")
        if not opts.simpletex_token:
            raise RuntimeError("SimpleTex token required")

        backend = simpletex_mod.SimpleTexMarkdownBackend(
            simpletex_mod.SimpleTexOptions(
                token=opts.simpletex_token,
                api_url=opts.simpletex_api_url,
                dpi=opts.simpletex_dpi,
                inline_formula_wrapper=opts.simpletex_inline_formula_wrapper,
                isolated_formula_wrapper=opts.simpletex_isolated_formula_wrapper,
                qps=opts.simpletex_qps,
                max_retries=opts.simpletex_max_retries,
                timeout_sec=opts.simpletex_timeout_sec,
            )
        )

        result = backend.pdf_to_markdown(path)
        pages_md = result["pages_md"]
        pages_records = [
            {
                "doc_id": doc_id,
                "page": p["page"],
                "text": p["markdown"],
                "source_mode": "simpletex:markdown",
                "request_id": p.get("request_id"),
            }
            for p in pages_md
        ]
        cleaned_md_path = os.path.join(opts.out_dir, f"{doc_id}.cleaned.md")
        cleaned_txt_path = os.path.join(opts.out_dir, f"{doc_id}.cleaned.txt")
        segments_jsonl_path = os.path.join(opts.out_dir, f"{doc_id}.segments.jsonl")
        pages_jsonl_path = os.path.join(opts.out_dir, f"{doc_id}.pages.jsonl")
        meta_json_path = os.path.join(opts.out_dir, f"{doc_id}.meta.json")

        write_cleaned_markdown(cleaned_md_path, result["full_markdown"])
        write_cleaned_text(cleaned_txt_path, [markdown_to_text(result["full_markdown"])])
        write_pages_jsonl(pages_jsonl_path, pages_records)
        write_segments_jsonl(segments_jsonl_path, [])

        meta = {
            "doc_id": doc_id,
            "input_pdf": os.path.abspath(path),
            "pages": result["pages"],
            "page_modes": ["simpletex:markdown" for _ in pages_md],
            "ocr_enabled": False,
            "ocr_backend": None,
            "mode": "simpletex_markdown",
            "options": dataclass_to_dict(opts),
            "warnings": warnings,
            "errors": errors + result.get("errors", []),
        }
        write_meta(meta_json_path, meta)

        return CleanResult(
            cleaned_txt_path=cleaned_txt_path,
            cleaned_md_path=cleaned_md_path,
            segments_jsonl_path=segments_jsonl_path,
            pages_jsonl_path=pages_jsonl_path,
            meta_json_path=meta_json_path,
            meta=meta,
        )

    def _export_math_crop(
        self,
        doc: fitz.Document,
        page_num: int,
        bbox: list,
        opts: ScribeOptions,
        doc_id: str,
        segment_index: int,
    ) -> None:
        try:
            page = doc.load_page(page_num - 1)
            rect = fitz.Rect(bbox)
            pix = page.get_pixmap(clip=rect, dpi=opts.math_crop_dpi)
            crops_dir = os.path.join(opts.out_dir, "math_crops")
            ensure_out_dir(crops_dir)
            name = f"{doc_id}-p{page_num:03d}-s{segment_index:03d}.png"
            pix.save(os.path.join(crops_dir, name))
        except Exception as exc:  # pragma: no cover
            self.logger.warning("Failed to export math crop: %s", exc)
