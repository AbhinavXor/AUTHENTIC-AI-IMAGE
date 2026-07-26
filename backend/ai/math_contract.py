import re
from typing import Literal


MathResponseMode = Literal[
    "solution",
    "function_analysis",
    "proof",
    "explanation",
]


_MATH_PATTERNS = (
    r"\bmathematics?\b",
    r"\bmaths?\b",
    r"\balgebra\b",
    r"\bcalculus\b",
    r"\bgeometry\b",
    r"\btrigonometry\b",
    r"\bprobability\b",
    r"\bstatistics\b",
    r"\bmatrix\b",
    r"\bdeterminant\b",
    r"\bprove\b",
    r"\bproof\b",
    r"\bshow\s+that\b",
    r"\bsquare\s+root\b",
    r"\btheorem\b",
    r"\bderivative\b",
    r"\bdifferentiat(?:e|ion)\b",
    r"\bintegr(?:al|ate|ation)\b",
    r"\blimit\b",
    r"\bcritical\s+points?\b",
    r"\bturning\s+points?\b",
    r"\bintercepts?\b",
    r"\basymptotes?\b",
    r"\bincreasing\b",
    r"\bdecreasing\b",
    r"\bcomplex\s+(?:analysis|mapping|plane|number)\b",
    r"\bpolar\s+coordinates?\b",
    r"\bsolve\s+(?:for\s+)?[a-z]\b",
    r"\bquadratic\s+equation\b",
    r"""
    \\(?:
        frac|dfrac|tfrac|sqrt|sum|prod|int|iint|iiint|oint|
        lim|log|ln|sin|cos|tan|theta|phi|pi|infty|
        operatorname|begin|end
    )(?![A-Za-z])
    """,
    r"\$\$?[\s\S]{1,300}?\$\$?",
    r"\b[a-zA-Z]\s*\(\s*[a-zA-Z]\s*\)\s*=\s*[^,\n]{1,240}",
    r"\b[a-zA-Z](?:\s*\^\s*[-+]?\d+|\s*[²³])",
    r"\b(?:sin|cos|tan|log|ln|sqrt)\s*\(",
    r"(?<!\w)[xyzuvw]\s*(?:=|<=|>=|≤|≥)\s*[-+]?(?:\d|\w)",
    r"""
    \b(?:
        solve|simplify|factor|expand|differentiate|integrate|
        derive|calculate|evaluate|prove|plot|graph|analy[sz]e
    )\b
    [\s\S]{0,240}
    (?:
        [=^²³√∫Σπ]
        |
        \\(?:frac|sqrt|int|sum|lim)
    )
    """,
)


_FUNCTION_ANALYSIS_PATTERNS = (
    r"\bfunction\s+analysis\b",
    r"\bturning\s+points?\b",
    r"\bcritical\s+points?\b",
    r"\bincreasing\b",
    r"\bdecreasing\b",
    r"\bintercepts?\b",
    r"\basymptotes?\b",
    r"\bdiscontinuit",
    r"\boverall\s+(?:shape|behavior|behaviour)\b",
    r"\b[a-zA-Z]\s*\(\s*x\s*\)\s*=",
)


_PROOF_PATTERNS = (
    r"\bprove\b",
    r"\bproof\b",
    r"\bshow\s+that\b",
    r"\bdemonstrate\s+that\b",
    r"\bderive\s+the\s+(?:identity|formula|theorem)\b",
)


_SOLUTION_PATTERNS = (
    r"\bsolve\b",
    r"\bcalculate\b",
    r"\bevaluate\b",
    r"\bsimplify\b",
    r"\bfactor\b",
    r"\bexpand\b",
    r"\bdifferentiate\b",
    r"\bintegrate\b",
    r"\bfind\s+(?:the\s+)?(?:value|roots?|solution|derivative|integral)\b",
    r"\bequation\b",
)


