"""Tests for UI text helpers."""

from src.ui_text import best_week_fp_column_label, best_week_scoring_label, title_case_ui


def test_title_case_ui():
    assert title_case_ui("peer z (season)") == "Peer Z (Season)"


def test_best_week_labels():
    assert "Half-PPR" in best_week_fp_column_label("half_ppr")
    assert best_week_scoring_label("kicker") == "ESPN Kicker"


def test_title_case_csv():
    assert title_case_ui("Download weekly CSV") == "Download Weekly CSV"
    assert title_case_ui("Download career CSV") == "Download Career CSV"
