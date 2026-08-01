from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass

from artifacts.source_visuals import derive_supported_chart_blocks
from artifacts.quality import (
    equation_expression_is_structurally_valid,
)
from core.artifact_settings import artifact_settings
from schemas.artifact_composer import ArtifactComposeRequest


_PRESERVE_PATTERNS = (
    r"authoritative\s+source",
    r"preserve\s+(?:all|every|complete)",
    r"do\s+not\s+(?:remove|omit|drop|summari[sz]e|shorten)",
    r"without\s+(?:removing|omitting|dropping)",
    r"koi\s+(?:important\s+)?(?:detail|section|topic|equation|example|content).*?(?:remove|omit|drop).*?mat",
    r"kuch\s+bhi\s+(?:remove|omit|drop).*?mat",
    r"jitna\s+(?:bhi\s+)?(?:content|likha)",
    r"same\s+content",
    r"complete\s+content",
    r"full\s+content",
    r"word\s+for\s+word",
    r"lossless",
)

_COMPRESSION_PATTERNS = (
    r"summari[sz]e",
    r"shorten",
    r"make\s+it\s+short",
    r"brief\s+summary",
    r"concise\s+summary",
    r"more\s+concise",
    r"make\s+(?:it|this|the\s+document)\s+concise",
    r"sirf\s+summary",
    r"chhota\s+kar",
    r"short\s+version",
)

_TRAILING_MARKER = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:"
    r"FINAL\s+(?:PDF|DOCUMENT|ARTIFACT)\s+"
    r"(?:(?:GENERATION|CREATION|PRODUCTION)\s+)?INSTRUCTIONS?"
    r"|(?:PDF|DOCUMENT|ARTIFACT)\s+"
    r"(?:(?:GENERATION|CREATION|PRODUCTION)\s+)?INSTRUCTIONS?"
    r")\s*:?[ \t]*$"
)
_TRAILING_CREATE_PARAGRAPH = re.compile(
    r"(?is)(?:\n\s*){2,}([^\n]{0,3500}\b(?:create|make|generate|prepare|bana\s*do|banado|banao|taiyar\s*karo)\b[^\n]{0,3500}\b(?:pdf|docx|pptx|document|file)\b[^\n]{0,3500})\s*$"
)
_PREVIEW_MARKER = re.compile(
    r"(?:\[\s*)?Large\s+source\s+preserved\s+for\s+document\s+generation\s*:\s*[\d,]+\s+(?:middle\s+)?characters\s+hidden\s+in\s+(?:the\s+)?chat\s+preview(?:\s*\])?",
    re.IGNORECASE | re.DOTALL,
)
_TITLE_LINE = re.compile(r"^[A-Z0-9][A-Z0-9 &—–\-,:()/'’.]{8,240}$")
_NUMBERED_HEADING = re.compile(r"^\s*(\d{1,3})[.)]\s+(.{2,180}?)\s*$")
_WARNING_LINE = re.compile(
    r"^(?:warning|common\s+mistake|important\s+warning|caution)\s*:?[ ]*(.*)$",
    re.IGNORECASE,
)
_COMMON_MISTAKE_LINE = re.compile(
    r"^(?:a\s+)?common\s+mistake\b\s*(?:is|:)?\s*(.*)$",
    re.IGNORECASE,
)
_COMMAND_TITLE = re.compile(
    r"\b(?:add|create|make|generate|rename|convert|revise|update|new\s+version|professionally\s+organise|pdf\s+bana)\b",
    re.IGNORECASE,
)
_EQUATION_HINT = re.compile(
    r"(?:=|≤|≥|≠|±|√|∫|lim\b|d/dx|dy/dx|det\(|"
    r"\blog(?:[_₂]|\s*\(|\b)|sin\(|cos\(|tan\(|\^[0-9]|[²³⁴⁵])"
)
_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+")
_NATURAL_LANGUAGE_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}")
_DEFINITION_LINE = re.compile(
    r"^\s*([A-Za-zΑ-Ωα-ω][A-Za-z0-9Α-Ωα-ω₀-₉′'()|]{0,20})\s*=\s*([A-Za-z][A-Za-z ,/\-]{3,100})\s*$"
)
_EXPLICIT_DEFINITION = re.compile(r"^\s*([^:]{2,60})\s*:\s*(.{8,300})\s*$")
_ORDERED_ITEM = re.compile(r"^\s*\d+[.)]\s+.+")
_BULLET_ITEM = re.compile(r"^\s*[-*+]\s+.+")

