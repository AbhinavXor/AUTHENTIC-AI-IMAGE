from __future__ import annotations

import ast
import json
import math
import re
from dataclasses import dataclass
from typing import Any

from ai.deterministic_math import (
    extract_equation_graph_expression,
    normalize_spoken_math,
)
from ai.math_contract import wants_math_response
from ai.visualization_contract import wants_visualization
from ai.visualization_need import assess_visualization_need


_CHART_BLOCK = re.compile(
    r"```authentic-chart\s*[\s\S]*?```",
    re.IGNORECASE,
)

_LABEL_VALUE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9 &/_().-]{0,70})"
    r"\s*(?:=|:)\s*"
    r"([-+]?(?:\d+(?:\.\d+)?|\.\d+))"
    r"\s*(%?)\s*$"
)

_FLOW = re.compile(
    r"^\s*(.{1,80}?)\s*(?:->|→)\s*(.{1,80}?)"
    r"\s*(?:=|:)\s*"
    r"([-+]?(?:\d+(?:\.\d+)?|\.\d+))\s*$"
)

_FUNCTION = re.compile(
    r"(?im)\b([fgh]\s*\(\s*x\s*\)|y)\s*=\s*"
    r"([^\n;,]{1,300})"
)

_DOMAIN = re.compile(
    r"([-+]?(?:\d+(?:\.\d+)?|\.\d+))"
    r"\s*(?:<=|≤)\s*x\s*(?:<=|≤)\s*"
    r"([-+]?(?:\d+(?:\.\d+)?|\.\d+))",
    re.IGNORECASE,
)

_FROM_TO = re.compile(
    r"\b(?:from|between)\s+"
    r"([-+]?(?:\d+(?:\.\d+)?|\.\d+))"
    r"\s+(?:to|and)\s+"
    r"([-+]?(?:\d+(?:\.\d+)?|\.\d+))",
    re.IGNORECASE,
)

_TIME_WORDS = (
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "annual",
    "yearly",
    "trend",
    "timeline",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
)

_PART_WORDS = (
    "market share",
    "share breakdown",
    "composition",
    "distribution",
    "proportion",
    "revenue mix",
)

_ALLOWED_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "log": math.log,
    "exp": math.exp,
    "abs": abs,
}

_ALLOWED_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


