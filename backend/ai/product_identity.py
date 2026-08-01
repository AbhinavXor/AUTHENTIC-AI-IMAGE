from __future__ import annotations

import re


_SERENYA = re.compile(r"\b(?:serenya|serena)\b", re.IGNORECASE)
_SHERRY = re.compile(r"\b(?:sherry|shery)\b", re.IGNORECASE)
_AUTHENTIC_AI = re.compile(
    r"\bauthentic(?:[\s-]+)ai\b",
    re.IGNORECASE,
)

_SELF_IDENTITY = re.compile(
    r"\b(?:who are you|what are you|introduce yourself|"
    r"tum kaun ho|aap kaun ho|apne baare me batao)\b",
    re.IGNORECASE,
)
_IDENTITY_CUE = re.compile(
    r"\b(?:who|what|about|introduce|identity|role|capabilities|features|"
    r"help|works?|describe|explain|tell|kya|kaun|kon|batao|batana|"
    r"baare|bare|kaise|kis tarah)\b",
    re.IGNORECASE,
)
_INTERNAL_CUE = re.compile(
    r"\b(?:api|backend|provider|model|infrastructure|runtime|powered|"
    r"built|architecture|technology|engine)\b",
    re.IGNORECASE,
)
_CONTENT_TASK = re.compile(
    r"\b(?:pdf|document|file|logo|icon|image|screenshot|code|bug|error|"
    r"rename|create|generate|make|banao|report|presentation|project)\b",
    re.IGNORECASE,
)
_HINGLISH = re.compile(
    r"(?:[\u0900-\u097f]|\b(?:kya|kaun|kon|hai|ho|batao|batana|"
    r"baare|bare|kaise|kis|aur|ke|ki)\b)",
    re.IGNORECASE,
)


def _subject_names(message: str) -> tuple[str, ...]:
    subjects: list[str] = []
    if _SERENYA.search(message):
        subjects.append("serenya")
    if _SHERRY.search(message):
        subjects.append("sherry")
    if _AUTHENTIC_AI.search(message):
        subjects.append("authentic_ai")
    return tuple(subjects)


def _is_identity_request(
    message: str,
    subjects: tuple[str, ...],
) -> bool:
    if _SELF_IDENTITY.search(message):
        return True
    if not subjects:
        return False
    if _INTERNAL_CUE.search(message):
        return True
    if _CONTENT_TASK.search(message):
        return False
    if _IDENTITY_CUE.search(message):
        return True

    # A bare product name, with optional punctuation, is a natural request for
    # an introduction in a conversational interface.
    words = re.findall(r"[A-Za-z]+", message)
    return len(words) <= 4


def _english(subjects: tuple[str, ...]) -> str:
    paragraphs: list[str] = []
    if "serenya" in subjects:
        paragraphs.append(
            "**Serenya** is Authentic AI’s native intelligence experience, "
            "being developed to bring reasoning, learning, research, creation, "
            "and complex digital work into one unified assistant."
        )
    if "sherry" in subjects:
        paragraphs.append(
            "**Sherry** is Authentic AI’s voice intelligence, designed for "
            "natural spoken conversations and hands-free assistance."
        )
    if "authentic_ai" in subjects:
        paragraphs.append(
            "**Authentic AI** is a next-generation AI ecosystem under active "
            "development, built with the ambition to become one of the world’s "
            "most powerful and capable AI ecosystems. Serenya provides its "
            "native intelligence experience, while Sherry provides its voice "
            "intelligence experience."
        )
    return "\n\n".join(paragraphs)


def _hinglish(subjects: tuple[str, ...]) -> str:
    paragraphs: list[str] = []
    if "serenya" in subjects:
        paragraphs.append(
            "**Serenya** Authentic AI ki native intelligence hai—ise reasoning, "
            "learning, research, creation aur complex digital work ko ek unified "
            "assistant experience me handle karne ke liye develop kiya ja raha hai."
        )
    if "sherry" in subjects:
        paragraphs.append(
            "**Sherry** Authentic AI ki voice intelligence hai—natural voice "
            "conversations aur hands-free assistance ke liye design ki ja rahi hai."
        )
    if "authentic_ai" in subjects:
        paragraphs.append(
            "**Authentic AI** ek next-generation AI ecosystem hai jo world ke "
            "most powerful aur capable AI ecosystems me se ek banne ke vision ke "
            "saath active development me hai. Serenya iski native intelligence aur "
            "Sherry iski voice intelligence experience hai."
        )
    return "\n\n".join(paragraphs)


def resolve_product_identity_response(
    message: str,
) -> str | None:
    """Return the stable public product identity for genuine identity queries."""

    subjects = _subject_names(message)
    if _SELF_IDENTITY.search(message) and "serenya" not in subjects:
        subjects = ("serenya", *subjects)

    if not _is_identity_request(message, subjects):
        return None

    # When the ecosystem itself is requested, explain the two intelligence
    # experiences together without exposing implementation infrastructure.
    if "authentic_ai" in subjects:
        subjects = tuple(
            dict.fromkeys((*subjects, "serenya", "sherry"))
        )

    if _HINGLISH.search(message):
        return _hinglish(subjects)
    return _english(subjects)