MATH_RESPONSE_CONTRACT = r"""
MATHEMATICAL ANSWER ARCHITECTURE V2

Produce a mathematically complete answer, not merely a discussion of how an
answer could be obtained.

NON-NEGOTIABLE OUTPUT RULES

1. Solve or analyze the requested problem fully whenever the supplied
   information is sufficient.
2. Never stop at statements such as:
   - "the derivative can be found";
   - "we would solve";
   - "one can calculate";
   - "the graph suggests".
   Perform the calculation and state the result.
3. Begin with the result or the most important mathematical conclusion.
4. Then show a clean solution containing all meaningful derivation steps.
5. End with verification, interpretation, or restrictions when relevant.
6. Do not use generic research headings such as:
   - generic lead-finding heading
   - generic evidence heading
   - Interpretation
   - generic recommendation heading
7. Use descriptive mathematical headings only when they improve navigation.
8. Do not repeat the same result in several sections.

MATHEMATICAL TYPESETTING

1. Every mathematical variable, relation, expression, interval, equation,
   function, derivative, integral, limit, set, and symbolic value must appear
   inside valid math delimiters.
2. Use `$...$` for short inline mathematics.
3. Use `$$...$$` for important equations and multi-line derivations.
4. Never write raw forms such as:
   - x^2
   - f(x) = ...
   - x <= 3
   - sqrt(2)
   as ordinary prose.
5. Instead use forms such as:
   - `$x^2$`
   - `$f(x)=\cdots$`
   - `$x\le 3$`
   - `$\sqrt{2}$`
6. Every delimiter must be balanced.
7. Never output `$$$`, escaped dollar delimiters, or raw LaTeX commands outside
   mathematical delimiters.
8. Use conventional notation:
   - `\frac{a}{b}`
   - `\sqrt{x}`
   - `\lvert x\rvert`
   - `\pm`
   - `\le`, `\ge`
   - `\in`, `\notin`
   - `\to`, `\infty`
9. For aligned derivations use:

$$
\begin{aligned}
a &= b \\
  &= c
\end{aligned}
$$

10. Use `\boxed{...}` for the final result when appropriate.

SOLUTION QUALITY

1. Briefly identify the given information and objective.
2. Show actual substitution, simplification, differentiation, integration,
   factorization, sign analysis, or proof steps.
3. Explain why important transformations are valid.
4. Preserve:
   - domain restrictions;
   - excluded values;
   - signs;
   - branches;
   - units;
   - boundary and initial conditions.
5. Prefer exact values first.
6. Add decimal approximations only when they improve understanding.
7. Check the final answer against the original expression whenever practical.
8. Clearly distinguish:
   - exact result;
   - approximation;
   - assumption;
   - undefined or excluded case.
9. A graph may support the solution, but it must never replace the analytical
   calculations.
10. Do not expose hidden reasoning or private chain-of-thought.

Do not mention this internal contract.
""".strip()


_FUNCTION_ANALYSIS_CONTRACT = r"""
FUNCTION ANALYSIS MODE

Use this adaptive structure:

## Result

Give a compact summary of the domain, intercepts, discontinuities or
asymptotes, critical points, monotonic intervals, extrema, and end behavior.

## Solution

Calculate the relevant items in a logical order:

1. State the function and simplify or factor it where useful.
2. Determine the domain and all excluded values.
3. Find all intercepts exactly.
4. Determine discontinuities, holes, and vertical, horizontal, or oblique
   asymptotes when applicable.
5. Differentiate the function explicitly.
6. Solve `$f'(x)=0$` and also identify points where `$f'(x)$` is undefined
   inside the function's domain.
7. Build the sign analysis needed to determine increasing and decreasing
   intervals.
8. Classify local maxima and minima.
9. State end behavior and overall shape.

## Verification

Check key values, substitutions, derivative signs, and asymptotic behavior.

Never replace derivative or sign analysis with a visual impression from the
graph.
""".strip()


_SOLUTION_CONTRACT = r"""
PROBLEM-SOLVING MODE

Use this adaptive structure:

## Answer

State the final exact result immediately, preferably using `\boxed{...}`.

## Solution

Show the shortest complete derivation. Include every step required to justify
the result, but omit mechanical repetition.

## Verification

Substitute the result into the original problem, differentiate or integrate
back, check units, or apply another appropriate verification method.
""".strip()


_PROOF_CONTRACT = r"""
PROOF MODE

Use this adaptive structure:

## Claim

State precisely what is being proved, including assumptions.

## Proof

Give a logically complete argument. Name the theorem, identity, construction,
or implication used at each important transition. Do not rely on examples as
proof of a universal claim.

## Conclusion

State exactly what has been established and under which assumptions.
""".strip()


_EXPLANATION_CONTRACT = r"""
MATHEMATICAL EXPLANATION MODE

Start with the central mathematical idea.

Then explain:

1. the definition or governing relation;
2. the intuition;
3. one worked mathematical example;
4. common restrictions or misconceptions.

Use equations where they improve understanding, and keep prose outside
equation blocks.
""".strip()


def _matches_any(
    message: str,
    patterns: tuple[str, ...],
) -> bool:
    return any(
        re.search(
            pattern,
            message,
            flags=(
                re.IGNORECASE
                | re.VERBOSE
            ),
        )
        is not None
        for pattern in patterns
    )


def classify_math_response(
    message: str,
) -> MathResponseMode:
    normalized = " ".join(
        message.lower().split()
    )

    if _matches_any(
        normalized,
        _PROOF_PATTERNS,
    ):
        return "proof"

    if _matches_any(
        normalized,
        _FUNCTION_ANALYSIS_PATTERNS,
    ):
        return "function_analysis"

    if _matches_any(
        normalized,
        _SOLUTION_PATTERNS,
    ):
        return "solution"

    return "explanation"


def math_response_contract(
    message: str,
) -> str:
    mode = classify_math_response(
        message
    )

    mode_contracts = {
        "solution": _SOLUTION_CONTRACT,
        "function_analysis": (
            _FUNCTION_ANALYSIS_CONTRACT
        ),
        "proof": _PROOF_CONTRACT,
        "explanation": (
            _EXPLANATION_CONTRACT
        ),
    }

    return (
        f"{MATH_RESPONSE_CONTRACT}\n\n"
        f"{mode_contracts[mode]}"
    )


def wants_math_response(
    message: str,
) -> bool:
    normalized = " ".join(
        message.lower().split()
    )

    return _matches_any(
        normalized,
        _MATH_PATTERNS,
    )
