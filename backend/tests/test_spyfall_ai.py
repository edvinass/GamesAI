from app.games.spyfall.ai import actor_is_spy, build_role_brief


def _make_state(spy_id: str = "p0") -> dict:
    return {
        "spy_id": spy_id,
        "location": {"name": "Hospital", "roles": ["Doctor", "Nurse"]},
        "assignments": {"p0": None, "p1": "Doctor", "p2": "Nurse"},
        "players": [
            {"id": "p0", "nickname": "Alice"},
            {"id": "p1", "nickname": "Bob"},
            {"id": "p2", "nickname": "Carol"},
        ],
        "question_log": [],
    }


def test_actor_is_spy_normalizes_ids() -> None:
    state = _make_state("p0")
    assert actor_is_spy(state, "p0") is True
    assert actor_is_spy(state, "p1") is False


def test_spy_brief_never_includes_location() -> None:
    state = _make_state("p0")
    brief = build_role_brief(state, "p0")
    assert "SPY" in brief
    assert "Hospital" not in brief
    assert "Doctor" not in brief


def test_resident_brief_includes_location_and_role() -> None:
    state = _make_state("p0")
    brief = build_role_brief(state, "p1")
    assert "Hospital" in brief
    assert "Doctor" in brief
    assert "SPY" not in brief or "not the spy" in brief.lower()
