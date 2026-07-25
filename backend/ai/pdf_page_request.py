import re
from dataclasses import dataclass

import pymupdf

from core.document_settings import (
    document_settings,
)


maximum_explicit_pages = 16
minimum_page_text_characters = 20


class ExplicitPageRequestError(
    RuntimeError
):
    """Raised when an explicit PDF page request is invalid."""


@dataclass(frozen=True, slots=True)
class ExplicitPageRequest:
    pages: tuple[int, ...]
    sequential: bool


@dataclass(frozen=True, slots=True)
class PreparedExplicitPdf:
    pdf_bytes: bytes
    original_page_count: int

    page_map: tuple[int, ...]
    sequential: bool
    forced_ocr: bool


def _is_sequential_request(
    prompt: str,
) -> bool:
    lowered = prompt.lower()

    indicators = (
        "one by one",
        "page by page",
        "each page",
        "every page",
        "in order",
        "sequential",
        "sequentially",
        "ek ek",
        "ek-ek",
        "har page",
        "order mein",
        "order me",
    )

    return any(
        indicator in lowered
        for indicator in indicators
    )


def _unique_pages(
    pages: list[int],
) -> tuple[int, ...]:
    result: list[int] = []
    seen: set[int] = set()

    for page in pages:
        if page in seen:
            continue

        seen.add(page)
        result.append(page)

    return tuple(result)


def parse_explicit_page_request(
    prompt: str,
) -> ExplicitPageRequest | None:
    normalized = (
        prompt.lower()
        .replace("–", "-")
        .replace("—", "-")
    )

    sequential = (
        _is_sequential_request(
            normalized
        )
    )

    first_pages_match = re.search(
        r"\bfirst\s+(\d+)\s+pages?\b",
        normalized,
        flags=re.IGNORECASE,
    )

    if first_pages_match:
        final_page = int(
            first_pages_match.group(1)
        )

        return ExplicitPageRequest(
            pages=tuple(
                range(
                    1,
                    final_page + 1,
                )
            ),
            sequential=sequential,
        )

    range_match = re.search(
        (
            r"\bpages?\s*"
            r"(\d+)\s*"
            r"(?:-|to|through|until|se)\s*"
            r"(?:pages?\s*)?"
            r"(\d+)"
            r"(?:\s*tak)?\b"
        ),
        normalized,
        flags=re.IGNORECASE,
    )

    if range_match:
        start_page = int(
            range_match.group(1)
        )

        end_page = int(
            range_match.group(2)
        )

        if end_page < start_page:
            raise ExplicitPageRequestError(
                "The requested PDF page range is reversed."
            )

        return ExplicitPageRequest(
            pages=tuple(
                range(
                    start_page,
                    end_page + 1,
                )
            ),
            sequential=sequential,
        )

    until_match = re.search(
        r"\bpage\s+(\d+)\s+tak\b",
        normalized,
        flags=re.IGNORECASE,
    )

    if until_match:
        end_page = int(
            until_match.group(1)
        )

        return ExplicitPageRequest(
            pages=tuple(
                range(
                    1,
                    end_page + 1,
                )
            ),
            sequential=sequential,
        )

    list_match = re.search(
        (
            r"\bpages?\s+"
            r"("
            r"\d+"
            r"(?:\s*(?:,|and|aur)\s*\d+)+"
            r")\b"
        ),
        normalized,
        flags=re.IGNORECASE,
    )

    if list_match:
        page_numbers = [
            int(value)
            for value in re.findall(
                r"\d+",
                list_match.group(1),
            )
        ]

        return ExplicitPageRequest(
            pages=_unique_pages(
                page_numbers
            ),
            sequential=sequential,
        )

    single_match = re.search(
        r"\bpage\s+(\d+)\b",
        normalized,
        flags=re.IGNORECASE,
    )

    if single_match:
        return ExplicitPageRequest(
            pages=(
                int(
                    single_match.group(1)
                ),
            ),
            sequential=sequential,
        )

    return None


