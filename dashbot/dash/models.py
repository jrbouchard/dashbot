"""Plain data models for the pieces of Dash data the bot cares about.

These are intentionally decoupled from whatever field names the real Dash
JSON:API responses use. All translation from raw API payloads happens in
client.py, so if Dash's field names differ from what we assumed, only the
parsing code needs to change -- not every cog that consumes these models.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    league: str | None = None
    division: str | None = None


@dataclass(frozen=True)
class Game:
    id: str
    starts_at: datetime
    home_team: str
    away_team: str
    location: str | None = None
    league: str | None = None
    home_score: int | None = None
    away_score: int | None = None

    @property
    def is_final(self) -> bool:
        return self.home_score is not None and self.away_score is not None


@dataclass(frozen=True)
class RosterPlayer:
    id: str
    team_id: str
    name: str
    jersey_number: str | None = None


@dataclass(frozen=True)
class PaymentStatus:
    id: str
    team_id: str
    team_name: str
    description: str
    amount_due_cents: int
    due_date: datetime | None
    paid: bool


@dataclass(frozen=True)
class StatLine:
    player_id: str
    player_name: str
    team_id: str
    games_played: int = 0
    goals: int = 0
    assists: int = 0
    penalty_minutes: int = 0

    @property
    def points(self) -> int:
        return self.goals + self.assists
