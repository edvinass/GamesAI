"""Scribble: one player draws, everyone else guesses the word."""

from __future__ import annotations

import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.games.base import GamePlugin
from app.games.scribble.ai import choose_word_index, due_guesses, plan_guesses, queue_strokes
from app.games.scribble.words import POINTS, WORDS

CANVAS_W = 1000
CANVAS_H = 700
MAX_STROKES = 140
MAX_POINTS = 180
COLORS = {
    "#1c1917",
    "#e11d48",
    "#f97316",
    "#eab308",
    "#16a34a",
    "#0284c7",
    "#4f46e5",
    "#9333ea",
    "#92400e",
    "#f6f1e7",
}
PAPER = "#f6f1e7"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def normalize_guess(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _distance(left: str, right: str) -> int:
    if abs(len(left) - len(right)) > 2:
        return 99
    prev = list(range(len(right) + 1))
    for i, ch in enumerate(left, start=1):
        curr = [i]
        for j, other in enumerate(right, start=1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ch != other)))
        prev = curr
    return prev[-1]


def mask_word(word: str, revealed: set[int]) -> str:
    parts: list[str] = []
    for index, ch in enumerate(word):
        if ch == " ":
            parts.append(" ")
        elif index in revealed:
            parts.append(ch.upper())
        else:
            parts.append("_")
    return " ".join(parts)


