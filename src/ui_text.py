"""Title-case helpers for UI headings and labels."""

from __future__ import annotations

import re

# Lowercase token -> display form (abbreviations and fantasy terms)
_SPECIAL_WORDS: dict[str, str] = {
    "z": "Z",
    "fp": "FP",
    "d/st": "D/ST",
    "dst": "DST",
    "espn": "ESPN",
    "ppr": "PPR",
    "nfl": "NFL",
    "qb": "QB",
    "rb": "RB",
    "wr": "WR",
    "te": "TE",
    "k": "K",
    "pat": "PAT",
    "fg": "FG",
    "td": "TD",
    "tds": "TDs",
    "int": "INT",
    "csv": "CSV",
    "ecr": "ECR",
    "σ": "σ",
    "δ": "Δ",
}

# Lowercase in titles unless first/last word (or after hyphen chunk start)
_SMALL_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "but",
        "or",
        "for",
        "nor",
        "on",
        "at",
        "to",
        "from",
        "by",
        "vs",
        "in",
        "of",
        "as",
        "per",
        "with",
    }
)


def _cap_subword(word: str, *, force: bool) -> str:
    if not word:
        return word
    if len(word) == 1 and not word.isalnum():
        return word
    if word.startswith("(") and ")" in word:
        inner = word[1 : word.index(")")]
        rest = word[word.index(")") :]
        return "(" + _cap_subword(inner, force=True) + rest
    key = word.lower()
    if key in _SPECIAL_WORDS:
        return _SPECIAL_WORDS[key]
    if not force and key in _SMALL_WORDS:
        return key
    if word.isupper() and len(word) <= 6:
        return word
    if word.isdigit():
        return word
    return word[:1].upper() + word[1:].lower() if word else word


def _cap_word(word: str, *, index: int, total: int) -> str:
    force = index == 0 or index == total - 1
    if "-" in word:
        parts = word.split("-")
        return "-".join(
            _cap_subword(part, force=force or (i == 0) or (i == len(parts) - 1))
            for i, part in enumerate(parts)
        )
    return _cap_subword(word, force=force)


def title_case_ui(text: str) -> str:
    """Title-case a UI label; keeps short prepositions lowercase; preserves abbreviations."""
    if not text or not str(text).strip():
        return text
    raw = str(text).strip()
    # Preserve simple parenthetical segments: "Season detail (2023)"
    if "(" in raw and raw.endswith(")"):
        m = re.match(r"^(.+?)\s*(\([^)]+\))\s*$", raw)
        if m:
            return f"{title_case_ui(m.group(1).strip())} {m.group(2)}"
    words = raw.split()
    return " ".join(_cap_word(w, index=i, total=len(words)) for i, w in enumerate(words))


def section_h3(title: str) -> str:
    """Markdown H3 section heading with consistent title casing."""
    return f"### {title_case_ui(title)}"


def bold_heading(title: str) -> str:
    """Bold markdown subheading with consistent title casing."""
    return f"**{title_case_ui(title)}**"


def page_title_suffix(page_name: str) -> str:
    """Browser tab title: `Page Name | Fantasy Tracker`."""
    return f"{title_case_ui(page_name)} | Fantasy Tracker"


_BEST_WEEK_SCORING_LABELS: dict[str, str] = {
    "standard": "Standard",
    "half_ppr": "Half-PPR",
    "full_ppr": "Full PPR",
    "kicker": "ESPN Kicker",
    "dst": "ESPN D/ST",
}


def best_week_scoring_label(scoring_key: str | None) -> str:
    """Human label for which preset best_week_fp uses (stored at ingest)."""
    if not scoring_key or str(scoring_key).strip().lower() in ("", "nan"):
        return "Half-PPR"
    return _BEST_WEEK_SCORING_LABELS.get(str(scoring_key).strip().lower(), str(scoring_key))


def best_week_fp_column_label(scoring_key: str | None = None) -> str:
    preset = best_week_scoring_label(scoring_key)
    return f"Best Week FP ({preset})"
