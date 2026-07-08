"""Go AI — heuristic-guided MCTS with policy playouts."""

from __future__ import annotations

import copy
import math
import random
import time
from typing import Any

from app.games.go import board as go

DIFFICULTY_BUDGET_SEC = {
    "easy": 0.0,
    "medium": 4.0,
    "hard": 8.0,
}

DIFFICULTY_MAX_SIMS = {
    "easy": 0,
    "medium": 6400,
    "hard": 10000,
}

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


def _stone_count(position: dict[str, Any]) -> int:
    return sum(1 for row in position["board"] for c in row if c != go.EMPTY)


def _heuristic_score(position: dict[str, Any], row: int, col: int, color: int) -> float:
    board = position["board"]
    score = 0.0
    temp = copy.deepcopy(board)
    temp[row][col] = color

    for group in go._captures_if_played(temp, row, col, color):
        score += len(group) * 20.0

    for nr, nc in go.neighbors(row, col):
        stone = board[nr][nc]
        if stone == color:
            score += 4.0
            group = go.get_group(board, nr, nc)
            if len(go.group_liberties(board, group)) == 1:
                score += 8.0
        elif stone == go.OPPONENT[color]:
            score += 2.0

    for nr, nc in go.neighbors(row, col):
        if temp[nr][nc] != go.OPPONENT[color]:
            continue
        group = go.get_group(temp, nr, nc)
        if len(go.group_liberties(temp, group)) == 1:
            score += 7.0

    stones = _stone_count(position)
    if (row, col) in OPENING_POINTS and stones < 14:
        score += 4.0
    dist = abs(row - 4) + abs(col - 4)
    if stones < 20 and dist <= 2:
        score += 2.0
    if stones < 16 and (row == 0 or row == 8 or col == 0 or col == 8):
        score -= 2.0

    return score


def _quick_heuristic(board: list[list[int]], row: int, col: int, color: int) -> float:
    score = 0.0
    for nr, nc in go.neighbors(row, col):
        stone = board[nr][nc]
        if stone == color:
            score += 3.0
        elif stone == go.OPPONENT[color]:
            score += 1.5
        else:
            score += 0.4
    dist = abs(row - 4) + abs(col - 4)
    if dist <= 2:
        score += 0.5
    return score


def _top_plays(position: dict[str, Any], color: int, limit: int) -> list[dict[str, Any]]:
    legal = go.generate_legal_plays(position)
    if len(legal) <= limit:
        return legal
    scored = [(_heuristic_score(position, p["row"], p["col"], color), p) for p in legal]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]


def _quick_pick_play(position: dict[str, Any], color: int) -> dict[str, Any] | None:
    legal = go.generate_legal_plays(position)
    if not legal:
        return None
    board = position["board"]
    best_score = float("-inf")
    picks: list[dict[str, Any]] = []
    for play in legal:
        score = _quick_heuristic(board, play["row"], play["col"], color)
        if score > best_score:
            best_score = score
            picks = [play]
        elif score == best_score:
            picks.append(play)
    return random.choice(picks)


def _policy_playout(position: dict[str, Any], max_moves: int = 55) -> float:
    state = copy.deepcopy(position)
    passes = 0
    for _ in range(max_moves):
        if go.game_over_by_passes(state):
            break
        legal = go.generate_legal_plays(state)
        late_game = _stone_count(state) > 55

        if not legal:
            state = go.apply_pass_raw(state)
            passes += 1
            if passes >= 2:
                break
            continue

        if late_game and passes == 0 and random.random() < 0.1:
            state = go.apply_pass_raw(state)
            passes += 1
            continue

        passes = 0
        color = go.CHAR_COLOR[state["turn"]]
        play = _quick_pick_play(state, color)
        if not play:
            break
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
    budget_sec: float,
    max_sims: int,
) -> dict[str, Any] | None:
    root_plays = go.generate_legal_plays(position)
    if not root_plays:
        return None

    ordered_root = _top_plays(position, ai_color, 22)
    root = _MCTSNode(None, None, list(ordered_root))
    root.visits = 1
    deadline = time.monotonic() + budget_sec
    sims = 0

    while sims < max_sims and time.monotonic() < deadline:
        node = root
        state = copy.deepcopy(position)
        path: list[_MCTSNode] = [root]

        while not node.untried and node.children:
            node = max(node.children.values(), key=lambda n: n.uct_score(1.25))
            if node.move:
                state = go.apply_play_raw(state, node.move["row"], node.move["col"])
            path.append(node)

        if node.untried:
            move = node.untried.pop(0)
            state = go.apply_play_raw(state, move["row"], move["col"])
            next_color = go.CHAR_COLOR[state["turn"]]
            child = _MCTSNode(move, node, _top_plays(state, next_color, 14))
            node.children[move["coord"]] = child
            node = child
            path.append(node)

        outcome = _policy_playout(state)
        ai_sign = 1.0 if ai_color == go.BLACK else -1.0
        result = outcome * ai_sign

        for n in path:
            n.visits += 1
            n.value += result
        sims += 1

    if not root.children:
        return ordered_root[0] if ordered_root else root_plays[0]

    best_child = max(root.children.values(), key=lambda n: n.visits)
    return best_child.move


def choose_go_move(game_state: dict[str, Any], player_id: str) -> dict[str, Any]:
    """Pick a legal move for the AI seat."""
    position = game_state["position"]
    legal = go.generate_legal_plays(position)
    difficulty = str(game_state.get("settings", {}).get("ai_difficulty", "medium")).lower()
    if difficulty not in DIFFICULTY_BUDGET_SEC:
        difficulty = "medium"

    ai_color = _color_int(game_state, player_id)

    if difficulty == "easy":
        if random.random() < 0.35 and legal:
            play = random.choice(legal)
            return {"type": "play", "coord": play["coord"]}
        ordered = _top_plays(position, ai_color, 12)
        if ordered:
            top = ordered[: max(3, len(ordered) // 4)]
            play = random.choice(top)
            return {"type": "play", "coord": play["coord"]}
        return {"type": "pass"}

    play = _mcts_best_play(
        position,
        ai_color,
        DIFFICULTY_BUDGET_SEC[difficulty],
        DIFFICULTY_MAX_SIMS[difficulty],
    )
    if play:
        return {"type": "play", "coord": play["coord"]}

    return {"type": "pass"}
