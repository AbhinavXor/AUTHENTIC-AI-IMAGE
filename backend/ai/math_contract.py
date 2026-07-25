import re


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
    r"\btheorem\b",
    r"\bderivative\b",
    r"\bdifferentiat(?:e|ion)\b",
    r"\bintegr(?:al|ate|ation)\b",
    r"\blimit\b",
    r"\bcomplex\s+(?:analysis|mapping|plane|number)\b",
    r"\bpolar\s+coordinates?\b",
    r"\bsolve\s+(?:for\s+)?[a-z]\b",
    r"\bquadratic\s+equation\b",
    r"\\(?:frac|dfrac|tfrac|sqrt|sum|prod|int|iint|iiint|oint|lim|log|ln|sin|cos|tan|theta|phi|pi|infty|operatorname|begin|end)(?![A-Za-z])",
    r"\$\$?[\s\S]{1,240}?\$\$?",
    r"\b[xyzuvw]\s*=\s*[^,\n]{1,120}",
)


MATH_RESPONSE_CONTRACT = r"""
MATHEMATICAL RESPONSE CONTRACT

Produce mathematically correct, professionally typeset Markdown that can be
rendered with KaTeX.

Notation requirements:

1. Use `$...$` only for short inline mathematics.
2. Use `$$...$$` for displayed equations.
3. Every delimiter must be balanced.
4. Never output `$$$`, escaped dollar delimiters such as `\$x\$`, or raw
   LaTeX commands outside mathematical delimiters.
5. Keep Markdown headings in plain text. Do not wrap an entire heading in
   dollar signs.
6. Keep explanatory prose outside equation blocks.
7. Use `\text{...}` for words appearing inside equations.
8. Use conventional notation such as:
   - `\frac{a}{b}`
   - `\sqrt{x}`
   - `\lvert z \rvert`
   - `\operatorname{Arg}(z)`
   - `\le`, `\ge`, `\in`, `\to`
9. For a multi-line derivation, use one display block:

$$
\begin{aligned}
a &= b \\
  &= c
\end{aligned}
$$

10. Do not place several unrelated equations in one long paragraph.

Answer-quality requirements:

- State the given information and objective briefly.
- Define symbols before using them.
- Show only meaningful derivation steps.
- Explain why each important transformation is valid.
- Preserve domain restrictions, signs, branches, units, and boundary
  conditions.
- Check the final result against the original expression whenever practical.
- Use `\boxed{...}` for the final result when appropriate.
- Do not invent missing assumptions or silently change the problem.
- Avoid repetitive headings such as “Step 1”, “Step 2” when descriptive
  headings are clearer.
- Do not expose raw LaTeX as ordinary text.

For complex-variable mappings:

- Define `$z=x+iy$` and `$w=u+iv$`.
- Separate real and imaginary parts carefully.
- Map every boundary independently.
- State the mapped region, orientation, and relevant restrictions.
- Do not use malformed notation such as `$$$` to represent a region.

Do not mention this internal contract.
""".strip()


def wants_math_response(
    message: str,
) -> bool:
    normalized = " ".join(
        message.lower().split()
    )

    return any(
        re.search(
            pattern,
            normalized,
        )
        is not None
        for pattern in _MATH_PATTERNS
    )
