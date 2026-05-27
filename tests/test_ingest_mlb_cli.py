"""MLB ingest CLI helpers."""

from scripts.ingest_mlb import _parse_seasons_arg


def test_parse_seasons_arg_mixed_values():
    out = _parse_seasons_arg("2019,2021-2023,2020")
    assert out == [2019, 2020, 2021, 2022, 2023]


def test_parse_seasons_arg_reverse_range():
    out = _parse_seasons_arg("2024-2022")
    assert out == [2022, 2023, 2024]
