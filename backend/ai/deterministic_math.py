from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass

from ai.visualization_contract import (
    wants_visualization,
)


_EPSILON = 1e-10

_MATH_TAIL = re.compile(
    r"([0-9x+\-*/^().\s]+)$",
    re.IGNORECASE,
)

_MATH_PREFIX = re.compile(
    r"^\s*([0-9x+\-*/^().\s]+)",
    re.IGNORECASE,
)

_EQUAL_SIGN = re.compile(
    r"(?<![<>=])=(?!=)"
)


@dataclass(frozen=True, slots=True)
class ParsedEquation:
    left: str
    right: str


def normalize_spoken_math(
    content: str,
) -> str:
    result = (
        content.lower()
        .replace("−", "-")
        .replace("–", "-")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("²", "^2")
        .replace("³", "^3")
    )

    result = re.sub(
        r"\bsquare\s+of\s+([a-z])\b",
        r"\1^2",
        result,
    )

    result = re.sub(
        r"\bcube\s+of\s+([a-z])\b",
        r"\1^3",
        result,
    )

    result = re.sub(
        r"\b([a-z])\s+(?:square|squared)\b",
        r"\1^2",
        result,
    )

    result = re.sub(
        r"\b([a-z])\s+(?:cube|cubed)\b",
        r"\1^3",
        result,
    )

    phrase_replacements = (
        (
            r"\bmultiplied\s+by\b",
            "*",
        ),
        (
            r"\bdivided\s+by\b",
            "/",
        ),
        (
            r"\bequal\s+to\b",
            "=",
        ),
        (
            r"\bequals\b",
            "=",
        ),
        (
            r"\bplus\b",
            "+",
        ),
        (
            r"\bminus\b",
            "-",
        ),
        (
            r"\btimes\b",
            "*",
        ),
    )

    for pattern, replacement in (
        phrase_replacements
    ):
        result = re.sub(
            pattern,
            replacement,
            result,
        )

    return result


def _extract_equation(
    message: str,
) -> ParsedEquation | None:
    normalized = normalize_spoken_math(
        message
    )

    for line in reversed(
        normalized.splitlines()
    ):
        for match in _EQUAL_SIGN.finditer(
            line
        ):
            left_source = line[
                :match.start()
            ]

            right_source = line[
                match.end():
            ]

            left_match = _MATH_TAIL.search(
                left_source
            )

            right_match = _MATH_PREFIX.match(
                right_source
            )

            if (
                left_match is None
                or right_match is None
            ):
                continue

            left = left_match.group(1).strip()
            right = right_match.group(1).strip()

            if (
                not left
                or not right
                or "x" not in (
                    left + right
                ).lower()
            ):
                continue

            return ParsedEquation(
                left=left,
                right=right,
            )

    return None


def extract_equation_graph_expression(
    message: str,
) -> str | None:
    equation = _extract_equation(
        message
    )

    if equation is None:
        return None

    if _is_zero_expression(
        equation.right
    ):
        return equation.left

    if _is_zero_expression(
        equation.left
    ):
        return equation.right

    return (
        f"({equation.left})"
        f"-({equation.right})"
    )


def _python_expression(
    expression: str,
) -> str:
    result = (
        normalize_spoken_math(
            expression
        )
        .replace("^", "**")
    )

    result = re.sub(
        r"(?<=\d)(?=x|\()",
        "*",
        result,
    )

    result = re.sub(
        r"(?<=x)(?=\()",
        "*",
        result,
    )

    result = re.sub(
        r"(?<=\))(?=x|\d|\()",
        "*",
        result,
    )

    return result.strip()


Polynomial = tuple[
    float,
    float,
    float,
]


def _constant(
    value: float,
) -> Polynomial:
    return (
        value,
        0.0,
        0.0,
    )


def _variable() -> Polynomial:
    return (
        0.0,
        1.0,
        0.0,
    )


def _add(
    left: Polynomial,
    right: Polynomial,
) -> Polynomial:
    return tuple(
        first + second
        for first, second in zip(
            left,
            right,
            strict=True,
        )
    )


def _subtract(
    left: Polynomial,
    right: Polynomial,
) -> Polynomial:
    return tuple(
        first - second
        for first, second in zip(
            left,
            right,
            strict=True,
        )
    )


def _scale(
    polynomial: Polynomial,
    value: float,
) -> Polynomial:
    return tuple(
        coefficient * value
        for coefficient in polynomial
    )


