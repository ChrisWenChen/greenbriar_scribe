"""SimpleTex markdown backend."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import fitz


def is_simpletex_available() -> bool:
    try:
        import requests  # noqa: F401
    except Exception:
        return False
    return True


@dataclass
class SimpleTexOptions:
    token: str
    api_url: str = "https://server.simpletex.cn/api/doc_ocr"
    dpi: int = 150
    inline_formula_wrapper: Optional[List[str]] = None
    isolated_formula_wrapper: Optional[List[str]] = None
    qps: float = 1.0
    max_retries: int = 2
    timeout_sec: int = 60


class SimpleTexMarkdownBackend:
    def __init__(self, opts: SimpleTexOptions):
        self.opts = opts
        self._min_interval = 1.0 / max(opts.qps, 0.1)
        self._last_call_ts = 0.0

    def _sleep_if_needed(self) -> None:
        now = time.time()
        gap = now - self._last_call_ts
        if gap < self._min_interval:
            time.sleep(self._min_interval - gap)

    @staticmethod
    def _pixmap_to_png_bytes(pix: fitz.Pixmap) -> bytes:
        return pix.tobytes("png")

    def _render_page_png(self, page: fitz.Page) -> bytes:
        zoom = self.opts.dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return self._pixmap_to_png_bytes(pix)

    def _ocr_page(self, png_bytes: bytes) -> Dict:
        import requests

        data = {}
        if self.opts.inline_formula_wrapper is not None:
            data["inline_formula_wrapper"] = json.dumps(self.opts.inline_formula_wrapper, ensure_ascii=False)
        if self.opts.isolated_formula_wrapper is not None:
            data["isolated_formula_wrapper"] = json.dumps(
                self.opts.isolated_formula_wrapper, ensure_ascii=False
            )

        headers = {"token": self.opts.token}
        files = {"file": ("page.png", png_bytes, "image/png")}

        self._sleep_if_needed()
        self._last_call_ts = time.time()

        resp = requests.post(
            self.opts.api_url,
            headers=headers,
            files=files,
            data=data,
            timeout=self.opts.timeout_sec,
        )
        resp.raise_for_status()
        return resp.json()

    def pdf_to_markdown(self, pdf_path: str) -> Dict:
        doc = fitz.open(pdf_path)
        pages_md: List[dict] = []
        errors: List[dict] = []

        for i in range(doc.page_count):
            page = doc.load_page(i)
            png = self._render_page_png(page)

            attempt = 0
            ok = False
            last_err = None
            while attempt <= self.opts.max_retries and not ok:
                try:
                    res = self._ocr_page(png)
                    if not res.get("status"):
                        raise RuntimeError(f"SimpleTex status=false: {res}")
                    content = res["res"]["content"]
                    pages_md.append(
                        {
                            "page": i + 1,
                            "markdown": content,
                            "request_id": res.get("request_id"),
                        }
                    )
                    ok = True
                except Exception as exc:
                    last_err = str(exc)
                    attempt += 1
                    time.sleep(1.0 * attempt)

            if not ok:
                errors.append({"page": i + 1, "error": last_err})

        full_parts = []
        for p in pages_md:
            full_parts.append(f"<!-- PAGE {p['page']} -->\n{p['markdown']}\n\n---\n")
        full_markdown = "\n".join(full_parts).strip()

        return {
            "pages": doc.page_count,
            "pages_md": pages_md,
            "full_markdown": full_markdown,
            "errors": errors,
        }
