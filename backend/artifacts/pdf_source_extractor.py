from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pymupdf


_WHITESPACE = re.compile(r"\s+")
_NUMBERED_HEADING = re.compile(
    r"^(?P<number>\d{1,3}(?:\.\d{1,3}){0,4})[.)]?\s+(?P<title>\S[\s\S]{1,180})$"
)
_BULLET = re.compile(r"^[•●▪◦‣]\s*(.+)$")
_TOC_TITLE = re.compile(r"^(?:table\s+of\s+contents|contents)$", re.IGNORECASE)
_TOC_ENTRY = re.compile(r"^.{2,180}?\s+\d{1,4}$")
_BAD_METADATA_TITLE = re.compile(
    r"^(?:untitled|document|pdf|user|assistant|serenya|authentic\s+ai)$",
    re.IGNORECASE,
)


# Typography and repeated-margin discovery are sampled so extraction memory
# remains bounded independently of the document's page count. Every page is
# still processed during the sequential extraction pass.
MAX_TYPOGRAPHY_SAMPLE_PAGES = 32


@dataclass(frozen=True, slots=True)
class PdfLine:
    text: str
    bbox: tuple[float, float, float, float]
    size: float
    bold: bool
    block_index: int


@dataclass(frozen=True, slots=True)
class PdfTable:
    bbox: tuple[float, float, float, float]
    rows: tuple[tuple[str, ...], ...]


def _clean_text(value: object) -> str:
    return _WHITESPACE.sub(" ", str(value or "").replace("\x00", " ")).strip()


def _rect_contains_midpoint(
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
) -> bool:
    x = (inner[0] + inner[2]) / 2
    y = (inner[1] + inner[3]) / 2
    return outer[0] - 1 <= x <= outer[2] + 1 and outer[1] - 1 <= y <= outer[3] + 1


def _table_rows(table: Any) -> tuple[tuple[str, ...], ...]:
    try:
        extracted = table.extract()
    except Exception:
        return ()
    if not isinstance(extracted, list):
        return ()

    rows: list[tuple[str, ...]] = []
    width = 0
    for raw_row in extracted:
        if not isinstance(raw_row, (list, tuple)):
            continue
        row = tuple(
            _clean_text(cell).replace("|", "/")
            for cell in raw_row
        )
        if not any(row):
            continue
        width = max(width, len(row))
        rows.append(row)
    if width < 2 or len(rows) < 2:
        return ()
    return tuple(
        row + ("",) * (width - len(row))
        for row in rows
    )


def _page_tables(page: pymupdf.Page) -> tuple[PdfTable, ...]:
    try:
        finder = page.find_tables()
    except Exception:
        return ()

    output: list[PdfTable] = []
    for table in getattr(finder, "tables", ()):
        rows = _table_rows(table)
        bbox = tuple(float(value) for value in table.bbox)
        if rows and len(bbox) == 4:
            output.append(PdfTable(bbox=bbox, rows=rows))
    return tuple(output)


def _page_lines(
    page: pymupdf.Page,
    tables: tuple[PdfTable, ...],
) -> tuple[PdfLine, ...]:
    payload = page.get_text("dict", sort=True)
    blocks = payload.get("blocks", ()) if isinstance(payload, dict) else ()
    output: list[PdfLine] = []
    for block_index, block in enumerate(blocks):
        if not isinstance(block, dict) or block.get("type") != 0:
            continue
        for line in block.get("lines", ()):
            spans = [
                span
                for span in line.get("spans", ())
                if isinstance(span, dict) and _clean_text(span.get("text"))
            ]
            if not spans:
                continue
            bbox_value = line.get("bbox") or block.get("bbox")
            if not isinstance(bbox_value, (list, tuple)) or len(bbox_value) != 4:
                continue
            bbox = tuple(float(value) for value in bbox_value)
            if any(_rect_contains_midpoint(table.bbox, bbox) for table in tables):
                continue
            text = _clean_text(" ".join(str(span.get("text") or "") for span in spans))
            if not text:
                continue
            weighted_size = sum(
                float(span.get("size") or 0) * max(len(_clean_text(span.get("text"))), 1)
                for span in spans
            ) / sum(max(len(_clean_text(span.get("text"))), 1) for span in spans)
            bold_characters = sum(
                len(_clean_text(span.get("text")))
                for span in spans
                if "bold" in str(span.get("font") or "").casefold()
                or int(span.get("flags") or 0) & 16
            )
            output.append(
                PdfLine(
                    text=text,
                    bbox=bbox,
                    size=weighted_size,
                    bold=bold_characters >= max(len(text) * 0.45, 1),
                    block_index=block_index,
                )
            )
    return tuple(output)


