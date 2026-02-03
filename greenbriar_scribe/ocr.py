"""PaddleOCR backend integration."""

from __future__ import annotations

from typing import List, Optional, Tuple

import fitz

from .utils import safe_float

_OCR_INSTANCE = None


def is_ocr_available() -> bool:
    try:
        import paddleocr  # noqa: F401
    except Exception:
        return False
    return True


def render_page_array(page: fitz.Page, dpi: int = 250):
    pix = page.get_pixmap(dpi=dpi)
    return _pixmap_to_numpy(pix)


def _pixmap_to_numpy(pix: fitz.Pixmap):
    import numpy as np

    if pix.n < 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    data = pix.samples
    arr = np.frombuffer(data, dtype=np.uint8)
    arr = arr.reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        arr = arr[:, :, :3]
    return arr[:, :, ::-1]  # RGB to BGR


def _init_worker(lang: str, use_angle_cls: bool) -> None:
    global _OCR_INSTANCE
    from paddleocr import PaddleOCR

    _OCR_INSTANCE = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang)


def _ocr_image_array(img) -> Tuple[str, Optional[float], List[dict]]:
    global _OCR_INSTANCE
    if _OCR_INSTANCE is None:  # pragma: no cover
        _init_worker("ch", True)
    results = _OCR_INSTANCE.ocr(img, cls=True)
    lines: List[str] = []
    confs: List[float] = []
    blocks: List[dict] = []
    for line in results[0] if results else []:
        bbox, (text, conf) = line
        if text:
            lines.append(text)
        conf_val = safe_float(conf)
        if conf_val is not None:
            confs.append(conf_val)
        blocks.append({"text": text, "bbox": None, "avg_size": None, "type": "ocr"})
    confidence = sum(confs) / len(confs) if confs else None
    return "\n".join(lines), confidence, blocks


def ocr_images_parallel(
    images: List,
    lang: str = "ch",
    use_angle_cls: bool = True,
    workers: int = 2,
) -> List[Tuple[str, Optional[float], List[dict]]]:
    if not images:
        return []
    if workers <= 1:
        _init_worker(lang, use_angle_cls)
        return [_ocr_image_array(img) for img in images]
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers, initializer=_init_worker, initargs=(lang, use_angle_cls)) as pool:
        return pool.map(_ocr_image_array, images)


def ocr_page(
    page: fitz.Page,
    lang: str = "ch",
    dpi: int = 250,
    use_angle_cls: bool = True,
) -> Tuple[str, Optional[float], List[dict]]:
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:  # pragma: no cover - gated by availability
        raise RuntimeError("PaddleOCR is not available") from exc

    img = render_page_array(page, dpi=dpi)
    ocr = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang)
    results = ocr.ocr(img, cls=use_angle_cls)
    lines: List[str] = []
    confs: List[float] = []
    blocks: List[dict] = []
    for line in results[0] if results else []:
        bbox, (text, conf) = line
        if text:
            lines.append(text)
        conf_val = safe_float(conf)
        if conf_val is not None:
            confs.append(conf_val)
        blocks.append({"text": text, "bbox": None, "avg_size": None, "type": "ocr"})
    confidence = sum(confs) / len(confs) if confs else None
    return "\n".join(lines), confidence, blocks
