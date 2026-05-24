class GameClock:
    """Abstract game-time. Real seconds map to game-days via scale."""

    def __init__(self, days_per_real_second: float = 30.0):
        self.game_day: float = 0.0
        self.paused: bool = False
        self.days_per_real_second = days_per_real_second

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    def advance(self, real_delta_seconds: float) -> float:
        """Advance game-time. Returns game-days elapsed (0 if paused)."""
        if self.paused or real_delta_seconds <= 0:
            return 0.0
        elapsed = real_delta_seconds * self.days_per_real_second
        self.game_day += elapsed
        return elapsed

    def game_month(self) -> int:
        return int(self.game_day // 30)

    def game_year(self) -> int:
        return int(self.game_day // 365)
