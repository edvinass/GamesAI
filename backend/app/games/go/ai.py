"""Go AI — heuristic move ordering with MCTS for medium/hard difficulties."""

from __future__ import annotations

import copy
import math
import random
from typing import Any

from app.games.go import board as go

DIFFICULTY_SIMULATIONS = {
    "easy": 0,
    "medium": 120,
    "hard": 400,
}

# 9×9 star points and center for opening bias
OPENING_POINTS = {
    (2, 2),
    (2, 6),
    (6, 2),
    (6, 6),
    (4, 4),
}


def _color_int(game_state: dict[str, Any], player_id: str) -> int:
    color_char = game_state["players"][player_id]["color"]
    return go.CHAR_COLOR[color_char]


def _heuristic_score(position: dict[str, Any], row: int, col: int, color: int) -> float:
    score = 0.0
    temp = copy.deepcopy(position["board"])
    temp[row][col] = color
    for group in go._captures_if_played(temp, row, col, color):
        score += len(group) * 12.0

    for nr, nc in go.neighbors(row, col):
        stone = position["board"][nr][nc]
        if stone == color:
            score += 3.0
        elif stone == go.OPPONENT[color]:
            score += 1.5

    if (row, col) in OPENING_POINTS and sum(
        1 for r in position["board"] for c in r if c != go.EMPTY
    ) < 12:
        score += 2.0

    # Prefer moves near center early
    dist = abs(row - 4) + abs(col - 4)
    if dist <= 2:
        score += 1.0

    return score


def _order_plays(position: dict[str, Any], color: int) -> list[dict[str, Any]]:
    plays = go.generate_legal_plays(position)
    scored = [( _heuristic_score(position, p["row"], p["col"], color), p) for p in plays]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored]


def _random_playout(position: dict[str, Any], max_moves: int = 80) -> float:
    """Return +1 if black wins, -1 if white wins, 0 for draw."""
    state = copy.deepcopy(position)
    passes = 0
    for _ in range(max_moves):
        if go.game_over_by_passes(state):
            break
        legal = go.generate_legal_plays(state)
        if not legal or random.random() < 0.08:
            state = go.apply_pass_raw(state)
            passes += 1
            if passes >= 2:
                break
            continue
        passes = 0
        play = random.choice(legal)
        state = go.apply_play_raw(state, play["row"], play["col"])

    if not go.game_over_by_passes(state):
        state = go.apply_pass_raw(state)
        if not go.game_over_by_passes(state):
            state = go.apply_pass_raw(state)

    result = go.score_position(state)
    wc = result["winner_color"]
    if wc == "B":
        return 1.0
    if wc == "W":
        return -1.0
    return 0.0


class _MCTSNode:
    __slots__ = ("move", "parent", "children", "untried", "visits", "value")

    def __init__(
        self,
        move: dict[str, Any] | None,
        parent: _MCTSNode | None,
        untried: list[dict[str, Any]],
    ) -> None:
        self.move = move
        self.parent = parent
        self.children: dict[str, _MCTSNode] = {}
        self.untried = untried
        self.visits = 0
        self.value = 0.0

    def uct_score(self, exploration: float) -> float:
        if self.visits == 0:
            return float("inf")
        assert self.parent is not None
        return self.value / self.visits + exploration * math.sqrt(
            math.log(self.parent.visits) / self.visits
        )


def _mcts_best_play(
    position: dict[str, Any],
    ai_color: int,
    simulations: int,
) -> dict[str, Any] | None:
    root_plays = go.generate_legal_plays(position)
    if not root_plays:
        return None

    root = _MCTSNode(None, None, list(root_plays))
    root.visits = 1

    for _ in range(simulations):
        node = root
        state = copy.deepcopy(position)
        path: list[_MCTSNode] = [root]

        # Selection
        while not node.untried and node.children:
            node = max(node.children.values(), key=lambda n: n.uct_score(1.4))
            if node.move:
                state = go.apply_play_raw(state, node.move["row"], node.move["col"])
            path.append(node)

        # Expansion
        if node.untried:
            move = node.untried.pop(random.randrange(len(node.untried)))
            state = go.apply_play_raw(state, move["row"], move["col"])
            child = _MCTSNode(move, node, go.generate_legal_plays(state))
            node.children[move["coord"]] = child
            node = child
            path.append(node)

        # Simulation
        outcome = _random_playout(state)
        ai_sign = 1.0 if ai_color == go.BLACK else -1.0
        result = outcome * ai_sign

        # Backpropagation
        for n in path:
            n.visits += 1
            n.value += result

    if not root.children:
        return root_plays[0]

    best_child = max(root.children.values(), key=lambda n: n.visits)
    return best_child.move


def choose_go_move(game_state: dict[str, Any], player_id: str) -> dict[str, Any]:
    """Pick a legal move for the AI seat."""
    position = game_state["position"]
    legal = go.generate_legal_plays(position)
    difficulty = str(game_state.get("settings", {}).get("ai_difficulty", "medium")).lower()
    if difficulty not in DIFFICULTY_SIMULATIONS:
        difficulty = "medium"

    ai_color = _color_int(game_state, player_id)
    color_char = go.COLOR_CHAR[ai_color]

    # Easy: often random, sometimes heuristic
    if difficulty == "easy":
        if random.random() < 0.5 and legal:
            play = random.choice(legal)
            return {"type": "play", "coord": play["coord"]}
        ordered = _order_plays(position, ai_color)
        if ordered:
            top = ordered[: max(3, len(ordered) // 3)]
            play = random.choice(top)
            return {"type": "play", "coord": play["coord"]}
        return {"type": "pass"}

    sims = DIFFICULTY_SIMULATIONS[difficulty]
    play = _mcts_best_play(position, ai_color, sims)
    if play:
        return {"type": "play", "coord": play["coord"]}

    # Pass if no legal plays (shouldn't happen often)
    return {"type": "pass"}