_CANONICAL_H1 = re.compile(r"(?m)^#\s+(.+?)\s*$")
_CANONICAL_SECTION = re.compile(r"(?m)^##\s+(.+?)\s*$")
_INTERNAL_SECTION_TITLES = {
    "document production requirements",
    "production requirements",
    "artifact production requirements",
    "document creation instructions",
    "artifact creation instructions",
    "pdf creation instructions",
    "final pdf instruction",
    "final document instruction",
    "final artifact instruction",
    "generation instructions",
    "internal instructions",
    "source recovery instructions",
}
_INTERNAL_SECTION_PATTERN = re.compile(
    r"^(?:document|artifact|pdf|source|generation|internal|final)\s+"
    r"(?:production|creation|recovery)?\s*(?:requirements?|instructions?|directives?)$",
    re.IGNORECASE,
)
_INTERNAL_DIRECTIVE_LINE = re.compile(
    r"^(?:[-*+]\s+|\d+[.)]\s+)?(?:"
    r"(?:create|make|generate|prepare|produce|export|render|convert|recover|use|preserve|include|exclude|remove|omit|do\s+not|koi|sabhi|complete|existing|content\s+ko)\b"
    r")[\s\S]{0,500}\b(?:pdf|document|artifact|source|chapters?|equations?|graphs?|instructions?|preview|markers?|title|glossary|conclusion|page\s+numbers?)\b",
    re.IGNORECASE,
)
_PLACEHOLDER_LINE = re.compile(
    r"(?:\bTBD\b|\bTODO\b|\bFIXME\b|\[insert\b|\[placeholder\]|lorem ipsum|example\.com)",
    re.IGNORECASE,
)
_GENERIC_RECOVERED_TITLES = {
    "executive overview",
    "executive summary",
    "learning roadmap",
    "contents",
    "table of contents",
}

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "into", "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "with", "create", "pdf", "document", "professional", "content",
    "karo", "bana", "do", "mat", "aur", "ko", "ka", "ki", "ke", "mein",
}

_PART_BOUNDARIES: tuple[tuple[int, str], ...] = (
    (1, "Part I — Mathematical Foundations"),
    (4, "Part II — Algebra, Equations and Functions"),
    (13, "Part III — Trigonometry and Linear Algebra"),
    (17, "Part IV — Calculus and Continuous Change"),
    (27, "Part V — Probability, Statistics and Regression"),
    (32, "Part VI — Numerical Methods and Mathematical Modelling"),
    (35, "Part VII — Communication, Visualisation and Verification"),
)

_PART_DESCRIPTIONS = {
    "Part I — Mathematical Foundations": "Core language, number systems and proportional reasoning used throughout the rest of the document.",
    "Part II — Algebra, Equations and Functions": "Symbolic methods, equations, functions and graph behaviour developed through definitions and worked examples.",
    "Part III — Trigonometry and Linear Algebra": "Geometric relationships, vectors, matrices and determinants presented with visual and computational interpretation.",
    "Part IV — Calculus and Continuous Change": "Limits, derivatives, integrals and differential equations organised around rate, accumulation and verification.",
    "Part V — Probability, Statistics and Regression": "Uncertainty, distributions, descriptive measures, inference and relationships between variables.",
    "Part VI — Numerical Methods and Mathematical Modelling": "Approximation, model construction, validation, uncertainty and limitations.",
    "Part VII — Communication, Visualisation and Verification": "Standards for graphs, mathematical writing, quality checks and professional presentation.",
}

_CHART_CHAPTER_RULES: tuple[tuple[str, int], ...] = (
    ("Linear Cost Model", 5),
    ("Quadratic Function", 8),
    ("Graph Transformations", 10),
    ("Exponential Population Growth", 11),
    ("Base-2 Logarithm", 12),
    ("Unit Circle", 13),
    ("Sine and Cosine", 13),
    ("Secant-to-Tangent", 19),
    ("Signed Area", 24),
    ("Direction Field", 26),
    ("Fair Die Probability", 28),
    ("Frequency Distribution", 29),
    ("Regression", 31),
)


@dataclass(frozen=True, slots=True)
class SourceFidelityProfile:
    preserve_all: bool
    explicit_preservation_request: bool
    allows_condensation: bool
    source_text: str
    source_body: str
    directive_tail: str
    source_character_count: int
    body_character_count: int
    numbered_heading_titles: tuple[str, ...]
    minimum_expected_pages: int
    source_truncated: bool = False


@dataclass(frozen=True, slots=True)
class SourceFidelityMetrics:
    token_coverage_ratio: float
    heading_coverage_ratio: float
    character_retention_ratio: float

    @property
    def passed(self) -> bool:
        return (
            self.token_coverage_ratio >= 0.92
            and self.heading_coverage_ratio >= 0.95
            and self.character_retention_ratio >= 0.78
        )


