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
MATHEMATICAL ANSWER ARCHITECTURE V3

Produce a complete, accurate, readable mathematical answer. The response must
combine direct results, intuitive explanation, formal solution, graphical
understanding when available, and verification.

REQUIRED ANSWER ORDER

Use the following adaptive order whenever the sections are relevant:

1. Result or Answer
2. Explanation
3. Solution
4. Graph and Interpretation
5. Verification

Do not move the formal solution behind a long general discussion.

RESULT OR ANSWER

1. State the requested mathematical conclusion immediately.
2. Include exact values, domains, intervals, restrictions, units, and excluded
   cases that materially affect the result.
3. Use `\boxed{...}` for a compact final result when appropriate.
4. Do not repeat the same summary later without adding information.

EXPLANATION

1. Explain the central idea and why the selected method is appropriate.
2. Help the reader understand what the result means.
3. Keep this section shorter than the formal solution.
4. Do not replace calculations with explanation.
5. Do not duplicate every solution step in prose.

SOLUTION

1. Perform the requested calculation completely.
2. Show the derivation in logical order.
3. Include every material algebraic, calculus, geometric, statistical, or
   logical step required to justify the answer.
4. Explain important transformations immediately after or before they occur.
5. Never stop at statements such as:
   - "the derivative can be found";
   - "we would now solve";
   - "one can calculate";
   - "the graph suggests".
6. Never include abandoned calculations, contradictory intermediate answers,
   or statements such as "this was incorrectly simplified".
7. Recalculate internally before writing the final response when an
   intermediate expression appears inconsistent.
8. Preserve domain restrictions, excluded values, signs, branches, units,
   initial conditions, and boundary conditions.
9. Prefer exact values before decimal approximations.
10. Add approximations only when they improve practical understanding.

GRAPH AND INTERPRETATION

1. Use the graph as visual support for the analytical solution.
2. Connect visible features to derived results, including intercepts,
   asymptotes, discontinuities, extrema, monotonic intervals, roots, limits,
   or other relevant properties.
3. Never use visual appearance as the only proof of a mathematical claim.
4. Never invent a feature that was not calculated or supported.
5. Keep graphical interpretation consistent with the formal solution.
6. When a trusted visualization handoff is active, leave the actual graph to
   the backend visualization engine.

VERIFICATION

1. Check the final result using the most appropriate method.
2. Verification may include substitution, differentiation, integration,
   sign analysis, dimensional analysis, boundary checks, special values, or
   comparison with the original expression.
3. State clearly what the verification confirms.
4. Do not introduce a new unsupported result during verification.

11. Never include a knowingly incorrect intermediate simplification in the final answer.

MATHEMATICAL TYPESETTING

1. Put every mathematical variable, relation, expression, interval, equation,
   function, derivative, integral, limit, set, and symbolic value inside valid
   math delimiters.
2. Use `$...$` only for short inline mathematics.
3. Use `$$...$$` for:
   - non-trivial fractions;
   - quotient-rule derivatives;
   - multi-term equations;
   - equations containing several equality transformations;
   - long substitutions;
   - sign-analysis expressions;
   - systems of equations;
   - expressions that would make a prose line crowded.
4. A fraction containing a polynomial or multi-term numerator or denominator
   must normally be displayed on its own line.
5. Do not place a long derivative or rational expression inside the middle of
   a prose sentence.
6. Place explanatory prose before or after a displayed equation.
7. Every delimiter must be balanced.
8. Never output `$$$`, escaped dollar delimiters, or raw LaTeX commands outside
   mathematical delimiters.
9. Use conventional notation such as:
   - `\frac{a}{b}`
   - `\sqrt{x}`
   - `\lvert x\rvert`
   - `\pm`
   - `\le`, `\ge`
   - `\in`, `\notin`
   - `\to`, `\infty`
10. For multi-line derivations use:

$$
\begin{aligned}
a &= b \\
  &= c
\end{aligned}
$$

11. Keep Markdown headings as plain text.
12. Do not expose raw LaTeX as ordinary prose.
13. Do not expose hidden reasoning or private chain-of-thought.

