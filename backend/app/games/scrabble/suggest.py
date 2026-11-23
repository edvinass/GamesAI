"""Move suggestions for Scrabble cheat mode.

Suggestions only use the asking player's own rack and the public board, so a
hint never reveals another player's tiles.
"""

from __future__ import annotations

from app.games.scrabble.ai import _bind_tiles
from app.games.scrabble.moves import generate_moves

MAX_SUGGESTIONS = 5


def scrabble_position_key(state: dict, player_id: str) -> str:
    """Identity of the decision the viewer is looking at. Kept in sync with the client."""
    rack = ",".join(sorted(tile["id"] for tile in state.get("racks", {}).get(player_id, [])))
    return f"{state.get('turn_index', 0)}|{state.get('current_actor_id') or ''}|{rack}"


def suggest_moves(state: dict, player_id: str, limit: int = MAX_SUGGESTIONS) -> list[dict]:
    """Return the best scoring plays for this player's rack, highest first."""
    rack = list(state.get("racks", {}).get(player_id, []))
    if not rack:
        return []
    moves = generate_moves(state["board"], rack)
    moves.sort(key=lambda move: (move["score"], len(move["placements"])), reverse=True)

    suggestions: list[dict] = []
    seen_words: set[tuple[str, ...]] = set()
    for move in moves:
        if len(suggestions) >= limit:
            break
        # Show distinct words: the same word in another spot is rarely a useful second option.
        words_key = tuple(sorted(word["word"] for word in move["words"]))
        if words_key in seen_words:
            continue
        seen_words.add(words_key)
        bound = _bind_tiles(rack, move["placements"])
        suggestions.append(
            {
                "score": move["score"],
                "bingo": move["bingo"],
                "words": move["words"],
                "placements": [
                    {
                        "row": item["row"],
                        "col": item["col"],
                        "tile_id": item["tile_id"],
                        "letter": item["letter"],
                        "blank": placement["blank"],
                    }
                    for item, placement in zip(bound, move["placements"])
                ],
            }
        )
    return suggestions
