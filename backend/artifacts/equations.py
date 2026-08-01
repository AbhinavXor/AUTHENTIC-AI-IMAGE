from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from pathlib import Path
from threading import RLock

import matplotlib

matplotlib.use("Agg")

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import math_to_image
from PIL import Image


_EQUATION_RENDER_LOCK = RLock()
_EQUATION_PNG_CACHE: OrderedDict[str, bytes] = OrderedDict()
_MAXIMUM_CACHED_EQUATIONS = 512
_MAXIMUM_EXPRESSION_CHARACTERS = 4_000
_SUPERSCRIPTS = str.maketrans({
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
})
_SUBSCRIPTS = str.maketrans({
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
})
_MATRIX_PATTERN = re.compile(
    r"^(?P<prefix>.*?)\[\s*\[(?P<rows>.+)\]\s*\]\s*$"
)


class EquationRenderingError(RuntimeError):
    """Raised when a mathematical expression cannot be rendered safely."""


def _convert_super_and_subscripts(value: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char in "⁰¹²³⁴⁵⁶⁷⁸⁹":
            digits: list[str] = []
            while index < len(value) and value[index] in "⁰¹²³⁴⁵⁶⁷⁸⁹":
                digits.append(value[index].translate(_SUPERSCRIPTS))
                index += 1
            output.append("^{" + "".join(digits) + "}")
            continue
        if char in "₀₁₂₃₄₅₆₇₈₉":
            digits = []
            while index < len(value) and value[index] in "₀₁₂₃₄₅₆₇₈₉":
                digits.append(value[index].translate(_SUBSCRIPTS))
                index += 1
            output.append("_{" + "".join(digits) + "}")
            continue
        output.append(char)
        index += 1
    return "".join(output)


def normalize_math_expression(expression: str) -> str:
    normalized = expression.strip()
    while len(normalized) >= 2 and normalized.startswith("$") and normalized.endswith("$"):
        normalized = normalized[1:-1].strip()

    if not normalized:
        raise EquationRenderingError("Equation expression cannot be empty.")
    if len(normalized) > _MAXIMUM_EXPRESSION_CHARACTERS:
        raise EquationRenderingError("Equation expression is too large to render.")

    normalized = normalized.replace("−", "-").replace("×", r"\times ")
    normalized = normalized.replace("·", r"\cdot ").replace("⇒", r"\Rightarrow ")
    normalized = normalized.replace("→", r"\to ").replace("≤", r"\le ")
    normalized = normalized.replace("≥", r"\ge ").replace("≠", r"\ne ")
    normalized = normalized.replace("±", r"\pm ").replace("π", r"\pi ")
    normalized = normalized.replace("θ", r"\theta ").replace("∇", r"\nabla ")
    normalized = normalized.replace("∩", r"\cap ").replace("∪", r"\cup ")
    normalized = normalized.replace("∈", r"\in ").replace("∞", r"\infty ")
    normalized = _convert_super_and_subscripts(normalized)

    normalized = re.sub(
        r"\b([0-9]+(?:\.[0-9]+)?)\s*degrees?\b",
        lambda match: match.group(1) + r"^{\circ}",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\b(?:radians?|radian)\b",
        lambda _match: r"\mathrm{radians}",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"(\\pi)\s*(\\mathrm\{radians\})",
        r"\1\,\2",
        normalized,
    )
    normalized = re.sub(
        r"\b([A-Za-z]{3,})\s*/\s*([A-Za-z]{3,})\b",
        lambda match: (
            r"\frac{\mathrm{" + match.group(1) + "}}"
            r"{\mathrm{" + match.group(2) + "}}"
        ),
        normalized,
    )

    normalized = re.sub(r"\blim\s+([A-Za-z])\s*\\to\s*([^\s\[({]+)", r"\\lim_{\1\\to \2}", normalized)
    normalized = re.sub(r"\blog_?\{?([0-9]+)\}?", r"\\log_{\1}", normalized)
    normalized = re.sub(r"\blog\s*\(\s*", r"\\log(", normalized)
    normalized = re.sub(r"\bsin\s*\(", r"\\sin(", normalized)
    normalized = re.sub(r"\bcos\s*\(", r"\\cos(", normalized)
    normalized = re.sub(r"\btan\s*\(", r"\\tan(", normalized)
    normalized = re.sub(r"\bdet\s*\(", r"\\det(", normalized)
    normalized = re.sub(r"(?<!\\)\bsin(?=\^|_|\\theta|[A-Za-z])", r"\\sin", normalized)
    normalized = re.sub(r"(?<!\\)\bcos(?=\^|_|\\theta|[A-Za-z])", r"\\cos", normalized)
    normalized = re.sub(r"(?<!\\)\btan(?=\^|_|\\theta|[A-Za-z])", r"\\tan", normalized)
    normalized = re.sub(r"(?<!\\)\blog(?=\^|_|[0-9A-Za-z])", r"\\log", normalized)

    # Common radical forms in user-provided plain mathematics.
    normalized = re.sub(r"√\s*\(([^()]+)\)", r"\\sqrt{\1}", normalized)
    normalized = re.sub(r"√\s*([A-Za-z0-9]+)", r"\\sqrt{\1}", normalized)

    # Common integral notation. Limits are recognised only when they are
    # explicitly written as Unicode subscript/superscript digits. This avoids
    # misreading an indefinite integral such as ∫(3x² - 4) dx as limits 3 to 2.
    raw_expression = expression.strip().strip("$").strip()
    definite_integral = re.match(
        r"^∫\s*(?P<lower>[₀₁₂₃₄₅₆₇₈₉]+)\s*"
        r"(?P<upper>[⁰¹²³⁴⁵⁶⁷⁸⁹]+)\s*"
        r"(?P<integrand>.+?)\s+d(?P<variable>[A-Za-z])$",
        raw_expression,
    )
    if definite_integral is not None:
        lower = definite_integral.group("lower").translate(_SUBSCRIPTS)
        upper = definite_integral.group("upper").translate(_SUPERSCRIPTS)
        integrand = normalize_math_expression(
            definite_integral.group("integrand")
        )
        variable = definite_integral.group("variable")
        normalized = rf"\int_{{{lower}}}^{{{upper}}} {integrand}\,d{variable}"
    else:
        indefinite_integral = re.match(
            r"^∫\s*(?P<integrand>.+?)\s+d(?P<variable>[A-Za-z])$",
            raw_expression,
        )
        if indefinite_integral is not None:
            integrand = indefinite_integral.group("integrand").strip()
            if integrand.startswith("(") and integrand.endswith(")"):
                integrand = integrand[1:-1].strip()
            integrand = normalize_math_expression(integrand)
            variable = indefinite_integral.group("variable")
            normalized = rf"\int ({integrand})\,d{variable}"

    # Convert common plain-text fractions into real mathematical fractions.
    # The patterns intentionally avoid broad free-form parsing and target the
    # source formats produced by the artifact pipeline: bracketed sums,
    # parenthesised expressions, function calls, symbols, and numeric values.
    normalized = re.sub(
        r"\[([^\[\]]+)\]\s*/\s*"
        r"(\([^()]+\)|[A-Za-z0-9.]+)",
        lambda match: (
            r"\frac{" + match.group(1).strip() + "}{"
            + match.group(2).strip("()").strip() + "}"
        ),
        normalized,
    )

    fraction_operand = (
        r"(?:[A-Za-z]+\([^()]*\)|\([^()]+\)|"
        r"[A-Za-z0-9.]+)"
    )
    fraction_pattern = re.compile(
        rf"(?P<numerator>{fraction_operand})\s*/\s*"
        rf"(?P<denominator>{fraction_operand})"
    )

    def _fraction_replacement(match: re.Match[str]) -> str:
        numerator = match.group("numerator").strip()
        denominator = match.group("denominator").strip()
        if numerator == "d" and denominator in {"dx", "dy", "dt", "du", "dv"}:
            return match.group(0)
        numerator = numerator[1:-1].strip() if numerator.startswith("(") and numerator.endswith(")") else numerator
        denominator = denominator[1:-1].strip() if denominator.startswith("(") and denominator.endswith(")") else denominator
        return rf"\frac{{{numerator}}}{{{denominator}}}"

    normalized = fraction_pattern.sub(_fraction_replacement, normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _parse_matrix(expression: str) -> tuple[str, list[list[str]]] | None:
    match = _MATRIX_PATTERN.match(expression.strip())
    if match is None:
        return None
    rows_raw = re.split(r"\]\s*,\s*\[", match.group("rows"))
    rows: list[list[str]] = []
    for row_raw in rows_raw:
        cells = [cell.strip() for cell in row_raw.split(",")]
        if not cells or any(not cell for cell in cells):
            return None
        rows.append(cells)
    if len(rows) < 1 or len({len(row) for row in rows}) != 1 or len(rows[0]) > 6:
        return None
    prefix = match.group("prefix").strip()
    return prefix, rows


def _render_matrix_image(
    expression: str,
    output_path: Path,
    *,
    color: str,
    dpi: int,
    font_size: float,
) -> tuple[int, int] | None:
    parsed = _parse_matrix(expression)
    if parsed is None:
        return None
    prefix, rows = parsed
    row_count = len(rows)
    column_count = len(rows[0])
    width = max(3.0, 0.75 * column_count + (1.4 if prefix else 0.5))
    height = max(1.0, 0.48 * row_count + 0.35)

    figure = Figure(figsize=(width, height), dpi=dpi)
    FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    axis.set_axis_off()
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)

    matrix_left = 0.34 if prefix else 0.12
    matrix_right = 0.94
    matrix_bottom = 0.12
    matrix_top = 0.88
    if prefix:
        axis.text(
            0.02,
            0.5,
            f"${normalize_math_expression(prefix.rstrip('=').strip())} =$",
            ha="left",
            va="center",
            fontsize=font_size,
            color=color,
        )

    for row_index, row in enumerate(rows):
        y = matrix_top - (row_index + 0.5) * (matrix_top - matrix_bottom) / row_count
        for column_index, cell in enumerate(row):
            x = matrix_left + (column_index + 0.5) * (matrix_right - matrix_left) / column_count
            axis.text(
                x,
                y,
                f"${normalize_math_expression(cell)}$",
                ha="center",
                va="center",
                fontsize=font_size,
                color=color,
            )

    bracket_width = 0.018
    axis.plot([matrix_left - bracket_width, matrix_left - bracket_width, matrix_left], [matrix_top, matrix_bottom, matrix_bottom], color=color, linewidth=1.6)
    axis.plot([matrix_left - bracket_width, matrix_left, matrix_left], [matrix_top, matrix_top, matrix_top - 0.001], color=color, linewidth=1.6)
    axis.plot([matrix_right + bracket_width, matrix_right + bracket_width, matrix_right], [matrix_top, matrix_bottom, matrix_bottom], color=color, linewidth=1.6)
    axis.plot([matrix_right + bracket_width, matrix_right, matrix_right], [matrix_top, matrix_top, matrix_top - 0.001], color=color, linewidth=1.6)

    figure.savefig(output_path, dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0.05)
    with Image.open(output_path) as rendered:
        size = rendered.size
        rendered.verify()
    return size


def render_equation_image(
    expression: str,
    output_path: Path,
    *,
    color: str = "#172033",
    dpi: int = 260,
    font_size: float = 15.5,
) -> tuple[int, int]:
    """Render a safe mathematical expression into a tightly cropped PNG."""

    normalized = normalize_math_expression(expression)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(
        f"{expression}|{normalized}|{color}|{dpi}|{font_size}".encode("utf-8")
    ).hexdigest()

    try:
        with _EQUATION_RENDER_LOCK:
            cached = _EQUATION_PNG_CACHE.get(cache_key)
            if cached is not None:
                _EQUATION_PNG_CACHE.move_to_end(cache_key)
                output_path.write_bytes(cached)
            else:
                matrix_size = _render_matrix_image(
                    expression,
                    output_path,
                    color=color,
                    dpi=dpi,
                    font_size=font_size,
                )
                if matrix_size is None:
                    math_to_image(
                        f"${normalized}$",
                        str(output_path),
                        dpi=dpi,
                        format="png",
                        color=color,
                        prop=FontProperties(size=font_size),
                    )
                _EQUATION_PNG_CACHE[cache_key] = output_path.read_bytes()
                _EQUATION_PNG_CACHE.move_to_end(cache_key)
                while len(_EQUATION_PNG_CACHE) > _MAXIMUM_CACHED_EQUATIONS:
                    _EQUATION_PNG_CACHE.popitem(last=False)
    except Exception as error:
        raise EquationRenderingError("Equation could not be rendered.") from error

    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise EquationRenderingError("Equation renderer did not produce an image.")

    try:
        with Image.open(output_path) as rendered:
            width, height = rendered.size
            rendered.verify()
    except Exception as error:
        raise EquationRenderingError("Rendered equation image is invalid.") from error

    if width <= 0 or height <= 0:
        raise EquationRenderingError("Rendered equation image has invalid dimensions.")
    return width, height