def _sample_page_indexes(
    page_count: int,
    *,
    maximum: int = MAX_TYPOGRAPHY_SAMPLE_PAGES,
) -> tuple[int, ...]:
    """Return evenly distributed page indexes with constant upper bound."""

    if page_count <= 0 or maximum <= 0:
        return ()

    # Skip the cover when another page exists because display typography on a
    # cover is not representative of the document body.
    first = 1 if page_count > 1 else 0
    available = page_count - first
    if available <= maximum:
        return tuple(range(first, page_count))
    if maximum == 1:
        return (first,)

    span = available - 1
    indexes = {
        first + round(span * offset / (maximum - 1))
        for offset in range(maximum)
    }
    return tuple(sorted(indexes))


def _body_font_size_from_lines(
    sampled_pages: tuple[tuple[tuple[PdfLine, ...], float], ...],
) -> float:
    weights: Counter[float] = Counter()
    for lines, height in sampled_pages:
        top_limit = max(34.0, height * 0.045)
        bottom_limit = min(height - 34.0, height * 0.955)
        for line in lines:
            if line.bbox[1] < top_limit or line.bbox[3] > bottom_limit:
                continue
            if 5.5 <= line.size <= 18:
                weights[round(line.size, 1)] += max(len(line.text), 1)
    return weights.most_common(1)[0][0] if weights else 10.0


def _margin_signature(value: str) -> str:
    normalized = re.sub(r"\d+", "#", _clean_text(value).casefold())
    return re.sub(r"[^a-z0-9#]+", " ", normalized).strip()