@dataclass(frozen=True, slots=True)
class DeterministicVisualization:
    chart_type: str
    specification: dict[str, Any]
    reason: str

    def to_block(self) -> str:
        return (
            "```authentic-chart\n"
            + json.dumps(
                self.specification,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n```"
        )


def _finite_number(value: float) -> int | float:
    if not math.isfinite(value):
        raise ValueError("Non-finite chart value.")

    rounded = round(value)

    if math.isclose(
        value,
        rounded,
        rel_tol=0,
        abs_tol=1e-10,
    ):
        return int(rounded)

    return round(value, 10)


def _base_spec(
    *,
    title: str,
    description: str,
    alt_text: str,
    source: str,
    option: dict[str, Any],
    columns: list[str],
    rows: list[list[Any]],
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "version": "1.0",
        "title": title,
        "description": description,
        "alt_text": alt_text,
        "source": source,
        "timestamp": None,
        "estimated": False,
        "limitations": limitations or [],
        "option": option,
        "table": {
            "columns": columns,
            "rows": rows[:1000],
        },
    }


def _lines(message: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in message.replace(";", "\n").splitlines()
        if line.strip()
    )


def _labelled_values(
    message: str,
) -> tuple[tuple[str, float, bool], ...]:
    result: list[tuple[str, float, bool]] = []

    for line in _lines(message):
        match = _LABEL_VALUE.fullmatch(line)

        if match is None:
            continue

        label = " ".join(match.group(1).split())
        value = float(match.group(2))
        is_percent = bool(match.group(3))

        if label.lower() in {
            "x",
            "y",
            "f(x)",
            "g(x)",
            "h(x)",
        }:
            continue

        if math.isfinite(value):
            result.append(
                (
                    label,
                    value,
                    is_percent,
                )
            )

    if not 2 <= len(result) <= 200:
        return ()

    return tuple(result)


def _choose_labelled_type(
    message: str,
    values: tuple[tuple[str, float, bool], ...],
) -> str:
    normalized = " ".join(message.lower().split())
    decision = assess_visualization_need(message)

    has_percent = any(
        is_percent
        for _, _, is_percent in values
    )

    if (
        (
            has_percent
            or "pie" in decision.suggested_types
            or any(
                term in normalized
                for term in _PART_WORDS
            )
        )
        and all(
            value >= 0
            for _, value, _ in values
        )
        and sum(
            value
            for _, value, _ in values
        ) > 0
    ):
        return "pie"

    if (
        "line" in decision.suggested_types
        or any(
            re.search(
                rf"\b{re.escape(term)}\b",
                normalized,
            )
            for term in _TIME_WORDS
        )
    ):
        return "line"

    return "bar"


def _build_labelled(
    message: str,
) -> DeterministicVisualization | None:
    values = _labelled_values(message)

    if not values:
        return None

    chart_type = _choose_labelled_type(
        message,
        values,
    )

    labels = [
        label
        for label, _, _ in values
    ]

    numbers = [
        _finite_number(value)
        for _, value, _ in values
    ]

    value_name = (
        "Percent"
        if any(
            is_percent
            for _, _, is_percent in values
        )
        else "Value"
    )

    rows = [
        [
            label,
            _finite_number(value),
        ]
        for label, value, _ in values
    ]

    if chart_type == "pie":
        option = {
            "tooltip": {
                "trigger": "item",
            },
            "legend": {
                "type": "scroll",
                "bottom": 0,
            },
            "series": [
                {
                    "name": value_name,
                    "type": "pie",
                    "radius": [
                        "38%",
                        "68%",
                    ],
                    "data": [
                        {
                            "name": label,
                            "value": value,
                        }
                        for label, value in zip(
                            labels,
                            numbers,
                            strict=True,
                        )
                    ],
                }
            ],
        }

        title = "Distribution of supplied values"

    else:
        option = {
            "tooltip": {
                "trigger": "axis",
            },
            "xAxis": {
                "type": "category",
                "name": "Category",
                "data": labels,
                "axisLabel": {
                    "interval": 0,
                    "rotate": (
                        28
                        if len(labels) > 6
                        else 0
                    ),
                },
            },
            "yAxis": {
                "type": "value",
                "name": value_name,
            },
            "series": [
                {
                    "name": value_name,
                    "type": chart_type,
                    "smooth": chart_type == "line",
                    "data": numbers,
                }
            ],
        }

        title = (
            "Trend in supplied values"
            if chart_type == "line"
            else "Comparison of supplied values"
        )

    specification = _base_spec(
        title=title,
        description=(
            "Generated deterministically from "
            "user-provided numeric data."
        ),
        alt_text=(
            f"A {chart_type} chart containing "
            f"{len(values)} supplied values."
        ),
        source="User-provided data",
        option=option,
        columns=[
            "Category",
            value_name,
        ],
        rows=rows,
    )

    return DeterministicVisualization(
        chart_type=chart_type,
        specification=specification,
        reason=(
            "Structured labelled data "
            "was parsed locally."
        ),
    )


def _build_sankey(
    message: str,
) -> DeterministicVisualization | None:
    links: list[tuple[str, str, float]] = []

    for line in _lines(message):
        match = _FLOW.fullmatch(line)

        if match is None:
            continue

        source = " ".join(
            match.group(1).split()
        )

        target = " ".join(
            match.group(2).split()
        )

        value = float(match.group(3))

        if (
            source
            and target
            and source != target
            and math.isfinite(value)
            and value >= 0
        ):
            links.append(
                (
                    source,
                    target,
                    value,
                )
            )

    if not 2 <= len(links) <= 300:
        return None

    nodes = sorted(
        {
            node
            for source, target, _ in links
            for node in (
                source,
                target,
            )
        }
    )

    specification = _base_spec(
        title="Flow between stages",
        description=(
            "Generated deterministically from "
            "user-provided flow data."
        ),
        alt_text=(
            f"A Sankey diagram with "
            f"{len(nodes)} stages and "
            f"{len(links)} connections."
        ),
        source="User-provided flow data",
        option={
            "tooltip": {
                "trigger": "item",
            },
            "series": [
                {
                    "name": "Flow",
                    "type": "sankey",
                    "data": [
                        {
                            "name": node,
                        }
                        for node in nodes
                    ],
                    "links": [
                        {
                            "source": source,
                            "target": target,
                            "value": _finite_number(value),
                        }
                        for source, target, value in links
                    ],
                    "emphasis": {
                        "focus": "adjacency",
                    },
                }
            ],
        },
        columns=[
            "Source",
            "Target",
            "Value",
        ],
        rows=[
            [
                source,
                target,
                _finite_number(value),
            ]
            for source, target, value in links
        ],
    )

    return DeterministicVisualization(
        chart_type="sankey",
        specification=specification,
        reason=(
            "Flow edges were parsed locally."
        ),
    )


def _normalize_expression(
    expression: str,
) -> str:
    result = (
        normalize_spoken_math(
            expression
        ).strip()
        .replace("−", "-")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("π", "pi")
        .replace("²", "**2")
        .replace("³", "**3")
        .replace("^", "**")
    )

    result = re.split(
        (
            r"\s*[.!?]\s+"
            r"(?=(?:find|explain|analy[sz]e|determine|identify|"
            r"calculate|evaluate|show|state|use|plot|graph|"
            r"describe|classify)\b)"
        ),
        result,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    result = re.split(
        r"\s+(?:for|from|between|over)\s+"
        r"(?=[-+]?\d|x\b)",
        result,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip().rstrip(".")

    result = re.sub(
        r"\bln\s*\(",
        "log(",
        result,
        flags=re.IGNORECASE,
    )

    result = re.sub(
        r"(?<=\d)(?=[A-Za-z(])",
        "*",
        result,
    )

    result = re.sub(
        r"(?<=\))(?=[A-Za-z0-9(])",
        "*",
        result,
    )

    return result


def _validate_tree(
    tree: ast.AST,
) -> None:
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.UAdd,
        ast.USub,
    )

    nodes = list(ast.walk(tree))

    if len(nodes) > 100:
        raise ValueError(
            "Expression too complex."
        )

    for node in nodes:
        if not isinstance(node, allowed):
            raise ValueError(
                "Unsafe expression."
            )

        if isinstance(node, ast.Name):
            if (
                node.id != "x"
                and node.id not in _ALLOWED_CONSTANTS
                and node.id not in _ALLOWED_FUNCTIONS
            ):
                raise ValueError(
                    "Unsupported name."
                )

        if isinstance(node, ast.Call):
            if (
                not isinstance(node.func, ast.Name)
                or node.func.id
                not in _ALLOWED_FUNCTIONS
                or node.keywords
                or len(node.args) != 1
            ):
                raise ValueError(
                    "Unsafe function call."
                )


def _evaluate(
    node: ast.AST,
    x_value: float,
) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(
            node.body,
            x_value,
        )

    if isinstance(node, ast.Constant):
        if not isinstance(
            node.value,
            (int, float),
        ):
            raise ValueError

        return float(node.value)

    if isinstance(node, ast.Name):
        if node.id == "x":
            return x_value

        return _ALLOWED_CONSTANTS[node.id]

    if isinstance(node, ast.UnaryOp):
        value = _evaluate(
            node.operand,
            x_value,
        )

        if isinstance(node.op, ast.USub):
            return -value

        return value

    if isinstance(node, ast.BinOp):
        left = _evaluate(
            node.left,
            x_value,
        )

        right = _evaluate(
            node.right,
            x_value,
        )

        if isinstance(node.op, ast.Add):
            return left + right

        if isinstance(node.op, ast.Sub):
            return left - right

        if isinstance(node.op, ast.Mult):
            return left * right

        if isinstance(node.op, ast.Div):
            return left / right

        if isinstance(node.op, ast.Pow):
            if abs(right) > 20:
                raise ValueError(
                    "Exponent too large."
                )

            return left**right

    if isinstance(node, ast.Call):
        function = _ALLOWED_FUNCTIONS[
            node.func.id
        ]

        arguments = [
            _evaluate(
                argument,
                x_value,
            )
            for argument in node.args
        ]

        return float(
            function(*arguments)
        )

    raise ValueError(
        "Unsupported expression."
    )


def _extract_domain(
    message: str,
) -> tuple[float, float]:
    match = (
        _DOMAIN.search(message)
        or _FROM_TO.search(message)
    )

    if match is None:
        return (
            -10.0,
            10.0,
        )

    minimum = float(match.group(1))
    maximum = float(match.group(2))

    if (
        not math.isfinite(minimum)
        or not math.isfinite(maximum)
        or minimum >= maximum
    ):
        return (
            -10.0,
            10.0,
        )

    return (
        max(minimum, -10000.0),
        min(maximum, 10000.0),
    )


def _build_function(
    message: str,
) -> DeterministicVisualization | None:
    normalized_message = (
        normalize_spoken_math(
            message
        )
    )

    match = _FUNCTION.search(
        normalized_message
    )

    if match is not None:
        function_name = re.sub(
            r"\s+",
            "",
            match.group(1),
        )

        raw_expression = (
            match.group(2).strip()
        )
    else:
        raw_expression = (
            extract_equation_graph_expression(
                normalized_message
            )
        )

        if raw_expression is None:
            return None

        function_name = "y"

    expression = _normalize_expression(
        raw_expression
    )

    if not expression:
        return None

    try:
        tree = ast.parse(
            expression,
            mode="eval",
        )

        _validate_tree(tree)

    except (
        SyntaxError,
        ValueError,
    ):
        return None

    minimum, maximum = _extract_domain(
        message
    )

    sample_count = 201
    step = (
        maximum - minimum
    ) / (
        sample_count - 1
    )

    points: list[list[Any]] = []

    for index in range(sample_count):
        x_value = (
            minimum
            + index * step
        )

        try:
            y_value = _evaluate(
                tree,
                x_value,
            )

            if (
                not math.isfinite(y_value)
                or abs(y_value) > 1e12
            ):
                y_result = None
            else:
                y_result = _finite_number(
                    y_value
                )

        except (
            ArithmeticError,
            OverflowError,
            TypeError,
            ValueError,
        ):
            y_result = None

        points.append(
            [
                _finite_number(x_value),
                y_result,
            ]
        )

    if not any(
        point[1] is not None
        for point in points
    ):
        return None

    specification = _base_spec(
        title=(
            f"Graph of {function_name} = "
            f"{raw_expression}"
        ),
        description=(
            f"Generated locally from {sample_count} "
            "deterministic sample points."
        ),
        alt_text=(
            f"A line graph of {function_name} "
            f"from {_finite_number(minimum)} "
            f"to {_finite_number(maximum)}."
        ),
        source=(
            "Deterministically calculated from "
            "the user's equation"
        ),
        option={
            "animation": False,
            "tooltip": {
                "trigger": "axis",
            },
            "xAxis": {
                "type": "value",
                "name": "x",
                "min": _finite_number(
                    minimum
                ),
                "max": _finite_number(
                    maximum
                ),
            },
            "yAxis": {
                "type": "value",
                "name": function_name,
                "scale": True,
            },
            "series": [
                {
                    "name": function_name,
                    "type": "line",
                    "showSymbol": False,
                    "connectNulls": False,
                    "sampling": "lttb",
                    "data": points,
                }
            ],
        },
        columns=[
            "x",
            function_name,
        ],
        rows=points,
        limitations=[
            (
                "Undefined or non-finite values "
                "are shown as gaps."
            )
        ],
    )

    return DeterministicVisualization(
        chart_type="line",
        specification=specification,
        reason=(
            "Mathematical function sampled locally."
        ),
    )


def build_deterministic_visualization(
    message: str,
) -> DeterministicVisualization | None:
    if not message.strip():
        return None

    explicit_visualization = (
        wants_visualization(message)
    )

    automatic_visualization = (
        assess_visualization_need(
            message
        )
    )

    if (
        not explicit_visualization
        and not automatic_visualization.should_render
    ):
        return None

    return (
        _build_sankey(message)
        or _build_labelled(message)
        or _build_function(message)
    )


def remove_provider_chart_blocks(
    content: str,
) -> str:
    return (
        _CHART_BLOCK
        .sub(
            "",
            content,
        )
        .strip()
    )


_VISUALIZATION_SLOT = (
    "<!--AUTHENTIC_VISUALIZATION_SLOT-->"
)

_GRAPH_HEADING = re.compile(
    r"(?im)^##\s+"
    r"(?:Graph(?:\s+and\s+Interpretation)?|Visualization)"
    r"\s*$"
)

_VERIFICATION_HEADING = re.compile(
    r"(?im)^##\s+Verification\s*$"
)


def _insert_visualization_at_semantic_position(
    *,
    message: str,
    cleaned_answer: str,
    chart_block: str,
) -> str:
    slot_count = cleaned_answer.count(
        _VISUALIZATION_SLOT
    )

    if slot_count:
        result = cleaned_answer.replace(
            _VISUALIZATION_SLOT,
            chart_block,
            1,
        )

        result = result.replace(
            _VISUALIZATION_SLOT,
            "",
        )

        return result.strip()

    if wants_math_response(message):
        graph_heading = (
            _GRAPH_HEADING.search(
                cleaned_answer
            )
        )

        if graph_heading is not None:
            return (
                cleaned_answer[
                    :graph_heading.end()
                ].rstrip()
                + "\n\n"
                + chart_block
                + "\n\n"
                + cleaned_answer[
                    graph_heading.end():
                ].lstrip()
            ).strip()

        verification_heading = (
            _VERIFICATION_HEADING.search(
                cleaned_answer
            )
        )

        graph_section = (
            "## Graph and Interpretation\n\n"
            f"{chart_block}"
        )

        if verification_heading is not None:
            return (
                cleaned_answer[
                    :verification_heading.start()
                ].rstrip()
                + "\n\n"
                + graph_section
                + "\n\n"
                + cleaned_answer[
                    verification_heading.start():
                ].lstrip()
            ).strip()

        return (
            f"{cleaned_answer.rstrip()}\n\n"
            f"{graph_section}"
        ).strip()

    if wants_visualization(message):
        return (
            f"{chart_block}\n\n"
            f"{cleaned_answer}"
        ).strip()

    return (
        f"{cleaned_answer}\n\n"
        f"{chart_block}"
    ).strip()


_VISUALIZATION_SLOT = (
    "<!--AUTHENTIC_VISUALIZATION_SLOT-->"
)

_GRAPH_HEADING = re.compile(
    r"(?im)^##\s+"
    r"(?:Graph(?:\s+and\s+Interpretation)?|Visualization)"
    r"\s*$"
)

_VERIFICATION_HEADING = re.compile(
    r"(?im)^##\s+Verification\s*$"
)


def _insert_visualization_at_semantic_position(
    *,
    message: str,
    cleaned_answer: str,
    chart_block: str,
) -> str:
    slot_count = cleaned_answer.count(
        _VISUALIZATION_SLOT
    )

    if slot_count:
        result = cleaned_answer.replace(
            _VISUALIZATION_SLOT,
            chart_block,
            1,
        )

        result = result.replace(
            _VISUALIZATION_SLOT,
            "",
        )

        return result.strip()

    if wants_math_response(message):
        graph_heading = (
            _GRAPH_HEADING.search(
                cleaned_answer
            )
        )

        if graph_heading is not None:
            return (
                cleaned_answer[
                    :graph_heading.end()
                ].rstrip()
                + "\n\n"
                + chart_block
                + "\n\n"
                + cleaned_answer[
                    graph_heading.end():
                ].lstrip()
            ).strip()

        verification_heading = (
            _VERIFICATION_HEADING.search(
                cleaned_answer
            )
        )

        graph_section = (
            "## Graph and Interpretation\n\n"
            f"{chart_block}"
        )

        if verification_heading is not None:
            return (
                cleaned_answer[
                    :verification_heading.start()
                ].rstrip()
                + "\n\n"
                + graph_section
                + "\n\n"
                + cleaned_answer[
                    verification_heading.start():
                ].lstrip()
            ).strip()

        return (
            f"{cleaned_answer.rstrip()}\n\n"
            f"{graph_section}"
        ).strip()

    if wants_visualization(message):
        return (
            f"{chart_block}\n\n"
            f"{cleaned_answer}"
        ).strip()

    return (
        f"{cleaned_answer}\n\n"
        f"{chart_block}"
    ).strip()


_VISUALIZATION_SLOT = (
    "<!--AUTHENTIC_VISUALIZATION_SLOT-->"
)

_GRAPH_HEADING = re.compile(
    r"(?im)^##\s+"
    r"(?:Graph(?:\s+and\s+Interpretation)?|Visualization)"
    r"\s*$"
)

_VERIFICATION_HEADING = re.compile(
    r"(?im)^##\s+Verification\s*$"
)


def _insert_visualization_at_semantic_position(
    *,
    message: str,
    cleaned_answer: str,
    chart_block: str,
) -> str:
    slot_count = cleaned_answer.count(
        _VISUALIZATION_SLOT
    )

    if slot_count:
        result = cleaned_answer.replace(
            _VISUALIZATION_SLOT,
            chart_block,
            1,
        )

        result = result.replace(
            _VISUALIZATION_SLOT,
            "",
        )

        return result.strip()

    if wants_math_response(message):
        graph_heading = (
            _GRAPH_HEADING.search(
                cleaned_answer
            )
        )

        if graph_heading is not None:
            return (
                cleaned_answer[
                    :graph_heading.end()
                ].rstrip()
                + "\n\n"
                + chart_block
                + "\n\n"
                + cleaned_answer[
                    graph_heading.end():
                ].lstrip()
            ).strip()

        verification_heading = (
            _VERIFICATION_HEADING.search(
                cleaned_answer
            )
        )

        graph_section = (
            "## Graph and Interpretation\n\n"
            f"{chart_block}"
        )

        if verification_heading is not None:
            return (
                cleaned_answer[
                    :verification_heading.start()
                ].rstrip()
                + "\n\n"
                + graph_section
                + "\n\n"
                + cleaned_answer[
                    verification_heading.start():
                ].lstrip()
            ).strip()

        return (
            f"{cleaned_answer.rstrip()}\n\n"
            f"{graph_section}"
        ).strip()

    if wants_visualization(message):
        return (
            f"{chart_block}\n\n"
            f"{cleaned_answer}"
        ).strip()

    return (
        f"{cleaned_answer}\n\n"
        f"{chart_block}"
    ).strip()


def attach_deterministic_visualization(
    *,
    message: str,
    provider_answer: str,
) -> str:
    visualization = (
        build_deterministic_visualization(
            message
        )
    )

    cleaned_answer = (
        remove_provider_chart_blocks(
            provider_answer
        )
    )

    if visualization is None:
        return (
            cleaned_answer.replace(
                _VISUALIZATION_SLOT,
                "",
            ).strip()
        )

    chart_block = (
        visualization.to_block()
    )

    return (
        _insert_visualization_at_semantic_position(
            message=message,
            cleaned_answer=cleaned_answer,
            chart_block=chart_block,
        )
    )
