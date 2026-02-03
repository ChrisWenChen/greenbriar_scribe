"""Text extraction using PyMuPDF."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import fitz

from .utils import normalize_line

_MATH_SYMBOL_RE = r"[=<>±×÷∑∫√∞≈≠≤≥πθλμΩαβγδΔΣ∏∂]"


def _reconstruct_line(line: Dict[str, Any]) -> Tuple[str, bool]:
    spans = line.get("spans", [])
    if not spans:
        return "", False
    line_bbox = line.get("bbox") or [0, 0, 0, 0]
    line_y0, line_y1 = line_bbox[1], line_bbox[3]
    line_center = (line_y0 + line_y1) / 2 if line_y1 > line_y0 else line_y0
    line_height = max(1.0, line_y1 - line_y0)
    parts: List[str] = []
    has_script = False
    for span in spans:
        text = span.get("text", "")
        if not text:
            continue
        bbox = span.get("bbox") or [0, 0, 0, 0]
        span_center = (bbox[1] + bbox[3]) / 2 if bbox[3] > bbox[1] else bbox[1]
        offset = (line_center - span_center) / line_height
        if offset > 0.25:
            parts.append(f"^{{{text}}}")
            has_script = True
        elif offset < -0.25:
            parts.append(f"_{{{text}}}")
            has_script = True
        else:
            parts.append(text)
    return "".join(parts), has_script


def extract_page_dict(page: fitz.Page) -> Dict[str, Any]:
    return page.get_text("dict")


def extract_blocks(page_dict: Dict[str, Any]) -> Tuple[List[dict], dict]:
    blocks: List[dict] = []
    text_blocks = 0
    image_blocks = 0
    for block in page_dict.get("blocks", []):
        btype = block.get("type")
        if btype == 0:
            text_blocks += 1
            lines = []
            font_sizes = []
            has_script = False
            for line in block.get("lines", []):
                line_text, line_has_script = _reconstruct_line(line)
                if line_text:
                    lines.append(line_text)
                has_script = has_script or line_has_script
                for span in line.get("spans", []):
                    if "size" in span:
                        font_sizes.append(span["size"])
            text = "\n".join(lines).strip()
            if text:
                avg_size = sum(font_sizes) / len(font_sizes) if font_sizes else None
                math_hint = bool(has_script)
                if not math_hint:
                    import regex as re

                    math_hint = bool(re.search(_MATH_SYMBOL_RE, text))
                blocks.append(
                    {
                        "bbox": block.get("bbox"),
                        "text": text,
                        "avg_size": avg_size,
                        "type": "text",
                        "math_hint": math_hint,
                    }
                )
        elif btype == 1:
            image_blocks += 1
        else:
            continue
    stats = {"text_blocks": text_blocks, "image_blocks": image_blocks}
    return blocks, stats


def extract_lines(page_dict: Dict[str, Any]) -> List[dict]:
    lines: List[dict] = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            line_text, _ = _reconstruct_line(line)
            if not line_text:
                continue
            bbox = line.get("bbox") or block.get("bbox")
            lines.append({"text": normalize_line(line_text), "bbox": bbox})
    return lines


def extract_page_text(page_dict: Dict[str, Any]) -> str:
    text = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            line_text = "".join(span.get("text", "") for span in spans)
            if line_text:
                text.append(line_text)
    return "\n".join(text)
