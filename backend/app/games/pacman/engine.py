"""Multiplayer Pac-Man — shared maze, pellets, ghosts, last pac standing / score clear."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.games.base import GamePlugin
from app.games.pacman.ai import (
    DIRECTIONS,
    choose_ghost_direction,
    choose_pacman_direction,
)
from app.games.pacman.maps import (
    build_map,
    get_map,
    is_passable,
    list_maps,
    pellet_count,
    wrap_through_tunnel,
)

PAC_COLORS = ["#ffff00", "#00ffff", "#ffb8ff", "#ffb852"]
GHOST_DEFS = [
    {"id": "blinky", "name": "blinky", "color": "#ff0000"},
    {"id": "pinky", "name": "pinky", "color": "#ffb8ff"},
    {"id": "inky", "name": "inky", "color": "#00ffff"},
    {"id": "clyde", "name": "clyde", "color": "#ffb852"},
]

PELLET_SCORE = 10
POWER_PELLET_SCORE = 50
GHOST_EAT_BASE = 200
PAC_EAT_SCORE = 500
POWERED_TICKS = 45
SCATTER_DURATION = 60
CHASE_DURATION = 180
BASE_MOVE_RATE = 1.0
GHOST_MOVE_RATE = 0.92
FRIGHTENED_GHOST_RATE = 0.5
EATEN_GHOST_RATE = 1.7
RESPAWN_TICKS = 12
INVULN_TICKS = 8


class PacmanEngine(GamePlugin):
    game_type = "pacman"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 4,
            "map_id": "classic",
            "available_maps": list_maps(),
            "tick_ms": 90,
            "countdown_sec": 3,
            "lives": 3,
            "solo_practice": False,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = max(2, min(4, int(merged.get("min_players", 2))))
        merged["max_players"] = max(
            merged["min_players"], min(4, int(merged.get("max_players", 4)))
        )
        map_id = str(merged.get("map_id", "classic"))
        try:
            meta = get_map(map_id)
        except ValueError:
            map_id = "classic"
            meta = get_map(map_id)
        merged["map_id"] = map_id
        merged["available_maps"] = list_maps()
        merged["grid_width"] = int(meta["width"])
        merged["grid_height"] = int(meta["height"])
        merged["tick_ms"] = max(70, min(250, int(merged.get("tick_ms", 90))))
        merged["countdown_sec"] = max(1, min(10, int(merged.get("countdown_sec", 3))))
        merged["lives"] = max(1, min(5, int(merged.get("lives", 3))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        return merged

    def tick_interval_ms(self) -> int:
        return 90

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

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        built = build_map(settings["map_id"])
        grid = built["grid"]
        width = built["width"]
        height = built["height"]
        spawns = built["pac_spawns"][: len(players)]
        ghost_homes = built["ghost_homes"]
        gate = built["gate"]

        pacmen: dict[str, dict] = {}
        for i, player in enumerate(players):
            sx, sy = spawns[i % len(spawns)]
            pacmen[player["id"]] = {
                "x": sx,
                "y": sy,
                "spawn_x": sx,
                "spawn_y": sy,
                "direction": "left",
                "next_direction": "left",
                "facing": "left",
                "alive": True,
                "lives": settings["lives"],
                "score": 0,
                "color": PAC_COLORS[i % len(PAC_COLORS)],
                "powered_ticks": 0,
                "ghost_combo": 0,
                "move_credit": 0.0,
                "respawn_ticks": 0,
                "invuln_ticks": INVULN_TICKS,
            }

        ghosts = []
        for i, gdef in enumerate(GHOST_DEFS):
            hx, hy = ghost_homes[i % len(ghost_homes)]
            ghosts.append(
                {
                    "id": gdef["id"],
                    "name": gdef["name"],
                    "color": gdef["color"],
                    "x": hx,
                    "y": hy,
                    "home": [hx, hy],
                    "direction": "up" if i == 0 else "left",
                    "mode": "scatter",
                    "frightened_ticks": 0,
                    "eaten": False,
                    "move_credit": 0.0,
                    "_force_reverse": False,
                }
            )

        countdown_sec = settings["countdown_sec"]
        countdown_ends_at = (
            datetime.now(timezone.utc) + timedelta(seconds=countdown_sec)
        ).isoformat()

        return {
            "phase": "countdown",
            "countdown_ends_at": countdown_ends_at,
            "tick": 0,
            "tick_ms": settings["tick_ms"],
            "grid_width": width,
            "grid_height": height,
            "grid": grid,
            "pellets": built["pellets"],
            "power_pellets": built["power_pellets"],
            "map_id": built["map_id"],
            "map_name": built["map_name"],
            "tunnels": built["tunnels"],
            "ghost_homes": [[x, y] for x, y in ghost_homes],
            "gate": [gate[0], gate[1]],
            "scatter_corners": [[x, y] for x, y in built["scatter_corners"]],
            "pacmen": pacmen,
            "ghosts": ghosts,
            "mode": "scatter",
            "mode_ticks": SCATTER_DURATION,
            "players": players,
            "settings": settings,
            "winner": None,
            "win_reason": None,
            "last_action": None,
            "pellets_remaining": pellet_count(built["pellets"], built["power_pellets"]),
        }

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        events: list[dict] = []
        if state["phase"] != "playing":
            return state, events

        player_id = player["id"]
        pac = state["pacmen"].get(player_id)
        if not pac or not pac.get("alive"):
            return state, events
        if int(pac.get("respawn_ticks", 0)) > 0:
            return state, events

        if action.get("type") != "set_direction":
            return state, events

        direction = action.get("direction")
        if direction not in DIRECTIONS:
            return state, events

        pac["next_direction"] = direction
        state["last_action"] = {
            "type": "set_direction",
            "player_id": player_id,
            "direction": direction,
        }
        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        public = {
            "phase": state["phase"],
            "countdown_ends_at": state.get("countdown_ends_at"),
            "tick": state["tick"],
            "tick_ms": state.get("tick_ms"),
            "grid_width": state["grid_width"],
            "grid_height": state["grid_height"],
            "grid": state["grid"],
            "pellets": state["pellets"],
            "power_pellets": state["power_pellets"],
            "map_id": state.get("map_id"),
            "map_name": state.get("map_name"),
            "tunnels": state.get("tunnels") or [],
            "ghost_homes": state.get("ghost_homes") or [],
            "gate": state.get("gate"),
            "pacmen": state["pacmen"],
            "ghosts": [
                {k: v for k, v in g.items() if not k.startswith("_")}
                for g in state.get("ghosts") or []
            ],
            "mode": state.get("mode"),
            "mode_ticks": state.get("mode_ticks"),
            "players": state["players"],
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "last_action": state.get("last_action"),
            "pellets_remaining": state.get("pellets_remaining"),
            "viewer_id": viewer_player["id"] if viewer_player else None,
        }
        return public

    def check_winner(self, state: dict) -> str | None:
        return state.get("winner")

    def tick(self, state: dict) -> tuple[dict, list[dict]]:
        events: list[dict] = []

        if state["phase"] == "countdown":
            ends = state.get("countdown_ends_at")
            if ends:
                try:
                    end_dt = datetime.fromisoformat(ends)
                    if end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) >= end_dt:
                        state["phase"] = "playing"
                        state["countdown_ends_at"] = None
                        events.append({"type": "game_started"})
                except ValueError:
                    state["phase"] = "playing"
                    events.append({"type": "game_started"})
            state["tick"] = int(state.get("tick", 0)) + 1
            return state, events

        if state["phase"] != "playing":
            return state, events

        events.extend(self._apply_ai_pacmen(state))
        events.extend(self._tick_mode(state))
        events.extend(self._tick_timers(state))
        events.extend(self._move_pacmen(state))
        events.extend(self._move_ghosts(state))
        events.extend(self._resolve_collisions(state))
        events.extend(self._maybe_finish(state))

        state["tick"] = int(state.get("tick", 0)) + 1
        return state, events

    def _apply_ai_pacmen(self, state: dict) -> list[dict]:
        events: list[dict] = []
        for player in state["players"]:
            if not player.get("is_ai"):
                continue
            pid = player["id"]
            pac = state["pacmen"].get(pid)
            if not pac or not pac.get("alive"):
                continue
            if int(pac.get("respawn_ticks", 0)) > 0:
                continue
            direction = choose_pacman_direction(state, pid, pac)
            if direction in DIRECTIONS:
                pac["next_direction"] = direction
        return events

    def _tick_mode(self, state: dict) -> list[dict]:
        events: list[dict] = []
        # While any ghost is frightened via power, hold chase/scatter clock.
        if any(int(g.get("frightened_ticks", 0)) > 0 for g in state.get("ghosts") or []):
            return events

        mode = state.get("mode") or "scatter"
        ticks = int(state.get("mode_ticks", 0)) - 1
        if ticks > 0:
            state["mode_ticks"] = ticks
            return events

        if mode == "scatter":
            state["mode"] = "chase"
            state["mode_ticks"] = CHASE_DURATION
        else:
            state["mode"] = "scatter"
            state["mode_ticks"] = SCATTER_DURATION

        for g in state.get("ghosts") or []:
            if g.get("eaten"):
                continue
            g["mode"] = state["mode"]
            g["_force_reverse"] = True
        events.append({"type": "mode_change", "mode": state["mode"]})
        return events

    def _tick_timers(self, state: dict) -> list[dict]:
        events: list[dict] = []
        for pac in state["pacmen"].values():
            if int(pac.get("powered_ticks", 0)) > 0:
                pac["powered_ticks"] = int(pac["powered_ticks"]) - 1
                if pac["powered_ticks"] <= 0:
                    pac["ghost_combo"] = 0
            if int(pac.get("respawn_ticks", 0)) > 0:
                pac["respawn_ticks"] = int(pac["respawn_ticks"]) - 1
                if pac["respawn_ticks"] <= 0:
                    pac["invuln_ticks"] = INVULN_TICKS
            elif int(pac.get("invuln_ticks", 0)) > 0:
                pac["invuln_ticks"] = int(pac["invuln_ticks"]) - 1

        for g in state.get("ghosts") or []:
            if int(g.get("frightened_ticks", 0)) > 0:
                g["frightened_ticks"] = int(g["frightened_ticks"]) - 1
                if g["frightened_ticks"] <= 0 and not g.get("eaten"):
                    restore = state.get("mode") or "chase"
                    if restore == "frightened":
                        restore = "chase"
                    g["mode"] = restore
        return events

    def _try_turn(self, state: dict, entity: dict, next_dir: str) -> bool:
        if next_dir not in DIRECTIONS:
            return False
        dx, dy = DIRECTIONS[next_dir]
        nx, ny = wrap_through_tunnel(
            entity["x"],
            entity["y"],
            dx,
            dy,
            state["grid_width"],
            state["grid_height"],
            state.get("tunnels") or [],
        )
        if (nx, ny) == (entity["x"], entity["y"]) and (dx or dy):
            return False
        if not is_passable(state["grid"], nx, ny):
            return False
        entity["direction"] = next_dir
        entity["facing"] = next_dir
        return True

    def _step_entity(self, state: dict, entity: dict) -> bool:
        direction = entity.get("direction")
        if direction not in DIRECTIONS:
            return False
        dx, dy = DIRECTIONS[direction]
        nx, ny = wrap_through_tunnel(
            entity["x"],
            entity["y"],
            dx,
            dy,
            state["grid_width"],
            state["grid_height"],
            state.get("tunnels") or [],
        )
        if (nx, ny) == (entity["x"], entity["y"]) and (dx or dy):
            return False
        if not is_passable(state["grid"], nx, ny):
            return False
        entity["x"], entity["y"] = nx, ny
        entity["facing"] = direction
        return True

    def _move_pacmen(self, state: dict) -> list[dict]:
        events: list[dict] = []
        for pid, pac in state["pacmen"].items():
            if not pac.get("alive") or int(pac.get("respawn_ticks", 0)) > 0:
                continue

            # Buffered turn at intersections / whenever next is open.
            next_dir = pac.get("next_direction")
            if next_dir and next_dir != pac.get("direction"):
                self._try_turn(state, pac, next_dir)

            pac["move_credit"] = float(pac.get("move_credit", 0.0)) + BASE_MOVE_RATE
            while pac["move_credit"] >= 1.0:
                pac["move_credit"] -= 1.0
                if not self._step_entity(state, pac):
                    pac["move_credit"] = 0.0
                    break
                events.extend(self._pickup_at(state, pid, pac))
        return events

    def _pickup_at(self, state: dict, pid: str, pac: dict) -> list[dict]:
        events: list[dict] = []
        x, y = pac["x"], pac["y"]
        power = state["power_pellets"]
        pellets = state["pellets"]
        if power[y][x]:
            power[y][x] = False
            pac["score"] = int(pac["score"]) + POWER_PELLET_SCORE
            pac["powered_ticks"] = POWERED_TICKS
            pac["ghost_combo"] = 0
            for g in state.get("ghosts") or []:
                if g.get("eaten"):
                    continue
                g["frightened_ticks"] = POWERED_TICKS
                g["mode"] = "frightened"
                g["_force_reverse"] = True
            # Keep scatter/chase clock mode; fright is per-ghost via frightened_ticks.
            state["pellets_remaining"] = pellet_count(pellets, power)
            events.append(
                {
                    "type": "power_pellet",
                    "player_id": pid,
                    "x": x,
                    "y": y,
                    "score": pac["score"],
                }
            )
        elif pellets[y][x]:
            pellets[y][x] = False
            pac["score"] = int(pac["score"]) + PELLET_SCORE
            state["pellets_remaining"] = pellet_count(pellets, power)
            events.append(
                {
                    "type": "pellet",
                    "player_id": pid,
                    "x": x,
                    "y": y,
                    "score": pac["score"],
                }
            )
        return events

    def _ghost_move_rate(self, ghost: dict) -> float:
        if ghost.get("eaten"):
            return EATEN_GHOST_RATE
        if int(ghost.get("frightened_ticks", 0)) > 0 or ghost.get("mode") == "frightened":
            return FRIGHTENED_GHOST_RATE
        return GHOST_MOVE_RATE

    def _move_ghosts(self, state: dict) -> list[dict]:
        events: list[dict] = []
        for ghost in state.get("ghosts") or []:
            # Sync mode from global when not frightened/eaten.
            if not ghost.get("eaten") and int(ghost.get("frightened_ticks", 0)) <= 0:
                if state.get("mode") != "frightened":
                    ghost["mode"] = state.get("mode") or "chase"

            direction = choose_ghost_direction(state, ghost)
            ghost["direction"] = direction
            ghost["_force_reverse"] = False

            # Leaving house when eaten reaches home.
            if ghost.get("eaten"):
                home = ghost.get("home") or [ghost["x"], ghost["y"]]
                if ghost["x"] == home[0] and ghost["y"] == home[1]:
                    ghost["eaten"] = False
                    ghost["frightened_ticks"] = 0
                    ghost["mode"] = state.get("mode") if state.get("mode") != "frightened" else "chase"
                    gate = state.get("gate") or home
                    ghost["x"], ghost["y"] = int(gate[0]), int(gate[1])
                    events.append({"type": "ghost_revived", "ghost_id": ghost["id"]})

            rate = self._ghost_move_rate(ghost)
            ghost["move_credit"] = float(ghost.get("move_credit", 0.0)) + rate
            while ghost["move_credit"] >= 1.0:
                ghost["move_credit"] -= 1.0
                # Re-choose each cell for intersections.
                ghost["direction"] = choose_ghost_direction(state, ghost)
                ghost["_force_reverse"] = False
                if not self._step_entity(state, ghost):
                    ghost["move_credit"] = 0.0
                    break
        return events

    def _hurt_pac(
        self, state: dict, pid: str, pac: dict, *, reason: str, by: str | None
    ) -> list[dict]:
        events: list[dict] = []
        if int(pac.get("invuln_ticks", 0)) > 0 or int(pac.get("respawn_ticks", 0)) > 0:
            return events

        pac["lives"] = int(pac.get("lives", 1)) - 1
        pac["powered_ticks"] = 0
        pac["ghost_combo"] = 0
        events.append(
            {
                "type": "life_lost",
                "player_id": pid,
                "reason": reason,
                "by": by,
                "lives": pac["lives"],
            }
        )

        if pac["lives"] <= 0:
            pac["alive"] = False
            pac["lives"] = 0
            events.append(
                {
                    "type": "player_died",
                    "player_id": pid,
                    "reason": reason,
                    "by": by,
                }
            )
        else:
            pac["x"] = pac["spawn_x"]
            pac["y"] = pac["spawn_y"]
            pac["direction"] = "left"
            pac["next_direction"] = "left"
            pac["facing"] = "left"
            pac["move_credit"] = 0.0
            pac["respawn_ticks"] = RESPAWN_TICKS
            events.append(
                {
                    "type": "player_respawn",
                    "player_id": pid,
                    "x": pac["x"],
                    "y": pac["y"],
                }
            )
        return events

    def _resolve_collisions(self, state: dict) -> list[dict]:
        events: list[dict] = []

        # Pac vs ghost
        for pid, pac in list(state["pacmen"].items()):
            if not pac.get("alive") or int(pac.get("respawn_ticks", 0)) > 0:
                continue
            for ghost in state.get("ghosts") or []:
                if ghost["x"] != pac["x"] or ghost["y"] != pac["y"]:
                    continue
                if ghost.get("eaten"):
                    continue

                frightened = (
                    int(ghost.get("frightened_ticks", 0)) > 0
                    or ghost.get("mode") == "frightened"
                    or int(pac.get("powered_ticks", 0)) > 0
                )
                if frightened and int(pac.get("powered_ticks", 0)) > 0:
                    combo = int(pac.get("ghost_combo", 0))
                    points = GHOST_EAT_BASE * (2**combo)
                    pac["ghost_combo"] = combo + 1
                    pac["score"] = int(pac["score"]) + points
                    ghost["eaten"] = True
                    ghost["frightened_ticks"] = 0
                    ghost["mode"] = "eaten"
                    events.append(
                        {
                            "type": "ghost_eaten",
                            "player_id": pid,
                            "ghost_id": ghost["id"],
                            "score": pac["score"],
                            "points": points,
                        }
                    )
                elif not frightened:
                    events.extend(
                        self._hurt_pac(
                            state, pid, pac, reason="ghost", by=ghost["id"]
                        )
                    )
                    break

        # Powered pac vs non-powered pac
        pids = list(state["pacmen"].keys())
        for i, a_id in enumerate(pids):
            a = state["pacmen"][a_id]
            if not a.get("alive") or int(a.get("powered_ticks", 0)) <= 0:
                continue
            if int(a.get("respawn_ticks", 0)) > 0:
                continue
            for b_id in pids[i + 1 :]:
                b = state["pacmen"][b_id]
                if not b.get("alive") or int(b.get("respawn_ticks", 0)) > 0:
                    continue
                if a["x"] != b["x"] or a["y"] != b["y"]:
                    continue
                # Only one direction of eating if both powered: skip.
                if int(b.get("powered_ticks", 0)) > 0:
                    continue
                a["score"] = int(a["score"]) + PAC_EAT_SCORE
                events.append(
                    {
                        "type": "pac_eaten",
                        "player_id": a_id,
                        "victim_id": b_id,
                        "score": a["score"],
                    }
                )
                events.extend(
                    self._hurt_pac(state, b_id, b, reason="pac", by=a_id)
                )

            # Also check pids before i (asymmetric: a powered, earlier b not)
            for b_id in pids[:i]:
                b = state["pacmen"][b_id]
                if not b.get("alive") or int(b.get("respawn_ticks", 0)) > 0:
                    continue
                if a["x"] != b["x"] or a["y"] != b["y"]:
                    continue
                if int(b.get("powered_ticks", 0)) > 0:
                    continue
                a["score"] = int(a["score"]) + PAC_EAT_SCORE
                events.append(
                    {
                        "type": "pac_eaten",
                        "player_id": a_id,
                        "victim_id": b_id,
                        "score": a["score"],
                    }
                )
                events.extend(
                    self._hurt_pac(state, b_id, b, reason="pac", by=a_id)
                )

        return events

    def _alive_pacmen(self, state: dict) -> list[str]:
        return [
            pid
            for pid, p in state["pacmen"].items()
            if p.get("alive") and int(p.get("lives", 0)) > 0
        ]

    def _maze_cleared(self, state: dict) -> bool:
        return int(state.get("pellets_remaining") or 0) <= 0

    def _maybe_finish(self, state: dict) -> list[dict]:
        events: list[dict] = []
        if state.get("phase") == "finished":
            return events

        alive = self._alive_pacmen(state)

        if len(alive) <= 1:
            if len(alive) == 1:
                state["winner"] = alive[0]
                state["win_reason"] = "last_standing"
            else:
                scores = {
                    pid: int(p.get("score", 0)) for pid, p in state["pacmen"].items()
                }
                max_score = max(scores.values()) if scores else 0
                winners = [pid for pid, sc in scores.items() if sc == max_score]
                state["winner"] = winners[0] if winners else None
                state["win_reason"] = "highest_score"
            state["phase"] = "finished"
            events.append({"type": "game_over", "winner": state["winner"]})
            return events

        if self._maze_cleared(state):
            scores = {
                pid: int(state["pacmen"][pid].get("score", 0)) for pid in alive
            }
            max_score = max(scores.values())
            winners = [pid for pid, sc in scores.items() if sc == max_score]
            state["winner"] = winners[0]
            state["win_reason"] = "maze_clear"
            state["phase"] = "finished"
            events.append({"type": "game_over", "winner": state["winner"]})
        return events
