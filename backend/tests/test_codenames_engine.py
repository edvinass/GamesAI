from app.games.codenames.engine import CodenamesEngine


def _make_state() -> dict:
    engine = CodenamesEngine()
    return engine.create_initial_state(
        [
            {"id": "s1", "name": "Spy", "team": "red", "role": "spymaster", "is_ai": False},
            {"id": "o1", "name": "Op", "team": "red", "role": "operative", "is_ai": False},
        ],
        {},
    )


def test_ai_model_setting_accepts_openai_and_falls_back() -> None:
    engine = CodenamesEngine()

    assert engine.validate_settings({})["ai_model"] == "deepseek-v4-pro"
    assert engine.validate_settings({"ai_model": "gpt-6-astra"})["ai_model"] == "gpt-6-astra"
    assert engine.validate_settings({"ai_model": "gpt-6.1-sol"})["ai_model"] == "gpt-6.1-sol"
    assert engine.validate_settings({"ai_model": "gpt-4o"})["ai_model"] == "deepseek-v4-pro"


def test_spymaster_sees_all_card_colors() -> None:
    engine = CodenamesEngine()
    state = _make_state()
    view = engine.get_public_state(
        state, {"id": "s1", "team": "red", "role": "spymaster"}
    )

    assert all("color" in card for card in view["cards"])
    assert view["viewer_role"] == "spymaster"


def test_operative_and_anonymous_views_hide_unrevealed_colors() -> None:
    engine = CodenamesEngine()
    state = _make_state()
    op_view = engine.get_public_state(
        state, {"id": "o1", "team": "red", "role": "operative"}
    )
    anon_view = engine.get_public_state(state, None)

    for view in (op_view, anon_view):
        for card in view["cards"]:
            if card["revealed"]:
                assert "color" in card
            else:
                assert "color" not in card
