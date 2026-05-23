"""Tests for UI text helpers."""

from src.ui_text import (
    best_week_fp_column_label,
    best_week_scoring_label,
    bold_heading,
    page_title_suffix,
    section_h3,
    title_case_ui,
)


def test_title_case_ui():
    assert title_case_ui("peer z (season)") == "Peer Z (Season)"


def test_title_case_small_words():
    assert title_case_ui("Fantasy points by season") == "Fantasy Points by Season"
    assert title_case_ui("Season by season") == "Season by Season"
    assert title_case_ui("Winners & losers vs draft rank") == "Winners & Losers vs Draft Rank"


def test_title_case_parenthetical_year():
    assert title_case_ui("Season detail (2023)") == "Season Detail (2023)"


def test_section_h3():
    assert section_h3("Career & window") == "### Career & Window"


def test_bold_heading():
    assert bold_heading("Beat draft rank — top 10") == "**Beat Draft Rank — Top 10**"


def test_page_title_suffix():
    assert page_title_suffix("Compare Players") == "Compare Players | Fantasy Tracker"


def test_best_week_labels():
    assert "Half-PPR" in best_week_fp_column_label("half_ppr")
    assert best_week_scoring_label("kicker") == "ESPN Kicker"


def test_title_case_csv():
    assert title_case_ui("Download weekly CSV") == "Download Weekly CSV"
    assert title_case_ui("Download career CSV") == "Download Career CSV"
