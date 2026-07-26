import re
from dataclasses import dataclass
from typing import Literal


TaskCategory = Literal[
    "general",
    "fast_chat",
    "deep_reasoning",
    "coding",
    "mathematics",
    "physics",
    "chemistry",
    "biology",
    "research",
]

TaskComplexity = Literal[
    "simple",
    "standard",
    "complex",
]


@dataclass(frozen=True, slots=True)
class TaskClassification:
    category: TaskCategory
    complexity: TaskComplexity
    confidence: float
    matched_terms: tuple[str, ...]


_TERM_WEIGHTS: dict[
    TaskCategory,
    tuple[tuple[str, float], ...],
] = {
    "coding": (
        ("software architecture", 7.0),
        ("fastapi", 6.0),
        ("typescript", 6.0),
        ("javascript", 6.0),
        ("python", 6.0),
        ("programming", 6.0),
        ("coding", 6.0),
        ("api endpoint", 5.0),
        ("database", 4.0),
        ("debug", 5.0),
        ("bug", 4.0),
        ("compile", 4.0),
        ("repository", 4.0),
        ("algorithm", 3.0),
        ("code", 3.0),
        ("function", 1.0),
        ("class", 1.0),
    ),

    "physics": (
        ("physics", 9.0),
        ("projectile motion", 9.0),
        ("newton", 8.0),
        ("momentum", 8.0),
        ("acceleration", 7.0),
        ("velocity", 7.0),
        ("kinetic energy", 7.0),
        ("potential energy", 7.0),
        ("electric field", 7.0),
        ("thermodynamics", 7.0),
        ("gravity", 6.0),
        ("optics", 6.0),
        ("circuit", 5.0),
        ("wave", 4.0),
        ("force", 4.0),
        ("motion", 3.0),
    ),

    "chemistry": (
        ("chemistry", 9.0),
        ("chemical equation", 9.0),
        ("chemical reaction", 8.0),
        ("stoichiometry", 8.0),
        ("organic chemistry", 8.0),
        ("inorganic chemistry", 8.0),
        ("periodic table", 7.0),
        ("molecule", 7.0),
        ("molecular", 6.0),
        ("compound", 5.0),
        ("molar", 5.0),
        ("acid", 4.0),
        ("base", 3.0),
        ("element", 3.0),
        ("reaction", 3.0),
    ),

    "biology": (
        ("biology", 9.0),
        ("life science", 9.0),
        ("photosynthesis", 9.0),
        ("genetics", 8.0),
        ("microbiology", 8.0),
        ("physiology", 8.0),
        ("anatomy", 7.0),
        ("ecosystem", 7.0),
        ("evolution", 7.0),
        ("organism", 6.0),
        ("protein", 6.0),
        ("dna", 7.0),
        ("rna", 7.0),
        ("gene", 6.0),
        ("cell", 5.0),
        ("biological", 5.0),
    ),

    "mathematics": (
        ("mathematics", 9.0),
        ("calculus", 8.0),
        ("trigonometry", 8.0),
        ("algebra", 8.0),
        ("differentiate", 7.0),
        ("derivative", 7.0),
        ("integrate", 7.0),
        ("integral", 7.0),
        ("matrix", 7.0),
        ("polynomial", 6.0),
        ("probability", 6.0),
        ("statistics", 6.0),
        ("geometry", 6.0),
        ("theorem", 5.0),
        ("solve for x", 6.0),
        ("math", 6.0),

        # Generic mathematical words intentionally have
        # low weight because they also occur in science.
        ("equation", 1.5),
        ("equations", 1.5),
        ("formula", 1.0),
        ("calculate", 1.0),
    ),

    "research": (
        ("deep research", 9.0),
        ("market research", 9.0),
        ("literature review", 9.0),
        ("verify claims", 8.0),
        ("fact check", 8.0),
        ("research paper", 8.0),
        ("citations", 6.0),
        ("sources", 5.0),
        ("evidence", 5.0),
        ("investigate", 5.0),
        ("research", 5.0),
    ),

    "deep_reasoning": (
        ("enterprise architecture", 9.0),
        ("security design", 8.0),
        ("production system", 8.0),
        ("scalable system", 8.0),
        ("complete system", 7.0),
        ("industry grade", 7.0),
        ("trade-offs", 6.0),
        ("comprehensive", 5.0),
        ("strategy", 4.0),
        ("architecture", 4.0),
        ("evaluate", 3.0),
        ("analysis", 3.0),
        ("analyze", 3.0),
    ),

    "general": (),
    "fast_chat": (),
}


# Domain categories come before generic mathematical and
# analytical categories when scores are exactly equal.
_CATEGORY_PRIORITY: tuple[TaskCategory, ...] = (
    "coding",
    "physics",
    "chemistry",
    "biology",
    "mathematics",
    "research",
    "deep_reasoning",
)