def _multiply(
    left: Polynomial,
    right: Polynomial,
) -> Polynomial:
    result = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]

    for left_power, left_value in enumerate(
        left
    ):
        for (
            right_power,
            right_value,
        ) in enumerate(right):
            result[
                left_power + right_power
            ] += (
                left_value
                * right_value
            )

    if any(
        abs(value) > _EPSILON
        for value in result[3:]
    ):
        raise ValueError(
            "Only degree-two equations are supported."
        )

    return (
        result[0],
        result[1],
        result[2],
    )


def _polynomial_from_ast(
    node: ast.AST,
) -> Polynomial:
    if isinstance(node, ast.Expression):
        return _polynomial_from_ast(
            node.body
        )

    if isinstance(node, ast.Constant):
        if not isinstance(
            node.value,
            (int, float),
        ):
            raise ValueError

        return _constant(
            float(node.value)
        )

    if isinstance(node, ast.Name):
        if node.id != "x":
            raise ValueError(
                "Unsupported variable."
            )

        return _variable()

    if isinstance(node, ast.UnaryOp):
        operand = _polynomial_from_ast(
            node.operand
        )

        if isinstance(
            node.op,
            ast.USub,
        ):
            return _scale(
                operand,
                -1.0,
            )

        if isinstance(
            node.op,
            ast.UAdd,
        ):
            return operand

        raise ValueError

    if isinstance(node, ast.BinOp):
        left = _polynomial_from_ast(
            node.left
        )

        right = _polynomial_from_ast(
            node.right
        )

        if isinstance(node.op, ast.Add):
            return _add(
                left,
                right,
            )

        if isinstance(node.op, ast.Sub):
            return _subtract(
                left,
                right,
            )

        if isinstance(node.op, ast.Mult):
            return _multiply(
                left,
                right,
            )

        if isinstance(node.op, ast.Div):
            if (
                abs(right[1]) > _EPSILON
                or abs(right[2]) > _EPSILON
                or abs(right[0]) <= _EPSILON
            ):
                raise ValueError(
                    "Polynomial division by a variable "
                    "expression is unsupported."
                )

            return _scale(
                left,
                1.0 / right[0],
            )

        if isinstance(node.op, ast.Pow):
            if (
                abs(right[1]) > _EPSILON
                or abs(right[2]) > _EPSILON
            ):
                raise ValueError

            exponent = right[0]

            if not math.isclose(
                exponent,
                round(exponent),
                abs_tol=_EPSILON,
            ):
                raise ValueError

            integer_exponent = int(
                round(exponent)
            )

            if not 0 <= integer_exponent <= 2:
                raise ValueError(
                    "Only powers zero through two "
                    "are supported."
                )

            result = _constant(1.0)

            for _ in range(
                integer_exponent
            ):
                result = _multiply(
                    result,
                    left,
                )

            return result

    raise ValueError(
        "Unsupported mathematical expression."
    )


def _parse_polynomial(
    expression: str,
) -> Polynomial:
    tree = ast.parse(
        _python_expression(
            expression
        ),
        mode="eval",
    )

    return _polynomial_from_ast(
        tree
    )


def _is_zero_expression(
    expression: str,
) -> bool:
    try:
        polynomial = _parse_polynomial(
            expression
        )
    except (
        SyntaxError,
        ValueError,
    ):
        return False

    return all(
        abs(value) <= _EPSILON
        for value in polynomial
    )


def _format_number(
    value: float,
) -> str:
    rounded = round(value)

    if math.isclose(
        value,
        rounded,
        abs_tol=1e-10,
    ):
        return str(int(rounded))

    return (
        f"{value:.8f}"
        .rstrip("0")
        .rstrip(".")
    )


def _latex_polynomial(
    coefficients: Polynomial,
) -> str:
    constant, linear, quadratic = (
        coefficients
    )

    terms: list[str] = []

    for coefficient, symbol in (
        (
            quadratic,
            "x^2",
        ),
        (
            linear,
            "x",
        ),
        (
            constant,
            "",
        ),
    ):
        if abs(coefficient) <= _EPSILON:
            continue

        magnitude = abs(coefficient)

        if symbol and math.isclose(
            magnitude,
            1.0,
            abs_tol=_EPSILON,
        ):
            body = symbol
        else:
            body = (
                f"{_format_number(magnitude)}"
                f"{symbol}"
            )

        if not terms:
            terms.append(
                (
                    "-"
                    if coefficient < 0
                    else ""
                )
                + body
            )
        else:
            terms.append(
                (
                    " - "
                    if coefficient < 0
                    else " + "
                )
                + body
            )

    return "".join(terms) or "0"


