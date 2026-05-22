"""Title-case helpers for UI headings and labels."""

from __future__ import annotations

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
}


def _cap_word(word: str) -> str:
    if word.startswith("(") and word.endswith(")") and len(word) > 2:
        return "(" + _cap_word(word[1:-1]) + ")"
    key = word.lower()
    if key in _SPECIAL_WORDS:
        return _SPECIAL_WORDS[key]
    if word.isupper() and len(word) <= 5:
        return word
    return word.capitalize()


def title_case_ui(text: str) -> str:
    """Title-case a UI label (every word capitalized; preserves abbreviations)."""
    if not text or not str(text).strip():
        return text
    return " ".join(_cap_word(w) for w in str(text).split())


def section_h3(title: str) -> str:
    """Markdown H3 section heading with consistent title casing."""
    return f"### {title_case_ui(title)}"


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