def _sample_document_style(
    document: pymupdf.Document,
) -> tuple[float, frozenset[str]]:
    """Infer body typography and repeated margins using bounded samples."""

    sampled_pages: list[tuple[tuple[PdfLine, ...], float]] = []
    for page_index in _sample_page_indexes(int(document.page_count)):
        page = document.load_page(page_index)
        tables = _page_tables(page)
        sampled_pages.append(
            (_page_lines(page, tables), float(page.rect.height))
        )

    sampled_tuple = tuple(sampled_pages)
    body_size = _body_font_size_from_lines(sampled_tuple)
    if len(sampled_tuple) < 2:
        return body_size, frozenset()

    occurrences: Counter[str] = Counter()
    for lines, height in sampled_tuple:
        top_limit = max(34.0, height * 0.045)
        bottom_limit = min(height - 34.0, height * 0.955)
        page_signatures = {
            _margin_signature(line.text)
            for line in lines
            if line.size <= body_size + 1.2
            and (
                line.bbox[3] <= top_limit
                or line.bbox[1] >= bottom_limit
            )
            and _margin_signature(line.text)
        }
        occurrences.update(page_signatures)

    # A running margin must recur across multiple sampled pages. This removes
    # true headers/footers while preserving unique footnotes and edge content.
    threshold = max(2, (len(sampled_tuple) + 2) // 3)
    return body_size, frozenset(
        signature
        for signature, count in occurrences.items()
        if count >= threshold
    )


def _safe_title(value: str | None) -> str | None:
    candidate = _clean_text(value or "").strip(" .,:;-_")
    if not candidate or _BAD_METADATA_TITLE.fullmatch(candidate):
        return None
    if len(candidate) < 4 or len(candidate) > 180:
        return None
    return candidate


def _infer_title(
    metadata_title: str | None,
    first_page: tuple[PdfLine, ...],
    fallback_title: str | None,
) -> str:
    safe_metadata = _safe_title(metadata_title)
    if safe_metadata:
        return safe_metadata

    candidates = [
        line
        for line in first_page
        if 3 <= len(line.text) <= 120
        and not _BAD_METADATA_TITLE.fullmatch(line.text)
    ]
    if candidates:
        maximum = max(line.size for line in candidates)
        prominent = [
            line.text
            for line in sorted(candidates, key=lambda item: (item.bbox[1], item.bbox[0]))
            if line.size >= maximum * 0.72
        ][:3]
        joined = _safe_title(" ".join(prominent))
        if joined:
            return joined

    fallback = _safe_title(fallback_title)
    if fallback:
        return fallback
    return "Professional Document"


def _looks_like_title_fragment(text: str, title: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    normalized_title = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
    return bool(
        normalized
        and len(normalized) >= 4
        and normalized in normalized_title
    )


def _heading_level(line: PdfLine, body_size: float) -> int | None:
    text = line.text.strip(" .")
    if not text or len(text) > 190 or text.endswith(("?", "!", ";")):
        return None
    words = text.split()
    if len(words) > 20:
        return None

    numbered = _NUMBERED_HEADING.match(text)
    if numbered is not None:
        # Numbered references, citations and table rows are common in long
        # reports. A number alone is not hierarchy: it must also carry the
        # visual prominence of a heading in the source PDF.
        if line.size >= body_size + 0.7 or (
            line.bold and line.size >= body_size - 0.25
        ):
            depth = numbered.group("number").count(".")
            return min(2 + depth, 4)
        return None

    if line.size >= body_size + 7:
        return 2
    if line.size >= body_size + 4:
        return 2
    if line.size >= body_size + 1.7:
        return 3
    if line.bold and line.size >= body_size * 1.06:
        return 4
    if (
        line.bold
        and len(words) <= 10
        and not text.endswith((".", ",", ":"))
    ):
        return 4
    return None


def _is_running_margin_line(
    line: PdfLine,
    *,
    page_height: float,
    body_size: float,
    running_margin_signatures: frozenset[str] = frozenset(),
) -> bool:
    top_limit = max(34.0, page_height * 0.045)
    bottom_limit = min(page_height - 34.0, page_height * 0.955)
    within_margin = bool(
        line.size <= body_size + 1.2
        and (
            line.bbox[3] <= top_limit
            or line.bbox[1] >= bottom_limit
        )
    )
    if not within_margin:
        return False
    if not running_margin_signatures:
        return False
    return _margin_signature(line.text) in running_margin_signatures


def _looks_like_toc_page(
    lines: tuple[PdfLine, ...],
    *,
    body_size: float,
    continuing: bool,
) -> bool:
    visible = [line.text for line in lines if line.text]
    if any(_TOC_TITLE.fullmatch(text.strip(" .")) for text in visible[:20]):
        return True
    if not continuing:
        return False
    entry_count = sum(bool(_TOC_ENTRY.match(text)) for text in visible)
    if entry_count >= 3:
        return True
    prominent_non_toc = any(
        _heading_level(line, body_size) in {2, 3}
        and not _TOC_TITLE.fullmatch(line.text.strip(" ."))
        for line in lines[:20]
    )
    if prominent_non_toc:
        return False
    return entry_count >= 3


def _markdown_table(rows: tuple[tuple[str, ...], ...]) -> list[str]:
    width = max(len(row) for row in rows)
    padded = [row + ("",) * (width - len(row)) for row in rows]
    header = list(padded[0])
    seen: Counter[str] = Counter()
    for index, value in enumerate(header):
        base = value or f"Column {index + 1}"
        seen[base] += 1
        header[index] = base if seen[base] == 1 else f"{base} {seen[base]}"
    output = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    output.extend(
        "| " + " | ".join(row) + " |"
        for row in padded[1:]
    )
    return output


def _render_page_markdown(
    *,
    page_index: int,
    lines: tuple[PdfLine, ...],
    tables: tuple[PdfTable, ...],
    page_height: float,
    body_size: float,
    title: str,
    running_margin_signatures: frozenset[str],
) -> list[str]:
    filtered_lines = [
        line
        for line in lines
        if not _is_running_margin_line(
            line,
            page_height=page_height,
            body_size=body_size,
            running_margin_signatures=running_margin_signatures,
        )
    ]
    elements: list[tuple[float, int, object]] = [
        (line.bbox[1], 1, line)
        for line in filtered_lines
    ]
    elements.extend((table.bbox[1], 0, table) for table in tables)
    elements.sort(key=lambda item: (item[0], item[1]))

    output: list[str] = [f"<!--AUTHENTIC_SOURCE_PAGE:{page_index + 1:04d}-->"]
    paragraph: list[str] = []
    paragraph_block: int | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph_block
        if paragraph:
            output.extend([" ".join(paragraph).strip(), ""])
            paragraph.clear()
        paragraph_block = None

    for _, _, value in elements:
        if isinstance(value, PdfTable):
            flush_paragraph()
            output.extend(_markdown_table(value.rows))
            output.append("")
            continue

        line = value
        assert isinstance(line, PdfLine)
        text = line.text
        if (
            page_index == 0
            and _looks_like_title_fragment(text, title)
        ):
            continue

        level = _heading_level(line, body_size)
        if page_index == 0 and level is not None and line.size < body_size + 7:
            level = None
        if level is not None:
            flush_paragraph()
            output.extend([f"{'#' * level} {text}", ""])
            continue

        bullet = _BULLET.match(text)
        if bullet is not None:
            flush_paragraph()
            output.append(f"- {bullet.group(1).strip()}")
            continue

        if paragraph_block is not None and paragraph_block != line.block_index:
            flush_paragraph()
        paragraph.append(text)
        paragraph_block = line.block_index

    flush_paragraph()
    while output and not output[-1]:
        output.pop()
    return output


def extract_structured_pdf_source(
    pdf_bytes: bytes,
    *,
    fallback_title: str | None = None,
) -> tuple[str, str, int]:
    """Extract a PDF into structure-preserving Markdown.

    Font hierarchy becomes Markdown headings, detected tables remain tables,
    generated source headers/footers are discarded, and a source TOC is
    omitted because the final renderer creates a canonical TOC.
    """

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise ValueError("The uploaded file is not a readable PDF.") from error

    try:
        if document.needs_pass or document.is_encrypted:
            raise ValueError(
                "Password-protected PDFs cannot be used as artifact sources."
            )
        page_count = int(document.page_count)
        if page_count < 1:
            raise ValueError("The uploaded PDF does not contain any pages.")

        body_size, running_margin_signatures = _sample_document_style(document)
        first_page = document.load_page(0)
        first_tables = _page_tables(first_page)
        first_lines = _page_lines(first_page, first_tables)
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        title = _infer_title(
            str(metadata.get("title") or ""),
            first_lines,
            fallback_title,
        )

        output = StringIO()
        output.write(f"# {title}\n\n")
        toc_active = False
        for page_index in range(page_count):
            if page_index == 0:
                page = first_page
                tables = first_tables
                lines = first_lines
            else:
                page = document.load_page(page_index)
                tables = _page_tables(page)
                lines = _page_lines(page, tables)
            page_height = float(page.rect.height)
            visible_lines = tuple(
                line
                for line in lines
                if not _is_running_margin_line(
                    line,
                    page_height=page_height,
                    body_size=body_size,
                    running_margin_signatures=running_margin_signatures,
                )
            )
            is_toc = _looks_like_toc_page(
                visible_lines,
                body_size=body_size,
                continuing=toc_active,
            )
            if is_toc:
                toc_active = True
                continue
            toc_active = False
            rendered_page = _render_page_markdown(
                page_index=page_index,
                lines=lines,
                tables=tables,
                page_height=page_height,
                body_size=body_size,
                title=title,
                running_margin_signatures=running_margin_signatures,
            )
            output.write("\n".join(rendered_page))
            output.write("\n\n")

        content = output.getvalue()
        content = re.sub(r"\n{4,}", "\n\n\n", content).strip() + "\n"
        return content, title, page_count
    finally:
        document.close()


def filename_fallback_title(filename: str) -> str:
    stem = Path(filename).stem
    return _clean_text(re.sub(r"[_-]+", " ", stem)) or "Professional Document"
