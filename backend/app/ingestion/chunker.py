"""
Section-aware chunker.
Groups text spans into chunks that:
  - Never straddle two detected sections (when avoidable)
  - Stay under MAX_CHUNK_TOKENS with CHUNK_OVERLAP_TOKENS at boundaries
  - Track page_number and bbox for each chunk
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tiktoken

from backend.app.config import CHUNK_OVERLAP_TOKENS, MAX_CHUNK_TOKENS
from backend.app.ingestion.pdf_parser import ParsedPage, TextSpan, detect_body_font_size, is_section_header
from backend.app.models.schema import Chunk

# Use cl100k_base tokenizer (GPT-4 / Gemini approximate token counts)
_tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text))


@dataclass
class SpanGroup:
    """A group of spans forming a logical chunk candidate."""
    spans: list[TextSpan]
    section_title: Optional[str]

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.spans)

    @property
    def page_number(self) -> int:
        return self.spans[0].page_number if self.spans else 0

    @property
    def bbox(self) -> Optional[tuple[float, float, float, float]]:
        if not self.spans:
            return None
        x0 = min(s.bbox[0] for s in self.spans)
        y0 = min(s.bbox[1] for s in self.spans)
        x1 = max(s.bbox[2] for s in self.spans)
        y1 = max(s.bbox[3] for s in self.spans)
        return (x0, y0, x1, y1)


def chunk_document(
    pages: list[ParsedPage],
    document_id: str,
    table_page_numbers: Optional[set[int]] = None,
) -> list[Chunk]:
    """
    Main chunking entrypoint.
    Returns a list of Chunk objects ready for DB insertion.
    Table pages are skipped here — table_extractor handles them separately.
    """
    if table_page_numbers is None:
        table_page_numbers = set()

    body_font_size = detect_body_font_size(pages)
    chunks: list[Chunk] = []

    # Collect all spans with section annotations, skipping table pages
    current_section: Optional[str] = None
    current_group_spans: list[TextSpan] = []
    current_section_of_group: Optional[str] = None
    current_token_count: int = 0
    overlap_buffer: list[TextSpan] = []

    def flush_group(spans: list[TextSpan], section: Optional[str]) -> None:
        """Flush current span group into one or more chunks."""
        if not spans:
            return

        text = " ".join(s.text for s in spans)
        if not text.strip():
            return

        # Determine page_number and bbox for the chunk (use first span's page)
        page_num = spans[0].page_number
        x0 = min(s.bbox[0] for s in spans)
        y0 = min(s.bbox[1] for s in spans)
        x1 = max(s.bbox[2] for s in spans)
        y1 = max(s.bbox[3] for s in spans)

        chunk = Chunk(
            id=str(uuid.uuid4()),
            document_id=document_id,
            page_number=page_num,
            bbox=(x0, y0, x1, y1),
            text=text,
            section_title=section,
        )
        chunks.append(chunk)

    for page in pages:
        if page.page_number in table_page_numbers:
            # Table pages handled by table_extractor — flush current group first
            if current_group_spans:
                flush_group(current_group_spans, current_section_of_group)
                current_group_spans = []
                current_token_count = 0
            continue

        for span in page.spans:
            if is_section_header(span, body_font_size):
                # New section — flush current group
                if current_group_spans:
                    flush_group(current_group_spans, current_section_of_group)
                    # Keep last few spans as overlap for next chunk
                    overlap_buffer = current_group_spans[-3:]
                    current_group_spans = list(overlap_buffer)
                    current_token_count = count_tokens(" ".join(s.text for s in current_group_spans))
                current_section = span.text.strip()
                current_section_of_group = current_section
                # Don't add header span to body content
                continue

            span_tokens = count_tokens(span.text)

            # If adding this span would exceed max tokens, flush first
            if current_token_count + span_tokens > MAX_CHUNK_TOKENS and current_group_spans:
                flush_group(current_group_spans, current_section_of_group)
                # Overlap: carry last N tokens worth of spans
                overlap_spans = _take_last_n_tokens(current_group_spans, CHUNK_OVERLAP_TOKENS)
                current_group_spans = list(overlap_spans)
                current_token_count = count_tokens(" ".join(s.text for s in current_group_spans))
                current_section_of_group = current_section

            current_group_spans.append(span)
            current_token_count += span_tokens

    # Flush remaining
    if current_group_spans:
        flush_group(current_group_spans, current_section_of_group)

    return chunks


def _take_last_n_tokens(spans: list[TextSpan], n_tokens: int) -> list[TextSpan]:
    """Take spans from the end that together total approximately n_tokens."""
    result = []
    total = 0
    for span in reversed(spans):
        t = count_tokens(span.text)
        if total + t > n_tokens:
            break
        result.insert(0, span)
        total += t
    return result