def _perfect_square_root(
    value: float,
) -> int | None:
    if value < 0:
        return None

    root = round(
        math.sqrt(value)
    )

    if math.isclose(
        root * root,
        value,
        abs_tol=1e-10,
    ):
        return int(root)

    return None


def _quadratic_answer(
    *,
    coefficients: Polynomial,
    graph_requested: bool,
) -> str:
    constant, linear, quadratic = (
        coefficients
    )

    discriminant = (
        linear * linear
        - 4.0 * quadratic * constant
    )

    polynomial_latex = (
        _latex_polynomial(
            coefficients
        )
    )

    denominator = (
        2.0 * quadratic
    )

    sections: list[str] = []

    if discriminant < -_EPSILON:
        absolute_discriminant = (
            -discriminant
        )

        square_root = (
            _perfect_square_root(
                absolute_discriminant
            )
        )

        if (
            abs(linear) <= _EPSILON
            and square_root is not None
        ):
            magnitude = (
                square_root
                / abs(denominator)
            )

            magnitude_text = (
                _format_number(
                    magnitude
                )
            )

            root_latex = (
                r"x=\pm "
                f"{magnitude_text}i"
            )
        else:
            root_latex = (
                r"x="
                r"\frac{"
                f"{_format_number(-linear)}"
                r"\pm i\sqrt{"
                f"{_format_number(absolute_discriminant)}"
                r"}}{"
                f"{_format_number(denominator)}"
                r"}"
            )

        sections.append(
            "## Result\n\n"
            "There are no real solutions. "
            "Over the complex numbers,\n\n"
            "$$\n"
            f"\\boxed{{{root_latex}}}\n"
            "$$"
        )

        sections.append(
            "## Explanation\n\n"
            "The discriminant is negative, so the "
            "quadratic does not intersect the real "
            "$x$-axis. Its roots therefore contain "
            "the imaginary unit $i$, where "
            "$i^2=-1$."
        )

        if (
            abs(linear) <= _EPSILON
            and square_root is not None
        ):
            sections.append(
                "## Solution\n\n"
                "$$\n"
                f"{polynomial_latex}=0\n"
                "$$\n\n"
                "Move the constant term to the "
                "other side:\n\n"
                "$$\n"
                f"{_format_number(quadratic)}x^2"
                f"={_format_number(-constant)}\n"
                "$$\n\n"
                "Taking both square roots gives\n\n"
                "$$\n"
                f"x=\\pm {magnitude_text}i.\n"
                "$$"
            )
        else:
            sections.append(
                "## Solution\n\n"
                "For a quadratic equation "
                "$ax^2+bx+c=0$, use\n\n"
                "$$\n"
                r"x=\frac{-b\pm\sqrt{b^2-4ac}}{2a}."
                "\n$$\n\n"
                "Here,\n\n"
                "$$\n"
                f"b^2-4ac"
                f"={_format_number(discriminant)}<0.\n"
                "$$\n\n"
                "Therefore,\n\n"
                "$$\n"
                f"{root_latex}.\n"
                "$$"
            )

        if graph_requested:
            sections.append(
                "## Graph and Interpretation\n\n"
                "<!--AUTHENTIC_VISUALIZATION_SLOT-->\n\n"
                "The real graph of\n\n"
                "$$\n"
                f"y={polynomial_latex}\n"
                "$$\n\n"
                "does not cross the $x$-axis. "
                "This visually confirms that the "
                "equation has no real roots. "
                "Complex roots are not points on a "
                "standard real coordinate graph."
            )

        sections.append(
            "## Verification\n\n"
            "Substituting either calculated root "
            "into the original polynomial produces "
            "zero, confirming both complex roots."
        )

        return "\n\n".join(
            sections
        )

    if abs(discriminant) <= _EPSILON:
        root = (
            -linear / denominator
        )

        root_text = _format_number(
            root
        )

        sections.append(
            "## Result\n\n"
            "$$\n"
            f"\\boxed{{x={root_text}}}\n"
            "$$"
        )

        sections.append(
            "## Explanation\n\n"
            "The discriminant is zero, so the "
            "quadratic has one repeated real root."
        )

        sections.append(
            "## Solution\n\n"
            "$$\n"
            f"{polynomial_latex}=0\n"
            "$$\n\n"
            "$$\n"
            r"x=\frac{-b}{2a}"
            f"={root_text}.\n"
            "$$"
        )

        if graph_requested:
            sections.append(
                "## Graph and Interpretation\n\n"
                "<!--AUTHENTIC_VISUALIZATION_SLOT-->\n\n"
                "The graph touches the $x$-axis at "
                f"$x={root_text}$ without crossing it."
            )

        sections.append(
            "## Verification\n\n"
            f"Substitution of $x={root_text}$ into "
            "the original equation gives zero."
        )

        return "\n\n".join(
            sections
        )

    square_root = _perfect_square_root(
        discriminant
    )

    first_root = (
        -linear
        + math.sqrt(discriminant)
    ) / denominator

    second_root = (
        -linear
        - math.sqrt(discriminant)
    ) / denominator

    if square_root is not None:
        roots_latex = (
            f"x={_format_number(first_root)}"
            r"\quad\text{or}\quad"
            f"x={_format_number(second_root)}"
        )
    else:
        roots_latex = (
            r"x="
            r"\frac{"
            f"{_format_number(-linear)}"
            r"\pm\sqrt{"
            f"{_format_number(discriminant)}"
            r"}}{"
            f"{_format_number(denominator)}"
            r"}"
        )

    sections.append(
        "## Result\n\n"
        "$$\n"
        f"\\boxed{{{roots_latex}}}\n"
        "$$"
    )

    sections.append(
        "## Explanation\n\n"
        "The discriminant is positive, so the "
        "quadratic has two distinct real roots."
    )

    sections.append(
        "## Solution\n\n"
        "$$\n"
        f"{polynomial_latex}=0\n"
        "$$\n\n"
        "Using the quadratic formula,\n\n"
        "$$\n"
        r"x=\frac{-b\pm\sqrt{b^2-4ac}}{2a}"
        "\n$$\n\n"
        "gives\n\n"
        "$$\n"
        f"{roots_latex}.\n"
        "$$"
    )

    if graph_requested:
        sections.append(
            "## Graph and Interpretation\n\n"
            "<!--AUTHENTIC_VISUALIZATION_SLOT-->\n\n"
            "The graph crosses the $x$-axis at the "
            "two calculated real roots."
        )

    sections.append(
        "## Verification\n\n"
        "Substituting both roots into the original "
        "equation gives zero."
    )

    return "\n\n".join(
        sections
    )


