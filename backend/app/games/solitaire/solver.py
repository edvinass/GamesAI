"""Klondike solvability search used to filter random deals.

A deal is accepted only when a complete win is found within a node budget.
Hard-but-solvable deals may be rejected (we reshuffle). Unsolvable deals are
never reported as solvable.
"""

from __future__ import annotations

from app.games.solitaire.cards import RANKS, SUITS

# Card ids: suit * 13 + rank_index (A=0 … K=12)
_RANK_K = 12
_SUIT_OF = [i // 13 for i in range(52)]
_RANK_OF = [i % 13 for i in range(52)]
_IS_RED = [s in (0, 1) for s in _SUIT_OF]  # hearts=0, diamonds=1

_SUIT_INDEX = {suit: i for i, suit in enumerate(SUITS)}
_RANK_INDEX = {rank: i for i, rank in enumerate(RANKS)}


def _card_id(card: dict) -> int:
    return _SUIT_INDEX[card["suit"]] * 13 + _RANK_INDEX[card["rank"]]


class _State:
    __slots__ = ("tab", "fu", "found", "stock", "waste", "draw")

    def __init__(
        self,
        tab: list[list[int]],
        fu: list[list[bool]],
        found: list[int],
        stock: list[int],
        waste: list[int],
        draw: int,
    ) -> None:
        self.tab = tab
        self.fu = fu
        self.found = found
        self.stock = stock
        self.waste = waste
        self.draw = draw

    def clone(self) -> _State:
        return _State(
            [c[:] for c in self.tab],
            [f[:] for f in self.fu],
            self.found[:],
            self.stock[:],
            self.waste[:],
            self.draw,
        )

    def key(self) -> tuple:
        return (
            tuple((tuple(c), tuple(f)) for c, f in zip(self.tab, self.fu)),
            tuple(self.found),
            tuple(self.stock),
            tuple(self.waste),
        )

    def won(self) -> bool:
        return self.found[0] == 13 and self.found[1] == 13 and self.found[2] == 13 and self.found[3] == 13

    def foundation_total(self) -> int:
        return self.found[0] + self.found[1] + self.found[2] + self.found[3]


def from_engine_state(state: dict) -> _State:
    tab: list[list[int]] = []
    fu: list[list[bool]] = []
    for col in state["tableau"]:
        tab.append([_card_id(c) for c in col])
        fu.append([bool(c["face_up"]) for c in col])

    found = [0, 0, 0, 0]
    for suit, pile in state["foundations"].items():
        found[_SUIT_INDEX[suit]] = len(pile)

    draw = int(state["settings"].get("draw_count", 1) or 1)
    if draw not in (1, 3):
        draw = 1

    return _State(
        tab,
        fu,
        found,
        [_card_id(c) for c in state["stock"]],
        [_card_id(c) for c in state["waste"]],
        draw,
    )


def is_solvable(state: dict, *, max_nodes: int = 80_000) -> bool:
    """Return True if a winning line is found within max_nodes expansions."""
    root = from_engine_state(state)
    if root.won():
        return True
    visited: set[int] = set()
    return _search(root, visited, [max_nodes], recycle_without_progress=0)


def deal_until_solvable(
    deal_fn,
    *,
    max_attempts: int = 60,
    max_nodes: int = 80_000,
) -> dict:
    """Call deal_fn() until is_solvable succeeds, or return the last deal."""
    last = deal_fn()
    if is_solvable(last, max_nodes=max_nodes):
        return last
    for _ in range(max_attempts - 1):
        last = deal_fn()
        if is_solvable(last, max_nodes=max_nodes):
            return last
    return last


def _search(
    state: _State,
    visited: set[int],
    nodes_left: list[int],
    recycle_without_progress: int,
) -> bool:
    if state.won():
        return True
    if nodes_left[0] <= 0:
        return False

    # Collapse forced / safe foundation plays before branching.
    _autoplay_safe_foundations(state)
    if state.won():
        return True

    kh = hash(state.key())
    if kh in visited:
        return False
    visited.add(kh)
    nodes_left[0] -= 1

    progress_before = state.foundation_total()

    for kind, payload in _choice_moves(state):
        child = state.clone()
        _apply_choice(child, kind, payload)

        next_recycle = recycle_without_progress
        if kind == "reset":
            if child.foundation_total() == progress_before:
                next_recycle += 1
                if next_recycle > 2:
                    continue
            else:
                next_recycle = 0
        elif kind in ("foundation", "tableau") and child.foundation_total() > progress_before:
            next_recycle = 0

        if _search(child, visited, nodes_left, next_recycle):
            return True
    return False


def _can_stack_tab(card: int, target: int) -> bool:
    return _IS_RED[card] != _IS_RED[target] and _RANK_OF[target] == _RANK_OF[card] + 1


def _can_to_foundation(card: int, found: list[int]) -> bool:
    return _RANK_OF[card] == found[_SUIT_OF[card]]


def _is_safe_foundation(card: int, found: list[int]) -> bool:
    """Foundation move that cannot block a still-needed build card."""
    rank = _RANK_OF[card]
    if rank <= 1:  # A, 2
        return True
    # Both opposite-color cards of rank-1 must already be playable-safe on foundations
    # (they are already on foundations).
    need = rank - 1
    for suit in range(4):
        if _IS_RED[suit * 13] == _IS_RED[card]:
            continue
        if found[suit] < need:
            return False
    return True


def _autoplay_safe_foundations(state: _State) -> None:
    changed = True
    while changed:
        changed = False
        if state.waste:
            card = state.waste[-1]
            if _can_to_foundation(card, state.found) and _is_safe_foundation(card, state.found):
                state.waste.pop()
                state.found[_SUIT_OF[card]] += 1
                changed = True
                continue
        for i, col in enumerate(state.tab):
            if not col or not state.fu[i][-1]:
                continue
            card = col[-1]
            if not (_can_to_foundation(card, state.found) and _is_safe_foundation(card, state.found)):
                continue
            col.pop()
            state.fu[i].pop()
            if col and not state.fu[i][-1]:
                state.fu[i][-1] = True
            state.found[_SUIT_OF[card]] += 1
            changed = True
            break


def _can_place(state: _State, card: int, tgt: int) -> bool:
    target = state.tab[tgt]
    if not target:
        return _RANK_OF[card] == _RANK_K
    if not state.fu[tgt][-1]:
        return False
    return _can_stack_tab(card, target[-1])


def _valid_run(col: list[int], fu: list[bool], start: int) -> bool:
    if not fu[start]:
        return False
    for i in range(start, len(col) - 1):
        if not fu[i + 1] or not _can_stack_tab(col[i + 1], col[i]):
            return False
    return True


def _choice_moves(state: _State) -> list[tuple[str, tuple]]:
    """Branching moves after safe autoplay — ordered best-first."""
    expose: list[tuple[str, tuple]] = []
    foundation: list[tuple[str, tuple]] = []
    build: list[tuple[str, tuple]] = []

    if state.waste:
        card = state.waste[-1]
        if _can_to_foundation(card, state.found):
            foundation.append(("foundation", ("waste", -1)))
        for tgt in range(7):
            if _can_place(state, card, tgt):
                build.append(("tableau", ("waste", -1, 0, tgt)))

    for src, col in enumerate(state.tab):
        if not col or not state.fu[src][-1]:
            continue
        if _can_to_foundation(col[-1], state.found):
            foundation.append(("foundation", ("tableau", src)))

        for card_i, card in enumerate(col):
            if not state.fu[src][card_i]:
                continue
            if not _valid_run(col, state.fu[src], card_i):
                continue
            exposes = card_i > 0 and not state.fu[src][card_i - 1]
            # Skip non-exposing rearrangements unless emptying for a King slot
            empties = card_i == 0
            if not exposes and not empties:
                # Allow sliding onto another pile only when it frees nothing —
                # still useful rarely; keep a cheap subset: single-card only
                if card_i != len(col) - 1:
                    continue
            for tgt in range(7):
                if tgt == src or not _can_place(state, card, tgt):
                    continue
                if not state.tab[tgt] and empties and _RANK_OF[card] == _RANK_K:
                    continue  # useless King column bounce
                move = ("tableau", ("tableau", src, card_i, tgt))
                if exposes:
                    expose.append(move)
                else:
                    build.append(move)

    moves = expose + foundation + build
    if state.stock:
        moves.append(("draw", ()))
    elif state.waste:
        moves.append(("reset", ()))
    return moves


def _apply_choice(state: _State, kind: str, payload: tuple) -> None:
    if kind == "draw":
        n = min(state.draw, len(state.stock))
        for _ in range(n):
            state.waste.append(state.stock.pop())
        return

    if kind == "reset":
        state.stock = list(reversed(state.waste))
        state.waste = []
        return

    if kind == "foundation":
        src, src_i = payload
        if src == "waste":
            card = state.waste.pop()
        else:
            card = state.tab[src_i].pop()
            state.fu[src_i].pop()
            if state.tab[src_i] and not state.fu[src_i][-1]:
                state.fu[src_i][-1] = True
        state.found[_SUIT_OF[card]] += 1
        return

    # tableau
    src, src_i, card_i, tgt = payload
    if src == "waste":
        cards = [state.waste.pop()]
    else:
        cards = state.tab[src_i][card_i:]
        del state.tab[src_i][card_i:]
        del state.fu[src_i][card_i:]
        if state.tab[src_i] and not state.fu[src_i][-1]:
            state.fu[src_i][-1] = True
    state.tab[tgt].extend(cards)
    state.fu[tgt].extend([True] * len(cards))
