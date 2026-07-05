import copy

import pytest

from app.games.tetris.engine import TetrisEngine, _drop_interval_ticks
from app.games.tetris.pieces import piece_cells


def make_players(count: int = 2, ai_count: int = 0) -> list[dict]:
    players = []
    for i in range(count):
        players.append(
            {
                "id": f"p{i}",
                "nickname": f"Player {i}",
                "team": None,
                "role": None,
                "is_ai": i >= count - ai_count,
                "is_connected": True,
            }
        )
    return players


@pytest.fixture
def engine() -> TetrisEngine:
    return TetrisEngine()


@pytest.fixture
def state(engine: TetrisEngine) -> dict:
    players = make_players(2)
    s = engine.create_initial_state(players, {"countdown_sec": 0})
    s["phase"] = "playing"
    s["countdown_ends_at"] = None
    return s


def test_lobby_validation(engine: TetrisEngine) -> None:
    assert engine.validate_lobby(make_players(1), {}) is not None
    assert engine.validate_lobby(make_players(2), {}) is None
    assert engine.validate_lobby(make_players(4), {}) is None
    assert engine.validate_lobby(make_players(5), {}) is not None
    assert engine.validate_lobby(make_players(1), {"solo_practice": True}) is None
    assert engine.validate_lobby(make_players(2), {"solo_practice": True}) is not None
    assert engine.validate_lobby(make_players(1), {"single_player": True}) is None
    assert engine.validate_lobby(make_players(2), {"single_player": True}) is not None
    ai_player = make_players(1) + [{"id": "ai", "nickname": "AI", "team": None, "role": None, "is_ai": True, "is_connected": True}]
    assert engine.validate_lobby(ai_player, {"single_player": True}) is not None


def test_four_player_game_with_three_ai(engine: TetrisEngine) -> None:
    players = make_players(4, ai_count=3)
    game = engine.create_initial_state(players, {"countdown_sec": 0})
    assert len(game["boards"]) == 4
    assert len(game["players"]) == 4
    assert sum(1 for p in game["players"] if p["is_ai"]) == 3


def test_initial_state_per_player_boards(engine: TetrisEngine) -> None:
    players = make_players(3)
    game = engine.create_initial_state(players, {})
    assert len(game["boards"]) == 3
    assert game["phase"] == "countdown"
    for pid in game["boards"]:
        board = game["boards"][pid]
        assert board["active"] is not None
        assert board["alive"] is True
        assert len(board["grid"]) == 20


