from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable


_MAXIMUM_DERIVED_CHARTS = 13


def _chart_block(
    *,
    title: str,
    description: str,
    source: str,
    columns: list[str],
    rows: list[list[object]],
    chart_type: str = "line",
) -> str:
    payload = {
        "title": title,
        "description": description,
        "source": source,
        "table": {"columns": columns, "rows": rows},
        "option": {"series": [{"type": chart_type}]},
    }
    return "```authentic-chart\n" + json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n```"


def _contains(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def _linear_cost_chart(text: str) -> str | None:
    if not _contains(r"C\s*\(\s*d\s*\)\s*=\s*80\s*\+\s*18\s*d", text):
        return None
    rows = [[distance, 80 + 18 * distance] for distance in (0, 4, 8, 12, 16, 20)]
    return _chart_block(
        title="Linear Cost Model C(d) = 80 + 18d",
        description="The straight line shows a fixed starting cost of 80 units and a constant marginal cost of 18 units per kilometre.",
        source="Derived deterministically from the user-provided linear model C(d) = 80 + 18d.",
        columns=["Distance d (km)", "Total cost C(d)"],
        rows=rows,
        chart_type="line",
    )


def _quadratic_chart(text: str) -> str | None:
    if not _contains(r"x\s*[²^]\s*[-−]\s*5\s*x\s*\+\s*6", text):
        return None
    values = [value / 2 for value in range(-2, 13)]
    rows = [[x, round(x * x - 5 * x + 6, 3)] for x in values]
    return _chart_block(
        title="Quadratic Function y = x² - 5x + 6",
        description="The parabola crosses the horizontal axis at x = 2 and x = 3; its turning point lies halfway between the roots.",
        source="Derived deterministically from x² - 5x + 6 = 0.",
        columns=["x", "y"],
        rows=rows,
        chart_type="line",
    )


def _graph_transformations_chart(text: str) -> str | None:
    if not (_contains(r"y\s*=\s*\(\s*x\s*-\s*2\s*\)\s*[²^]", text) and _contains(r"y\s*=\s*-\s*x\s*[²^]", text)):
        return None
    values = [value / 2 for value in range(-6, 13)]
    rows = [[x, x * x, (x - 2) ** 2, -(x * x)] for x in values]
    return _chart_block(
        title="Graph Transformations of the Parent Function y = x²",
        description="The comparison shows a horizontal shift to the right and a reflection across the x-axis relative to the parent parabola.",
        source="Derived from the user-provided graph-transformation examples.",
        columns=["x", "y = x²", "y = (x - 2)²", "y = -x²"],
        rows=rows,
        chart_type="line",
    )


def _exponential_growth_chart(text: str) -> str | None:
    if not _contains(r"12000\s*\(\s*1[.]04\s*\)", text):
        return None
    rows = [[year, round(12000 * (1.04 ** year), 2)] for year in range(0, 11)]
    return _chart_block(
        title="Exponential Population Growth P(t) = 12000(1.04)ᵗ",
        description="A constant four-percent growth rate produces increasingly large absolute yearly gains.",
        source="Derived from the user-provided exponential-growth model.",
        columns=["Year t", "Population P(t)"],
        rows=rows,
        chart_type="line",
    )


def _logarithm_chart(text: str) -> str | None:
    if not _contains(r"log\s*[₂_]?\s*\(?\s*32\s*\)?\s*=\s*5", text):
        return None
    x_values = [1, 2, 4, 8, 16, 32, 64]
    rows = [[x, round(math.log2(x), 4)] for x in x_values]
    return _chart_block(
        title="Base-2 Logarithm y = log₂(x)",
        description="Each doubling of x increases log₂(x) by one, illustrating the inverse relationship with powers of two.",
        source="Derived from the example log₂(32) = 5.",
        columns=["x", "log₂(x)"],
        rows=rows,
        chart_type="line",
    )


def _unit_circle_chart(text: str) -> str | None:
    if not (_contains(r"unit\s+circle", text) and _contains(r"cos\s*θ|cos\s*\(\s*θ", text)):
        return None
    angles = list(range(0, 361, 30))
    rows = [[f"{angle}°", round(math.cos(math.radians(angle)), 4), round(math.sin(math.radians(angle)), 4)] for angle in angles]
    return _chart_block(
        title="Unit Circle: Coordinates (cos θ, sin θ)",
        description="Points remain one unit from the origin while the horizontal and vertical coordinates trace cosine and sine.",
        source="Derived from the unit-circle definition in the supplied trigonometry section.",
        columns=["Angle", "cos(θ)", "sin(θ)"],
        rows=rows,
        chart_type="unit_circle",
    )


def _trigonometric_chart(text: str) -> str | None:
    if not _contains(r"sin[²^]?\s*[θt]", text) or not _contains(r"cos[²^]?\s*[θt]", text):
        return None
    angles = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360]
    rows = [[f"{angle}°", round(math.sin(math.radians(angle)), 4), round(math.cos(math.radians(angle)), 4)] for angle in angles]
    return _chart_block(
        title="Sine and Cosine Across One Full Cycle",
        description="Sine and cosine remain between -1 and 1 and are phase-shifted by ninety degrees.",
        source="Derived from the supplied trigonometric identities and unit-circle discussion.",
        columns=["Angle", "sin(θ)", "cos(θ)"],
        rows=rows,
        chart_type="line",
    )


def _derivative_tangent_chart(text: str) -> str | None:
    if not _contains(r"f\s*\(\s*x\s*\)\s*=\s*x\s*[²^]", text):
        return None
    x_values = [value / 4 for value in range(-8, 17)]
    rows = [
        [
            x,
            round(x * x, 4),
            round(3 * x - 2, 4),
            round(4 * x - 4, 4),
        ]
        for x in x_values
    ]
    return _chart_block(
        title="Secant-to-Tangent View of f(x) = x² at x = 2",
        description="The secant through x = 1 and x = 2 has slope 3, while the tangent at x = 2 has slope f′(2) = 4. This visualises how secant slopes approach the derivative.",
        source="Derived from the first-principles derivative of f(x) = x².",
        columns=["x", "f(x) = x²", "Secant y = 3x - 2", "Tangent y = 4x - 4"],
        rows=rows,
        chart_type="line",
    )


def _integral_area_chart(text: str) -> str | None:
    if not _contains(r"∫\s*[₀0].*[²2]\s*x[²^]", text):
        return None
    values = [round(index * 0.1, 1) for index in range(0, 21)]
    rows = [[x, round(x * x, 4)] for x in values]
    return _chart_block(
        title="Signed Area for ∫₀² x² dx",
        description="The shaded region represents the accumulated positive area under y = x² from x = 0 to x = 2, equal to 8/3.",
        source="Derived from the supplied definite-integral example.",
        columns=["x", "y = x²"],
        rows=rows,
        chart_type="area",
    )


def _direction_field_chart(text: str) -> str | None:
    if not _contains(r"dy\s*/\s*dx\s*=\s*k\s*y", text):
        return None
    rows: list[list[object]] = []
    for x in (-2, -1, 0, 1, 2):
        for y in (-2, -1, 0, 1, 2):
            rows.append([f"{x},{y}", y])
    return _chart_block(
        title="Direction Field for dy/dx = y",
        description="Short line segments show positive slopes above the x-axis, zero slope on the axis, and negative slopes below it.",
        source="Derived from the supplied separable differential-equation model dy/dx = ky using k = 1 for visualisation.",
        columns=["Point (x,y)", "Slope dy/dx"],
        rows=rows,
        chart_type="slope_field",
    )


def _fair_die_chart(text: str) -> str | None:
    if not (_contains(r"fair\s+six-sided\s+die", text) or _contains(r"X\s*∈\s*\{1,\s*2,\s*3", text)):
        return None
    rows = [[face, round(1 / 6, 6)] for face in range(1, 7)]
    return _chart_block(
        title="Fair Die Probability Distribution",
        description="Each face has equal probability 1/6, while the expected value is 3.5.",
        source="Derived from the supplied fair-die random-variable example.",
        columns=["Die face", "Probability"],
        rows=rows,
        chart_type="bar",
    )


def _statistics_chart(text: str) -> str | None:
    if not _contains(r"2\s*,\s*4\s*,\s*4\s*,\s*6\s*,\s*9", text):
        return None
    counts = {2: 1, 4: 2, 6: 1, 9: 1}
    rows = [[value, frequency] for value, frequency in counts.items()]
    return _chart_block(
        title="Frequency Distribution for the Dataset 2, 4, 4, 6, 9",
        description="The value 4 occurs twice, while 2, 6 and 9 each occur once.",
        source="Derived from the descriptive-statistics dataset in the source.",
        columns=["Value", "Frequency"],
        rows=rows,
        chart_type="bar",
    )


def _regression_chart(text: str) -> str | None:
    if not _contains(r"y\s*=\s*12\s*\+\s*3\s*x", text):
        return None
    observed_offsets = [0.2, -0.4, 0.5, -0.3, 0.1, 0.6, -0.2, 0.3, -0.5, 0.4, 0.0]
    rows = [[x, round(12 + 3 * x + observed_offsets[x], 2), 12 + 3 * x] for x in range(0, 11)]
    return _chart_block(
        title="Regression Example: Observations and Fitted Line y = 12 + 3x",
        description="The fitted line increases by three units for each one-unit increase in x; nearby deterministic points illustrate residuals.",
        source="Derived from the supplied regression equation y = 12 + 3x; illustrative residuals are deterministic and explicitly labelled.",
        columns=["x", "Illustrative observation", "Fitted y"],
        rows=rows,
        chart_type="scatter",
    )


def derive_supported_chart_blocks(source_text: str) -> tuple[str, ...]:
    builders: Iterable = (
        _linear_cost_chart,
        _quadratic_chart,
        _graph_transformations_chart,
        _exponential_growth_chart,
        _logarithm_chart,
        _unit_circle_chart,
        _trigonometric_chart,
        _derivative_tangent_chart,
        _integral_area_chart,
        _direction_field_chart,
        _fair_die_chart,
        _statistics_chart,
        _regression_chart,
    )
    blocks: list[str] = []
    for builder in builders:
        block = builder(source_text)
        if block is not None:
            blocks.append(block)
        if len(blocks) >= _MAXIMUM_DERIVED_CHARTS:
            break
    return tuple(blocks)