def _validate_requested_pages(
    request: ExplicitPageRequest,
    page_count: int,
) -> None:
    if not request.pages:
        raise ExplicitPageRequestError(
            "No PDF pages were requested."
        )

    if (
        len(request.pages)
        > maximum_explicit_pages
    ):
        raise ExplicitPageRequestError(
            "A maximum of "
            f"{maximum_explicit_pages} explicit PDF pages "
            "can be analyzed in one request. "
            "Use a smaller page range."
        )

    invalid_pages = [
        page
        for page in request.pages
        if page < 1
        or page > page_count
    ]

    if invalid_pages:
        invalid_text = ", ".join(
            str(page)
            for page in invalid_pages
        )

        raise ExplicitPageRequestError(
            "Requested page number is outside the PDF: "
            f"{invalid_text}. "
            f"This PDF contains {page_count} pages."
        )


def _page_has_readable_text(
    page: pymupdf.Page,
) -> bool:
    try:
        text = page.get_text(
            "text",
            sort=True,
        )

    except Exception:
        return False

    compact_text = re.sub(
        r"\s+",
        "",
        text,
    )

    return (
        len(compact_text)
        >= minimum_page_text_characters
    )


def prepare_explicit_pdf_subset(
    *,
    pdf_bytes: bytes,
    request: ExplicitPageRequest,
) -> PreparedExplicitPdf:
    try:
        source = pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf",
        )

    except Exception as error:
        raise ExplicitPageRequestError(
            "The PDF could not be opened for page-range analysis."
        ) from error

    try:
        if (
            source.needs_pass
            or source.is_encrypted
        ):
            raise ExplicitPageRequestError(
                "Password-protected PDFs are not supported."
            )

        page_count = len(source)

        if page_count <= 0:
            raise ExplicitPageRequestError(
                "The PDF does not contain any pages."
            )

        if (
            page_count
            > document_settings
            .maximum_pdf_pages
        ):
            raise ExplicitPageRequestError(
                "The PDF exceeds the "
                f"{document_settings.maximum_pdf_pages:,}-page "
                "safety limit."
            )

        _validate_requested_pages(
            request,
            page_count,
        )

        requested_source_pages = [
            source.load_page(
                page_number - 1
            )
            for page_number
            in request.pages
        ]

        forced_ocr = any(
            not _page_has_readable_text(
                page
            )
            for page
            in requested_source_pages
        )

        subset = pymupdf.open()

        try:
            if forced_ocr:
                render_matrix = (
                    pymupdf.Matrix(
                        1.7,
                        1.7,
                    )
                )

                for source_page in (
                    requested_source_pages
                ):
                    pixmap = (
                        source_page
                        .get_pixmap(
                            matrix=render_matrix,
                            alpha=False,
                        )
                    )

                    target_page = (
                        subset.new_page(
                            width=(
                                source_page
                                .rect.width
                            ),
                            height=(
                                source_page
                                .rect.height
                            ),
                        )
                    )

                    target_page.insert_image(
                        target_page.rect,
                        pixmap=pixmap,
                    )

            else:
                for original_page in (
                    request.pages
                ):
                    subset.insert_pdf(
                        source,
                        from_page=(
                            original_page - 1
                        ),
                        to_page=(
                            original_page - 1
                        ),
                    )

            metadata = {
                key: value
                for key, value
                in source.metadata.items()
                if value
            }

            if metadata:
                subset.set_metadata(
                    metadata
                )

            subset_bytes = (
                subset.tobytes(
                    garbage=4,
                    deflate=True,
                )
            )

        finally:
            subset.close()

        return PreparedExplicitPdf(
            pdf_bytes=subset_bytes,
            original_page_count=(
                page_count
            ),
            page_map=request.pages,
            sequential=(
                request.sequential
            ),
            forced_ocr=forced_ocr,
        )

    finally:
        source.close()