def test_move_and_rotate(engine: TetrisEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    board = state["boards"][pid]
    start_x = board["active"]["x"]

    state, _ = engine.apply_action(state, {"type": "move", "direction": "right"}, player)
    engine.tick(state)
    assert state["boards"][pid]["active"]["x"] == start_x + 1

    state, _ = engine.apply_action(state, {"type": "rotate", "direction": "cw"}, player)
    engine.tick(state)
    assert state["boards"][pid]["active"]["rotation"] == 1


def test_line_clear(engine: TetrisEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    board = state["boards"][pid]
    width = state["board_width"]
    color = "#000000"
    for x in range(width):
        board["grid"][19][x] = color
    board["grid"][18][0] = color
    board["active"] = {"type": "I", "rotation": 0, "x": 3, "y": 16}
    board["input_queue"] = [{"type": "hard_drop"}]

    state, events = engine.tick(state)
    assert state["boards"][pid]["lines_cleared"] >= 1
    assert any(e.get("type") == "lines_cleared" for e in events)


def _filled_rows(grid: list[list[str | None]], width: int) -> list[int]:
    return [y for y, row in enumerate(grid) if all(row[x] is not None for x in range(width))]


def test_multi_line_clear_removes_all_rows(engine: TetrisEngine) -> None:
    width, height = 10, 20
    for line_count in (2, 3, 4):
        grid = [[None] * width for _ in range(height)]
        for y in range(height - line_count, height):
            for x in range(width):
                grid[y][x] = "#111111"
        board = {
            "grid": grid,
            "active": {"type": "O", "rotation": 0, "x": 0, "y": 0},
            "lines_cleared": 0,
            "level": 1,
        }
        cleared = engine._lock_piece(board, width, height)
        assert cleared == line_count
        assert board["lines_cleared"] == line_count
        assert _filled_rows(board["grid"], width) == []
        assert len(board["grid"]) == height


def test_elimination_on_top_out(engine: TetrisEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    other = state["players"][1]["id"]
    board = state["boards"][pid]
    width = state["board_width"]
    height = state["board_height"]
    for y in range(3):
        for x in range(width):
            board["grid"][y][x] = "#111"
    board["active"] = None

    engine._spawn_or_eliminate(board, width, height)
    assert board["alive"] is False

    engine._resolve_winner(state)
    assert state["phase"] == "finished"
    assert state["winner"] == other


def test_last_standing_wins(engine: TetrisEngine, state: dict) -> None:
    p0, p1 = state["players"][0]["id"], state["players"][1]["id"]
    state["boards"][p0]["alive"] = False
    state["boards"][p1]["alive"] = True
    engine._resolve_winner(state)
    assert state["winner"] == p1
    assert state["win_reason"] == "last_standing"


def test_acceleration_by_level() -> None:
    assert _drop_interval_ticks(1, 20) == 20
    assert _drop_interval_ticks(2, 20) < 20
    assert _drop_interval_ticks(10, 20) >= 2


def test_gravity_tick_advances(engine: TetrisEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    board = state["boards"][pid]
    start_y = board["active"]["y"]
    for _ in range(25):
        engine.tick(state)
    assert state["boards"][pid]["active"]["y"] >= start_y


def test_natural_fall_spawns_next_piece(engine: TetrisEngine) -> None:
    players = make_players(1)
    players[0]["is_ai"] = False
    state = engine.create_initial_state(
        players, {"countdown_sec": 0, "single_player": True}
    )
    state["phase"] = "playing"
    pid = players[0]["id"]
    first_type = state["boards"][pid]["active"]["type"]

    for _ in range(2000):
        engine.tick(state)
        active = state["boards"][pid]["active"]
        if active["type"] != first_type and active["y"] <= 1:
            return

    pytest.fail("next piece never spawned after natural gravity fall")


def test_resting_piece_locks_without_hard_drop(engine: TetrisEngine, state: dict) -> None:
    from app.games.tetris.engine import LOCK_DELAY_TICKS

    player = state["players"][0]
    pid = player["id"]
    board = state["boards"][pid]
    width = state["board_width"]
    height = state["board_height"]

    for x in range(width):
        board["grid"][19][x] = "#111111"
    board["active"] = {"type": "O", "rotation": 0, "x": 4, "y": 17}
    board["input_queue"] = []
    board["lock_counter"] = 0
    board["drop_counter"] = 0

    assert not engine._can_move_down(board, width, height)

    for _ in range(LOCK_DELAY_TICKS):
        engine.tick(state)

    new_active = state["boards"][pid]["active"]
    assert new_active is not None
    assert new_active["y"] == 0


def test_ai_tick_does_not_crash(engine: TetrisEngine) -> None:
    players = make_players(2, ai_count=2)
    for p in players:
        if p["is_ai"]:
            p["ai_difficulty"] = "normal"
    game = engine.create_initial_state(players, {"countdown_sec": 0})
    game["phase"] = "playing"
    for _ in range(50):
        game, _ = engine.tick(game)
    assert game["phase"] in ("playing", "finished")


def test_ai_easy_slower_than_hard() -> None:
    from app.games.tetris.ai import get_ai_config

    easy = get_ai_config("easy")
    hard = get_ai_config("hard")
    assert easy["think_ticks"] > hard["think_ticks"]
    assert easy["action_delay_ticks"] > hard["action_delay_ticks"]


def test_assign_lobby_roles_sets_ai_difficulty(engine: TetrisEngine) -> None:
    players = make_players(2, ai_count=1)
    settings = {"ai_difficulties": {players[1]["id"]: "easy"}}
    result = engine.assign_lobby_roles(players, settings)
    assert result[1]["ai_difficulty"] == "easy"


def test_single_player_high_score_finish(engine: TetrisEngine) -> None:
    players = make_players(1)
    game = engine.create_initial_state(players, {"countdown_sec": 0, "single_player": True})
    game["phase"] = "playing"
    pid = players[0]["id"]
    board = game["boards"][pid]
    board["lines_cleared"] = 42
    board["level"] = 5
    board["alive"] = False
    board["active"] = None

    game, events = engine.tick(game)
    assert game["phase"] == "finished"
    assert game["win_reason"] == "high_score"
    assert game["final_score"] == 42
    assert game["winner"] == pid


def test_single_player_does_not_end_while_alive(engine: TetrisEngine) -> None:
    players = make_players(1)
    game = engine.create_initial_state(players, {"countdown_sec": 0, "single_player": True})
    game["phase"] = "playing"

    game, _ = engine.tick(game)
    assert game["phase"] == "playing"
    assert game.get("winner") is None
