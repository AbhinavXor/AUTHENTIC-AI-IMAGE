from dataclasses import dataclass
from typing import Literal

from ai.visualization_contract import (
    VISUALIZATION_CONTRACT,
    wants_visualization,
)


ResponseIntent = Literal[
    "direct",
    "comparison",
    "procedure",
    "coding",
    "decision",
    "analysis",
    "summary",
    "brainstorming",
]

ReasoningEffort = Literal[
    "low",
    "medium",
    "high",
]


@dataclass(frozen=True, slots=True)
class ResponsePlan:
    """Deterministic answer-generation contract."""

    intent: ResponseIntent
    reasoning_effort: ReasoningEffort
    max_completion_tokens: int
    contract: str


_COMPARISON_TERMS = (
    "compare",
    "comparison",
    "difference between",
    "differences between",
    "versus",
    " vs ",
    "better than",
    "farak",
    "antar",
)

_PROCEDURE_TERMS = (
    "how to",
    "how do i",
    "steps",
    "step by step",
    "setup",
    "configure",
    "install",
    "implement",
    "kaise",
    "kaha paste",
    "kahan paste",
)

_CODING_TERMS = (
    "code",
    "typescript",
    "javascript",
    "python",
    "react",
    "fastapi",
    "api",
    "database",
    "sql",
    "docker",
    "backend",
    "frontend",
    "architecture",
    "repository",
    "function",
    "class",
    "bug",
    "error",
    "stack trace",
)

_DECISION_TERMS = (
    "which is better",
    "which should",
    "should i",
    "recommend",
    "recommendation",
    "best option",
    "choose",
    "decision",
    "trade-off",
    "tradeoff",
)

_ANALYSIS_TERMS = (
    "analyze",
    "analysis",
    "deep research",
    "research",
    "evaluate",
    "investigate",
    "audit",
    "review",
    "market gap",
    "strategy",
)

_SUMMARY_TERMS = (
    "summarize",
    "summary",
    "shorten",
    "brief",
    "recap",
)

_BRAINSTORMING_TERMS = (
    "brainstorm",
    "ideas",
    "idea list",
    "suggest names",
    "creative options",
)

_COMPLEXITY_TERMS = (
    "production",
    "enterprise",
    "security",
    "scalable",
    "millions of users",
    "industry grade",
    "architecture",
    "performance",
    "compliance",
    "detailed",
    "deep",
    "comprehensive",
    "complete system",
)


_CONTRACTS: dict[ResponseIntent, str] = {
    "direct": """
Give the direct answer immediately.

Structure:
- Use two to four short paragraphs.
- Do not add a heading unless the topic genuinely needs one.
- Use a list only when there are at least three parallel points.
- Include one concrete example when it materially improves clarity.
- Do not add a generic conclusion.
""".strip(),

    "comparison": """
Start with the core relationship or most important distinction in one
or two sentences.

Then:
1. Use a compact Markdown table with only meaningful comparison
   dimensions.
2. Give one concrete example for each compared item.
3. Add a short practical decision rule explaining when each option is
   appropriate.

Do not use generic headings such as "Introduction", "Key Differences",
or "Conclusion". Do not repeat the same distinction in prose and table.
""".strip(),

    "procedure": """
Start with the intended result.

Then provide:
1. Prerequisites only when required.
2. Numbered implementation steps in execution order.
3. Exact commands or code where applicable.
4. A verification step with expected output.
5. Common failure cases only when they are realistically relevant.

Do not bury the required action beneath background explanation.
""".strip(),

    "coding": """
Act as a principal software engineer.

Structure:
1. State the architecture or implementation decision.
2. Explain any important trade-off before code.
3. Provide production-ready, complete code rather than fragments.
4. Preserve existing architecture and modify only necessary files.
5. Include input validation, error handling, security, type safety,
   observability, and cleanup where applicable.
6. Include exact verification commands.
7. Mention remaining risks only when real.

Do not generate beginner demo code or rewrite unrelated project files.
""".strip(),

    "decision": """
Start with the recommendation.

Then provide:
1. Why it is the best option.
2. Important trade-offs.
3. Situations where another option would be better.
4. A short decision rule the user can apply.

Separate facts, assumptions, and recommendations clearly.
""".strip(),

    "analysis": """
Start with the principal finding.

Then organize the response into a small number of descriptive sections:
- Evidence or observations
- Interpretation
- Risks or limitations
- Recommended action

Prioritize important findings. Avoid generic filler, repeated summaries,
and unsupported certainty.
""".strip(),

    "summary": """
Preserve the source meaning and terminology.

Structure:
- Begin with the central point.
- Retain important decisions, numbers, constraints, and unresolved
  issues.
- Use a short bullet list only when it improves scanning.
- Do not introduce information that was not present in the source.
""".strip(),

    "brainstorming": """
Produce distinct, non-duplicate options.

For every meaningful option include:
- The idea
- Why it could work
- The main risk or weakness

Group options by strategy rather than returning one undifferentiated
list. Prefer quality and originality over a large count.
""".strip(),
}


