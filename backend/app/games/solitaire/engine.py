from app.games.base import GamePlugin
from app.games.solitaire.cards import (
    SUITS,
    Card,
    can_stack_on_foundation,
    can_stack_on_tableau,
    create_deck,
    is_valid_tableau_run,
    shuffle_deck,
)


class SolitaireEngine(GamePlugin):
    game_type = "solitaire"

    def default_settings(self) -> dict:
        return {
            "min_players": 1,
            "max_players": 1,
            "single_player": True,
            "draw_count": 1,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = 1
        merged["max_players"] = 1
        merged["single_player"] = True
        draw = int(merged.get("draw_count", 1))
        merged["draw_count"] = 1 if draw not in (1, 3) else draw
        return merged

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        humans = [p for p in players if not p.get("is_ai")]
        if len(humans) != 1:
            return "Solitaire requires exactly one player"
        if any(p.get("is_ai") for p in players):
            return "Solitaire is single-player only — remove AI players"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        return self._new_game(players, settings)

    def _new_game(self, players: list[dict], settings: dict) -> dict:
        deck = shuffle_deck(create_deck())

        tableau: list[list[Card]] = [[] for _ in range(7)]
        idx = 0
        for col in range(7):
            for row in range(col + 1):
                card = deck[idx]
                card["face_up"] = row == col
                tableau[col].append(card)
                idx += 1

        stock = deck[idx:]
        for card in stock:
            card["face_up"] = False

        foundations: dict[str, list[Card]] = {
            "hearts": [],
            "diamonds": [],
            "clubs": [],
            "spades": [],
        }

        return {
            "phase": "playing",
            "tableau": tableau,
            "foundations": foundations,
            "stock": stock,
            "waste": [],
            "moves": 0,
            "players": players,
            "settings": settings,
            "winner": None,
            "win_reason": None,
            "last_action": None,
            "autoplay": False,
            "hint": None,
        }

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []
        state.setdefault("autoplay", False)
        state.setdefault("hint", None)

        # Allow restarting after a win; all other actions require an active game.
        if action_type == "new_game":
            state = self._new_game(state["players"], state["settings"])
            state["last_action"] = {"type": "new_game"}
            events.append({"type": "game_restarted"})
            return state, events

        if state["phase"] != "playing":
            return state, events

        if action_type == "hint":
            from app.games.solitaire.ai import choose_action

            chosen, reason = choose_action(state)
            if chosen:
                state["hint"] = {**chosen, "reason": reason}
            else:
                state["hint"] = {"type": "none", "reason": reason}
            state["last_action"] = {"type": "hint"}
            events.append({"type": "hint_shown"})
            return state, events

        if action_type == "set_autoplay":
            enabled = bool(action.get("enabled"))
            state["autoplay"] = enabled
            if enabled:
                state["hint"] = None
            state["last_action"] = {"type": "set_autoplay", "enabled": enabled}
            events.append({"type": "autoplay_changed", "enabled": enabled})
            return state, events

        if action_type == "draw":
            before = len(state["stock"])
            state = self._draw_from_stock(state)
            if len(state["stock"]) != before:
                state["hint"] = None
                state["last_action"] = {"type": "draw"}
                events.append({"type": "cards_drawn"})

        elif action_type == "reset_stock":
            if not state["stock"] and state["waste"]:
                state = self._reset_stock(state)
                state["hint"] = None
                state["last_action"] = {"type": "reset_stock"}
                events.append({"type": "stock_reset"})

        elif action_type == "move_to_foundation":
            source = action.get("source")
            source_index = action.get("source_index")
            if source_index is not None and not isinstance(source_index, str):
                try:
                    source_index = int(source_index)
                except (TypeError, ValueError):
                    return state, events
            state, moved = self._move_to_foundation(state, source, source_index)
            if moved:
                state["hint"] = None
                state["moves"] += 1
                state["last_action"] = {
                    "type": "move_to_foundation",
                    "source": source,
                    "source_index": source_index,
                }
                events.append({"type": "card_to_foundation"})

        elif action_type == "move_to_tableau":
            source = action.get("source")
            source_index = action.get("source_index")
            card_index = action.get("card_index", 0)
            target_col = action.get("target_col")
            try:
                if source_index is not None and not isinstance(source_index, str):
                    source_index = int(source_index)
                if card_index is None:
                    card_index = 0
                card_index = int(card_index)
                if target_col is None:
                    return state, events
                target_col = int(target_col)
            except (TypeError, ValueError):
                return state, events
            state, moved = self._move_to_tableau(
                state, source, source_index, card_index, target_col
            )
            if moved:
                state["hint"] = None
                state["moves"] += 1
                state["last_action"] = {
                    "type": "move_to_tableau",
                    "source": source,
                    "source_index": source_index,
                    "target_col": target_col,
                }
                events.append({"type": "card_to_tableau"})

        elif action_type == "auto_complete":
            state, completed = self._auto_complete(state)
            if completed:
                state["hint"] = None
                state["autoplay"] = False
                state["last_action"] = {"type": "auto_complete"}
                events.append({"type": "auto_completed"})

        if self._check_win(state):
            state["phase"] = "finished"
            state["autoplay"] = False
            state["hint"] = None
            state["winner"] = player["id"]
            state["win_reason"] = "all_cards_to_foundation"
            events.append({"type": "game_won", "player_id": player["id"]})

        return state, events

    def tick_interval_ms(self) -> int | None:
        return 750

    def tick(self, state: dict) -> tuple[dict, list[dict]]:
        state.setdefault("autoplay", False)
        state.setdefault("hint", None)
        if state.get("phase") != "playing" or not state.get("autoplay"):
            return state, []

        from app.games.solitaire.ai import choose_action

        chosen, reason = choose_action(state)
        if not chosen:
            state["autoplay"] = False
            state["hint"] = {"type": "none", "reason": reason}
            state["last_action"] = {"type": "autoplay_stuck"}
            return state, [{"type": "autoplay_stuck", "reason": reason}]

        players = state.get("players") or []
        player = players[0] if players else {"id": "player", "name": "Player"}
        # Apply as a normal move (clears hint, updates last_action)
        return self.apply_action(state, chosen, player)

    def _draw_from_stock(self, state: dict) -> dict:
        draw_count = state["settings"]["draw_count"]
        stock = state["stock"]
        waste = state["waste"]

        if not stock:
            return state

        for _ in range(min(draw_count, len(stock))):
            card = stock.pop()
            card["face_up"] = True
            waste.append(card)

        return state

    def _reset_stock(self, state: dict) -> dict:
        if state["stock"]:
            return state

        waste = state["waste"]
        stock = list(reversed(waste))
        for card in stock:
            card["face_up"] = False

        state["stock"] = stock
        state["waste"] = []
        return state

    def _move_to_foundation(
        self, state: dict, source: str, source_index: int | None
    ) -> tuple[dict, bool]:
        card = None
        source_pile = None

        if source == "waste":
            if not state["waste"]:
                return state, False
            card = state["waste"][-1]
            source_pile = state["waste"]
        elif source == "tableau":
            if source_index is None or source_index < 0 or source_index >= 7:
                return state, False
            col = state["tableau"][source_index]
            if not col:
                return state, False
            card = col[-1]
            if not card["face_up"]:
                return state, False
            source_pile = col
        else:
            return state, False

        foundation = state["foundations"][card["suit"]]
        if not can_stack_on_foundation(card, foundation):
            return state, False

        source_pile.pop()
        foundation.append(card)

        if source == "tableau" and source_pile:
            top = source_pile[-1]
            if not top["face_up"]:
                top["face_up"] = True

        return state, True

    def _move_to_tableau(
        self,
        state: dict,
        source: str,
        source_index: int | None,
        card_index: int,
        target_col: int,
    ) -> tuple[dict, bool]:
        if target_col < 0 or target_col >= 7:
            return state, False

        target = state["tableau"][target_col]
        cards_to_move: list[Card] = []

        if source == "waste":
            if not state["waste"]:
                return state, False
            cards_to_move = [state["waste"][-1]]
            source_pile = state["waste"]
            remove_count = 1
        elif source == "tableau":
            if source_index is None or source_index < 0 or source_index >= 7:
                return state, False
            if source_index == target_col:
                return state, False
            col = state["tableau"][source_index]
            if card_index < 0 or card_index >= len(col):
                return state, False
            if not col[card_index]["face_up"]:
                return state, False
            cards_to_move = col[card_index:]
            if not is_valid_tableau_run(cards_to_move):
                return state, False
            source_pile = col
            remove_count = len(cards_to_move)
        elif source == "foundation":
            if source_index is None:
                return state, False
            suit = SUITS[source_index] if isinstance(source_index, int) else source_index
            foundation = state["foundations"].get(suit)
            if not foundation:
                return state, False
            cards_to_move = [foundation[-1]]
            source_pile = foundation
            remove_count = 1
        else:
            return state, False

        if not cards_to_move:
            return state, False

        first_card = cards_to_move[0]

        if not target:
            if first_card["rank"] != "K":
                return state, False
        else:
            top_card = target[-1]
            if not top_card["face_up"]:
                return state, False
            if not can_stack_on_tableau(first_card, top_card):
                return state, False

        for _ in range(remove_count):
            source_pile.pop()

        target.extend(cards_to_move)

        if source == "tableau" and source_pile and not source_pile[-1]["face_up"]:
            source_pile[-1]["face_up"] = True

        return state, True

    def _auto_complete(self, state: dict) -> tuple[dict, bool]:
        moved_any = False
        changed = True

        while changed:
            changed = False

            if state["waste"]:
                card = state["waste"][-1]
                foundation = state["foundations"][card["suit"]]
                if can_stack_on_foundation(card, foundation):
                    state["waste"].pop()
                    foundation.append(card)
                    state["moves"] += 1
                    changed = True
                    moved_any = True
                    continue

            for col_idx, col in enumerate(state["tableau"]):
                if col and col[-1]["face_up"]:
                    card = col[-1]
                    foundation = state["foundations"][card["suit"]]
                    if can_stack_on_foundation(card, foundation):
                        col.pop()
                        foundation.append(card)
                        state["moves"] += 1
                        changed = True
                        moved_any = True
                        if col and not col[-1]["face_up"]:
                            col[-1]["face_up"] = True
                        break

        return state, moved_any

    def _check_win(self, state: dict) -> bool:
        for foundation in state["foundations"].values():
            if len(foundation) != 13:
                return False
        return True

    def _can_auto_complete(self, state: dict) -> bool:
        """Offer auto-complete only when remaining play is face-up foundation moves."""
        if state.get("phase") != "playing":
            return False
        if state["stock"] or state["waste"]:
            return False
        for col in state["tableau"]:
            for card in col:
                if not card["face_up"]:
                    return False
        # Don't show the button when nothing can actually move yet.
        for col in state["tableau"]:
            if not col:
                continue
            card = col[-1]
            if can_stack_on_foundation(card, state["foundations"][card["suit"]]):
                return True
        return False

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        tableau_public = []
        for col in state["tableau"]:
            tableau_public.append(
                [
                    {
                        "rank": c["rank"] if c["face_up"] else None,
                        "suit": c["suit"] if c["face_up"] else None,
                        "face_up": c["face_up"],
                    }
                    for c in col
                ]
            )

        waste_count = len(state["waste"])
        waste_top = None
        if state["waste"]:
            top = state["waste"][-1]
            waste_top = {"rank": top["rank"], "suit": top["suit"], "face_up": True}

        # Fan the most recent draw so Draw-3 mode shows the visible waste cards.
        draw_count = int(state["settings"].get("draw_count", 1) or 1)
        fan_size = min(draw_count, waste_count) if waste_count else 0
        waste_fan = [
            {"rank": c["rank"], "suit": c["suit"], "face_up": True}
            for c in state["waste"][-fan_size:]
        ]

        foundations_public = {}
        for suit, pile in state["foundations"].items():
            if pile:
                top = pile[-1]
                foundations_public[suit] = {
                    "top": {"rank": top["rank"], "suit": top["suit"]},
                    "count": len(pile),
                }
            else:
                foundations_public[suit] = {"top": None, "count": 0}

        return {
            "phase": state["phase"],
            "tableau": tableau_public,
            "foundations": foundations_public,
            "stock_count": len(state["stock"]),
            "waste_top": waste_top,
            "waste_fan": waste_fan,
            "waste_count": waste_count,
            "moves": state["moves"],
            "players": state["players"],
            "settings": state["settings"],
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "last_action": state.get("last_action"),
            "viewer_id": viewer_player["id"] if viewer_player else None,
            "can_auto_complete": self._can_auto_complete(state),
            "autoplay": bool(state.get("autoplay")),
            "hint": state.get("hint"),
        }

    def check_winner(self, state: dict) -> str | None:
        if state.get("phase") == "finished":
            return state.get("winner")
        return None
