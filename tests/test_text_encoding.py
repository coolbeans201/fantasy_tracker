"""Unicode normalization for scraped player names."""

from src.text_encoding import normalize_unicode_text


def test_literal_utf8_hex_escapes_in_name():
    broken = "Jos\\xc3\\xa9 Ram\\xc3\\xadrez"
    assert normalize_unicode_text(broken) == "José Ramírez"


def test_mojibake_latin1_read_of_utf8():
    assert normalize_unicode_text("JosÃ© RamÃ­rez") == "José Ramírez"


def test_passthrough_ascii_name():
    assert normalize_unicode_text("Mike Trout") == "Mike Trout"


def test_unicode_escape_u_form():
    assert normalize_unicode_text("Jos\\u00e9") == "José"
