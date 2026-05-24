"""Active wars between countries — start, ceasefire, casualties tracking."""

from dataclasses import dataclass, field


@dataclass
class War:
    country_a: str
    country_b: str
    started_turn: int
    active: bool = True
    casualties_a: int = 0
    casualties_b: int = 0
    ceasefire_turn: int | None = None

    def pair(self) -> frozenset[str]:
        return frozenset({self.country_a, self.country_b})

    def other(self, country: str) -> str:
        return self.country_b if country == self.country_a else self.country_a

    def add_casualties(self, country: str, amount: int) -> None:
        if country == self.country_a:
            self.casualties_a += amount
        else:
            self.casualties_b += amount


@dataclass
class BattleReport:
    turn: int
    attacker: str
    defender: str
    territory: str
    attacker_casualties: int
    defender_casualties: int
    attacker_loss_military: int
    defender_loss_military: int
    territory_changed: bool
    holder_after: str
    summary: str


def find_war(wars: list[War], a: str, b: str) -> War | None:
    pair = frozenset({a, b})
    for war in wars:
        if war.pair() == pair and war.active:
            return war
    return None


def declare_war(wars: list[War], a: str, b: str, turn: int) -> War:
    existing = find_war(wars, a, b)
    if existing:
        return existing
    war = War(country_a=a, country_b=b, started_turn=turn, active=True)
    wars.append(war)
    return war


def ceasefire(war: War, turn: int) -> None:
    war.active = False
    war.ceasefire_turn = turn
