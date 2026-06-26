import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import async_session
from app.games.codenames.ai import ai_operative_guesses, ai_spymaster_clue, fallback_clue
from app.games.codenames.engine import CodenamesEngine
from app.games.registry import get_game
from app.models import GameState, Room, RoomPlayer, RoomStatus, Role, Team
from app.utils import generate_session_token, hash_session_token, player_to_dict

logger = logging.getLogger(__name__)

_ai_locks: dict[str, asyncio.Lock] = {}


def _get_ai_lock(room_id: str) -> asyncio.Lock:
    if room_id not in _ai_locks:
        _ai_locks[room_id] = asyncio.Lock()
    return _ai_locks[room_id]


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
            team=Team.RED,
            role=Role.SPYMASTER,
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

    def _assign_lobby_slot(self, room: Room) -> tuple[Team, Role]:
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

    async def add_ai_player(self, room_id: uuid.UUID, host_id: uuid.UUID, team: str, role: str) -> Room:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        if room.host_player_id != host_id:
            raise ValueError("Only host can add AI players")
        if room.status != RoomStatus.LOBBY:
            raise ValueError("Cannot add AI after game started")

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
        ai_names = {"spymaster": "AI Spymaster", "operative": "AI Operative"}
        nickname = f"🤖 {ai_names.get(role, 'AI')}"

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
        await self.db.commit()
        await self.db.refresh(room, ["players"])
        return room

    async def start_game(self, room_id: uuid.UUID, host_id: uuid.UUID) -> tuple[Room, dict]:
        room = await self._load_room(room_id)
        if not room:
            raise ValueError("Room not found")
        if room.host_player_id != host_id:
            raise ValueError("Only host can start the game")
        if room.status != RoomStatus.LOBBY:
            raise ValueError("Game already started")

        game = get_game(room.game_type)
        settings = game.validate_settings(room.settings)

        if settings.get("solo_practice"):
            await self._setup_solo_practice(room)
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
        game_state = GameState(room_id=room.id, version=1, state=state)
        room.status = RoomStatus.PLAYING
        self.db.add(game_state)
        await self.db.commit()
        await self.db.refresh(room, ["players", "game_state"])
        return room, state

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
            (Team.RED, Role.SPYMASTER, "🤖 AI Spymaster"),
            (Team.BLUE, Role.SPYMASTER, "🤖 AI Spymaster"),
            (Team.BLUE, Role.OPERATIVE, "🤖 AI Operative"),
        ]
        for team, role, name in slots:
            token = generate_session_token()
            self.db.add(
                RoomPlayer(
                    room_id=room.id,
                    nickname=name,
                    session_token_hash=hash_session_token(token),
                    team=team,
                    role=role,
                    is_ai=True,
                    is_connected=True,
                )
            )
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
        if room.status != RoomStatus.PLAYING or not room.game_state:
            raise ValueError("Game not in progress")

        player = next((p for p in room.players if p.id == player_id), None)
        if not player:
            raise ValueError("Player not found")
        if player.is_ai and not allow_ai:
            raise ValueError("AI players act automatically")

        game = get_game(room.game_type)
        player_data = self._player_data(player)
        state, events = game.apply_action(room.game_state.state, action, player_data)

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

                if room.game_type != "codenames":
                    return

                engine: CodenamesEngine = get_game("codenames")  # type: ignore
                state = room.game_state.state
                if state.get("winner"):
                    return

                actor_data = engine.get_current_actor(state)
                if not actor_data or not actor_data.get("is_ai"):
                    return

                actor = next((p for p in room.players if str(p.id) == actor_data["id"]), None)
                if not actor:
                    return

                try:
                    if state["phase"] == "clue":
                        clue, number = await ai_spymaster_clue(state, actor.team.value)
                        action = {"type": "submit_clue", "clue_word": clue, "clue_number": number}
                        try:
                            room, state, events = await service.apply_game_action(
                                room_id, actor.id, action, allow_ai=True
                            )
                        except ValueError:
                            clue, number = fallback_clue(state)
                            action = {"type": "submit_clue", "clue_word": clue, "clue_number": number}
                            room, state, events = await service.apply_game_action(
                                room_id, actor.id, action, allow_ai=True
                            )
                        await broadcast_fn(room, events)
                        await asyncio.sleep(0.3)
                        continue

                    guesses = await ai_operative_guesses(
                        state, actor.team.value, state.get("guesses_remaining", 1)
                    )
                    if not guesses:
                        room, state, events = await service.apply_game_action(
                            room_id, actor.id, {"type": "end_turn"}, allow_ai=True
                        )
                        await broadcast_fn(room, events)
                        await asyncio.sleep(0.3)
                        continue

                    for idx in guesses:
                        room = await service._load_room(room_id)
                        if not room or not room.game_state:
                            return
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
                            return
                        if state["phase"] == "clue":
                            break

                    await asyncio.sleep(0.3)
                    continue

                except Exception as e:
                    logger.exception("AI turn failed: %s", e)
                    return
