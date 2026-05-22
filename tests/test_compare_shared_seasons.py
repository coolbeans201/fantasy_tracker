from src.db.queries import compare_shared_seasons, compare_union_seasons


def test_compare_shared_seasons_intersection():
    class FakeConn:
        pass

    calls: list[str] = []

    def fake_available(_conn, entity_id: str, _preset: str) -> list[int]:
        calls.append(entity_id)
        if entity_id == "a":
            return [2018, 2019, 2020]
        return [2019, 2020, 2021]

    import src.db.queries as qmod

    original = qmod.entity_seasons_available
    qmod.entity_seasons_available = fake_available
    try:
        shared = compare_shared_seasons(FakeConn(), "a", "b", "Half-PPR")
    finally:
        qmod.entity_seasons_available = original

    assert shared == [2020, 2019]
    assert calls == ["a", "b"]


def test_compare_union_seasons_union():
    class FakeConn:
        pass

    def fake_available(_conn, entity_id: str, _preset: str) -> list[int]:
        if entity_id == "a":
            return [2018, 2019, 2020]
        return [2019, 2020, 2021]

    import src.db.queries as qmod

    original = qmod.entity_seasons_available
    qmod.entity_seasons_available = fake_available
    try:
        union = compare_union_seasons(FakeConn(), "a", "b", "Half-PPR")
    finally:
        qmod.entity_seasons_available = original

    assert union == [2021, 2020, 2019, 2018]
