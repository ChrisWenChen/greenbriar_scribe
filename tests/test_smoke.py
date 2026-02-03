import json
import os
import re

import fitz

from greenbriar_scribe import Scribe, ScribeOptions


def _create_text_pdf(path, pages):
    doc = fitz.open()
    for header, body, footer in pages:
        page = doc.new_page()
        page.insert_text((72, 40), header)
        page.insert_text((72, 100), body)
        page.insert_text((72, 760), footer)
    doc.save(path)
    doc.close()


def _create_blank_pdf(path, page_count=1):
    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page()
    doc.save(path)
    doc.close()


def _read_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    return records


def test_smoke_text_pdf(tmp_path):
    pdf_path = tmp_path / "text.pdf"
    _create_text_pdf(
        str(pdf_path),
        [
            ("Header", "Body page one.", "Footer"),
            ("Header", "Body page two.", "Footer"),
        ],
    )
    out_dir = tmp_path / "out"
    scribe = Scribe()
    opts = ScribeOptions(out_dir=str(out_dir), enable_ocr=False)
    result = scribe.process_pdf(str(pdf_path), opts)

    assert os.path.exists(result.cleaned_txt_path)
    assert os.path.exists(result.segments_jsonl_path)
    assert os.path.exists(result.pages_jsonl_path)
    assert os.path.exists(result.meta_json_path)

    segments = _read_jsonl(result.segments_jsonl_path)
    assert segments


def test_smoke_scanned_pdf_no_ocr(tmp_path):
    pdf_path = tmp_path / "scan.pdf"
    _create_blank_pdf(str(pdf_path), page_count=1)
    out_dir = tmp_path / "out"
    scribe = Scribe()
    opts = ScribeOptions(out_dir=str(out_dir), enable_ocr=False)
    result = scribe.process_pdf(str(pdf_path), opts)

    assert os.path.exists(result.cleaned_txt_path)
    assert os.path.exists(result.segments_jsonl_path)
    assert os.path.exists(result.pages_jsonl_path)
    assert os.path.exists(result.meta_json_path)


def test_id_stability(tmp_path):
    pdf_path = tmp_path / "ids.pdf"
    _create_text_pdf(str(pdf_path), [("Header", "Body page one.", "Footer")])
    out_dir = tmp_path / "out"
    scribe = Scribe()
    opts = ScribeOptions(out_dir=str(out_dir), enable_ocr=False)
    result = scribe.process_pdf(str(pdf_path), opts)

    segments = _read_jsonl(result.segments_jsonl_path)
    assert segments
    pattern = re.compile(r"^ids-p\d{3}-s\d{3}$")
    assert all(pattern.match(seg["segment_id"]) for seg in segments)


def test_header_footer_removal(tmp_path):
    pdf_path = tmp_path / "hf.pdf"
    _create_text_pdf(
        str(pdf_path),
        [
            ("Header", "Body page one.", "Footer"),
            ("Header", "Body page two.", "Footer"),
            ("Header", "Body page three.", "Footer"),
        ],
    )
    out_dir = tmp_path / "out"
    scribe = Scribe()
    # Use smaller header/footer max lines to ensure detection works with few lines per page
    opts = ScribeOptions(
        out_dir=str(out_dir),
        enable_ocr=False,
        remove_headers_footers=True,
        header_max_lines=1,
        footer_max_lines=1,
    )
    result = scribe.process_pdf(str(pdf_path), opts)

    with open(result.cleaned_txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Header" not in content
    assert "Footer" not in content
    # Ensure body content is preserved
    assert "Body page one" in content
    assert "Body page two" in content
    assert "Body page three" in content


def test_custom_doc_id(tmp_path):
    pdf_path = tmp_path / "custom_id.pdf"
    _create_text_pdf(str(pdf_path), [("H", "Content", "F")])
    out_dir = tmp_path / "out"
    scribe = Scribe()
    custom_id = "my-custom-doc"
    opts = ScribeOptions(out_dir=str(out_dir), doc_id=custom_id, enable_ocr=False)
    result = scribe.process_pdf(str(pdf_path), opts)

    with open(result.meta_json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["doc_id"] == custom_id
    assert os.path.basename(result.cleaned_txt_path).startswith(custom_id)


def test_remove_page_numbers(tmp_path):
    pdf_path = tmp_path / "pagenums.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Real content text.")
    page.insert_text((300, 800), "42")
    page.insert_text((300, 810), "Page 1/20")
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "out"
    scribe = Scribe()
    opts = ScribeOptions(out_dir=str(out_dir), enable_ocr=False, remove_page_numbers=True)
    result = scribe.process_pdf(str(pdf_path), opts)

    with open(result.cleaned_txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Real content text" in content
    assert "42" not in content.splitlines()
    assert "Page 1/20" not in content


def test_dehyphenation(tmp_path):
    pdf_path = tmp_path / "hyphen.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "This is a demon-")
    page.insert_text((72, 112), "stration of text.")
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "out"
    scribe = Scribe()
    opts = ScribeOptions(out_dir=str(out_dir), enable_ocr=False, dehyphenate=True)
    result = scribe.process_pdf(str(pdf_path), opts)

    with open(result.cleaned_txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "demonstration" in content
    assert "demon-" not in content
