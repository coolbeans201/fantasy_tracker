"""Tests for career table highlighting."""

import pandas as pd

from app.career_table import (
    format_peak_prime_caption,
    peak_and_prime_overlap,
    prime_season_years,
    season_highlight_tags,
    style_career_breakdown,
)


def test_prime_season_years():
    career = pd.DataFrame(
        {
            "season": [2019, 2020, 2021],
            "career_z": [0.5, 1.2, -0.3],
            "peer_qualified": [True, True, True],
        }
    )
    assert prime_season_years(career) == [2020]


def test_peak_and_prime_overlap():
    assert peak_and_prime_overlap(2020, [2018, 2020, 2022]) == [2020]
    assert peak_and_prime_overlap(2020, [2018, 2022]) == []


def test_season_highlight_tags_both():
    seasons = pd.Series([2019, 2020, 2021])
    tags = season_highlight_tags(seasons, peak_season=2020, prime_seasons=[2020, 2021])
    assert tags.tolist() == ["", "Peak · Prime", "Prime"]


def test_format_peak_prime_caption_calls_out_both():
    text = format_peak_prime_caption(2020, [2018, 2020, 2022])
    assert "both peak FP and a prime" in text
    assert "**2020**" in text


def test_style_career_breakdown_builds():
    display = pd.DataFrame({"Season": [2019, 2020], "Fantasy Points": [100, 200]})
    seasons = pd.Series([2019, 2020], index=display.index)
    styled = style_career_breakdown(
        display, seasons, peak_season=2020, prime_seasons=[2019, 2020]
    )
    assert styled is not None
