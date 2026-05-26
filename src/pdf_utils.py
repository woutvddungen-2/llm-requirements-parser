from __future__ import annotations

from pathlib import Path
import subprocess


def _import_fitz():
    try:
        import fitz  # type: ignore
    except ImportError:
        return None
    return fitz


def load_pdf_page_texts(pdf_path: str | Path) -> dict[int, str]:
    """Return a zero-based page index to extracted text mapping for a PDF."""
    fitz = _import_fitz()
    if fitz is not None:
        doc = fitz.open(str(Path(pdf_path)))
        try:
            return {page_index: doc[page_index].get_text() for page_index in range(len(doc))}
        finally:
            doc.close()

    return _load_pdf_page_texts_via_pdftotext(pdf_path)


def load_pdf_toc(pdf_path: str | Path) -> list[tuple[int, str, int]]:
    """Return the PDF table of contents as `(level, title, page_number)` tuples."""
    fitz = _import_fitz()
    if fitz is None:
        return []

    doc = fitz.open(str(Path(pdf_path)))
    try:
        return doc.get_toc()
    finally:
        doc.close()


def _load_pdf_page_texts_via_pdftotext(pdf_path: str | Path) -> dict[int, str]:
    """Fallback page text extraction using the pdftotext CLI."""
    try:
        result = subprocess.run(
            ["pdftotext", str(Path(pdf_path)), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "PDF-backed test cases require either PyMuPDF or the 'pdftotext' CLI."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"Failed to extract PDF text from {pdf_path}: {stderr or exc}"
        ) from exc

    pages = result.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return {page_index: text for page_index, text in enumerate(pages)}
