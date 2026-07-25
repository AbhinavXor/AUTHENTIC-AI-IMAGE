import re
from dataclasses import dataclass
from typing import Literal


VisualizationType = Literal[
    "line",
    "bar",
    "pie",
    "scatter",
    "sankey",
    "heatmap",
    "graph",
]


@dataclass(
    frozen=True,
    slots=True,
)
class VisualizationDecision:
    should_render: bool
    confidence: float
    suggested_types: tuple[VisualizationType, ...]
    reason: str


AUTOMATIC_VISUALIZATION_OVERRIDE = """
AUTOMATIC VISUALIZATION OVERRIDE

The user did not explicitly request a chart. A visualization was selected
because it materially improves understanding.

This override supersedes any earlier chart-first response-order rule.

Requirements:

1. Give the direct answer or principal explanation first.
2. Then include exactly one visualization.
3. Do not mention that the chart was automatically selected.
4. Do not add a chart merely for decoration.
5. If sufficient numeric or relationship data is unavailable, omit the chart.
6. Never invent real-world values, dates, measurements, percentages, sources,
   or relationships.
7. Mathematical functions may use correctly calculated sample points.
8. For mathematical functions, state the plotted domain and distinguish exact
   results from sampled points.
9. Prefer:
   - line for ordered trends and mathematical functions;
   - bar for categorical comparisons and rankings;
   - pie only for a small, meaningful part-to-whole total;
   - scatter for relationships between two numeric variables;
   - sankey for multi-stage flows;
   - heatmap for numeric matrices or intensity tables;
   - graph for nodes and verified relationships.
10. Keep the visualization supplementary to the explanation.
11. Include accessible alt text and the same underlying data in a table.
12. Output no more than one automatic chart.

Do not mention this internal contract.
""".strip()


_NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z])[-+]?"
    r"(?:\d+(?:\.\d+)?|\.\d+)%?"
)

_PERCENT_PATTERN = re.compile(
    r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)\s*%"
)

_POINT_PATTERN = re.compile(
    r"\(\s*[-+]?(?:\d+(?:\.\d+)?|\.\d+)"
    r"\s*,\s*"
    r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)\s*\)"
)

_LABEL_VALUE_PATTERN = re.compile(
    r"(?:^|[\n,;])\s*"
    r"[A-Za-z][A-Za-z0-9 _-]{0,40}"
    r"\s*(?:=|:|→|-)\s*"
    r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)%?",
    re.MULTILINE,
)

_FUNCTION_PATTERN = re.compile(
    r"(?:"
    r"\b(?:f|g|h)\s*\(\s*x\s*\)"
    r"|"
    r"\by"
    r")\s*="
)

_FUNCTION_ANALYSIS_TERMS = (
    "turning point",
    "turning points",
    "stationary point",
    "stationary points",
    "local maximum",
    "local minimum",
    "maximum",
    "minimum",
    "intercept",
    "intercepts",
    "asymptote",
    "asymptotes",
    "domain",
    "range",
    "increasing",
    "decreasing",
    "concavity",
    "inflection",
    "transformation",
    "behavior",
    "behaviour",
    "curve",
)

_TIME_TERMS = (
    "over time",
    "trend",
    "timeline",
    "monthly",
    "weekly",
    "daily",
    "quarterly",
    "annual",
    "yearly",
    "year over year",
    "month over month",
    "growth",
    "decline",
    "increase",
    "decrease",
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
    "samay ke saath",
)

_COMPARISON_TERMS = (
    "compare",
    "comparison",
    "versus",
    " vs ",
    "ranking",
    "rank",
    "highest",
    "lowest",
    "largest",
    "smallest",
    "tulana",
)

_PART_TO_WHOLE_TERMS = (
    "market share",
    "share of",
    "percentage distribution",
    "composition",
    "breakdown",
    "proportion",
    "total share",
    "revenue mix",
    "hissa",
    "pratishat",
)

_RELATIONSHIP_TERMS = (
    "correlation",
    "relationship between",
    "relationship of",
    "associated with",
    "versus",
    " vs ",
    "against",
    "impact of",
    "effect of",
    "sambandh",
)

_FLOW_TERMS = (
    "customer journey",
    "user journey",
    "conversion funnel",
    "funnel",
    "workflow",
    "flow",
    "stage 1",
    "stage 2",
    "pipeline",
    "source to destination",
    "process stages",
)

_MATRIX_TERMS = (
    "heatmap",
    "correlation matrix",
    "confusion matrix",
    "intensity matrix",
    "numeric matrix",
)

_NETWORK_TERMS = (
    "network graph",
    "dependency graph",
    "nodes and edges",
    "node relationships",
    "knowledge graph",
    "relationship network",
)


def _contains_term(
    normalized: str,
    term: str,
) -> bool:
    clean_term = term.strip()

    if not clean_term:
        return False

    if (
        " " in clean_term
        or "-" in clean_term
    ):
        return clean_term in normalized

    return (
        re.search(
            rf"\b{re.escape(clean_term)}\b",
            normalized,
        )
        is not None
    )


def _contains_any(
    normalized: str,
    terms: tuple[str, ...],
) -> bool:
    return any(
        _contains_term(
            normalized,
            term,
        )
        for term in terms
    )