class ScribbleEngine(GamePlugin):
    game_type = "scribble"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 8,
            "rounds": 2,
            "draw_seconds": 70,
            "choose_seconds": 12,
            "reveal_seconds": 5,
            "solo_practice": False,
            "ai_difficulty": "medium",
        }

    def validate_settings(self, settings: dict) -> dict:
        merged = {**self.default_settings(), **(settings or {})}
        merged["min_players"] = 2
        merged["max_players"] = 8
        merged["rounds"] = max(1, min(5, int(merged.get("rounds") or 2)))
        merged["draw_seconds"] = max(30, min(120, int(merged.get("draw_seconds") or 70)))
        merged["choose_seconds"] = max(5, min(20, int(merged.get("choose_seconds") or 12)))
        merged["reveal_seconds"] = max(3, min(10, int(merged.get("reveal_seconds") or 5)))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        if merged.get("ai_difficulty") not in ("easy", "medium", "hard"):
            merged["ai_difficulty"] = "medium"
        raw = merged.get("ai_difficulties")
        if isinstance(raw, dict):
            merged["ai_difficulties"] = {
                str(key): value if value in ("easy", "medium", "hard") else merged["ai_difficulty"]
                for key, value in raw.items()
            }
        else:
            merged["ai_difficulties"] = {}
        return merged

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        settings = self.validate_settings(settings)
        if settings.get("solo_practice"):
            humans = [p for p in players if not p.get("is_ai")]
            if len(humans) != 1:
                return "Solo practice requires exactly one human player"
            return None
        count = len(players)
        if count < settings["min_players"]:
            return f"Need at least {settings['min_players']} players"
        if count > settings["max_players"]:
            return f"Maximum {settings['max_players']} players allowed"
        return None

    def tick_interval_ms(self) -> int:
        return 1000

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        if len(players) < 2:
            raise ValueError("Scribble needs at least 2 players")
        difficulty = settings["ai_difficulty"]
        per_player = settings.get("ai_difficulties") or {}
        roster = []
        for player in players:
            roster.append(
                {
                    "id": player["id"],
                    "nickname": player.get("nickname") or "Player",
                    "is_ai": bool(player.get("is_ai")),
                    "ai_difficulty": per_player.get(player["id"], difficulty),
                    "score": 0,
                }
            )
        order = [player["id"] for player in roster]
        random.shuffle(order)
        state = {
            "players": roster,
            "settings": settings,
            "order": order,
            "turn_index": 0,
            "total_turns": settings["rounds"] * len(roster),
            "round": 1,
            "rounds": settings["rounds"],
            "phase": "choosing",
            "drawer_id": order[0],
            "word": None,
            "word_difficulty": None,
            "word_options": [],
            "word_mask": "",
            "revealed": [],
            "hint_stage": 0,
            "strokes": [],
            "guessed_ids": [],
            "round_points": {},
            "messages": [],
            "last_awards": [],
            "used_words": [],
            "phase_ends_at": None,
            "drawing_started_at": None,
            "ai_choose_at": None,
            "ai_guesses": [],
            "ai_strokes": [],
            "ai_stroke_at": None,
            "winner": None,
            "winner_ids": [],
            "win_reason": None,
            "canvas_width": CANVAS_W,
            "canvas_height": CANVAS_H,
            "last_action": None,
        }
        self._begin_choose(state)
        return state

    def _player(self, state: dict, player_id: str) -> dict | None:
        return next((p for p in state["players"] if p["id"] == player_id), None)

    def _nick(self, state: dict, player_id: str) -> str:
        player = self._player(state, player_id)
        return player["nickname"] if player else "Player"

    def _say(self, state: dict, text: str, kind: str = "system", player_id: str | None = None) -> None:
        state["messages"].append(
            {
                "id": len(state["messages"]) + 1,
                "player_id": player_id,
                "nickname": self._nick(state, player_id) if player_id else "",
                "text": text,
                "kind": kind,
            }
        )
        if len(state["messages"]) > 60:
            state["messages"] = state["messages"][-60:]

    def _pick_options(self, state: dict) -> list[dict[str, str]]:
        used = set(state.get("used_words") or [])
        pool = [word for word in WORDS if word["text"] not in used]
        if len(pool) < 3:
            state["used_words"] = []
            pool = list(WORDS)
        options: list[dict[str, str]] = []
        remaining = list(pool)
        for difficulty in ("easy", "medium", "hard"):
            bucket = [word for word in remaining if word["difficulty"] == difficulty] or remaining
            choice = random.choice(bucket)
            options.append({"text": choice["text"], "difficulty": choice["difficulty"]})
            remaining = [word for word in remaining if word["text"] != choice["text"]]
            if not remaining:
                break
        random.shuffle(options)
        return options

    def _begin_choose(self, state: dict) -> None:
        if state["turn_index"] >= state["total_turns"]:
            self._finish(state)
            return
        players = len(state["players"])
        state["round"] = state["turn_index"] // players + 1
        drawer_id = state["order"][state["turn_index"] % players]
        state["phase"] = "choosing"
        state["drawer_id"] = drawer_id
        state["word"] = None
        state["word_difficulty"] = None
        state["word_options"] = self._pick_options(state)
        state["word_mask"] = ""
        state["revealed"] = []
        state["hint_stage"] = 0
        state["strokes"] = []
        state["guessed_ids"] = []
        state["round_points"] = {}
        state["last_awards"] = []
        state["drawing_started_at"] = None
        state["ai_guesses"] = []
        state["ai_strokes"] = []
        state["ai_stroke_at"] = None
        choose_seconds = int(state["settings"]["choose_seconds"])
        state["phase_ends_at"] = _iso(_now() + timedelta(seconds=choose_seconds))
        drawer = self._player(state, drawer_id)
        if drawer and drawer.get("is_ai"):
            state["ai_choose_at"] = _iso(_now() + timedelta(seconds=1.4))
        else:
            state["ai_choose_at"] = None
        self._say(state, f"{self._nick(state, drawer_id)} is choosing a word")

    def _start_drawing(self, state: dict, option: dict[str, str]) -> None:
        word = option["text"]
        state["used_words"].append(word)
        state["word"] = word
        state["word_difficulty"] = option["difficulty"]
        state["word_options"] = []
        state["revealed"] = []
        state["word_mask"] = mask_word(word, set())
        state["hint_stage"] = 0
        state["strokes"] = []
        state["guessed_ids"] = []
        state["round_points"] = {}
        state["phase"] = "drawing"
        started = _now()
        state["drawing_started_at"] = _iso(started)
        state["phase_ends_at"] = _iso(started + timedelta(seconds=int(state["settings"]["draw_seconds"])))
        state["ai_choose_at"] = None
        drawer = self._player(state, state["drawer_id"])
        if drawer and drawer.get("is_ai"):
            state["ai_strokes"] = queue_strokes(word)
            state["ai_stroke_at"] = _iso(started + timedelta(seconds=1.0))
        else:
            state["ai_strokes"] = []
            state["ai_stroke_at"] = None
        state["ai_guesses"] = plan_guesses(state, started)
        self._say(state, f"{self._nick(state, state['drawer_id'])} is drawing")

    def _award_drawer(self, state: dict) -> None:
        earned = [int(points) for points in state["round_points"].values() if int(points) > 0]
        if not earned:
            return
        drawer_points = max(10, int(round(sum(earned) * 0.5)))
        drawer = self._player(state, state["drawer_id"])
        if not drawer:
            return
        drawer["score"] = int(drawer["score"]) + drawer_points
        state["round_points"][state["drawer_id"]] = int(state["round_points"].get(state["drawer_id"], 0)) + drawer_points

    def _end_drawing(self, state: dict, reason: str) -> None:
        if state.get("phase") != "drawing":
            return
        self._award_drawer(state)
        state["phase"] = "reveal"
        state["ai_strokes"] = []
        state["ai_guesses"] = []
        state["phase_ends_at"] = _iso(_now() + timedelta(seconds=int(state["settings"]["reveal_seconds"])))
        awards = []
        for player_id, points in state["round_points"].items():
            if int(points) <= 0:
                continue
            awards.append(
                {
                    "player_id": player_id,
                    "nickname": self._nick(state, player_id),
                    "points": int(points),
                }
            )
        awards.sort(key=lambda item: item["points"], reverse=True)
        state["last_awards"] = awards
        label = state.get("word") or ""
        if reason == "time":
            self._say(state, f"Time. The word was {label}")
        elif reason == "end":
            self._say(state, f"The word was {label}")
        else:
            self._say(state, f"Everyone got it. The word was {label}")

    def _finish(self, state: dict) -> None:
        state["phase"] = "finished"
        state["phase_ends_at"] = None
        ranking = sorted(state["players"], key=lambda player: int(player["score"]), reverse=True)
        top = int(ranking[0]["score"]) if ranking else 0
        winners = [player["id"] for player in ranking if int(player["score"]) == top]
        state["winner_ids"] = winners
        if len(winners) == 1:
            state["winner"] = winners[0]
            state["win_reason"] = "score"
            self._say(state, f"{self._nick(state, winners[0])} wins")
        else:
            state["winner"] = "tie"
            state["win_reason"] = "tie"
            self._say(state, "It's a tie")

    def _advance(self, state: dict) -> None:
        state["turn_index"] = int(state["turn_index"]) + 1
        self._begin_choose(state)

    def _guessers(self, state: dict) -> list[dict]:
        return [player for player in state["players"] if player["id"] != state.get("drawer_id")]

    def _everyone_guessed(self, state: dict) -> bool:
        guessers = self._guessers(state)
        if not guessers:
            return False
        guessed = set(state.get("guessed_ids") or [])
        return all(player["id"] in guessed for player in guessers)

    def _reveal_hint(self, state: dict) -> None:
        word = state.get("word") or ""
        revealed = set(state.get("revealed") or [])
        hidden = [index for index, ch in enumerate(word) if ch != " " and index not in revealed]
        if len(hidden) <= 1:
            return
        letters = {}
        for index in hidden:
            letters.setdefault(word[index], []).append(index)
        choice = random.choice(list(letters.values()))
        revealed.update(choice)
        state["revealed"] = sorted(revealed)
        state["word_mask"] = mask_word(word, revealed)
        state["hint_stage"] = int(state.get("hint_stage") or 0) + 1

    def _apply_stroke(self, state: dict, stroke: dict) -> None:
        if len(state["strokes"]) >= MAX_STROKES:
            raise ValueError("Canvas is full")
        color = str(stroke.get("color") or "").lower()
        if color not in COLORS:
            raise ValueError("Unknown color")
        try:
            size = int(stroke.get("size") or 16)
        except (TypeError, ValueError) as exc:
            raise ValueError("Bad brush size") from exc
        size = max(6, min(64, size))
        raw_points = stroke.get("points")
        if not isinstance(raw_points, list) or not raw_points:
            raise ValueError("Stroke needs points")
        points: list[list[int]] = []
        for point in raw_points[:MAX_POINTS]:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                x = int(round(float(point[0])))
                y = int(round(float(point[1])))
            except (TypeError, ValueError):
                continue
            points.append([max(0, min(CANVAS_W, x)), max(0, min(CANVAS_H, y))])
        if not points:
            raise ValueError("Stroke needs points")
        if len(points) == 1:
            points.append([points[0][0], min(CANVAS_H, points[0][1] + 1)])
        state["strokes"].append({"color": color, "size": size, "points": points})

    def _accept_guess(self, state: dict, player: dict, text: str) -> None:
        if state.get("phase") != "drawing":
            raise ValueError("You can guess while someone is drawing")
        if player["id"] == state.get("drawer_id"):
            raise ValueError("The drawer cannot guess")
        if player["id"] in state.get("guessed_ids", []):
            raise ValueError("You already got it")
        cleaned = " ".join(str(text or "").split())
        if not cleaned:
            raise ValueError("Type a guess")
        if len(cleaned) > 40:
            raise ValueError("Guess is too long")
        target = normalize_guess(state.get("word") or "")
        guess = normalize_guess(cleaned)
        if not guess:
            raise ValueError("Type a guess")
        if any(
            item.get("player_id") == player["id"]
            and item.get("kind") in ("wrong", "close")
            and normalize_guess(item.get("text") or "") == guess
            for item in state["messages"][-12:]
        ):
            raise ValueError("You already tried that")
        if guess == target:
            elapsed = 0.0
            started = _parse(state.get("drawing_started_at"))
            total = float(state["settings"]["draw_seconds"])
            if started:
                elapsed = max(0.0, (_now() - started).total_seconds())
            remaining = max(0.0, 1 - elapsed / total) if total else 0
            order_index = len(state["guessed_ids"])
            base = POINTS.get(state.get("word_difficulty") or "easy", 100)
            points = max(10, int(round(base * (0.25 + 0.75 * remaining) * max(0.45, 1 - 0.12 * order_index))))
            player["score"] = int(player["score"]) + points
            state["round_points"][player["id"]] = points
            state["guessed_ids"].append(player["id"])
            self._say(state, f"guessed it for {points}", "correct", player["id"])
            if self._everyone_guessed(state):
                self._end_drawing(state, "all")
            return
        close = len(target) >= 4 and _distance(guess, target) == 1
        self._say(state, cleaned, "close" if close else "wrong", player["id"])

    def apply_action(self, state: dict, action: dict, player: dict) -> tuple[dict, list[dict]]:
        if state.get("phase") == "finished":
            raise ValueError("Game is already over")
        actor = self._player(state, player["id"])
        if not actor:
            raise ValueError("Player not found")
        action_type = action.get("type")

        if action_type == "choose_word":
            if state.get("phase") != "choosing":
                raise ValueError("Not choosing a word")
            if actor["id"] != state.get("drawer_id"):
                raise ValueError("Only the drawer picks the word")
            options = state.get("word_options") or []
            try:
                index = int(action.get("index"))
            except (TypeError, ValueError) as exc:
                raise ValueError("Pick one of the words") from exc
            if index < 0 or index >= len(options):
                raise ValueError("Pick one of the words")
            self._start_drawing(state, options[index])
            state["last_action"] = {"type": "choose_word", "player_id": actor["id"]}
            return state, [{"type": "drawing_started", "drawer_id": actor["id"]}]

        if action_type == "stroke":
            if state.get("phase") != "drawing":
                raise ValueError("You can draw during the drawing turn")
            if actor["id"] != state.get("drawer_id"):
                raise ValueError("Only the drawer can draw")
            self._apply_stroke(state, action)
            state["last_action"] = {"type": "stroke", "player_id": actor["id"]}
            return state, []

        if action_type in ("undo", "clear"):
            if state.get("phase") != "drawing" or actor["id"] != state.get("drawer_id"):
                raise ValueError("Only the drawer can change the canvas")
            if action_type == "undo":
                if state["strokes"]:
                    state["strokes"].pop()
            else:
                state["strokes"] = []
            state["last_action"] = {"type": action_type, "player_id": actor["id"]}
            return state, [{"type": action_type}]

        if action_type == "end_turn":
            if state.get("phase") != "drawing" or actor["id"] != state.get("drawer_id"):
                raise ValueError("Only the drawer can end the turn")
            self._end_drawing(state, "end")
            state["last_action"] = {"type": "end_turn", "player_id": actor["id"]}
            return state, [{"type": "reveal"}]

        if action_type == "guess":
            self._accept_guess(state, actor, str(action.get("text") or ""))
            state["last_action"] = {"type": "guess", "player_id": actor["id"]}
            return state, [{"type": "guess", "player_id": actor["id"]}]

        raise ValueError("Unknown action")

    def tick(self, state: dict) -> tuple[dict, list[dict]]:
        if state.get("phase") == "finished":
            return state, []
        now = _now()
        events: list[dict] = []
        phase = state.get("phase")

        if phase == "choosing":
            drawer = self._player(state, state.get("drawer_id"))
            choose_at = _parse(state.get("ai_choose_at"))
            if drawer and drawer.get("is_ai") and choose_at and now >= choose_at and state.get("word_options"):
                index = choose_word_index(state)
                self._start_drawing(state, state["word_options"][index])
                return state, [{"type": "drawing_started", "drawer_id": drawer["id"]}]
            ends = _parse(state.get("phase_ends_at"))
            if ends and now >= ends and state.get("word_options"):
                index = random.randrange(len(state["word_options"]))
                self._start_drawing(state, state["word_options"][index])
                self._say(state, "Time's up, a word was picked")
                return state, [{"type": "drawing_started", "drawer_id": state["drawer_id"]}]
            return state, []

        if phase == "drawing":
            started = _parse(state.get("drawing_started_at"))
            total = float(state["settings"]["draw_seconds"])
            elapsed = (now - started).total_seconds() if started else 0
            stage = int(state.get("hint_stage") or 0)
            if stage < 1 and elapsed >= total / 3:
                self._reveal_hint(state)
                events.append({"type": "hint"})
            elif stage < 2 and elapsed >= (2 * total) / 3:
                self._reveal_hint(state)
                events.append({"type": "hint"})

            stroke_at = _parse(state.get("ai_stroke_at"))
            if state.get("ai_strokes") and stroke_at and now >= stroke_at:
                stroke = state["ai_strokes"].pop(0)
                try:
                    self._apply_stroke(state, stroke)
                except ValueError:
                    state["ai_strokes"] = []
                else:
                    gap = random.uniform(0.7, 1.15)
                    state["ai_stroke_at"] = _iso(now + timedelta(seconds=gap)) if state["ai_strokes"] else None
                    events.append({"type": "stroke"})

            for guess in due_guesses(state, now):
                guesser = self._player(state, guess["player_id"])
                if not guesser or state.get("phase") != "drawing":
                    break
                try:
                    self._accept_guess(state, guesser, guess["text"])
                    events.append({"type": "guess", "player_id": guesser["id"]})
                except ValueError:
                    continue
                if state.get("phase") != "drawing":
                    return state, events

            ends = _parse(state.get("phase_ends_at"))
            if state.get("phase") == "drawing" and ends and now >= ends:
                self._end_drawing(state, "time")
                events.append({"type": "reveal"})
            return state, events

        if phase == "reveal":
            ends = _parse(state.get("phase_ends_at"))
            if ends and now >= ends:
                self._advance(state)
                events.append({"type": "next_turn", "phase": state["phase"]})
            return state, events

        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = viewer_player["id"] if viewer_player else None
        phase = state.get("phase")
        drawer_id = state.get("drawer_id")
        is_drawer = viewer_id == drawer_id
        guessed = viewer_id in (state.get("guessed_ids") or [])
        show_word = phase in ("reveal", "finished") or is_drawer or guessed
        show_choices = phase == "choosing" and is_drawer
        players = []
        for player in state.get("players") or []:
            players.append(
                {
                    "id": player["id"],
                    "nickname": player["nickname"],
                    "is_ai": player.get("is_ai", False),
                    "score": int(player.get("score") or 0),
                    "guessed": player["id"] in (state.get("guessed_ids") or []),
                    "is_drawer": player["id"] == drawer_id,
                }
            )
        return {
            "game": "scribble",
            "phase": phase,
            "round": state.get("round"),
            "rounds": state.get("rounds"),
            "turn_index": state.get("turn_index"),
            "total_turns": state.get("total_turns"),
            "drawer_id": drawer_id,
            "word": state.get("word") if show_word else None,
            "word_difficulty": state.get("word_difficulty") if show_word else None,
            "word_options": state.get("word_options") if show_choices else None,
            "word_mask": state.get("word_mask") or "",
            "strokes": state.get("strokes") or [],
            "messages": state.get("messages") or [],
            "guessed_ids": list(state.get("guessed_ids") or []),
            "last_awards": state.get("last_awards") or [],
            "players": players,
            "phase_ends_at": state.get("phase_ends_at"),
            "canvas_width": CANVAS_W,
            "canvas_height": CANVAS_H,
            "paper": PAPER,
            "winner": state.get("winner"),
            "winner_ids": list(state.get("winner_ids") or []),
            "win_reason": state.get("win_reason"),
            "viewer_id": viewer_id,
            "viewer_is_drawer": is_drawer,
            "viewer_has_guessed": guessed,
            "settings": {
                "rounds": state["settings"]["rounds"],
                "draw_seconds": state["settings"]["draw_seconds"],
            },
        }

    def check_winner(self, state: dict) -> str | None:
        if state.get("phase") != "finished":
            return None
        return state.get("winner")
