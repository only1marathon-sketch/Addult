"""First-line text filter for prompts and chat (both user input and model output).

This keyword layer is a baseline only. People will try to get around it, so
in production ALSO run a vetted text-moderation classifier (e.g. Hive, OpenAI
moderation, or a self-hosted safety classifier) and keep the image checks in
image_checks.py switched on. Extend these lists with guidance from child-safety
organisations (e.g. Thorn, NCMEC, IWF) rather than guesswork.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FilterResult:
    allowed: bool
    category: str | None = None


# Anything suggesting a person under 18.
MINOR_TERMS = [
    "child", "children", "kid", "kids", "minor", "minors", "underage", "under age",
    "teen", "teens", "teenager", "teenage", "preteen", "pre-teen", "toddler", "infant",
    "juvenile", "schoolgirl", "schoolboy", "school girl", "school boy",
    "high school", "middle school", "elementary school", "young girl", "young boy",
    "little girl", "little boy", "daughter", "son", "niece", "nephew",
    "child-like", "childlike", "young-looking", "looks young", "petite child",
]
# Ages written as numbers below 18, e.g. "15 years old", "16yo", "aged 12".
UNDERAGE_NUMBER = re.compile(
    r"\b(?:[1-9]|1[0-7])\s*(?:yo|y/o|y\.o\.|yrs?|years?(?:\s*-?\s*old)?|-year-old)\b"
    r"|\baged?\s+(?:[1-9]|1[0-7])\b",
    re.IGNORECASE,
)

# Non-consensual content is against this platform's policy.
NONCONSENT_TERMS = [
    "rape", "raped", "non-consensual", "nonconsensual", "without consent", "against her will",
    "against his will", "unconscious", "asleep", "drugged", "passed out", "forced",
]

# Requests to depict real people. A celebrity/name list can be loaded from a file
# (one name per line); the image check also face-matches against known people.
REAL_PERSON_TERMS = ["deepfake", "deep fake", "real person", "my ex", "my coworker", "my classmate", "celebrity"]
_names_file = Path(__file__).with_name("blocked_names.txt")
BLOCKED_NAMES = (
    [n.strip().lower() for n in _names_file.read_text().splitlines() if n.strip()]
    if _names_file.exists()
    else []
)


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(re.search(r"\b" + re.escape(t) + r"\b", text) for t in terms)


def check_text(text: str) -> FilterResult:
    t = text.lower()
    if _contains_any(t, MINOR_TERMS) or UNDERAGE_NUMBER.search(t):
        return FilterResult(False, "minor")
    if _contains_any(t, NONCONSENT_TERMS):
        return FilterResult(False, "non_consent")
    if _contains_any(t, REAL_PERSON_TERMS) or _contains_any(t, BLOCKED_NAMES):
        return FilterResult(False, "real_person")
    return FilterResult(True)