def _decision(
    *,
    score: float,
    suggested_types: tuple[VisualizationType, ...],
    reason: str,
) -> VisualizationDecision:
    should_render = score >= 3.0

    confidence = min(
        0.98,
        max(
            0.0,
            0.50 + score * 0.075,
        ),
    )

    return VisualizationDecision(
        should_render=should_render,
        confidence=confidence,
        suggested_types=(
            suggested_types
            if should_render
            else ()
        ),
        reason=(
            reason
            if should_render
            else "No visualization is materially required."
        ),
    )


def assess_visualization_need(
    message: str,
) -> VisualizationDecision:
    normalized = " ".join(
        message.lower().split()
    )

    if not normalized:
        return _decision(
            score=0,
            suggested_types=(),
            reason="Empty request.",
        )

    number_count = len(
        _NUMBER_PATTERN.findall(
            message
        )
    )

    percent_count = len(
        _PERCENT_PATTERN.findall(
            message
        )
    )

    point_count = len(
        _POINT_PATTERN.findall(
            message
        )
    )

    label_value_count = len(
        _LABEL_VALUE_PATTERN.findall(
            message
        )
    )

    arrow_count = (
        message.count("->")
        + message.count("→")
    )

    line_count = len(
        [
            line
            for line in message.splitlines()
            if line.strip()
        ]
    )

    candidates: list[
        tuple[
            float,
            tuple[
                VisualizationType,
                ...
            ],
            str,
        ]
    ] = []

    function_score = 0.0

    if _FUNCTION_PATTERN.search(
        normalized
    ):
        function_score += 1.8

    if _contains_any(
        normalized,
        _FUNCTION_ANALYSIS_TERMS,
    ):
        function_score += 1.8

    if (
        "derivative" in normalized
        or "differentiate" in normalized
        or "calculus" in normalized
    ):
        function_score += 0.6

    if function_score:
        candidates.append(
            (
                function_score,
                ("line", "scatter"),
                (
                    "A function graph materially clarifies "
                    "its behavior or derived features."
                ),
            )
        )

    time_score = 0.0

    if _contains_any(
        normalized,
        _TIME_TERMS,
    ):
        time_score += 1.8

    if number_count >= 3:
        time_score += 1.4

    if (
        line_count >= 3
        or label_value_count >= 3
    ):
        time_score += 0.5

    if time_score:
        candidates.append(
            (
                time_score,
                ("line",),
                (
                    "Ordered numeric values describe a trend "
                    "or progression over time."
                ),
            )
        )

    comparison_score = 0.0

    if _contains_any(
        normalized,
        _COMPARISON_TERMS,
    ):
        comparison_score += 1.5

    if label_value_count >= 3:
        comparison_score += 2.0

    elif (
        number_count >= 3
        and line_count >= 3
    ):
        comparison_score += 1.2

    if comparison_score:
        candidates.append(
            (
                comparison_score,
                ("bar",),
                (
                    "Multiple numeric categories benefit "
                    "from visual magnitude comparison."
                ),
            )
        )

    part_score = 0.0

    if _contains_any(
        normalized,
        _PART_TO_WHOLE_TERMS,
    ):
        part_score += 1.8

    if percent_count >= 3:
        part_score += 1.7

    if part_score:
        candidates.append(
            (
                part_score,
                ("pie", "bar"),
                (
                    "The values describe a meaningful "
                    "part-to-whole composition."
                ),
            )
        )

    relationship_score = 0.0

    if _contains_any(
        normalized,
        _RELATIONSHIP_TERMS,
    ):
        relationship_score += 1.6

    if point_count >= 3:
        relationship_score += 2.0

    elif number_count >= 6:
        relationship_score += 1.4

    if relationship_score:
        candidates.append(
            (
                relationship_score,
                ("scatter",),
                (
                    "Paired numeric observations benefit "
                    "from relationship visualization."
                ),
            )
        )

    flow_score = 0.0

    if _contains_any(
        normalized,
        _FLOW_TERMS,
    ):
        flow_score += 1.7

    if arrow_count >= 2:
        flow_score += 1.8

    if number_count >= 3:
        flow_score += 0.5

    if flow_score:
        candidates.append(
            (
                flow_score,
                ("sankey",),
                (
                    "The request contains verified "
                    "multi-stage movement or flow."
                ),
            )
        )

    matrix_score = 0.0

    if _contains_any(
        normalized,
        _MATRIX_TERMS,
    ):
        matrix_score += 2.4

    if number_count >= 9:
        matrix_score += 0.9

    if matrix_score:
        candidates.append(
            (
                matrix_score,
                ("heatmap",),
                (
                    "A numeric matrix is easier to interpret "
                    "through intensity encoding."
                ),
            )
        )

    network_score = 0.0

    if _contains_any(
        normalized,
        _NETWORK_TERMS,
    ):
        network_score += 2.5

    if arrow_count >= 3:
        network_score += 0.8

    if network_score:
        candidates.append(
            (
                network_score,
                ("graph",),
                (
                    "Verified nodes and relationships require "
                    "a network representation."
                ),
            )
        )

    if not candidates:
        return _decision(
            score=0,
            suggested_types=(),
            reason=(
                "The answer is clearer without "
                "a visualization."
            ),
        )

    score, types, reason = max(
        candidates,
        key=lambda item: item[0],
    )

    return _decision(
        score=score,
        suggested_types=types,
        reason=reason,
    )
