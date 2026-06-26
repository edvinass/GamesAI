import json
import random
import uuid
from pathlib import Path
from typing import Any

from app.games.base import GamePlugin

WORD_LIST_DIR = Path(__file__).parent / "word_lists"

CARD_COLORS = ("red", "blue", "neutral", "assassin")
STARTING_TEAM_COUNTS = {"red": 9, "blue": 8}


class CodenamesEngine(GamePlugin):
    game_type = "codenames"

    def default_settings(self) -> dict:
        return {
            "language": "en",
            "solo_practice": False,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        if merged["language"] not in ("en",):
            merged["language"] = "en"
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        return merged

    def _load_words(self, language: str) -> list[str]:
        path = WORD_LIST_DIR / f"{language}.json"
        with open(path) as f:
            return json.load(f)

    def _build_board(self, language: str) -> tuple[list[dict], str]:
        words = random.sample(self._load_words(language), 25)
        starting_team = random.choice(["red", "blue"])
        counts = {"red": 8, "blue": 8, "neutral": 7, "assassin": 1}
        counts[starting_team] = 9

        colors: list[str] = []
        for color, count in counts.items():
            colors.extend([color] * count)
        random.shuffle(colors)

        cards = [
            {"index": i, "word": words[i], "color": colors[i], "revealed": False}
            for i in range(25)
        ]
        return cards, starting_team

    def assign_lobby_roles(self, players: list[dict], settings: dict) -> list[dict]:
        settings = self.validate_settings(settings)
        red_players = [p for p in players if p.get("team") == "red"]
        blue_players = [p for p in players if p.get("team") == "blue"]

        if settings.get("solo_practice"):
            human = next((p for p in players if not p.get("is_ai")), players[0] if players else None)
            if human:
                human["team"] = "red"
                human["role"] = "operative"
            return players

        for team_players, team in ((red_players, "red"), (blue_players, "blue")):
            spymaster = next((p for p in team_players if p.get("role") == "spymaster"), None)
            if not spymaster and team_players:
                team_players[0]["role"] = "spymaster"
                for p in team_players[1:]:
                    if p.get("role") == "spymaster":
                        p["role"] = "operative"
                    elif not p.get("role"):
                        p["role"] = "operative"
            for p in team_players:
                if not p.get("role"):
                    p["role"] = "operative"

        return players

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        language = settings["language"]
        cards, starting_team = self._build_board(language)

        return {
            "cards": cards,
            "starting_team": starting_team,
            "current_team": starting_team,
            "phase": "clue",
            "current_clue": None,
            "guesses_remaining": 0,
            "winner": None,
            "win_reason": None,
            "red_remaining": sum(1 for c in cards if c["color"] == "red" and not c["revealed"]),
            "blue_remaining": sum(1 for c in cards if c["color"] == "blue" and not c["revealed"]),
            "players": players,
            "settings": settings,
            "last_action": None,
        }

    def _get_team_spymaster(self, state: dict, team: str) -> dict | None:
        return next(
            (p for p in state["players"] if p.get("team") == team and p.get("role") == "spymaster"),
            None,
        )

    def _validate_clue(self, state: dict, clue_word: str, clue_number: int) -> None:
        clue_word = clue_word.strip().upper()
        if not clue_word or len(clue_word.split()) > 1:
            raise ValueError("Clue must be a single word")
        board_words = {c["word"].upper() for c in state["cards"]}
        if clue_word in board_words:
            raise ValueError("Clue cannot match a word on the board")
        if clue_number < 0:
            raise ValueError("Clue number must be non-negative")

    def apply_action(self, state: dict, action: dict, player: dict) -> tuple[dict, list[dict]]:
        if state.get("winner"):
            raise ValueError("Game is already over")

        action_type = action.get("type")
        events: list[dict] = []
        team = player.get("team")
        role = player.get("role")

        if action_type == "submit_clue":
            if state["phase"] != "clue":
                raise ValueError("Not in clue phase")
            if team != state["current_team"]:
                raise ValueError("Not your team's turn")
            if role != "spymaster":
                raise ValueError("Only spymaster can give clues")

            clue_word = action["clue_word"].strip().upper()
            clue_number = int(action["clue_number"])
            self._validate_clue(state, clue_word, clue_number)

            state["current_clue"] = {"word": clue_word, "number": clue_number}
            state["phase"] = "guess"
            state["guesses_remaining"] = clue_number + 1
            state["last_action"] = {"type": "clue", "team": team, "clue": state["current_clue"]}
            events.append({"type": "turn_changed", "team": team, "phase": "guess"})

        elif action_type == "guess_word":
            if state["phase"] != "guess":
                raise ValueError("Not in guess phase")
            if team != state["current_team"]:
                raise ValueError("Not your team's turn")
            if role != "operative":
                raise ValueError("Only operatives can guess")

            index = int(action["card_index"])
            card = state["cards"][index]
            if card["revealed"]:
                raise ValueError("Card already revealed")

            card["revealed"] = True
            state["guesses_remaining"] -= 1
            state["red_remaining"] = sum(
                1 for c in state["cards"] if c["color"] == "red" and not c["revealed"]
            )
            state["blue_remaining"] = sum(
                1 for c in state["cards"] if c["color"] == "blue" and not c["revealed"]
            )
            state["last_action"] = {"type": "guess", "team": team, "card_index": index, "color": card["color"]}

            winner = self.check_winner(state)
            if winner:
                state["winner"] = winner
                if card["color"] == "assassin":
                    state["win_reason"] = "assassin"
                    opponent = "blue" if team == "red" else "red"
                    state["winner"] = opponent
                else:
                    state["win_reason"] = "all_revealed"
                events.append({"type": "game_over", "winner": state["winner"], "reason": state["win_reason"]})
                return state, events

            if card["color"] == "assassin":
                opponent = "blue" if team == "red" else "red"
                state["winner"] = opponent
                state["win_reason"] = "assassin"
                events.append({"type": "game_over", "winner": opponent, "reason": "assassin"})
                return state, events

            if card["color"] != team:
                state["phase"] = "clue"
                state["current_clue"] = None
                state["guesses_remaining"] = 0
                state["current_team"] = "blue" if team == "red" else "red"
                events.append({"type": "turn_changed", "team": state["current_team"], "phase": "clue"})
            elif state["guesses_remaining"] <= 0:
                state["phase"] = "clue"
                state["current_clue"] = None
                state["guesses_remaining"] = 0
                state["current_team"] = "blue" if team == "red" else "red"
                events.append({"type": "turn_changed", "team": state["current_team"], "phase": "clue"})

        elif action_type == "end_turn":
            if state["phase"] != "guess":
                raise ValueError("Not in guess phase")
            if team != state["current_team"]:
                raise ValueError("Not your team's turn")
            if role != "operative":
                raise ValueError("Only operatives can end turn")

            state["phase"] = "clue"
            state["current_clue"] = None
            state["guesses_remaining"] = 0
            state["current_team"] = "blue" if team == "red" else "red"
            state["last_action"] = {"type": "end_turn", "team": team}
            events.append({"type": "turn_changed", "team": state["current_team"], "phase": "clue"})

        else:
            raise ValueError(f"Unknown action: {action_type}")

        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        is_spymaster = viewer_player and viewer_player.get("role") == "spymaster"
        cards = []
        for card in state["cards"]:
            c = {"index": card["index"], "word": card["word"], "revealed": card["revealed"]}
            if card["revealed"] or is_spymaster:
                c["color"] = card["color"]
            cards.append(c)

        return {
            "cards": cards,
            "starting_team": state["starting_team"],
            "current_team": state["current_team"],
            "phase": state["phase"],
            "current_clue": state.get("current_clue"),
            "guesses_remaining": state.get("guesses_remaining", 0),
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "red_remaining": state["red_remaining"],
            "blue_remaining": state["blue_remaining"],
            "last_action": state.get("last_action"),
            "players": state.get("players", []),
            "viewer_role": viewer_player.get("role") if viewer_player else None,
            "viewer_team": viewer_player.get("team") if viewer_player else None,
        }

    def check_winner(self, state: dict) -> str | None:
        if state["red_remaining"] == 0:
            return "red"
        if state["blue_remaining"] == 0:
            return "blue"
        return None

    def get_current_actor(self, state: dict) -> dict | None:
        team = state["current_team"]
        phase = state["phase"]
        role = "spymaster" if phase == "clue" else "operative"
        return next(
            (p for p in state["players"] if p.get("team") == team and p.get("role") == role),
            None,
        )