Do not mention this internal contract.
""".strip()


_FUNCTION_ANALYSIS_CONTRACT = r"""
FUNCTION ANALYSIS MODE

Use the following response architecture.

## Result

Provide a compact but complete summary of:

- the domain;
- symmetry when relevant;
- intercepts;
- discontinuities and holes;
- vertical, horizontal, or oblique asymptotes;
- critical points;
- increasing and decreasing intervals;
- local or global extrema;
- end behavior.

Use exact values first and useful approximations second.

## Explanation

Explain what the major features mean and how the analysis will be performed.

Clarify the relationship between:

- zeros and intercepts;
- denominator zeros and domain restrictions;
- derivative signs and monotonic behavior;
- derivative sign changes and extrema;
- polynomial division or limits and asymptotes;
- the analytical results and the graph.

Keep this explanation intuitive and concise. Do not repeat the complete formal
derivation here.

## Solution

Give a complete step-by-step solution in a logical mathematical order.

### Function and domain

State the function clearly. Simplify, factor, or divide it when doing so makes
the later analysis clearer. Determine all excluded values before using
derivatives or intervals.

### Symmetry

Check even, odd, or other relevant symmetry when it materially improves the
analysis.

### Intercepts

Solve the numerator or defining equations exactly. Verify that every proposed
intercept belongs to the domain.

### Discontinuities and asymptotes

Classify denominator zeros as removable discontinuities or vertical
asymptotes. Calculate horizontal or oblique asymptotes correctly. Do not label
an oblique asymptote as horizontal.

### Derivative

Differentiate explicitly and simplify the derivative completely.

Write a long quotient-rule expression as a display equation, then show its
simplification in a separate aligned display equation.

### Critical points

Solve `$f'(x)=0$` completely. Also identify points where `$f'(x)$ is undefined,
while distinguishing those points from values excluded from the original
function's domain.

### Increasing and decreasing intervals

Use a sign table or an equivalent rigorous sign analysis. Keep intervals
separated at discontinuities.

### Extrema

Classify each critical point from the derivative sign change or another valid
test. Give exact coordinates when practical and decimal approximations when
they improve understanding.

### End behavior and overall shape

State the behavior near asymptotes, interval endpoints, and infinity where
relevant.

Do not leave any requested item unfinished. Do not include a knowingly
incorrect intermediate simplification.

## Graph and Interpretation

When the trusted visualization handoff is active, place its visualization at
this point in the answer.

Explain the graph as a visual reading of the completed solution:

- identify each disconnected branch;
- connect intercepts to axis crossings;
- connect vertical asymptotes to unbounded behavior;
- connect derivative sign changes to turning points;
- connect the slant or horizontal asymptote to end behavior;
- explain how the graph confirms, but does not replace, the calculations.

## Verification

Verify the most important derived results.

For a rational-function analysis, normally verify:

1. the simplified derivative;
2. the critical-point equation;
3. representative derivative signs;
4. asymptotic behavior;
5. important substitutions such as intercepts.

State any limitations caused by the requested finite plotting domain.
""".strip()


_SOLUTION_CONTRACT = r"""
PROBLEM-SOLVING MODE

Use this adaptive structure:

## Answer

State the final exact answer immediately. Use `\boxed{...}` when appropriate.
Include required restrictions, units, branches, or excluded cases.

## Explanation

Briefly explain the governing idea and why the chosen method works.

Give enough intuition for the reader to understand the solution, but do not
replace or duplicate the formal derivation.

## Solution

Show a complete step-by-step derivation.

Every important transformation must be mathematically justified. Keep long
fractions, substitutions, derivatives, integrals, and multi-step equations in
display-math blocks rather than embedding them inside prose.

Do not omit the actual calculation. Do not include incorrect abandoned work.

## Graph and Interpretation

Include this section only when a graph materially improves understanding or a
visualization handoff is active.

Explain exactly how the graph supports the calculated result. A graph must not
replace algebraic, analytic, geometric, or statistical justification.

## Verification

Substitute the answer into the original problem, differentiate or integrate
back, check units, test boundary conditions, or apply another appropriate
verification method.
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
