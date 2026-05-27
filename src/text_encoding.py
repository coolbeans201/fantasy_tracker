"""Fix mis-encoded text from scrapes (UTF-8 shown as literal \\x escapes or mojibake)."""

from __future__ import annotations

import codecs
import re
import unicodedata
from typing import Any

import pandas as pd

_LITERAL_X_ESC = re.compile(r"\\x[0-9a-fA-F]{2}")
_LITERAL_U_ESC = re.compile(r"\\u[0-9a-fA-F]{4}")


def normalize_unicode_text(value: Any) -> str:
    """
    Repair common encoding mistakes in names from HTML/API sources.

    - Literal ``\\xc3\\xa9`` sequences (UTF-8 bytes written as text) -> ``é``
    - Mojibake ``JosÃ©`` (UTF-8 read as Latin-1) -> ``José``
    """
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "latin-1"):
            try:
                return value.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="replace").strip()

    text = str(value).strip()
    if not text:
        return text

    if _LITERAL_X_ESC.search(text) or _LITERAL_U_ESC.search(text):
        try:
            decoded = codecs.decode(text, "unicode_escape")
            if decoded:
                text = decoded
        except (UnicodeDecodeError, UnicodeError):
            pass

    for _ in range(2):
        if "Ã" not in text and "Â" not in text:
            break
        try:
            repaired = text.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            break
        if repaired == text:
            break
        text = repaired

    return text.strip()


def normalize_unicode_series(series: pd.Series) -> pd.Series:
    return series.map(normalize_unicode_text)


def fold_for_search(value: Any) -> str:
    """Lowercase name with accents removed for substring / token matching."""
    text = normalize_unicode_text(value).casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def player_name_matches_query(name: str, query: str) -> bool:
    """True when every query token appears in the name (accent-insensitive)."""
    folded_name = fold_for_search(name)
    tokens = [t for t in fold_for_search(query).split() if t]
    if not tokens:
        return False
    return all(token in folded_name for token in tokens)