def _matches_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _normalize_transport_payload(source_text: str) -> str:
    """Normalize transport-only contamination without deleting user directives.

    Directive boundaries must be detected before the general recovered-source
    sanitizer runs. The older order removed the marker heading first and left
    the instruction body behind, which caused those instructions to be printed
    into the final document and then rejected by structural validation.
    """

    normalized = source_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(
        r"<!--AUTHENTIC_[A-Z0-9_]+:[\s\S]*?-->",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = _PREVIEW_MARKER.sub("", normalized)
    return normalized.strip()


def split_source_and_directives(source_text: str) -> tuple[str, str]:
    raw = _normalize_transport_payload(source_text)

    marker = _TRAILING_MARKER.search(raw)
    if marker is not None and marker.start() >= int(len(raw) * 0.35):
        body = sanitize_recovered_source_payload(raw[: marker.start()])
        directives = raw[marker.end() :].strip()
        return body, directives

    match = _TRAILING_CREATE_PARAGRAPH.search(raw)
    if match is not None and match.start() >= int(len(raw) * 0.7):
        body = sanitize_recovered_source_payload(raw[: match.start()])
        return body, match.group(1).strip()

    return sanitize_recovered_source_payload(raw), ""


def _is_numbered_chapter_line(lines: list[str], index: int) -> re.Match[str] | None:
    match = _NUMBERED_HEADING.match(lines[index].strip())
    if match is None:
        return None
    title = " ".join(match.group(2).split()).strip()
    if not title or len(title) > 140 or title.endswith((".", "!", "?", ";")):
        return None
    previous_blank = index == 0 or not lines[index - 1].strip()
    next_blank = index + 1 >= len(lines) or not lines[index + 1].strip()
    if not (previous_blank and next_blank):
        return None
    return match


def _numbered_headings(text: str) -> tuple[str, ...]:
    lines = text.splitlines()
    headings: list[str] = []
    for index in range(len(lines)):
        match = _is_numbered_chapter_line(lines, index)
        if match is None:
            continue
        title = " ".join(match.group(2).split()).strip(" .:;-_")
        headings.append(f"{match.group(1)}. {title}")
    return tuple(headings)


def _expected_pages(source_body: str, headings: tuple[str, ...]) -> int:
    words = len(_WORD.findall(source_body))
    # Professional textbook pages carry less text than plain reports because
    # equations, examples, diagrams, tables and callouts need visual space.
    by_words = math.ceil(
        words / artifact_settings.pdf_target_words_per_page
    ) + 3
    by_headings = math.ceil(len(headings) / 1.5) + 2 if headings else 0
    expected = max(4, max(by_words, by_headings))
    if artifact_settings.enforce_single_pdf_page_limit:
        return min(
            artifact_settings.maximum_single_pdf_pages,
            expected,
        )
    return expected


def resolve_source_fidelity(request: ArtifactComposeRequest, source_text: str) -> SourceFidelityProfile:
    body, directives = split_source_and_directives(source_text)
    combined_instructions = "\n".join(part for part in (request.prompt, directives) if part)
    explicit = _matches_any(_PRESERVE_PATTERNS, combined_instructions)
    allows_condensation = _matches_any(_COMPRESSION_PATTERNS, combined_instructions)
    preserve_all = explicit or (len(body) >= 8_000 and not allows_condensation)
    headings = _numbered_headings(body)
    return SourceFidelityProfile(
        preserve_all=preserve_all,
        explicit_preservation_request=explicit,
        allows_condensation=allows_condensation,
        source_text=source_text,
        source_body=body or source_text.strip(),
        directive_tail=directives,
        source_character_count=len(source_text),
        body_character_count=len(body or source_text.strip()),
        numbered_heading_titles=headings,
        minimum_expected_pages=_expected_pages(body or source_text, headings),
        source_truncated=_PREVIEW_MARKER.search(source_text) is not None,
    )


def _title_case(value: str) -> str:
    small = {"a", "an", "and", "as", "at", "for", "from", "in", "of", "on", "or", "the", "to", "with"}
    words = value.split()
    output: list[str] = []
    for index, word in enumerate(words):
        if index and word.casefold() in small:
            output.append(word.casefold())
        elif word.isupper() and len(word) <= 6:
            output.append(word)
        else:
            output.append(word[:1].upper() + word[1:].lower())
    return " ".join(output)


def _mathematics_title(text: str) -> str | None:
    lowered = text.casefold()
    signals = sum(
        key in lowered
        for key in (
            "mathematical thinking", "quadratic equations", "derivatives",
            "definite integrals", "probability", "regression", "trigonometry",
        )
    )
    if signals >= 4:
        return "Mathematics: Foundations, Algebra, Calculus, Probability and Modelling"
    return None


def infer_professional_title(source_body: str, fallback_title: str = "Professional Document") -> str:
    math_title = _mathematics_title(source_body)
    if math_title:
        return math_title

    meaningful = [line.strip() for line in source_body.splitlines() if line.strip()]

    for value in meaningful[:16]:
        candidate = value.lstrip("# ").strip(" .:-_")
        if not candidate or _COMMAND_TITLE.search(candidate):
            continue
        if candidate.casefold() in _GENERIC_RECOVERED_TITLES:
            continue
        if candidate.casefold().startswith("part "):
            continue
        if _TITLE_LINE.match(candidate) or candidate.isupper():
            candidate = re.sub(r"\bPDF\s+TEST\b", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\s+[—–-]\s+", ": ", candidate)
            candidate = re.sub(r"\s{2,}", " ", candidate).strip(" :")
            if candidate:
                return _title_case(candidate)[:180]
        if len(candidate.split()) <= 14 and len(candidate) <= 140:
            return _title_case(candidate)[:180]

    if fallback_title and not _COMMAND_TITLE.search(fallback_title):
        return fallback_title[:180]
    return "Professional Learning Document"


def canonical_revision_title(
    current_content: str,
    *,
    source_snapshot_content: str | None = None,
    fallback_title: str = "Professional Document",
) -> str:
    first_heading = re.search(r"(?m)^#\s+(.+?)\s*$", current_content)
    if first_heading is not None:
        candidate = first_heading.group(1).strip()
        if candidate and not _COMMAND_TITLE.search(candidate):
            return candidate[:180]
    for source in (source_snapshot_content, current_content):
        if source:
            title = infer_professional_title(source, fallback_title)
            if title and not _COMMAND_TITLE.search(title):
                return title
    return "Professional Document"


def _looks_like_equation(line: str) -> bool:
    stripped = line.strip().strip("$")
    if not stripped or len(stripped) > 260:
        return False
    if _PREVIEW_MARKER.search(stripped):
        return False
    if re.match(r"^(?:where|example|verification|consider|then|therefore|because|important|the result|the model|the function)\b", stripped, re.IGNORECASE):
        return False
    if stripped.endswith((".", "!", "?", ":")) and len(stripped.split()) > 5:
        return False
    if _EQUATION_HINT.search(stripped) is None:
        return False

    natural_words = _NATURAL_LANGUAGE_WORD.findall(stripped)
    math_words = {
        "sin", "cos", "tan", "log", "lim", "det", "dx", "dy", "dt",
        "sqrt", "exp", "min", "max", "mod", "or",
    }
    prose_words = [word for word in natural_words if word.casefold() not in math_words]
    symbol_count = len(re.findall(r"[=+\-*/^²³⁴⁵√∫≤≥≠±()\[\]{}|]", stripped))

    if len(prose_words) >= 5:
        return False
    if len(prose_words) >= 3 and symbol_count < 3:
        return False
    # Reuse the final structural gate here so PDF extraction and provider
    # output cannot disagree about what constitutes display mathematics. In
    # particular, token fragments such as the ``log`` inside "technology"
    # must remain prose instead of becoming an EquationBlock.
    return equation_expression_is_structurally_valid(
        stripped
    )


def looks_like_equation(line: str) -> bool:
    """Public testable wrapper for professional source classification."""
    return _looks_like_equation(line)


def _normalize_equation_source(value: str) -> str:
    normalized = value.strip().strip("$")
    normalized = normalized.replace("−", "-")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _part_for_chapter(number: int) -> str | None:
    for boundary, title in reversed(_PART_BOUNDARIES):
        if number >= boundary:
            return title
    return None


def _chart_title(block: str) -> str:
    match = re.search(r"```authentic-chart\s*([\s\S]*?)```", block, re.IGNORECASE)
    if match is None:
        return ""
    try:
        payload = json.loads(match.group(1))
    except Exception:
        return ""
    return str(payload.get("title", "")) if isinstance(payload, dict) else ""


def _chart_map(source_text: str) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for block in derive_supported_chart_blocks(source_text):
        title = _chart_title(block)
        chapter = next((number for marker, number in _CHART_CHAPTER_RULES if marker.casefold() in title.casefold()), 35)
        result.setdefault(chapter, []).append(block)
    return result


def _next_nonblank(lines: list[str], start: int) -> int | None:
    for index in range(start, len(lines)):
        if lines[index].strip():
            return index
    return None


def _collect_definitions(lines: list[str], start: int) -> tuple[list[tuple[str, str]], int]:
    definitions: list[tuple[str, str]] = []
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        match = _DEFINITION_LINE.match(stripped)
        if match is None:
            break
        definitions.append((match.group(1), match.group(2)))
        index += 1
    return definitions, index


def _collect_short_list(lines: list[str], start: int) -> tuple[list[str], int]:
    items: list[str] = []
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if len(stripped) > 70 or stripped.endswith((".", ":", ";", "?", "!")):
            break
        if _looks_like_equation(stripped) or _ORDERED_ITEM.match(stripped) or _BULLET_ITEM.match(stripped):
            break
        if _NUMBERED_HEADING.match(stripped):
            break
        items.append(stripped)
        index += 1
    return items, index


def _emit_structured_lines(lines: list[str]) -> list[str]:
    output: list[str] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            if output and output[-1] != "":
                output.append("")
            index += 1
            continue
        if _PREVIEW_MARKER.search(stripped):
            index += 1
            continue

        warning = _WARNING_LINE.match(stripped)
        if warning is not None:
            warning_text = warning.group(1).strip() or stripped
            output.extend(["> [!WARNING] Common mistake", f"> {warning_text}", ""])
            index += 1
            continue

        common_mistake = _COMMON_MISTAKE_LINE.match(stripped)
        if common_mistake is not None:
            mistake_text = common_mistake.group(1).strip() or stripped
            output.extend(["> [!WARNING] Common mistake", f"> {mistake_text}", ""])
            index += 1
            continue

        if stripped.casefold() == "where:":
            definitions, next_index = _collect_definitions(lines, index + 1)
            if len(definitions) >= 2:
                output.extend([
                    "#### Variables and notation",
                    "",
                    "| Symbol | Meaning |",
                    "| --- | --- |",
                    *[f"| {symbol} | {meaning} |" for symbol, meaning in definitions],
                    "",
                ])
                index = next_index
                continue

        if stripped.endswith(":") and len(stripped.split()) <= 10:
            items, next_index = _collect_short_list(lines, index + 1)
            label = stripped[:-1].strip()
            if len(items) >= 3:
                output.extend([f"**{label}:**", ""])
                output.extend([f"- {item}" for item in items])
                output.append("")
                index = next_index
                continue
            output.extend([f"**{label}:**", ""])
            index += 1
            continue

        if _ORDERED_ITEM.match(stripped) or _BULLET_ITEM.match(stripped):
            output.append(stripped)
            index += 1
            continue

        if _looks_like_equation(stripped):
            output.extend([f"$${_normalize_equation_source(stripped)}$$", ""])
            index += 1
            continue

        explicit = _EXPLICIT_DEFINITION.match(stripped)
        if explicit is not None and len(explicit.group(1).split()) <= 6:
            output.extend([f"**{explicit.group(1).strip()}:** {explicit.group(2).strip()}", ""])
            index += 1
            continue

        output.append(stripped)
        index += 1

    while output and output[-1] == "":
        output.pop()
    return output


def _split_chapters(source_body: str) -> tuple[list[str], list[tuple[int, str, list[str]]]]:
    lines = source_body.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    headings: list[tuple[int, re.Match[str]]] = []
    for index in range(len(lines)):
        match = _is_numbered_chapter_line(lines, index)
        if match is not None:
            headings.append((index, match))
    if not headings:
        return lines, []

    preamble = lines[: headings[0][0]]
    chapters: list[tuple[int, str, list[str]]] = []
    for position, (line_index, match) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        number = int(match.group(1))
        title = " ".join(match.group(2).split()).strip(" .:;-_")
        chapters.append((number, title, lines[line_index + 1 : end]))
    return preamble, chapters


_MATHEMATICS_GLOSSARY: tuple[tuple[str, str, str], ...] = (
    ("Natural numbers", r"\bnatural numbers\b", "Counting numbers such as 1, 2, 3, 4, 5, and so on."),
    ("Whole numbers", r"\bwhole numbers\b", "The natural numbers together with zero."),
    ("Integers", r"\bintegers\b", "Positive whole numbers, zero, and negative whole numbers."),
    ("Rational number", r"\brational numbers?\b", "A number that can be written as p/q, where p and q are integers and q is not zero."),
    ("Irrational number", r"\birrational numbers?\b", "A real number that cannot be written as a ratio of two integers."),
    ("Real number", r"\breal numbers?\b", "A number belonging to the combined set of rational and irrational numbers."),
    ("Fraction", r"\ba fraction represents\b", "A representation of a part of a whole or a division operation."),
    ("Ratio", r"\ba ratio compares\b", "A comparison between two quantities."),
    ("Proportion", r"\ba proportion states\b", "An equation stating that two ratios are equal."),
    ("Algebraic expression", r"\ban algebraic expression combines\b", "A combination of variables, constants, and mathematical operations."),
    ("Linear equation", r"\ba linear equation has\b", "An equation in which the variable is raised only to the first power."),
    ("Slope", r"\bm\s*=\s*slope\b", "The constant rate of change in a linear model."),
    ("Quadratic equation", r"\ba quadratic equation has\b", "An equation of the form ax² + bx + c = 0, where a is not zero."),
    ("Discriminant", r"\bcalled the discriminant\b", "The expression b² - 4ac, which determines the real-root structure of a quadratic equation."),
    ("Function", r"\ba function assigns\b", "A rule that assigns exactly one output to each valid input."),
    ("Exponential change", r"\bexponential change represents\b", "Change described by a constant percentage rate rather than a constant absolute amount."),
    ("Logarithm", r"\ba logarithm is the inverse\b", "The inverse operation of exponentiation."),
    ("Vector", r"\ba vector has both\b", "A quantity having both magnitude and direction."),
    ("Matrix", r"\ba matrix is a rectangular\b", "A rectangular arrangement of numbers."),
    ("Determinant", r"\bthe determinant is\b", "For a 2 x 2 matrix, the scalar ad - bc; a non-zero value indicates invertibility."),
    ("Limit", r"\ba limit describes\b", "The value approached by a function as its input approaches a specified value."),
    ("Continuity", r"\ba function is continuous\b", "The condition that the function value exists, the limit exists, and the two are equal at the point."),
    ("Derivative", r"\bthe derivative represents\b", "An instantaneous rate of change and the slope of a tangent line."),
    ("Critical point", r"\bthese are critical points\b", "A candidate point identified where a derivative is zero or otherwise requires classification."),
    ("Antiderivative", r"\ban antiderivative reverses\b", "A function whose derivative equals the given integrand."),
    ("Definite integral", r"\ba definite integral measures\b", "An accumulated signed quantity over a specified interval."),
    ("Differential equation", r"\ba differential equation relates\b", "An equation relating an unknown function to one or more of its derivatives."),
    ("Probability", r"\bprobability measures uncertainty\b", "A numerical measure of uncertainty between zero and one."),
    ("Conditional probability", r"\bconditional probability is\b", "The probability of an event under the condition that another event has occurred."),
    ("Independent events", r"\btwo events .* are independent\b", "Events whose joint probability equals the product of their individual probabilities."),
    ("Random variable", r"\ba random variable assigns\b", "A rule assigning numerical values to outcomes."),
    ("Mean", r"\bmean:\s*\n", "The arithmetic average of the observations in a dataset."),
    ("Median", r"\bmedian:\s*\n", "The middle ordered value, or the average of the two middle values when needed."),
    ("Regression", r"\bregression models the relationship\b", "A model of the relationship between a response variable and one or more predictors."),
    ("Newton's method", r"\bnewton's method approximates roots\b", "An iterative numerical method for approximating solutions of f(x) = 0."),
    ("Mathematical model", r"\ba mathematical model is a simplified\b", "A simplified mathematical representation of a real system."),
)


def _glossary_entries(source_body: str) -> list[tuple[str, str]]:
    """Build a domain glossary from definitions actually supported by the source."""

    normalized = source_body.replace("×", "x")
    entries: list[tuple[str, str]] = []
    for term, pattern, definition in _MATHEMATICS_GLOSSARY:
        if re.search(pattern, normalized, re.IGNORECASE | re.DOTALL):
            entries.append((term, definition))
    return entries



def _heading_details(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
    if match is None:
        return None
    return len(match.group(1)), match.group(2).strip()


def _is_internal_section_title(title: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
    return (
        normalized in _INTERNAL_SECTION_TITLES
        or _INTERNAL_SECTION_PATTERN.fullmatch(normalized) is not None
    )


def _remove_internal_sections_any_level(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    skip_level: int | None = None
    in_fence = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            if skip_level is None:
                output.append(raw_line.rstrip())
            in_fence = not in_fence
            continue

        if in_fence:
            if skip_level is None:
                output.append(raw_line.rstrip())
            continue

        heading = _heading_details(raw_line)
        if skip_level is not None:
            if heading is not None and heading[0] <= skip_level:
                skip_level = None
            else:
                continue

        if heading is not None and _is_internal_section_title(heading[1]):
            skip_level = heading[0]
            continue

        output.append(raw_line.rstrip())

    return "\n".join(output)


def _remove_orphan_directive_tail(markdown: str) -> str:
    """Remove trailing chat instructions that escaped a heading wrapper.

    Only the final tail is considered. This deliberately avoids deleting
    instructional prose inside legitimate chapters.
    """

    lines = markdown.splitlines()
    last_content = len(lines) - 1
    while last_content >= 0 and not lines[last_content].strip():
        last_content -= 1
    if last_content < 0:
        return markdown

    start = last_content
    directive_hits = 0
    scanned = 0
    while start >= 0 and scanned < 80:
        line = lines[start].strip()
        if not line:
            start -= 1
            scanned += 1
            continue
        if _heading_details(line) is not None:
            break
        if _INTERNAL_DIRECTIVE_LINE.search(line):
            directive_hits += 1
            start -= 1
            scanned += 1
            continue
        # A short continuation line may belong to the preceding directive.
        if directive_hits and len(line) <= 220:
            start -= 1
            scanned += 1
            continue
        break

    if directive_hits < 2:
        return markdown
    return "\n".join(lines[: start + 1]).rstrip()


def _strip_explicit_generation_tail(markdown: str) -> str:
    marker = _TRAILING_MARKER.search(markdown)
    if marker is None:
        return markdown
    if marker.start() < int(len(markdown) * 0.30):
        return markdown
    return markdown[: marker.start()].rstrip()


def _remove_placeholder_lines(markdown: str) -> str:
    lines = markdown.splitlines()
    cleaned = [line for line in lines if not _PLACEHOLDER_LINE.search(line)]
    return "\n".join(cleaned)


def sanitize_recovered_source_payload(source_text: str) -> str:
    """Remove transport/UI contamination from a recovered source payload.

    The function is intentionally idempotent and safe for both canonical
    artifact Markdown and raw authoritative source text.
    """

    normalized = source_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _strip_explicit_generation_tail(normalized)
    normalized = re.sub(
        r"<!--AUTHENTIC_[A-Z0-9_]+:[\s\S]*?-->",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = _PREVIEW_MARKER.sub("", normalized)
    normalized = _remove_internal_sections_any_level(normalized)
    normalized = _remove_orphan_directive_tail(normalized)
    normalized = _remove_placeholder_lines(normalized)
    normalized = re.sub(r"\n{4,}", "\n\n\n", normalized).strip()
    return normalized


def recovered_source_contamination(source_text: str) -> tuple[str, ...]:
    """Return known contamination signals for diagnostics and candidate scoring."""

    issues: list[str] = []
    h1 = _CANONICAL_H1.search(source_text)
    if h1 is not None and _COMMAND_TITLE.search(h1.group(1)):
        issues.append("command_title")
    if _PREVIEW_MARKER.search(source_text):
        issues.append("compact_preview")
    if any(
        _is_internal_section_title(title)
        for title in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", source_text)
    ):
        issues.append("internal_production_section")
    return tuple(issues)


def is_canonical_artifact_markdown(source_text: str) -> bool:
    """Return True when recovered content is already a structured artifact.

    Canonical artifact Markdown must never be sent back through the raw-source
    organiser. Re-organising it creates duplicate chapters, duplicated charts,
    leaked Markdown tokens, and structural validation failures.
    """

    normalized = sanitize_recovered_source_payload(source_text)
    h1 = _CANONICAL_H1.findall(normalized)
    sections = _CANONICAL_SECTION.findall(normalized)
    if len(h1) != 1 or len(sections) < 2:
        return False

    generic_structure = bool(
        len(sections) >= 3
        or len(re.findall(r"(?m)^###\s+\S", normalized)) >= 2
        or re.search(
            r"(?m)^\|\s*[^\n|]+(?:\|[^\n|]+)+\|\s*$\n"
            r"^\|(?:\s*:?-{3,}:?\s*\|){2,}\s*$",
            normalized,
        )
    )
    structural_signals = sum(
        bool(re.search(pattern, normalized, re.IGNORECASE | re.MULTILINE))
        for pattern in (
            r"^##\s+(?:Executive|Learning|Part\s+|Glossary|Conclusion)",
            r"^###\s+\d{1,3}[.]\s+",
            r"```authentic-chart\s+",
            r"\[page-break\]",
        )
    )
    return structural_signals >= 1 or generic_structure


def _remove_markdown_section(markdown: str, section_title: str) -> str:
    escaped = re.escape(section_title)
    return re.sub(
        rf"^##\s+{escaped}\s*$.*?(?=^##\s+|\Z)",
        "",
        markdown,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )


def normalize_recovered_artifact_markdown(
    source_text: str,
    *,
    fallback_title: str,
) -> str:
    """Make an existing canonical artifact safe and idempotent to re-render."""

    normalized = sanitize_recovered_source_payload(source_text)

    for title in _INTERNAL_SECTION_TITLES:
        normalized = _remove_markdown_section(normalized, title)

    lines: list[str] = []
    seen_h1 = False
    in_fence = False
    for raw_line in normalized.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            lines.append(raw_line.rstrip())
            continue
        if not in_fence and re.fullmatch(r"(?:-{3,}|_{3,}|\*{3,})", stripped):
            lines.append("")
            continue
        if not in_fence and stripped.startswith("# "):
            if seen_h1:
                lines.append("## " + stripped[2:].strip())
            else:
                seen_h1 = True
                lines.append(raw_line.rstrip())
            continue
        lines.append(raw_line.rstrip())

    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{4,}", "\n\n\n", normalized).strip()

    h1 = _CANONICAL_H1.search(normalized)
    existing_title = h1.group(1).strip() if h1 is not None else ""
    safe_fallback = (
        fallback_title
        if fallback_title and not _COMMAND_TITLE.search(fallback_title)
        else "Professional Document"
    )
    title_source = normalized
    if h1 is not None and _COMMAND_TITLE.search(existing_title):
        title_source = normalized[: h1.start()] + normalized[h1.end() :]
    if (
        existing_title
        and _COMMAND_TITLE.search(existing_title)
        and safe_fallback not in {
            "Professional Document",
            "Professional Learning Document",
        }
    ):
        title = safe_fallback[:180]
    else:
        title = infer_professional_title(title_source, safe_fallback)
    if _COMMAND_TITLE.search(title):
        title = infer_professional_title(title_source, "Professional Learning Document")

    if h1 is None:
        normalized = f"# {title}\n\n{normalized}"
    else:
        normalized = normalized[: h1.start()] + f"# {title}" + normalized[h1.end() :]

    # Exact repeated chart blocks can appear after old recovery attempts.
    chart_pattern = re.compile(r"```authentic-chart\s*[\s\S]*?```", re.IGNORECASE)
    seen_charts: set[str] = set()
    def keep_chart(match: re.Match[str]) -> str:
        block = match.group(0).strip()
        key = re.sub(r"\s+", "", block).casefold()
        if key in seen_charts:
            return ""
        seen_charts.add(key)
        return block
    normalized = chart_pattern.sub(keep_chart, normalized)
    normalized = sanitize_recovered_source_payload(normalized)
    normalized = re.sub(r"\n{4,}", "\n\n\n", normalized).strip()
    return normalized + "\n"


def organize_source_losslessly(
    profile: SourceFidelityProfile,
    *,
    fallback_title: str,
    include_derived_visualizations: bool = True,
) -> str:
    """Create a professional textbook-like Markdown document without source loss."""

    if is_canonical_artifact_markdown(profile.source_body):
        return normalize_recovered_artifact_markdown(
            profile.source_body,
            fallback_title=fallback_title,
        )

    title = infer_professional_title(profile.source_body, fallback_title)
    preamble, chapters = _split_chapters(profile.source_body)
    output: list[str] = [f"# {title}", ""]
    chart_map = _chart_map(profile.source_text) if include_derived_visualizations else {}

    title_index = next((i for i, line in enumerate(preamble) if line.strip()), -1)
    preamble_content = [line for i, line in enumerate(preamble) if i != title_index]
    structured_preamble = _emit_structured_lines(preamble_content)
    if structured_preamble:
        output.extend(["## Editorial Overview", "", *structured_preamble, ""])

    if chapters and len(chapters) >= 12:
        output.extend([
            "## Executive Overview",
            "",
            "This document develops a connected mathematical pathway from number systems and proportional reasoning through algebra, functions, trigonometry, linear algebra, calculus, probability, statistics, numerical methods and modelling. Definitions are paired with worked calculations, source-derived visualisations, verification checks and explicit limitations so the material can be read as both a learning reference and a professional technical document.",
            "",
        ])
        output.extend([
            "## Learning Roadmap",
            "",
            "This reference is organised into seven parts so definitions, worked examples, visual explanations and verification methods can be studied in a logical sequence.",
            "",
            "| Part | Chapter range | Focus |",
            "| --- | --- | --- |",
        ])
        boundaries = list(_PART_BOUNDARIES)
        for position, (start, part_title) in enumerate(boundaries):
            end = (boundaries[position + 1][0] - 1) if position + 1 < len(boundaries) else chapters[-1][0]
            if start <= chapters[-1][0]:
                output.append(f"| {part_title} | {start}-{min(end, chapters[-1][0])} | Structured progression through the source chapters |")
        output.extend(["", "[page-break]", ""])

    active_part: str | None = None
    for number, chapter_title, chapter_lines in chapters:
        part = _part_for_chapter(number) if len(chapters) >= 12 else None
        if part and part != active_part:
            if active_part is not None:
                output.extend(["[page-break]", ""])
            output.extend([
                f"## {part}",
                "",
                _PART_DESCRIPTIONS.get(part, "Structured source chapters in this part."),
                "",
            ])
            active_part = part

        heading_prefix = "###" if part else "##"
        output.extend([f"{heading_prefix} {number}. {chapter_title}", ""])
        output.extend(_emit_structured_lines(chapter_lines))
        output.append("")

        for chart in chart_map.get(number, []):
            output.extend([chart, ""])

    if not chapters:
        output.extend(_emit_structured_lines(preamble_content or preamble))

    requested_glossary = re.search(r"\bglossary\b", profile.directive_tail, re.IGNORECASE) is not None
    glossary = _glossary_entries(profile.source_body) if requested_glossary else []
    if glossary:
        output.extend([
            "[page-break]",
            "",
            "## Glossary and Notation",
            "",
            "| Term or symbol | Source-supported meaning |",
            "| --- | --- |",
            *[f"| {term.replace('|', '/')} | {definition.replace('|', '/')} |" for term, definition in glossary],
            "",
        ])

    if chapters:
        output.extend([
            "## Conclusion",
            "",
            "The chapters collectively show how mathematical work progresses from precise definitions and symbolic manipulation to rates of change, accumulation, uncertainty, approximation and model validation. The worked examples demonstrate that a result is not complete until its assumptions, domain, units and interpretation have been checked. The visualisations reinforce the relationships already present in the source, while the final verification standards provide a repeatable method for presenting mathematics accurately and professionally.",
            "",
            "> [!SUCCESS] Completion standard",
            "> A professional mathematical document preserves the full source, renders notation legibly, places visual evidence beside the relevant concept, and separates verified conclusions from assumptions and limitations.",
            "",
        ])

    # Production instructions govern rendering and must never be printed as body content.
    while output and output[-1] == "":
        output.pop()
    return "\n".join(output).strip() + "\n"


def _tokens(text: str) -> Counter[str]:
    return Counter(
        token.casefold()
        for token in _WORD.findall(text)
        if len(token) >= 2 and token.casefold() not in _STOP_WORDS
    )


def source_fidelity_metrics(
    source_body: str,
    document_content: str,
    headings: tuple[str, ...] = (),
) -> SourceFidelityMetrics:
    source_tokens = _tokens(source_body)
    output_tokens = _tokens(document_content)
    total = sum(source_tokens.values())
    retained = sum(min(count, output_tokens.get(token, 0)) for token, count in source_tokens.items())
    token_ratio = retained / total if total else 1.0

    normalized_output = " ".join(document_content.casefold().split())
    matched_headings = sum(
        1 for heading in headings if " ".join(heading.casefold().split()) in normalized_output
    )
    heading_ratio = matched_headings / len(headings) if headings else 1.0
    character_ratio = len(document_content) / len(source_body) if source_body else 1.0
    return SourceFidelityMetrics(
        token_coverage_ratio=min(token_ratio, 1.0),
        heading_coverage_ratio=min(heading_ratio, 1.0),
        character_retention_ratio=character_ratio,
    )


def is_additive_revision(instruction: str) -> bool:
    return re.search(
        r"\b(?:add|include|insert|append|comparison\s+table|new\s+section|new\s+version|updated\s+version|naya\s+version)\b",
        instruction,
        re.IGNORECASE,
    ) is not None


def is_destructive_or_condensing_revision(instruction: str) -> bool:
    return _matches_any(
        _COMPRESSION_PATTERNS + (r"remove\b", r"delete\b", r"exclude\b", r"rewrite\s+from\s+scratch"),
        instruction,
    )


def _section_details(markdown: str) -> list[tuple[str, str, str]]:
    lines = markdown.splitlines()
    results: list[tuple[str, str, str]] = []
    index = 0
    while index < len(lines):
        match = re.match(r"^###?\s+(\d{1,3}[.]\s+.+?|[^#].+?)\s*$", lines[index].strip())
        if match is None:
            index += 1
            continue
        title = match.group(1).strip()
        if title.startswith("Part ") or title in {"Learning Roadmap", "Glossary and Notation", "Comparative Concept Matrix"}:
            index += 1
            continue
        index += 1
        body: list[str] = []
        equations: list[str] = []
        while index < len(lines) and not re.match(r"^##+\s+", lines[index].strip()):
            candidate = lines[index].strip()
            equation = re.fullmatch(r"\$\$(.*?)\$\$", candidate)
            if equation is not None:
                equations.append(equation.group(1).strip())
            elif candidate and not candidate.startswith(("```", "[page-break]", "|", "- ")):
                body.append(candidate)
            index += 1
        summary = re.sub(r"[*_`>|]", " ", " ".join(body))
        summary = " ".join(summary.split())
        first_sentence = re.split(r"(?<=[.!?])\s+", summary, maxsplit=1)[0] if summary else "Source section preserved."
        formula = equations[0] if equations else "—"
        results.append((title, first_sentence[:180], formula[:120]))
    return results


def apply_deterministic_additive_revision(current_content: str, instruction: str) -> str | None:
    if re.search(r"comparison\s+table|summary\s+table", instruction, re.IGNORECASE) is None:
        return None

    sections = _section_details(current_content)
    if not sections:
        return None

    # Replace an older generated matrix instead of appending duplicates.
    base = re.sub(
        r"(?ms)\n\[page-break\]\n\n## Comparative Concept Matrix\n.*?(?=\n\[page-break\]\n|\Z)",
        "",
        current_content.rstrip(),
    )

    if len(sections) > 12:
        indexes = sorted({round(i * (len(sections) - 1) / 11) for i in range(12)})
        selected = [sections[i] for i in indexes]
    else:
        selected = sections

    rows = [
        "| Source section | Core idea retained from the document | Representative formula or example |",
        "| --- | --- | --- |",
    ]
    for title, summary, formula in selected:
        rows.append(
            f"| {title.replace('|', '/')} | {summary.replace('|', '/')} | {formula.replace('|', '/')} |"
        )

    return (
        base
        + "\n\n[page-break]\n\n"
        + "## Comparative Concept Matrix\n\n"
        + "The matrix below compares representative sections from the existing authoritative document. The revision is additive: every earlier chapter, equation, example and visualization remains unchanged.\n\n"
        + "\n".join(rows)
        + "\n"
    )
