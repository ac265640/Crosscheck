"""
PDF parser using PyMuPDF.
Extracts text spans with font size, position, and bounding boxes.
Used for section-header detection and chunk-level bbox tracking.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


@dataclass
class TextSpan:
    text: str
    font_size: float
    font_flags: int  # bold/italic flags
    bbox: tuple[float, float, float, float]
    page_number: int
    block_no: int
    line_no: int


@dataclass
class ParsedPage:
    page_number: int
    spans: list[TextSpan]
    width: float
    height: float
    has_table_hint: bool = False  # set later by table_extractor


def parse_pdf(pdf_path: Path) -> tuple[list[ParsedPage], int]:
    """
    Parse all pages of a PDF with PyMuPDF.
    Returns (list of ParsedPage, total page count).
    """
    doc = fitz.open(str(pdf_path))
    pages: list[ParsedPage] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_number = page_idx + 1

        spans: list[TextSpan] = []
        blocks = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        for block in blocks:
            if block.get("type") != 0:  # type 0 = text block
                continue
            block_no = block.get("number", 0)
            for line_idx, line in enumerate(block.get("lines", [])):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    bbox = tuple(span["bbox"])
                    spans.append(
                        TextSpan(
                            text=text,
                            font_size=round(span.get("size", 12.0), 2),
                            font_flags=span.get("flags", 0),
                            bbox=bbox,
                            page_number=page_number,
                            block_no=block_no,
                            line_no=line_idx,
                        )
                    )

        pages.append(
            ParsedPage(
                page_number=page_number,
                spans=spans,
                width=page.rect.width,
                height=page.rect.height,
            )
        )

    total_pages = len(doc)
    doc.close()
    return pages, total_pages


def render_page_as_image(pdf_path: Path, page_number: int, dpi: int = 150) -> bytes:
    """Render a page to PNG bytes. page_number is 1-indexed."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_number - 1]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes


def render_page_with_highlight(
    pdf_path: Path,
    page_number: int,
    bbox: tuple[float, float, float, float],
    dpi: int = 150,
) -> bytes:
    """Render page with a highlighted bounding box. Returns PNG bytes."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_number - 1]

    # Draw highlight rectangle
    rect = fitz.Rect(*bbox)
    highlight = page.add_highlight_annot(rect)
    highlight.set_colors(stroke=(1, 0.8, 0))  # yellow
    highlight.update()

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes


def detect_body_font_size(pages: list[ParsedPage]) -> float:
    """
    Estimate the dominant body text font size across all pages.
    Uses the mode of font sizes (weighted by character count).
    """
    from collections import Counter

    size_counts: Counter = Counter()
    for page in pages:
        for span in page.spans:
            # Round to nearest 0.5 to group similar sizes
            size_key = round(span.font_size * 2) / 2
            size_counts[size_key] += len(span.text)

    if not size_counts:
        return 10.0
    return size_counts.most_common(1)[0][0]


def is_section_header(span: TextSpan, body_font_size: float, threshold_ratio: float = 1.15) -> bool:
    """
    Heuristic: a span is a section header if its font size is meaningfully
    larger than the body font size, or it uses bold flags.
    Bold flag is bit 4 (value 16) in PDF font flags.
    """
    size_ratio = span.font_size / body_font_size if body_font_size > 0 else 1.0
    is_bold = bool(span.font_flags & 16)
    is_larger = size_ratio >= threshold_ratio
    # Short spans (< 5 words) that are bold or larger are likely headers
    word_count = len(span.text.split())
    return (is_larger or is_bold) and word_count <= 15 and word_count >= 1
