from src.sports.game_logs import mlb_two_way_career


class _Conn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _sql, _params):
        return self

    def fetchall(self):
        return self._rows


def test_mlb_two_way_career_true_when_roles_split_across_seasons():
    conn = _Conn([(2023, "DH"), (2024, "SP"), (2024, "DH")])
    assert mlb_two_way_career(conn, "660271") is True


def test_mlb_two_way_career_false_for_pitcher_only():
    conn = _Conn([(2024, "SP")])
    assert mlb_two_way_career(conn, "1") is False