def _contains_any(
    normalized_message: str,
    terms: tuple[str, ...],
) -> bool:
    return any(
        term in normalized_message
        for term in terms
    )


def _classify_intent(
    normalized_message: str,
) -> ResponseIntent:
    if _contains_any(
        normalized_message,
        _COMPARISON_TERMS,
    ):
        return "comparison"

    if _contains_any(
        normalized_message,
        _PROCEDURE_TERMS,
    ):
        return "procedure"

    if _contains_any(
        normalized_message,
        _CODING_TERMS,
    ):
        return "coding"

    if _contains_any(
        normalized_message,
        _DECISION_TERMS,
    ):
        return "decision"

    if _contains_any(
        normalized_message,
        _ANALYSIS_TERMS,
    ):
        return "analysis"

    if _contains_any(
        normalized_message,
        _SUMMARY_TERMS,
    ):
        return "summary"

    if _contains_any(
        normalized_message,
        _BRAINSTORMING_TERMS,
    ):
        return "brainstorming"

    return "direct"


def _complexity_score(
    normalized_message: str,
) -> int:
    score = 0
    word_count = len(normalized_message.split())

    if word_count >= 40:
        score += 1

    if word_count >= 100:
        score += 1

    if normalized_message.count("?") >= 2:
        score += 1

    if normalized_message.count("\n") >= 3:
        score += 1

    score += min(
        2,
        sum(
            term in normalized_message
            for term in _COMPLEXITY_TERMS
        ),
    )

    return score


def create_response_plan(
    message: str,
) -> ResponsePlan:
    """Create a low-latency answer plan without another model call."""

    normalized = " ".join(
        message.lower().split()
    )

    intent = _classify_intent(normalized)
    complexity = _complexity_score(normalized)

    if intent in {
        "coding",
        "analysis",
    }:
        reasoning_effort: ReasoningEffort = "high"
        max_tokens = 2_800

    elif intent in {
        "comparison",
        "decision",
        "procedure",
    }:
        reasoning_effort = (
            "high"
            if complexity >= 2
            else "medium"
        )
        max_tokens = 2_000

    elif intent in {
        "summary",
        "brainstorming",
    }:
        reasoning_effort = "medium"
        max_tokens = 1_800

    else:
        reasoning_effort = (
            "medium"
            if complexity >= 1
            else "low"
        )
        max_tokens = 1_200

    contract = _CONTRACTS[intent]

    if wants_visualization(message):
        reasoning_effort = "high"
        max_tokens = max(
            max_tokens,
            2_800,
        )
        contract = (
            f"{contract}\n\n"
            f"{VISUALIZATION_CONTRACT}"
        )

    return ResponsePlan(
        intent=intent,
        reasoning_effort=reasoning_effort,
        max_completion_tokens=max_tokens,
        contract=contract,
    )