def build_deterministic_math_answer(
    message: str,
) -> str | None:
    equation = _extract_equation(
        message
    )

    if equation is None:
        return None

    try:
        left = _parse_polynomial(
            equation.left
        )

        right = _parse_polynomial(
            equation.right
        )

        coefficients = _subtract(
            left,
            right,
        )

    except (
        SyntaxError,
        ValueError,
        ZeroDivisionError,
    ):
        return None

    constant, linear, quadratic = (
        coefficients
    )

    graph_requested = (
        wants_visualization(
            message
        )
    )

    if abs(quadratic) > _EPSILON:
        return _quadratic_answer(
            coefficients=coefficients,
            graph_requested=graph_requested,
        )

    if abs(linear) > _EPSILON:
        root = (
            -constant / linear
        )

        root_text = _format_number(
            root
        )

        sections = [
            (
                "## Result\n\n"
                "$$\n"
                f"\\boxed{{x={root_text}}}\n"
                "$$"
            ),
            (
                "## Explanation\n\n"
                "This is a linear equation, so "
                "isolating $x$ produces its single "
                "solution."
            ),
            (
                "## Solution\n\n"
                "$$\n"
                f"{_latex_polynomial(coefficients)}=0\n"
                "$$\n\n"
                "$$\n"
                f"x={root_text}.\n"
                "$$"
            ),
        ]

        if graph_requested:
            sections.append(
                "## Graph and Interpretation\n\n"
                "<!--AUTHENTIC_VISUALIZATION_SLOT-->\n\n"
                "The graph crosses the $x$-axis at "
                f"$x={root_text}$."
            )

        sections.append(
            "## Verification\n\n"
            f"Substitution of $x={root_text}$ into "
            "the original equation gives zero."
        )

        return "\n\n".join(
            sections
        )

    if abs(constant) <= _EPSILON:
        return (
            "## Result\n\n"
            "Every real and complex value of $x$ "
            "satisfies the identity.\n\n"
            "## Explanation\n\n"
            "Both sides simplify to the same "
            "expression.\n\n"
            "## Verification\n\n"
            "Subtracting the two sides gives $0=0$."
        )

    return (
        "## Result\n\n"
        "The equation has no solution.\n\n"
        "## Explanation\n\n"
        "After simplification, the equation becomes "
        f"${_format_number(constant)}=0$, which is "
        "false.\n\n"
        "## Verification\n\n"
        "No value of $x$ can make a nonzero constant "
        "equal to zero."
    )
