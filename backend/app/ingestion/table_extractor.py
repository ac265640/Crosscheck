"""
Table extractor using pdfplumber.
Detects pages with tables and represents them as markdown-style text.
Returns Chunk objects tagged with their section title.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import pdfplumber

from backend.app.models.schema import Chunk


def extract_tables_from_pdf(
    pdf_path: Path,
    document_id: str,
    section_map: Optional[dict[int, str]] = None,
) -> tuple[list[Chunk], dict[int, list[tuple[float, float, float, float]]]]:
    """
    Detect tables in a PDF using pdfplumber.
    Returns:
      - list of Chunk objects (one per table, markdown-formatted, with exact bbox)
      - dict mapping page_number -> list of table bounding boxes
    
    section_map: {page_number -> section_title} from the chunker's section detection.
    """
    if section_map is None:
        section_map = {}

    table_chunks: list[Chunk] = []
    table_bboxes_by_page: dict[int, list[tuple[float, float, float, float]]] = {}

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_number = page_idx + 1
            found_tables = page.find_tables()

            if not found_tables:
                continue

            for t in found_tables:
                table_data = t.extract()
                if not table_data or len(table_data) < 2 or max(len(r) for r in table_data) < 2:
                    continue

                markdown_table = _table_to_markdown(table_data)
                if not markdown_table.strip():
                    continue

                bbox = tuple(float(x) for x in t.bbox)
                table_bboxes_by_page.setdefault(page_number, []).append(bbox)
                section_title = section_map.get(page_number)

                chunk = Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    page_number=page_number,
                    bbox=bbox,
                    text=markdown_table,
                    section_title=section_title or "Table",
                )
                table_chunks.append(chunk)

    return table_chunks, table_bboxes_by_page


def _table_to_markdown(table: list[list[Optional[str]]]) -> str:
    """
    Convert a pdfplumber table (list of lists) to markdown table format.
    First row is treated as headers if it looks header-like.
    """
    if not table:
        return ""

    # Clean cells
    cleaned = []
    for row in table:
        cleaned_row = [_clean_cell(cell) for cell in row]
        cleaned.append(cleaned_row)

    # Normalize column count
    max_cols = max(len(row) for row in cleaned)
    normalized = [row + [""] * (max_cols - len(row)) for row in cleaned]

    if not normalized:
        return ""

    lines = []
    # Header row
    header = normalized[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    # Data rows
    for row in normalized[1:]:
        if any(cell.strip() for cell in row):
            lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _clean_cell(cell: Optional[str]) -> str:
    """Normalize a table cell value."""
    if cell is None:
        return ""
    return str(cell).replace("\n", " ").replace("|", "\\|").strip()


def build_section_map_from_pages(pages: list) -> dict[int, str]:
    """
    Build a page_number -> section_title mapping from parsed pages.
    Used to tag table chunks with the nearest section heading.
    """
    from backend.app.ingestion.pdf_parser import detect_body_font_size, is_section_header

    body_font_size = detect_body_font_size(pages)
    section_map: dict[int, str] = {}
    current_section = "Unknown"

    for page in pages:
        for span in page.spans:
            if is_section_header(span, body_font_size):
                current_section = span.text.strip()
        section_map[page.page_number] = current_section

    return section_map
