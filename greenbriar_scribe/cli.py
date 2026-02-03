"""Command line interface for Greenbriar Scribe."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List

from .core import Scribe
from .options import ScribeOptions
from .utils import setup_logger


def _collect_pdfs(input_path: str, recursive: bool) -> List[str]:
    if os.path.isfile(input_path):
        return [input_path]
    if not os.path.isdir(input_path):
        return []
    pdfs: List[str] = []
    if recursive:
        for root, _, files in os.walk(input_path):
            for name in files:
                if name.lower().endswith(".pdf"):
                    pdfs.append(os.path.join(root, name))
    else:
        for name in os.listdir(input_path):
            if name.lower().endswith(".pdf"):
                pdfs.append(os.path.join(input_path, name))
    return sorted(pdfs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="greenbriar-scribe")
    parser.add_argument("input", help="PDF file or directory")
    parser.add_argument("-o", "--out-dir", default=".", help="Output directory")
    parser.add_argument("--doc-id", default=None, help="Override doc_id for single PDF")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR")
    parser.add_argument("--ocr-lang", default="ch", help="OCR language for PaddleOCR")
    parser.add_argument("--ocr-dpi", type=int, default=250, help="OCR render DPI")
    parser.add_argument("--ocr-workers", type=int, default=2, help="OCR worker processes")
    parser.add_argument("--max-ocr-pages", type=int, default=None, help="Maximum pages to OCR")
    parser.add_argument("--no-multicol", action="store_true", help="Disable multi-column ordering")
    parser.add_argument("--keep-hf", action="store_true", help="Keep headers/footers")
    parser.add_argument("--hf-ratio", type=float, default=0.6, help="Header/footer repetition ratio")
    parser.add_argument("--header-max-lines", type=int, default=3, help="Header max lines")
    parser.add_argument("--footer-max-lines", type=int, default=3, help="Footer max lines")
    parser.add_argument("--max-pages-ocr", type=int, default=None, help="Maximum pages to OCR (deprecated)")
    parser.add_argument("--recursive", action="store_true", help="Recurse into directories")
    parser.add_argument("--quiet", action="store_true", help="Reduce logging")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--mode", default="local", help="Processing mode: local|simpletex_markdown|auto")
    parser.add_argument("--simpletex-token", default=None, help="SimpleTex API token")
    parser.add_argument("--simpletex-api-url", default="https://server.simpletex.cn/api/doc_ocr")
    parser.add_argument("--simpletex-qps", type=float, default=1.0)
    parser.add_argument("--simpletex-dpi", type=int, default=150)
    parser.add_argument("--simpletex-inline-wrapper", nargs=2, default=None)
    parser.add_argument("--simpletex-isolated-wrapper", nargs=2, default=None)
    parser.add_argument("--simpletex-timeout-sec", type=int, default=60)
    parser.add_argument("--simpletex-max-retries", type=int, default=2)
    parser.add_argument("--export-math-crops", action="store_true", help="Export math crops when detected")
    parser.add_argument("--math-crop-dpi", type=int, default=200)
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = setup_logger(args.quiet, args.verbose)
    pdfs = _collect_pdfs(args.input, args.recursive)
    if not pdfs:
        logger.error("No PDF files found at %s", args.input)
        return 2

    if args.doc_id and len(pdfs) > 1:
        logger.error("--doc-id can only be used with a single input PDF")
        return 2

    scribe = Scribe()
    exit_code = 0
    
    # Read SimpleTex token from environment if not provided via CLI
    simpletex_token = args.simpletex_token or os.environ.get("SIMPLETEX_TOKEN")

    for pdf in pdfs:
        opts = ScribeOptions(
            out_dir=args.out_dir,
            doc_id=args.doc_id,
            enable_ocr=not args.no_ocr,
            ocr_lang=args.ocr_lang,
            ocr_dpi=args.ocr_dpi,
            ocr_workers=args.ocr_workers,
            max_ocr_pages=args.max_ocr_pages,
            max_pages_ocr=args.max_pages_ocr,
            multicolumn=not args.no_multicol,
            remove_headers_footers=not args.keep_hf,
            header_max_lines=args.header_max_lines,
            footer_max_lines=args.footer_max_lines,
            min_repetition_ratio=args.hf_ratio,
            mode=args.mode,
            simpletex_token=simpletex_token,
            simpletex_api_url=args.simpletex_api_url,
            simpletex_qps=args.simpletex_qps,
            simpletex_dpi=args.simpletex_dpi,
            simpletex_inline_formula_wrapper=args.simpletex_inline_wrapper,
            simpletex_isolated_formula_wrapper=args.simpletex_isolated_wrapper,
            simpletex_timeout_sec=args.simpletex_timeout_sec,
            simpletex_max_retries=args.simpletex_max_retries,
            export_math_crops=args.export_math_crops,
            math_crop_dpi=args.math_crop_dpi,
            quiet=args.quiet,
            verbose=args.verbose,
        )
        try:
            scribe.process_pdf(pdf, opts)
        except Exception as exc:
            logger.error("Failed to process %s: %s", pdf, exc)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
