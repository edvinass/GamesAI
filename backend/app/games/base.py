from abc import ABC, abstractmethod
from typing import Any


class GamePlugin(ABC):
    game_type: str

    @abstractmethod
    def default_settings(self) -> dict:
        ...

    @abstractmethod
    def validate_settings(self, settings: dict) -> dict:
        ...

    @abstractmethod
    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        ...

    @abstractmethod
    def apply_action(self, state: dict, action: dict, player: dict) -> tuple[dict, list[dict]]:
        ...

    @abstractmethod
    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        ...

    @abstractmethod
    def check_winner(self, state: dict) -> str | None:
        ...

    def assign_lobby_roles(self, players: list[dict], settings: dict) -> list[dict]:
        return players

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        return None

    def tick_interval_ms(self) -> int | None:
        return None

    def tick(self, state: dict) -> tuple[dict, list[dict]]:
        return state, []