def _response_language_instruction(
    prompt: str,
) -> str:
    """
    Lock the answer language to the latest user request,
    rather than allowing earlier conversation language or
    internal routing instructions to influence the answer.
    """

    if re.search(
        r"[\u0900-\u097F]",
        prompt,
    ):
        return (
            "Answer entirely in natural Hindi using "
            "Devanagari script. Do not switch to English "
            "except for names and technical terms that "
            "must remain unchanged."
        )

    lowered = prompt.lower()

    hinglish_terms = (
        "samjhao",
        "samjha do",
        "batao",
        "bata do",
        "sirf",
        "agla",
        "agli",
        "agle",
        "aage",
        "ek-ek",
        "ek ek",
        "tak",
        "karo",
        "kar do",
        "pages samjhao",
        "page samjhao",
    )

    if any(
        term in lowered
        for term in hinglish_terms
    ):
        return (
            "Answer in clear, natural Hinglish using "
            "Latin script. Keep important technical terms "
            "in English. Do not switch to Devanagari Hindi."
        )

    return (
        "Answer entirely in English. Do not switch to "
        "Hindi, Hinglish, or another language unless the "
        "latest user request explicitly asks for it."
    )


def build_explicit_page_prompt(
    *,
    user_prompt: str,
    prepared: PreparedExplicitPdf,
) -> str:
    language_instruction = (
        _response_language_instruction(
            user_prompt
        )
    )

    mapping_lines = [
        (
            f"Temporary Page {index} "
            f"maps to Original Page {original_page}."
        )
        for index, original_page
        in enumerate(
            prepared.page_map,
            start=1,
        )
    ]

    sequential_rules = ""

    if prepared.sequential:
        sequential_rules = """
Explain every supplied page separately and in exact order.
Create exactly one Markdown heading for every supplied page:
### Page 1
### Page 2
and so on.

NON-NEGOTIABLE COMPLETION RULES

- Do not combine pages.
- Do not skip any supplied page.
- Do not stop before explaining the final supplied page.
- Every page must contain its own exact page citation.
- Keep each page explanation concise, normally within 80 to
  140 words.
- Prioritize the page purpose, key facts, important numbers,
  decisions, rules and limitations.
- Avoid long quotations and repeated introductory language.
- Complete all requested pages before adding any overall summary.
""".strip()

    return f"""
STRICT EXPLICIT PDF PAGE MODE

RESPONSE LANGUAGE — NON-NEGOTIABLE

{language_instruction}

Determine language only from the latest user request included
below. Ignore the language of internal instructions and earlier
assistant responses.

Use only the pages contained in this temporary PDF.
Do not use, infer from, or cite any page outside this temporary PDF.

The backend will convert temporary page labels back to the
original PDF page numbers after analysis.

Use temporary citations exactly as:
[Page 1]
[Page 2]

Do not mention:
- temporary pages
- page mapping
- PDF subsets
- backend processing
- temporary-to-original page conversion

These are internal implementation details and must never appear
in the user-facing answer.

Do not write unsupported page numbers.

PAGE MAPPING

{chr(10).join(mapping_lines)}

{sequential_rules}

ORIGINAL USER REQUEST

{user_prompt}
""".strip()



def find_missing_sequential_pages(
    answer: str,
    expected_pages: tuple[int, ...],
) -> tuple[int, ...]:
    """
    Detect requested page sections that are absent from a
    sequential page-by-page answer.

    A page is considered present when it appears as a Markdown
    page heading. Citations are also accepted as a fallback.
    """

    heading_pages = {
        int(value)
        for value in re.findall(
            (
                r"(?im)^"
                r"(?:#{1,6}\s+|\*\*)"
                r"Page\s*(\d+)\b"
            ),
            answer,
        )
    }

    citation_pages = {
        int(value)
        for value in re.findall(
            r"\[Page\s*(\d+)\]",
            answer,
            flags=re.IGNORECASE,
        )
    }

    present_pages = (
        heading_pages
        | citation_pages
    )

    return tuple(
        page
        for page in expected_pages
        if page not in present_pages
    )


def _extract_sequential_page_sections(
    answer: str,
) -> dict[int, str]:
    heading_pattern = re.compile(
        (
            r"(?im)^"
            r"(?:#{1,6}\s+|\*\*)"
            r"Page\s*(\d+)\b"
            r"[^\n]*"
        )
    )

    matches = list(
        heading_pattern.finditer(
            answer
        )
    )

    sections: dict[int, str] = {}

    for index, match in enumerate(
        matches
    ):
        page_number = int(
            match.group(1)
        )

        start = match.start()

        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(answer)
        )

        section = answer[
            start:end
        ].strip()

        if section:
            sections.setdefault(
                page_number,
                section,
            )

    return sections


