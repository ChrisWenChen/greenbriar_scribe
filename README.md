# Greenbriar Scribe

Greenbriar Scribe converts PDFs into cleaned text and structured JSONL segments.
It extracts text via PyMuPDF and optionally uses PaddleOCR for scanned pages.

## Features

- Per-page detection of scanned pages with OCR fallback.
- Span-level extraction with math heuristics (superscript/subscript reconstruction).
- Header/footer removal, page-number stripping, dehyphenation, whitespace normalization.
- Multi-column reading order recovery using bbox clustering.
- Structured segments with `page`, `bbox`, `role`, `text`, `source_mode` (includes `math` and `math_complex`).
- CLI and Python API support.
- Optional SimpleTex Markdown backend.

## Install

Editable install:

```bash
pip install -e .
```

OCR extras (PaddleOCR + PaddlePaddle):

```bash
pip install -e .[ocr]
```

SimpleTex extras:

```bash
pip install -e .[simpletex]
```

## CLI

### Basic Usage

Extract text from a single PDF:

```bash
greenbriar-scribe input.pdf -o out/
```

Process a directory of PDFs recursively:

```bash
greenbriar-scribe ./corpus/ -o out/ --recursive
```

### Advanced Cleaning Options

Control how headers and footers are detected and removed:

```bash
greenbriar-scribe input.pdf -o out/ \
  --hf-ratio 0.6 \
  --header-max-lines 5 \
  --footer-max-lines 5 \
  --keep-hf  # Disable removal if needed
```

Disable specific cleaning rules:

```bash
# Keep hyphenated words as-is and don't normalize whitespace
greenbriar-scribe input.pdf -o out/ --no-dehyphen --no-normalize
```

### OCR and Performance

Configure OCR for scanned documents:

```bash
greenbriar-scribe input.pdf -o out/ \
  --ocr-lang en \
  --ocr-dpi 300 \
  --ocr-workers 4 \
  --max-ocr-pages 50  # Only OCR the first 50 scanned pages
```

Disable OCR entirely:

```bash
greenbriar-scribe input.pdf -o out/ --no-ocr
```

### Layout and Math

Control reading order and math extraction:

```bash
# Disable multi-column detection (treat as single block)
greenbriar-scribe input.pdf -o out/ --no-multicol

# Export math segments as cropped images for verification
greenbriar-scribe input.pdf -o out/ --export-math-crops
```

### SimpleTex Markdown Mode

Route pages through SimpleTex API for high-quality Markdown and LaTeX formulas:

```bash
export SIMPLETEX_TOKEN="your_token"
greenbriar-scribe input.pdf -o out/ --mode simpletex_markdown
```

## Python API

### Basic Integration

```python
from greenbriar_scribe import Scribe, ScribeOptions

scribe = Scribe()
opts = ScribeOptions(out_dir="out")
result = scribe.process_pdf("input.pdf", opts)

print(f"Text saved to: {result.cleaned_txt_path}")
```

### Fine-grained Configuration

```python
from greenbriar_scribe import Scribe, ScribeOptions

opts = ScribeOptions(
    out_dir="processed",
    doc_id="my_custom_id",
    # Cleaning
    remove_headers_footers=True,
    min_repetition_ratio=0.5,
    remove_page_numbers=True,
    dehyphenate=True,
    # OCR
    enable_ocr=True,
    ocr_lang="ch",
    ocr_dpi=250,
    max_pages_ocr=100,
    # Layout
    multicolumn=True,
    merge_paragraphs=True,
    # Logging
    verbose=True
)

scribe = Scribe()
result = scribe.process_pdf("input.pdf", opts)

# Accessing segments programmatically
import json
with open(result.segments_jsonl_path, 'r') as f:
    for line in f:
        segment = json.loads(line)
        if segment["role"] == "math":
            print(f"Found formula on page {segment['page']}: {segment['text']}")
```

### Processing In-Memory (Page Data)

The `meta` object contains detailed statistics and per-page processing modes:

```python
print(f"Processing modes: {result.meta['page_modes']}") # e.g., ['extract:text', 'ocr:paddle']
print(f"Warnings: {result.meta['warnings']}")
```

## Outputs

For input `foo.pdf`, the default outputs are:

- `foo.cleaned.txt` (cleaned full text, page-separated)
- `foo.cleaned.md` (SimpleTex Markdown mode only)
- `foo.segments.jsonl` (structured segments)
- `foo.pages.jsonl` (page-level text)
- `foo.meta.json` (summary, warnings, page modes)

`segments.jsonl` example:

```json
{
  "doc_id": "foo",
  "page": 3,
  "segment_id": "foo-p003-s012",
  "role": "paragraph",
  "bbox": [72.0, 120.0, 520.0, 210.0],
  "text": "Example text",
  "source_mode": "extract:text",
  "confidence": null
}
```

`meta.json` example:

```json
{
  "doc_id": "foo",
  "input_pdf": "/abs/path/foo.pdf",
  "pages": 12,
  "page_modes": ["extract:text", "ocr:paddle"],
  "ocr_enabled": true,
  "ocr_backend": "paddleocr",
  "mode": "local",
  "options": {},
  "warnings": [],
  "errors": []
}
```

## Notes

- Default `enable_ocr=True`; missing OCR dependencies will trigger a warning and disable OCR.
- Only PaddleOCR is supported.
- OCR supports page-level multiprocessing via `ocr_workers`.
- For formulas, Scribe reconstructs basic superscripts/subscripts using span bbox offsets and labels segments as `math` or `math_complex`.
- You can enable math crop export with `export_math_crops=True` (CLI: `--export-math-crops`).
- SimpleTex Markdown mode requires the `simpletex` extras (`requests`) and a valid API token.
