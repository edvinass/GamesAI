import asyncio
import copy
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import async_session
from app.games.codenames.ai import ai_operative_guesses, ai_spymaster_clue, fallback_clue
from app.games.codenames.engine import CodenamesEngine
from app.games.chess.ai import choose_chess_move
from app.games.chess.engine import ChessEngine
from app.games.go.ai import choose_go_move
from app.games.go.engine import GoEngine
from app.games.roborally.ai import choose_ai_actions
from app.games.roborally.engine import RoboRallyEngine
from app.games.poker.ai import choose_poker_action
from app.games.poker.engine import PokerEngine
from app.services.poker_reactions import schedule_poker_reactions
from app.games.spyfall.ai import ai_answer_question, ai_ask_question, ai_cast_vote, ai_spy_guess
from app.games.spyfall.engine import SpyfallEngine
from app.games.registry import get_game
from app.models import GameState, Room, RoomPlayer, RoomStatus, Role, Team
from app.utils import generate_session_token, hash_session_token, player_to_dict

logger = logging.getLogger(__name__)

# Games where lobby players are not assigned red/blue teams or spymaster roles.
_NO_TEAM_LOBBY_GAMES = frozenset({"spyfall", "snake", "duel", "tetris", "poker", "gravity_master", "chess", "go", "roborally"})

_ai_locks: dict[str, asyncio.Lock] = {}


def _get_ai_lock(room_id: str) -> asyncio.Lock:
    if room_id not in _ai_locks:
        _ai_locks[room_id] = asyncio.Lock()
    return _ai_locks[room_id]


def _ai_nickname_for_role(role: Role) -> str:
    label = "AI Spymaster" if role == Role.SPYMASTER else "AI Operative"
    return f"🤖 {label}"


def _sync_ai_nickname(player: RoomPlayer) -> None:
    if player.is_ai and player.role:
        player.nickname = _ai_nickname_for_role(player.role)


