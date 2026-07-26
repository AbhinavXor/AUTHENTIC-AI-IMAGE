import re

from schemas.chat import ChatMessage


_FOLLOW_UP_PATTERN = re.compile(
    (
        r"\b(?:plot|graph|draw|visuali[sz]e|chart)\b"
        r"|"
        r"\b(?:it|this|that|same|above|previous)\b"
    ),
    re.IGNORECASE,
)

_SELF_CONTAINED_MATH_PATTERN = re.compile(
    (
        r"\b(?:[fgh]\s*\(\s*x\s*\)|y)\s*="
        r"|"
        r"\b[a-z]\s*(?:\^|\*\*)\s*[-+]?\d+"
        r"|"
        r"\b[a-z]\s+(?:square|squared|cube|cubed)\b"
        r"|"
        r"\b[a-z]\b[\s\S]{0,100}"
        r"(?<![<>])=(?!=)[\s\S]{0,100}\d"
    ),
    re.IGNORECASE,
)

_HISTORY_MATH_PATTERN = re.compile(
    (
        r"\b(?:math|algebra|calculus|equation|derivative|"
        r"integral|solve|factor|polynomial)\b"
        r"|"
        r"\b(?:[fgh]\s*\(\s*x\s*\)|y)\s*="
        r"|"
        r"\b[a-z]\s*(?:\^|\*\*)\s*[-+]?\d+"
        r"|"
        r"\b[a-z]\s+(?:square|squared|cube|cubed)\b"
        r"|"
        r"\b[a-z]\b[\s\S]{0,120}"
        r"(?<![<>])=(?!=)[\s\S]{0,120}\d"
    ),
    re.IGNORECASE,
)


def resolve_contextual_request(
    message: str,
    history: list[ChatMessage],
) -> str:
    """
    Resolve short follow-up requests such as "plot a graph"
    against the most recent relevant user mathematics message.
    """

    cleaned_message = message.strip()

    if (
        not cleaned_message
        or not _FOLLOW_UP_PATTERN.search(
            cleaned_message
        )
        or _SELF_CONTAINED_MATH_PATTERN.search(
            cleaned_message
        )
    ):
        return cleaned_message

    previous_math_request: str | None = None

    for item in reversed(history):
        if item.role != "user":
            continue

        candidate = item.content.strip()

        if (
            candidate
            and _HISTORY_MATH_PATTERN.search(
                candidate
            )
        ):
            previous_math_request = (
                candidate[:2_500]
            )
            break

    if previous_math_request is None:
        return cleaned_message

    return (
        f"{cleaned_message}\n\n"
        "Relevant earlier mathematical request:\n"
        f"{previous_math_request}\n\n"
        "Use the earlier mathematical expression as "
        "the subject of the current follow-up. "
        "For graphing an equation, treat the difference "
        "between its two sides as a function of x. "
        "Do not mention these contextual instructions."
    )
