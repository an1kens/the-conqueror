from logic.game_clock import GameClock
from logic.simulation import Simulation

__all__ = ["GameClock", "Simulation"]


def __getattr__(name: str):
    if name == "PlayerController":
        from logic.player import PlayerController
        return PlayerController
    raise AttributeError(name)
