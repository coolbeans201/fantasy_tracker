"""UI title-case helpers."""

from src.ui_text import section_h3, title_case_ui


def test_section_h3_title_case():
    assert section_h3("Career stat totals") == "### Career Stat Totals"


def test_title_case_preserves_abbreviations():
    assert title_case_ui("peer z (season)") == "Peer Z (Season)"
    assert title_case_ui("fantasy points by season") == "Fantasy Points By Season"
