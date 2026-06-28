from app.games.spyfall.ai import (
    RESIDENT_ANSWER_MAX_LEN,
    actor_is_spy,
    build_role_brief,
    is_answer_too_revealing,
)


def _make_state(spy_id: str = "p0", player_count: int = 3) -> dict:
    players = [{"id": f"p{i}", "nickname": f"Player {i}"} for i in range(player_count)]
    assignments = {f"p{i}": None if f"p{i}" == spy_id else "Doctor" for i in range(player_count)}
    return {
        "spy_id": spy_id,
        "location": {"name": "Hospital", "roles": ["Doctor", "Nurse", "Surgeon"]},
        "assignments": assignments,
        "players": players,
        "question_log": [],
    }


def test_actor_is_spy_normalizes_ids() -> None:
    state = _make_state("p0")
    assert actor_is_spy(state, "p0") is True
    assert actor_is_spy(state, "p1") is False


def test_spy_brief_never_includes_location_as_actionable() -> None:
    state = _make_state("p0")
    brief = build_role_brief(state, "p0")
    assert "SPY" in brief
    assert "do NOT know" in brief.lower() or "do NOT know the location" in brief


def test_resident_brief_marks_secrets() -> None:
    state = _make_state("p0")
    brief = build_role_brief(state, "p1")
    assert "Hospital" in brief
    assert "SECRET" in brief


def test_resident_answer_rejects_location_name() -> None:
    state = _make_state("p0")
    reason = is_answer_too_revealing("I love working at the Hospital cafeteria.", state, "p1")
    assert reason is not None


def test_resident_answer_rejects_role_and_job_language() -> None:
    state = _make_state("p0")
    state["assignments"]["p1"] = "Surgeon"
    assert is_answer_too_revealing("As a surgeon I scrub in early.", state, "p1") is not None
    assert is_answer_too_revealing("I handle patients every morning.", state, "p1") is not None


def test_resident_answer_rejects_long_or_wordy_replies() -> None:
    state = _make_state("p0")
    long_answer = "Well, you know, it really depends on quite a lot of different factors " * 2
    assert is_answer_too_revealing(long_answer, state, "p1") is not None


def test_resident_answer_allows_ultra_vague_replies() -> None:
    state = _make_state("p0")
    assert is_answer_too_revealing("Yeah, mostly.", state, "p1") is None
    assert is_answer_too_revealing("Not really, no.", state, "p1") is None
    assert is_answer_too_revealing("Same as always.", state, "p1") is None


def test_resident_answer_max_len_constant() -> None:
    assert RESIDENT_ANSWER_MAX_LEN <= 100
