import re
from enum import StrEnum


class ResponseLanguage(StrEnum):
    ENGLISH = "english"
    HINGLISH = "hinglish"
    HINDI = "hindi"


_DEVANAGARI_PATTERN = re.compile(
    r"[\u0900-\u097F]"
)

_WORD_PATTERN = re.compile(
    r"[a-zA-Z']+"
)

_ENGLISH_REQUEST_PATTERNS = (
    "in english",
    "reply in english",
    "respond in english",
    "answer in english",
    "english only",
    "use english",
)

_HINDI_REQUEST_PATTERNS = (
    "in hindi",
    "reply in hindi",
    "respond in hindi",
    "answer in hindi",
    "hindi only",
    "use hindi",
)

_HINGLISH_REQUEST_PATTERNS = (
    "in hinglish",
    "reply in hinglish",
    "respond in hinglish",
    "answer in hinglish",
    "hinglish only",
    "use hinglish",
)

_ENGLISH_GREETING_MESSAGES = frozenset(
    {
        "hi",
        "hii",
        "hiii",
        "hello",
        "hello there",
        "hey",
        "hey there",
        "he",
        "good morning",
        "good afternoon",
        "good evening",
        "how are you",
        "what's up",
        "whats up",
    }
)

_HINGLISH_MARKERS = frozenset(
    {
        "ab",
        "abhi",
        "acha",
        "accha",
        "aage",
        "aap",
        "aur",
        "bata",
        "batao",
        "chahiye",
        "chaiye",
        "dekh",
        "dekho",
        "fir",
        "hai",
        "hain",
        "hoga",
        "hogi",
        "ho",
        "ka",
        "kaha",
        "kaise",
        "kar",
        "karo",
        "ki",
        "kya",
        "kyu",
        "kyun",
        "ma",
        "main",
        "mein",
        "mera",
        "meri",
        "mujhe",
        "nahi",
        "nahin",
        "phir",
        "samjhao",
        "se",
        "sirf",
        "tak",
        "theek",
        "thik",
        "tum",
        "wala",
        "wali",
        "wo",
        "ya",
        "ye",
    }
)


def detect_response_language(
    latest_message: str,
) -> ResponseLanguage:
    normalized = " ".join(
        latest_message
        .strip()
        .lower()
        .split()
    )

    if any(
        phrase in normalized
        for phrase in _ENGLISH_REQUEST_PATTERNS
    ):
        return ResponseLanguage.ENGLISH

    if any(
        phrase in normalized
        for phrase in _HINGLISH_REQUEST_PATTERNS
    ):
        return ResponseLanguage.HINGLISH

    if any(
        phrase in normalized
        for phrase in _HINDI_REQUEST_PATTERNS
    ):
        return ResponseLanguage.HINDI

    if _DEVANAGARI_PATTERN.search(
        latest_message
    ):
        return ResponseLanguage.HINDI

    if normalized in _ENGLISH_GREETING_MESSAGES:
        return ResponseLanguage.ENGLISH

    words = {
        word.lower()
        for word in _WORD_PATTERN.findall(
            latest_message
        )
    }

    hinglish_score = len(
        words.intersection(
            _HINGLISH_MARKERS
        )
    )

    if hinglish_score >= 1:
        return ResponseLanguage.HINGLISH

    # Latin-script ambiguous messages default to English.
    return ResponseLanguage.ENGLISH


def response_language_contract(
    latest_message: str,
) -> str:
    language = detect_response_language(
        latest_message
    )

    if language is ResponseLanguage.HINDI:
        instruction = (
            "Answer entirely in natural Hindi using "
            "Devanagari script. Keep unavoidable product "
            "names and technical identifiers unchanged."
        )

    elif language is ResponseLanguage.HINGLISH:
        instruction = (
            "Answer in natural, professional Hinglish using "
            "Latin script. Do not switch to Devanagari. "
            "Keep technical terms in English."
        )

    else:
        instruction = (
            "Answer entirely in clear natural English. "
            "Do not switch to Hindi, Hinglish, or "
            "Devanagari unless the latest user message "
            "explicitly requests it."
        )

    return f"""
RESPONSE LANGUAGE — STRICT AND NON-NEGOTIABLE

{instruction}

Determine response language only from the latest user message.
Ignore the language used by previous assistant responses and
older conversation messages.

Short Latin-script greetings such as "hi", "hii", "hello",
"hey", and "how are you" are English.
""".strip()