def merge_sequential_page_answers(
    *,
    primary_answer: str,
    supplemental_answer: str,
    expected_pages: tuple[int, ...],
) -> str:
    """
    Merge primary and completion answers in exact page order.
    Supplemental sections are used only where the primary answer
    omitted a requested page.
    """

    primary_sections = (
        _extract_sequential_page_sections(
            primary_answer
        )
    )

    supplemental_sections = (
        _extract_sequential_page_sections(
            supplemental_answer
        )
    )

    merged_sections: list[str] = []

    for page_number in expected_pages:
        section = (
            primary_sections.get(
                page_number
            )
            or supplemental_sections.get(
                page_number
            )
        )

        if section:
            merged_sections.append(
                section
            )

    if (
        len(merged_sections)
        == len(expected_pages)
    ):
        return "\n\n".join(
            merged_sections
        ).strip()

    # Safe fallback when a model did not use the required
    # Markdown heading format.
    parts = [
        primary_answer.strip(),
        supplemental_answer.strip(),
    ]

    return "\n\n".join(
        part
        for part in parts
        if part
    ).strip()


def remap_page_numbers(
    page_numbers: list[int]
    | tuple[int, ...],
    page_map: tuple[int, ...],
) -> tuple[int, ...]:
    remapped: list[int] = []

    for temporary_page in page_numbers:
        if not (
            1
            <= temporary_page
            <= len(page_map)
        ):
            continue

        original_page = page_map[
            temporary_page - 1
        ]

        if original_page not in remapped:
            remapped.append(
                original_page
            )

    return tuple(remapped)


def remap_answer_page_references(
    answer: str,
    page_map: tuple[int, ...],
) -> str:
    def mapped_page(
        temporary_page: int,
    ) -> int:
        if (
            1
            <= temporary_page
            <= len(page_map)
        ):
            return page_map[
                temporary_page - 1
            ]

        return temporary_page

    def replace_citation(
        match: re.Match[str],
    ) -> str:
        temporary_page = int(
            match.group(1)
        )

        return (
            f"[Page "
            f"{mapped_page(temporary_page)}]"
        )

    remapped = re.sub(
        r"\[Page\s*(\d+)\]",
        replace_citation,
        answer,
        flags=re.IGNORECASE,
    )

    def replace_heading(
        match: re.Match[str],
    ) -> str:
        prefix = match.group(1)
        temporary_page = int(
            match.group(2)
        )

        return (
            f"{prefix}Page "
            f"{mapped_page(temporary_page)}"
        )

    remapped = re.sub(
        r"(?m)^(#{1,6}\s+)Page\s*(\d+)\b",
        replace_heading,
        remapped,
        flags=re.IGNORECASE,
    )

    def replace_bold_heading(
        match: re.Match[str],
    ) -> str:
        temporary_page = int(
            match.group(1)
        )

        return (
            f"**Page "
            f"{mapped_page(temporary_page)}**"
        )

    remapped = re.sub(
        r"\*\*Page\s*(\d+)\*\*",
        replace_bold_heading,
        remapped,
        flags=re.IGNORECASE,
    )

    # Remove parenthetical internal mapping disclosures,
    # for example:
    # Original Page 18 (which is Temporary Page 1)
    remapped = re.sub(
        (
            r"Original\s+Page\s+(\d+)\s*"
            r"\([^)]*Temporary\s+Page\s+\d+[^)]*\)"
        ),
        lambda match: (
            f"Page {match.group(1)}"
        ),
        remapped,
        flags=re.IGNORECASE,
    )

    # Convert any remaining temporary-page prose
    # into the corresponding user-facing page number.
    def replace_temporary_page(
        match: re.Match[str],
    ) -> str:
        temporary_page = int(
            match.group(1)
        )

        return (
            f"Page "
            f"{mapped_page(temporary_page)}"
        )

    remapped = re.sub(
        r"Temporary\s+Page\s+(\d+)\b",
        replace_temporary_page,
        remapped,
        flags=re.IGNORECASE,
    )

    # User-facing text should simply say Page N.
    remapped = re.sub(
        r"\bOriginal\s+Page\s+(\d+)\b",
        r"Page \1",
        remapped,
        flags=re.IGNORECASE,
    )

    return remapped
