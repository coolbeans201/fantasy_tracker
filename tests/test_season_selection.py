from src.season_selection import (
    SEASON_MODE_PICK,
    SEASON_MODE_RANGE,
    SEASON_MODE_SINGLE,
    format_season_label,
    format_season_span,
    is_multi_season_window,
    resolve_season_window,
)


def test_resolve_single_season():
    ingested = [2020, 2021, 2022]
    assert resolve_season_window(
        ingested, SEASON_MODE_SINGLE, single_year=2021
    ) == [2021]


def test_resolve_range_contiguous():
    ingested = list(range(2018, 2024))
    got = resolve_season_window(
        ingested, SEASON_MODE_RANGE, range_start=2019, range_end=2021
    )
    assert got == [2021, 2020, 2019]


def test_resolve_pick_non_contiguous():
    ingested = list(range(2018, 2024))
    got = resolve_season_window(
        ingested, SEASON_MODE_PICK, picked=[2018, 2022]
    )
    assert got == [2022, 2018]


def test_format_season_label_range_vs_pick():
    assert format_season_label([2018, 2019, 2020]) == "2018-2020"
    assert format_season_label([2018, 2020]) == "2018_2020"


def test_format_season_span_pick():
    assert format_season_span([2019, 2021, 2024]) == "2019, 2021, 2024"


def test_is_multi_season_window():
    assert not is_multi_season_window([2023])
    assert is_multi_season_window([2020, 2021])