def _term_present(
    normalized_message: str,
    term: str,
) -> bool:
    if " " in term or "-" in term:
        return term in normalized_message

    return re.search(
        rf"\b{re.escape(term)}\b",
        normalized_message,
    ) is not None


def _score_category(
    normalized_message: str,
    category: TaskCategory,
) -> tuple[float, tuple[str, ...]]:
    score = 0.0
    matched: list[str] = []

    for term, weight in _TERM_WEIGHTS[category]:
        if _term_present(
            normalized_message,
            term,
        ):
            score += weight
            matched.append(term)

    return score, tuple(matched)


def _looks_like_symbolic_mathematics(
    message: str,
) -> bool:
    normalized = " ".join(
        message.lower().split()
    )

    excluded_terms = (
        "python",
        "javascript",
        "typescript",
        "source code",
        "chemical equation",
        "reaction equation",
    )

    if any(
        term in normalized
        for term in excluded_terms
    ):
        return False

    patterns = (
        r"\b[a-z]\s+(?:square|squared|cube|cubed)\b",
        r"\b[a-z]\s*(?:\^|\*\*)\s*[-+]?\d+",
        (
            r"\b[a-z]\b[\s\S]{0,100}"
            r"(?<![<>])=(?!=)[\s\S]{0,100}\d"
        ),
    )

    return any(
        re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        )
        is not None
        for pattern in patterns
    )


def classify_task(
    message: str,
) -> TaskClassification:
    normalized = " ".join(
        message.lower().split()
    )

    word_count = len(
        normalized.split()
    )

    if _looks_like_symbolic_mathematics(
        message
    ):
        return TaskClassification(
            category="mathematics",
            complexity=(
                "complex"
                if word_count >= 70
                else "standard"
            ),
            confidence=0.99,
            matched_terms=(
                "symbolic mathematics",
            ),
        )

    complex_structure = (
        word_count >= 70
        or message.count("\n") >= 4
        or message.count("?") >= 3
    )

    # Strong subject-specific concepts override generic
    # cross-domain words such as equation, formula or reaction.
    domain_overrides: tuple[
        tuple[TaskCategory, tuple[str, ...]],
        ...,
    ] = (
        (
            "biology",
            (
                "photosynthesis",
                "cellular respiration",
                "protein synthesis",
                "natural selection",
                "dna replication",
                "mitosis",
                "meiosis",
                "genetics",
                "ecosystem",
                "physiology",
                "anatomy",
            ),
        ),
        (
            "physics",
            (
                "projectile motion",
                "newton's law",
                "newton law",
                "electric field",
                "magnetic field",
                "kinetic energy",
                "potential energy",
                "thermodynamics",
                "momentum",
            ),
        ),
        (
            "chemistry",
            (
                "balance this chemical equation",
                "balance the chemical equation",
                "stoichiometry",
                "molarity",
                "periodic table",
                "organic chemistry",
                "inorganic chemistry",
                "chemical bonding",
            ),
        ),
        (
            "mathematics",
            (
                "solve for x",
                "differentiate",
                "find the derivative",
                "find the integral",
                "matrix multiplication",
                "quadratic equation",
                "probability distribution",
            ),
        ),
    )

    for category, terms in domain_overrides:
        override_matches = tuple(
            term
            for term in terms
            if term in normalized
        )

        if override_matches:
            return TaskClassification(
                category=category,
                complexity=(
                    "complex"
                    if complex_structure
                    else "standard"
                ),
                confidence=0.99,
                matched_terms=override_matches,
            )

    scored_categories = {
        category: _score_category(
            normalized,
            category,
        )
        for category in _CATEGORY_PRIORITY
    }

    best_category: TaskCategory | None = None
    best_score = 0.0
    best_matches: tuple[str, ...] = ()

    for category in _CATEGORY_PRIORITY:
        score, matches = scored_categories[
            category
        ]

        if score > best_score:
            best_category = category
            best_score = score
            best_matches = matches

    if best_category is not None:
        complexity: TaskComplexity = (
            "complex"
            if (
                complex_structure
                or best_category in {
                    "deep_reasoning",
                    "research",
                }
            )
            else "standard"
        )

        confidence = min(
            0.99,
            0.72 + min(
                best_score,
                10.0,
            ) * 0.027,
        )

        return TaskClassification(
            category=best_category,
            complexity=complexity,
            confidence=round(
                confidence,
                2,
            ),
            matched_terms=best_matches,
        )

    if (
        word_count <= 14
        and "\n" not in message
    ):
        return TaskClassification(
            category="fast_chat",
            complexity="simple",
            confidence=0.72,
            matched_terms=(),
        )

    return TaskClassification(
        category="general",
        complexity=(
            "complex"
            if complex_structure
            else "standard"
        ),
        confidence=0.68,
        matched_terms=(),
    )