class RoomService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_room(self, room_id: uuid.UUID) -> Room | None:
        result = await self.db.execute(
            select(Room)
            .options(selectinload(Room.players), selectinload(Room.game_state))
            .where(Room.id == room_id)
        )
        return result.scalar_one_or_none()

    async def create_room(self, game_type: str, nickname: str) -> tuple[Room, RoomPlayer, str]:
        game = get_game(game_type)
        token = generate_session_token()
        room = Room(
            game_type=game_type,
            status=RoomStatus.LOBBY,
            settings=game.default_settings(),
        )
        self.db.add(room)
        await self.db.flush()

        player = RoomPlayer(
            room_id=room.id,
            nickname=nickname,
            session_token_hash=hash_session_token(token),
            team=Team.RED if game_type not in _NO_TEAM_LOBBY_GAMES else None,
            role=Role.SPYMASTER if game_type not in _NO_TEAM_LOBBY_GAMES else None,
            is_ai=False,
            is_connected=True,
        )
        self.db.add(player)
        await self.db.flush()
        room.host_player_id = player.id
        await self.db.commit()
        await self.db.refresh(room, ["players"])
        return room, player, token

    async def join_room(self, room_id: uuid.UUID, nickname: str) -> tuple[Room, RoomPlayer, str]:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        if room.status != RoomStatus.LOBBY:
            raise ValueError("Game already started")

        token = generate_session_token()
        team, role = self._assign_lobby_slot(room)

        player = RoomPlayer(
            room_id=room.id,
            nickname=nickname,
            session_token_hash=hash_session_token(token),
            team=team,
            role=role,
            is_ai=False,
            is_connected=True,
        )
        self.db.add(player)
        await self.db.commit()
        await self.db.refresh(room, ["players"])
        return room, player, token

    def _assign_lobby_slot(self, room: Room) -> tuple[Team | None, Role | None]:
        if room.game_type in _NO_TEAM_LOBBY_GAMES:
            return None, None

        red = [p for p in room.players if p.team == Team.RED]
        blue = [p for p in room.players if p.team == Team.BLUE]

        if len(red) <= len(blue):
            team = Team.RED
            team_players = red
        else:
            team = Team.BLUE
            team_players = blue

        has_spymaster = any(p.role == Role.SPYMASTER for p in team_players)
        role = Role.OPERATIVE if has_spymaster else Role.SPYMASTER
        return team, role

    async def authenticate_player(self, room_id: uuid.UUID, token: str) -> RoomPlayer | None:
        room = await self._load_room(room_id)
        if not room:
            return None
        token_hash = hash_session_token(token)
        for player in room.players:
            if player.session_token_hash == token_hash:
                return player
        return None

    async def set_connected(self, player_id: uuid.UUID, connected: bool) -> None:
        result = await self.db.execute(select(RoomPlayer).where(RoomPlayer.id == player_id))
        player = result.scalar_one_or_none()
        if player:
            player.is_connected = connected
            await self.db.commit()

    async def update_settings(self, room_id: uuid.UUID, player_id: uuid.UUID, settings: dict) -> Room:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        if room.host_player_id != player_id:
            raise ValueError("Only host can update settings")
        if room.status != RoomStatus.LOBBY:
            raise ValueError("Cannot update settings after game started")

        game = get_game(room.game_type)
        room.settings = game.validate_settings({**room.settings, **settings})
        await self.db.commit()
        await self.db.refresh(room, ["players"])
        return room

    async def add_ai_player(
        self,
        room_id: uuid.UUID,
        host_id: uuid.UUID,
        team: str | None = None,
        role: str | None = None,
    ) -> Room:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        if room.host_player_id != host_id:
            raise ValueError("Only host can add AI players")
        if room.status != RoomStatus.LOBBY:
            raise ValueError("Cannot add AI after game started")

        if room.game_type == "gravity_master":
            raise ValueError("Gravity Master is single-player only — AI players are not supported")

        if room.game_type in _NO_TEAM_LOBBY_GAMES:
            settings = get_game(room.game_type).validate_settings(room.settings)
            if len(room.players) >= settings["max_players"]:
                raise ValueError(f"Maximum {settings['max_players']} players allowed")

            ai_count = sum(1 for p in room.players if p.is_ai)
            token = generate_session_token()
            player = RoomPlayer(
                room_id=room.id,
                nickname=f"🤖 AI Player {ai_count + 1}",
                session_token_hash=hash_session_token(token),
                team=None,
                role=None,
                is_ai=True,
                is_connected=True,
            )
            self.db.add(player)
            await self.db.flush()
            if room.game_type in ("tetris", "poker", "duel"):
                settings = dict(room.settings or {})
                difficulties = dict(settings.get("ai_difficulties") or {})
                default = "normal" if room.game_type == "tetris" else str(
                    settings.get("ai_difficulty") or "medium"
                )
                difficulties[str(player.id)] = default
                settings["ai_difficulties"] = difficulties
                room.settings = get_game(room.game_type).validate_settings(settings)
            await self.db.commit()
            await self.db.refresh(room, ["players"])
            return room

        if team is None or role is None:
            raise ValueError("Team and role required for this game")

        team_enum = Team(team)
        role_enum = Role(role)
        existing = [
            p for p in room.players if p.team == team_enum and p.role == role_enum and not p.is_ai
        ]
        if existing:
            raise ValueError("Slot already occupied")

        for p in room.players:
            if p.team == team_enum and p.role == role_enum and p.is_ai:
                await self.db.delete(p)

        token = generate_session_token()
        nickname = _ai_nickname_for_role(role_enum)

        player = RoomPlayer(
            room_id=room.id,
            nickname=nickname,
            session_token_hash=hash_session_token(token),
            team=team_enum,
            role=role_enum,
            is_ai=True,
            is_connected=True,
        )
        self.db.add(player)
        await self.db.commit()
        await self.db.refresh(room, ["players"])
        return room

    async def remove_player(self, room_id: uuid.UUID, host_id: uuid.UUID, target_id: uuid.UUID) -> Room:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        if room.host_player_id != host_id:
            raise ValueError("Only host can remove players")
        if room.status != RoomStatus.LOBBY:
            raise ValueError("Cannot remove players after game started")

        target = next((p for p in room.players if p.id == target_id), None)
        if not target:
            raise ValueError("Player not found")
        if not target.is_ai and target.id == host_id:
            raise ValueError("Host cannot remove themselves")

        await self.db.delete(target)
        if room.game_type in ("tetris", "poker", "duel"):
            settings = dict(room.settings or {})
            difficulties = dict(settings.get("ai_difficulties") or {})
            difficulties.pop(str(target_id), None)
            settings["ai_difficulties"] = difficulties
            room.settings = get_game(room.game_type).validate_settings(settings)
        await self.db.commit()
        await self.db.refresh(room, ["players"])
        return room

    async def update_player(
        self,
        room_id: uuid.UUID,
        host_id: uuid.UUID,
        target_id: uuid.UUID,
        *,
        team: str | None = None,
        role: str | None = None,
    ) -> Room:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        if room.host_player_id != host_id:
            raise ValueError("Only host can rearrange teams")
        if room.status != RoomStatus.LOBBY:
            raise ValueError("Cannot rearrange teams after game started")

        target = next((p for p in room.players if p.id == target_id), None)
        if not target:
            raise ValueError("Player not found")

        if team is not None:
            new_team = Team(team)
            if target.team != new_team and target.role == Role.SPYMASTER:
                existing = next(
                    (
                        p
                        for p in room.players
                        if p.id != target.id and p.team == new_team and p.role == Role.SPYMASTER
                    ),
                    None,
                )
                if existing:
                    target.role = Role.OPERATIVE
                    _sync_ai_nickname(target)
            target.team = new_team

        if role is not None:
            new_role = Role(role)
            if new_role == Role.SPYMASTER:
                for p in room.players:
                    if p.id != target.id and p.team == target.team and p.role == Role.SPYMASTER:
                        p.role = Role.OPERATIVE
                        _sync_ai_nickname(p)
            target.role = new_role
            _sync_ai_nickname(target)

        await self.db.commit()
        await self.db.refresh(room, ["players"])
        return room

    async def start_game(
        self,
        room_id: uuid.UUID,
        host_id: uuid.UUID,
        settings_override: dict | None = None,
    ) -> tuple[Room, dict]:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        if room.host_player_id != host_id:
            raise ValueError("Only host can start the game")
        if room.status == RoomStatus.PLAYING:
            raise ValueError("Game already in progress")

        game = get_game(room.game_type)
        merged_settings = dict(room.settings or {})
        if settings_override:
            merged_settings.update(settings_override)
            room.settings = merged_settings
        settings = game.validate_settings(merged_settings)
        if room.game_type in ("poker", "chess", "go", "roborally") and room.host_player_id:
            settings = {**settings, "host_id": str(room.host_player_id)}
        players_data = [self._player_data(p) for p in room.players]

        lobby_error = game.validate_lobby(players_data, settings)
        if lobby_error:
            raise ValueError(lobby_error)

        if settings.get("solo_practice"):
            if room.game_type == "codenames":
                await self._setup_solo_practice(room)
            elif room.game_type == "spyfall":
                await self._setup_spyfall_solo(room)
            elif room.game_type == "snake":
                await self._setup_snake_solo(room)
            elif room.game_type == "duel":
                await self._setup_duel_solo(room)
            elif room.game_type == "tetris":
                await self._setup_tetris_solo(room)
            elif room.game_type == "poker":
                await self._setup_poker_solo(room)
            elif room.game_type == "chess":
                await self._setup_chess_solo(room)
            elif room.game_type == "go":
                await self._setup_go_solo(room)
            elif room.game_type == "roborally":
                await self._setup_roborally_solo(room)
            await self.db.refresh(room, ["players"])
        elif settings.get("single_player") and room.game_type == "tetris":
            await self._setup_tetris_single_player(room)
            await self.db.refresh(room, ["players"])
        elif room.game_type == "gravity_master":
            await self._setup_gravity_master_single_player(room)
            await self.db.refresh(room, ["players"])

        players_data = [self._player_data(p) for p in room.players]
        players_data = game.assign_lobby_roles(players_data, settings)

        for p in room.players:
            pdata = next(d for d in players_data if d["id"] == str(p.id))
            if pdata.get("team"):
                p.team = Team(pdata["team"])
            if pdata.get("role"):
                p.role = Role(pdata["role"])

        state = game.create_initial_state(players_data, settings)
        if room.game_type == "duel":
            layout_seed = state.get("settings", {}).get("layout_seed")
            if layout_seed is not None:
                room.settings = {**(room.settings or {}), "layout_seed": layout_seed}
        if room.game_state:
            room.game_state.state = state
            room.game_state.version = 1
        else:
            self.db.add(GameState(room_id=room.id, version=1, state=state))
        room.status = RoomStatus.PLAYING
        await self.db.commit()
        await self.db.refresh(room, ["players", "game_state"])
        return room, state

    async def return_to_lobby(self, room_id: uuid.UUID, player_id: uuid.UUID) -> Room:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        if room.status not in (RoomStatus.PLAYING, RoomStatus.FINISHED):
            raise ValueError("Game is not in progress")

        player = next((p for p in room.players if p.id == player_id), None)
        if not player:
            raise ValueError("Player not found")

        room.status = RoomStatus.LOBBY
        if room.game_state:
            await self.db.delete(room.game_state)

        await self.db.commit()
        await self.db.refresh(room, ["players", "game_state"])
        return room

    async def _setup_solo_practice(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

        human = next((p for p in room.players if not p.is_ai), None)
        if human:
            human.team = Team.RED
            human.role = Role.OPERATIVE

        slots = [
            (Team.RED, Role.SPYMASTER),
            (Team.BLUE, Role.SPYMASTER),
            (Team.BLUE, Role.OPERATIVE),
        ]
        for team, role in slots:
            token = generate_session_token()
            self.db.add(
                RoomPlayer(
                    room_id=room.id,
                    nickname=_ai_nickname_for_role(role),
                    session_token_hash=hash_session_token(token),
                    team=team,
                    role=role,
                    is_ai=True,
                    is_connected=True,
                )
            )
        await self.db.flush()

    async def _setup_spyfall_solo(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

        for i in range(2):
            token = generate_session_token()
            self.db.add(
                RoomPlayer(
                    room_id=room.id,
                    nickname=f"🤖 AI Player {i + 1}",
                    session_token_hash=hash_session_token(token),
                    team=None,
                    role=None,
                    is_ai=True,
                    is_connected=True,
                )
            )
        await self.db.flush()

    async def _setup_snake_solo(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

        for i in range(2):
            token = generate_session_token()
            self.db.add(
                RoomPlayer(
                    room_id=room.id,
                    nickname=f"🤖 AI Player {i + 1}",
                    session_token_hash=hash_session_token(token),
                    team=None,
                    role=None,
                    is_ai=True,
                    is_connected=True,
                )
            )
        await self.db.flush()

    async def _setup_duel_solo(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

        token = generate_session_token()
        ai_player = RoomPlayer(
            room_id=room.id,
            nickname="🤖 AI Player 1",
            session_token_hash=hash_session_token(token),
            team=None,
            role=None,
            is_ai=True,
            is_connected=True,
        )
        self.db.add(ai_player)
        await self.db.flush()
        settings = dict(room.settings or {})
        difficulties = dict(settings.get("ai_difficulties") or {})
        difficulties[str(ai_player.id)] = str(settings.get("ai_difficulty") or "medium")
        settings["ai_difficulties"] = difficulties
        room.settings = get_game(room.game_type).validate_settings(settings)

    async def handle_duel_disconnect_forfeit(
        self, room_id: uuid.UUID, player_id: uuid.UUID
    ) -> Room | None:
        room = await self._load_room(room_id)
        if not room or room.game_type != "duel":
            return room
        if room.status != RoomStatus.PLAYING or not room.game_state:
            return room

        player = next((p for p in room.players if p.id == player_id), None)
        if not player or player.is_ai:
            return room

        game = get_game("duel")
        state = copy.deepcopy(room.game_state.state)
        events: list[dict] = []
        if game.handle_disconnect_forfeit(state, str(player_id), events):
            room.game_state.state = state
            room.game_state.version += 1
            if state.get("winner"):
                room.status = RoomStatus.FINISHED
            await self.db.commit()
            await self.db.refresh(room, ["players", "game_state"])
        return room

    async def _setup_tetris_single_player(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

    async def _setup_gravity_master_single_player(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

    async def _setup_poker_solo(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

        for i in range(2):
            token = generate_session_token()
            self.db.add(
                RoomPlayer(
                    room_id=room.id,
                    nickname=f"🤖 AI Player {i + 1}",
                    session_token_hash=hash_session_token(token),
                    team=None,
                    role=None,
                    is_ai=True,
                    is_connected=True,
                )
            )
        await self.db.flush()

        settings = dict(room.settings or {})
        difficulties = dict(settings.get("ai_difficulties") or {})
        solo_defaults = list(settings.get("solo_ai_difficulties") or ["medium", "medium"])
        ai_index = 0
        for p in room.players:
            if p.is_ai:
                default = solo_defaults[ai_index] if ai_index < len(solo_defaults) else "medium"
                difficulties.setdefault(str(p.id), default)
                ai_index += 1
        settings["ai_difficulties"] = difficulties
        room.settings = get_game("poker").validate_settings(settings)
        await self.db.flush()

    async def _setup_chess_solo(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

        token = generate_session_token()
        self.db.add(
            RoomPlayer(
                room_id=room.id,
                nickname="🤖 AI Opponent",
                session_token_hash=hash_session_token(token),
                team=None,
                role=None,
                is_ai=True,
                is_connected=True,
            )
        )
        await self.db.flush()

    async def _setup_go_solo(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

        token = generate_session_token()
        self.db.add(
            RoomPlayer(
                room_id=room.id,
                nickname="🤖 AI Opponent",
                session_token_hash=hash_session_token(token),
                team=None,
                role=None,
                is_ai=True,
                is_connected=True,
            )
        )
        await self.db.flush()

    async def _setup_roborally_solo(self, room: Room) -> None:
        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

        token = generate_session_token()
        ai_player = RoomPlayer(
            room_id=room.id,
            nickname="🤖 AI Racer",
            session_token_hash=hash_session_token(token),
            team=None,
            role=None,
            is_ai=True,
            is_connected=True,
        )
        self.db.add(ai_player)
        await self.db.flush()
        settings = dict(room.settings or {})
        difficulties = dict(settings.get("ai_difficulties") or {})
        difficulties[str(ai_player.id)] = str(settings.get("ai_difficulty") or "medium")
        settings["ai_difficulties"] = difficulties
        room.settings = get_game(room.game_type).validate_settings(settings)

    async def _setup_tetris_solo(self, room: Room) -> None:
        settings = get_game("tetris").validate_settings(room.settings or {})
        max_players = settings["max_players"]
        human_count = sum(1 for p in room.players if not p.is_ai)
        target_ai = max(0, max_players - human_count)

        for p in list(room.players):
            if p.is_ai:
                await self.db.delete(p)
        await self.db.flush()

        for i in range(target_ai):
            token = generate_session_token()
            self.db.add(
                RoomPlayer(
                    room_id=room.id,
                    nickname=f"🤖 AI Player {i + 1}",
                    session_token_hash=hash_session_token(token),
                    team=None,
                    role=None,
                    is_ai=True,
                    is_connected=True,
                )
            )
        await self.db.flush()

        settings = dict(room.settings or {})
        difficulties = dict(settings.get("ai_difficulties") or {})
        solo_defaults = list(settings.get("solo_ai_difficulties") or ["normal", "normal", "normal"])
        ai_index = 0
        for p in room.players:
            if p.is_ai:
                default = solo_defaults[ai_index] if ai_index < len(solo_defaults) else "normal"
                difficulties.setdefault(str(p.id), default)
                ai_index += 1
        settings["ai_difficulties"] = difficulties
        room.settings = get_game("tetris").validate_settings(settings)
        await self.db.flush()

    def _player_data(self, player: RoomPlayer) -> dict:
        return {
            "id": str(player.id),
            "nickname": player.nickname,
            "team": player.team.value if player.team else None,
            "role": player.role.value if player.role else None,
            "is_ai": player.is_ai,
            "is_connected": player.is_connected,
        }

    async def apply_game_action(
        self, room_id: uuid.UUID, player_id: uuid.UUID, action: dict, *, allow_ai: bool = False
    ) -> tuple[Room, dict, list[dict]]:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        is_duel_rematch = (
            room.game_type == "duel"
            and action.get("type") == "request_rematch"
            and room.status == RoomStatus.FINISHED
        )
        if not is_duel_rematch and (room.status != RoomStatus.PLAYING or not room.game_state):
            raise ValueError("Game not in progress")

        game = get_game(room.game_type)
        if game.tick_interval_ms() and not is_duel_rematch:
            lock = _get_ai_lock(str(room_id))
            async with lock:
                return await self._apply_game_action_unlocked(
                    room_id, player_id, action, allow_ai=allow_ai
                )
        return await self._apply_game_action_unlocked(
            room_id, player_id, action, allow_ai=allow_ai
        )

    async def _apply_game_action_unlocked(
        self, room_id: uuid.UUID, player_id: uuid.UUID, action: dict, *, allow_ai: bool = False
    ) -> tuple[Room, dict, list[dict]]:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        is_duel_rematch = (
            room.game_type == "duel"
            and action.get("type") == "request_rematch"
            and room.status == RoomStatus.FINISHED
        )
        if not is_duel_rematch and (room.status != RoomStatus.PLAYING or not room.game_state):
            raise ValueError("Game not in progress")
        if not room.game_state:
            raise ValueError("Game not in progress")

        player = next((p for p in room.players if p.id == player_id), None)
        if not player:
            raise ValueError("Player not found")
        if player.is_ai and not allow_ai:
            raise ValueError("AI players act automatically")

        game = get_game(room.game_type)
        player_data = self._player_data(player)
        state, events = game.apply_action(
            copy.deepcopy(room.game_state.state), action, player_data
        )
        room.game_state.state = state
        room.game_state.version += 1
        if state.get("winner"):
            room.status = RoomStatus.FINISHED

        await self.db.commit()
        await self.db.refresh(room, ["players", "game_state"])
        return room, state, events

    async def apply_game_tick(
        self, room_id: uuid.UUID
    ) -> tuple[Room, dict, list[dict]]:
        lock = _get_ai_lock(str(room_id))
        async with lock:
            room = await self._load_room(room_id)
            if not room:
                raise ValueError("Room not found")
            if room.status != RoomStatus.PLAYING or not room.game_state:
                raise ValueError("Game not in progress")

            game = get_game(room.game_type)
            state, events = game.tick(copy.deepcopy(room.game_state.state))
            room.game_state.state = state
            room.game_state.version += 1
            if state.get("winner"):
                room.status = RoomStatus.FINISHED

            await self.db.commit()
            await self.db.refresh(room, ["players", "game_state"])
            return room, state, events

    def get_viewer_state(self, room: Room, viewer: RoomPlayer | None) -> dict | None:
        if not room.game_state:
            return None
        game = get_game(room.game_type)
        viewer_data = self._player_data(viewer) if viewer else None
        return game.get_public_state(room.game_state.state, viewer_data)

    async def run_ai_turn_if_needed(self, room_id: uuid.UUID, broadcast_fn) -> None:
        await process_ai_turns(room_id, broadcast_fn)


AI_CLUE_THINK_PAUSE_SEC = 2.0
AI_GUESS_THINK_PAUSE_SEC = 1.5
AI_REVEAL_PAUSE_SEC = 1.8
AI_TURN_PAUSE_SEC = 0.8
AI_SPYFALL_THINK_PAUSE_SEC = 2.0
AI_POKER_THINK_PAUSE_SEC = 3.0
AI_POKER_TURN_PAUSE_SEC = 1.5
AI_CHESS_THINK_PAUSE_SEC = 1.2
AI_CHESS_TURN_PAUSE_SEC = 0.6
AI_GO_THINK_PAUSE_SEC = 1.0
AI_GO_TURN_PAUSE_SEC = 0.5
AI_ROBORALLY_THINK_PAUSE_SEC = 1.0
AI_ROBORALLY_TURN_PAUSE_SEC = 0.4


async def _process_codenames_ai_turn(
    service: RoomService,
    room_id: uuid.UUID,
    room: Room,
    broadcast_fn,
) -> bool:
    """Run one Codenames AI action. Returns True if an action was taken."""
    engine: CodenamesEngine = get_game("codenames")  # type: ignore
    state = room.game_state.state
    if state.get("winner"):
        return False

    actor_data = engine.get_current_actor(state)
    if not actor_data or not actor_data.get("is_ai"):
        return False

    actor = next((p for p in room.players if str(p.id) == actor_data["id"]), None)
    if not actor:
        return False

    if state["phase"] == "clue":
        await asyncio.sleep(AI_CLUE_THINK_PAUSE_SEC)
        clue, number, targets = await ai_spymaster_clue(state, actor.team.value)
        action: dict[str, Any] = {
            "type": "submit_clue",
            "clue_word": clue,
            "clue_number": number,
        }
        if targets:
            action["targets"] = targets
        try:
            room, state, events = await service.apply_game_action(
                room_id, actor.id, action, allow_ai=True
            )
        except ValueError:
            clue, number, targets = await fallback_clue(state, actor.team.value)
            action = {
                "type": "submit_clue",
                "clue_word": clue,
                "clue_number": number,
            }
            if targets:
                action["targets"] = targets
            room, state, events = await service.apply_game_action(
                room_id, actor.id, action, allow_ai=True
            )
        await broadcast_fn(room, events)
        await asyncio.sleep(AI_TURN_PAUSE_SEC)
        return True

    await asyncio.sleep(AI_GUESS_THINK_PAUSE_SEC)
    guesses = await ai_operative_guesses(
        state, actor.team.value, state.get("guesses_remaining", 1)
    )
    if not guesses:
        await asyncio.sleep(AI_TURN_PAUSE_SEC)
        room, state, events = await service.apply_game_action(
            room_id, actor.id, {"type": "end_turn"}, allow_ai=True
        )
        await broadcast_fn(room, events)
        await asyncio.sleep(AI_TURN_PAUSE_SEC)
        return True

    for idx in guesses:
        room = await service._load_room(room_id)
        if not room or not room.game_state:
            return False
        state = room.game_state.state
        if state.get("winner") or state["phase"] != "guess":
            break
        room, state, events = await service.apply_game_action(
            room_id,
            actor.id,
            {"type": "guess_word", "card_index": idx},
            allow_ai=True,
        )
        await broadcast_fn(room, events)
        if state.get("winner"):
            return False
        if state["phase"] == "clue":
            break
        await asyncio.sleep(AI_REVEAL_PAUSE_SEC)

    await asyncio.sleep(AI_TURN_PAUSE_SEC)
    return True


async def _process_spyfall_ai_turn(
    service: RoomService,
    room_id: uuid.UUID,
    room: Room,
    broadcast_fn,
) -> bool:
    """Run one Spyfall AI action. Returns True if an action was taken."""
    engine: SpyfallEngine = get_game("spyfall")  # type: ignore
    state = room.game_state.state
    if state.get("winner"):
        return False

    actor_data = engine.get_current_actor(state)
    if not actor_data or not actor_data.get("is_ai"):
        return False

    actor = next((p for p in room.players if str(p.id) == actor_data["id"]), None)
    if not actor:
        return False

    await asyncio.sleep(AI_SPYFALL_THINK_PAUSE_SEC)
    phase = state.get("phase")

    if phase == "questioning" and state.get("pending_question"):
        answer = await ai_answer_question(state, actor_data)
        room, state, events = await service.apply_game_action(
            room_id,
            actor.id,
            {"type": "answer_question", "answer": answer},
            allow_ai=True,
        )
        await broadcast_fn(room, events)
        await asyncio.sleep(AI_TURN_PAUSE_SEC)
        return True

    if phase == "questioning":
        if engine._is_spy(state, actor_data["id"]):
            guess = await ai_spy_guess(state, actor_data)
            if guess:
                room, state, events = await service.apply_game_action(
                    room_id,
                    actor.id,
                    {"type": "spy_guess_location", "location_name": guess},
                    allow_ai=True,
                )
                await broadcast_fn(room, events)
                await asyncio.sleep(AI_TURN_PAUSE_SEC)
                return True

        target_id, question = await ai_ask_question(state, actor_data)
        room, state, events = await service.apply_game_action(
            room_id,
            actor.id,
            {"type": "ask_question", "target_player_id": target_id, "question": question},
            allow_ai=True,
        )
        await broadcast_fn(room, events)
        await asyncio.sleep(AI_TURN_PAUSE_SEC)
        return True

    if phase == "voting":
        vote_for = await ai_cast_vote(state, actor_data)
        room, state, events = await service.apply_game_action(
            room_id,
            actor.id,
            {"type": "cast_vote", "vote_for_player_id": vote_for},
            allow_ai=True,
        )
        await broadcast_fn(room, events)
        await asyncio.sleep(AI_TURN_PAUSE_SEC)
        return True

    return False


async def _process_poker_ai_turn(
    service: RoomService,
    room_id: uuid.UUID,
    room: Room,
    broadcast_fn,
) -> bool:
    """Run one Poker AI action. Returns True if an action was taken."""
    engine: PokerEngine = get_game("poker")  # type: ignore
    state = room.game_state.state
    if state.get("winner"):
        return False

    actor_data = engine.get_current_actor(state)
    if not actor_data or not actor_data.get("is_ai"):
        return False

    actor = next((p for p in room.players if str(p.id) == actor_data["id"]), None)
    if not actor:
        return False

    await asyncio.sleep(AI_POKER_THINK_PAUSE_SEC)
    action = choose_poker_action(state, str(actor_data["id"]))
    try:
        room, state, events = await service.apply_game_action(
            room_id, actor.id, action, allow_ai=True
        )
    except ValueError:
        to_call = max(
            0,
            state["current_bet"] - state["players"][str(actor_data["id"])]["bet_this_round"],
        )
        fallback = {"type": "call"} if to_call > 0 else {"type": "check"}
        room, state, events = await service.apply_game_action(
            room_id, actor.id, fallback, allow_ai=True
        )
    await broadcast_fn(room, events)
    schedule_poker_reactions(room_id, room, state, events, str(actor.id), action)
    await asyncio.sleep(AI_POKER_TURN_PAUSE_SEC)
    return True


async def _process_chess_ai_turn(
    service: RoomService,
    room_id: uuid.UUID,
    room: Room,
    broadcast_fn,
) -> bool:
    """Run one Chess AI action. Returns True if an action was taken."""
    engine: ChessEngine = get_game("chess")  # type: ignore
    state = room.game_state.state
    if state.get("winner") or state.get("phase") != "playing":
        return False

    actor_data = engine.get_current_actor(state)
    if not actor_data or not actor_data.get("is_ai"):
        return False

    actor = next((p for p in room.players if str(p.id) == actor_data["id"]), None)
    if not actor:
        return False

    await asyncio.sleep(AI_CHESS_THINK_PAUSE_SEC)
    action = await asyncio.to_thread(choose_chess_move, state, str(actor_data["id"]))
    try:
        room, state, events = await service.apply_game_action(
            room_id, actor.id, action, allow_ai=True
        )
    except ValueError:
        legal = state.get("legal_moves") or []
        if not legal:
            return False
        fallback_move = legal[0]
        fallback = {
            "type": "move",
            "from": fallback_move["from"],
            "to": fallback_move["to"],
        }
        if fallback_move.get("promotion"):
            fallback["promotion"] = str(fallback_move["promotion"]).lower()
        room, state, events = await service.apply_game_action(
            room_id, actor.id, fallback, allow_ai=True
        )
    await broadcast_fn(room, events)
    await asyncio.sleep(AI_CHESS_TURN_PAUSE_SEC)
    return True


async def _process_go_ai_turn(
    service: RoomService,
    room_id: uuid.UUID,
    room: Room,
    broadcast_fn,
) -> bool:
    """Run one Go AI action. Returns True if an action was taken."""
    engine: GoEngine = get_game("go")  # type: ignore
    state = room.game_state.state
    if state.get("winner") or state.get("phase") != "playing":
        return False

    actor_data = engine.get_current_actor(state)
    if not actor_data or not actor_data.get("is_ai"):
        return False

    actor = next((p for p in room.players if str(p.id) == actor_data["id"]), None)
    if not actor:
        return False

    await asyncio.sleep(AI_GO_THINK_PAUSE_SEC)
    action = await asyncio.to_thread(choose_go_move, state, str(actor_data["id"]))
    try:
        room, state, events = await service.apply_game_action(
            room_id, actor.id, action, allow_ai=True
        )
    except ValueError:
        legal = state.get("legal_plays") or []
        if not legal:
            fallback = {"type": "pass"}
        else:
            fallback = {"type": "play", "coord": legal[0]["coord"]}
        room, state, events = await service.apply_game_action(
            room_id, actor.id, fallback, allow_ai=True
        )
    await broadcast_fn(room, events)
    await asyncio.sleep(AI_GO_TURN_PAUSE_SEC)
    return True


async def _process_roborally_ai_turn(
    service: RoomService,
    room_id: uuid.UUID,
    room: Room,
    broadcast_fn,
) -> bool:
    """Program and lock one RoboRally AI player's register. Returns True if actions were taken."""
    engine: RoboRallyEngine = get_game("roborally")  # type: ignore
    state = room.game_state.state
    if state.get("winner") or state.get("phase") != "programming":
        return False

    actor_data = engine.get_current_actor(state)
    if not actor_data or not actor_data.get("is_ai"):
        return False

    actor = next((p for p in room.players if str(p.id) == actor_data["id"]), None)
    if not actor:
        return False

    await asyncio.sleep(AI_ROBORALLY_THINK_PAUSE_SEC)
    actions = await asyncio.to_thread(choose_ai_actions, state, str(actor_data["id"]))

    events: list[dict] = []
    for action in actions:
        try:
            room, state, step_events = await service.apply_game_action(
                room_id, actor.id, action, allow_ai=True
            )
            events.extend(step_events)
        except ValueError:
            break

    if events:
        await broadcast_fn(room, events)
        await asyncio.sleep(AI_ROBORALLY_TURN_PAUSE_SEC)
        return True
    return False


async def process_ai_turns(room_id: uuid.UUID, broadcast_fn) -> None:
    lock = _get_ai_lock(str(room_id))
    if lock.locked():
        return

    async with lock:
        while True:
            async with async_session() as db:
                service = RoomService(db)
                room = await service._load_room(room_id)
                if not room or room.status != RoomStatus.PLAYING or not room.game_state:
                    return

                try:
                    acted = False
                    if room.game_type == "codenames":
                        acted = await _process_codenames_ai_turn(service, room_id, room, broadcast_fn)
                    elif room.game_type == "spyfall":
                        acted = await _process_spyfall_ai_turn(service, room_id, room, broadcast_fn)
                    elif room.game_type == "poker":
                        acted = await _process_poker_ai_turn(service, room_id, room, broadcast_fn)
                    elif room.game_type == "chess":
                        acted = await _process_chess_ai_turn(service, room_id, room, broadcast_fn)
                    elif room.game_type == "go":
                        go_settings = (room.game_state.state or {}).get("settings") or {}
                        if go_settings.get("solo_practice") and go_settings.get(
                            "client_side_ai", True
                        ):
                            return
                        acted = await _process_go_ai_turn(service, room_id, room, broadcast_fn)
                    elif room.game_type == "roborally":
                        acted = await _process_roborally_ai_turn(service, room_id, room, broadcast_fn)
                    else:
                        return

                    if not acted:
                        return
                except Exception as e:
                    logger.exception("AI turn failed: %s", e)
                    return
