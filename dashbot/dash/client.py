"""Client for reading league data out of Dash (DaySmart Recreation).

Dash exposes an official JSON:API-flavored API for staff accounts.
IMPORTANT: the exact resource paths and attribute names below are our best
guess based on the JSON:API spec Dash documents publicly -- we have not yet
seen the authenticated reference docs (they require a logged-in Dash admin
session to view). Once NCI's service account/API key exists:

  1. Log into Dash, open the API reference under the API Key Management area.
  2. Confirm the real paths for teams/games/roster/invoices/stats and the
     actual attribute names on each resource.
  3. Update RESOURCE PATHS and the `_parse_*` functions below to match.
     Nothing outside this module needs to change -- cogs and the sync layer
     only depend on the plain dataclasses in models.py.

Until then, set DASH_USE_MOCK_CLIENT=true to develop against MockDashClient,
which returns realistic sample data shaped like NCI's leagues.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx

from dashbot.config import Config
from dashbot.dash.exceptions import DashApiError, DashAuthError
from dashbot.dash.models import Game, PaymentStatus, RosterPlayer, StatLine, Team

# --- RESOURCE PATHS (verify against real Dash API reference) ---
TEAMS_PATH = "/api/v1/teams"
GAMES_PATH = "/api/v1/games"
ROSTER_PATH = "/api/v1/teams/{team_id}/roster-players"
INVOICES_PATH = "/api/v1/invoices"
STATS_PATH = "/api/v1/stats"


class DashClient(Protocol):
    """Interface the rest of the bot codes against."""

    async def get_teams(self) -> list[Team]: ...

    async def get_games(
        self, *, since: datetime | None = None, team_id: str | None = None
    ) -> list[Game]: ...

    async def get_roster(self, team_id: str) -> list[RosterPlayer]: ...

    async def get_payment_statuses(
        self, *, team_id: str | None = None
    ) -> list[PaymentStatus]: ...

    async def get_stats(self, *, team_id: str | None = None) -> list[StatLine]:
        ...

    async def aclose(self) -> None: ...


def _attr(resource: dict[str, Any], key: str, default: Any = None) -> Any:
    return resource.get("attributes", {}).get(key, default)


def _parse_team(resource: dict[str, Any]) -> Team:
    return Team(
        id=str(resource["id"]),
        name=_attr(resource, "name", "Unknown Team"),
        league=_attr(resource, "league_name"),
        division=_attr(resource, "division_name"),
    )


def _parse_game(resource: dict[str, Any]) -> Game:
    starts_at_raw = _attr(resource, "start_time") or _attr(resource, "game_date")
    starts_at = (
        datetime.fromisoformat(starts_at_raw)
        if starts_at_raw
        else datetime.now(timezone.utc)
    )
    return Game(
        id=str(resource["id"]),
        starts_at=starts_at,
        home_team=_attr(resource, "home_team_name", "TBD"),
        away_team=_attr(resource, "away_team_name", "TBD"),
        location=_attr(resource, "location_name"),
        league=_attr(resource, "league_name"),
        home_score=_attr(resource, "home_score"),
        away_score=_attr(resource, "away_score"),
    )


def _parse_roster_player(resource: dict[str, Any], team_id: str) -> RosterPlayer:
    return RosterPlayer(
        id=str(resource["id"]),
        team_id=team_id,
        name=_attr(resource, "full_name", "Unknown Player"),
        jersey_number=_attr(resource, "jersey_number"),
    )


def _parse_invoice(resource: dict[str, Any]) -> PaymentStatus:
    due_date_raw = _attr(resource, "due_date")
    return PaymentStatus(
        id=str(resource["id"]),
        team_id=str(_attr(resource, "team_id", "")),
        team_name=_attr(resource, "team_name", "Unknown Team"),
        description=_attr(resource, "description", "League fees"),
        amount_due_cents=int(_attr(resource, "amount_due_cents", 0) or 0),
        due_date=datetime.fromisoformat(due_date_raw) if due_date_raw else None,
        paid=bool(_attr(resource, "paid", False)),
    )


def _parse_stat_line(resource: dict[str, Any]) -> StatLine:
    return StatLine(
        player_id=str(_attr(resource, "player_id", resource["id"])),
        player_name=_attr(resource, "player_name", "Unknown Player"),
        team_id=str(_attr(resource, "team_id", "")),
        games_played=int(_attr(resource, "games_played", 0) or 0),
        goals=int(_attr(resource, "goals", 0) or 0),
        assists=int(_attr(resource, "assists", 0) or 0),
        penalty_minutes=int(_attr(resource, "penalty_minutes", 0) or 0),
    )


class RealDashClient:
    """Talks to the live Dash API using a staff API key."""

    def __init__(self, config: Config):
        if not config.dash_api_key:
            raise DashAuthError(
                "DASH_API_KEY is not set. Get a service account API key from "
                "your Dash admin, or set DASH_USE_MOCK_CLIENT=true for local dev."
            )
        self._company = config.dash_company
        self._http = httpx.AsyncClient(
            base_url=config.dash_api_base_url,
            headers={
                "Authorization": f"Bearer {config.dash_api_key}",
                "Accept": "application/vnd.api+json",
            },
            timeout=30.0,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get_all_pages(
        self, path: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        params = dict(params or {})
        params.setdefault("company", self._company)
        results: list[dict[str, Any]] = []
        url: str | None = path
        while url:
            response = await self._http.get(url, params=params)
            if response.status_code == 401:
                raise DashAuthError("Dash API rejected the configured API key.")
            if response.is_error:
                raise DashApiError(
                    f"Dash API error {response.status_code} for {url}: {response.text}"
                )
            payload = response.json()
            results.extend(payload.get("data", []))
            next_link = payload.get("links", {}).get("next")
            url = next_link
            params = None  # next_link already has query params baked in
        return results

    async def get_teams(self) -> list[Team]:
        resources = await self._get_all_pages(TEAMS_PATH)
        return [_parse_team(r) for r in resources]

    async def get_games(
        self, *, since: datetime | None = None, team_id: str | None = None
    ) -> list[Game]:
        params: dict[str, Any] = {}
        if since is not None:
            params["filter[since]"] = since.isoformat()
        if team_id is not None:
            params["filter[team_id]"] = team_id
        resources = await self._get_all_pages(GAMES_PATH, params)
        return [_parse_game(r) for r in resources]

    async def get_roster(self, team_id: str) -> list[RosterPlayer]:
        resources = await self._get_all_pages(ROSTER_PATH.format(team_id=team_id))
        return [_parse_roster_player(r, team_id) for r in resources]

    async def get_payment_statuses(
        self, *, team_id: str | None = None
    ) -> list[PaymentStatus]:
        params = {"filter[team_id]": team_id} if team_id else {}
        resources = await self._get_all_pages(INVOICES_PATH, params)
        return [_parse_invoice(r) for r in resources]

    async def get_stats(self, *, team_id: str | None = None) -> list[StatLine]:
        params = {"filter[team_id]": team_id} if team_id else {}
        resources = await self._get_all_pages(STATS_PATH, params)
        return [_parse_stat_line(r) for r in resources]


class MockDashClient:
    """In-memory sample data shaped like NCI's leagues, for local dev/testing."""

    def __init__(self) -> None:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        self._teams = [
            Team(id="t1", name="Oakland Outlaws", league="Silver A", division="A"),
            Team(id="t2", name="Bay Bombers", league="Silver A", division="A"),
            Team(id="t3", name="Dry Ice Renegades", league="Bronze B", division="B"),
        ]
        self._games = [
            Game(
                id="g1",
                starts_at=now + timedelta(days=1, hours=19),
                home_team="Oakland Outlaws",
                away_team="Bay Bombers",
                location="Rink 1",
                league="Silver A",
            ),
            Game(
                id="g2",
                starts_at=now - timedelta(days=6, hours=-19),
                home_team="Oakland Outlaws",
                away_team="Dry Ice Renegades",
                location="Rink 1",
                league="Silver A",
                home_score=5,
                away_score=3,
            ),
        ]
        self._roster = {
            "t1": [
                RosterPlayer(id="p1", team_id="t1", name="J. Bouchard", jersey_number="7"),
                RosterPlayer(id="p2", team_id="t1", name="A. Smith", jersey_number="21"),
            ]
        }
        self._invoices = [
            PaymentStatus(
                id="i1",
                team_id="t1",
                team_name="Oakland Outlaws",
                description="Fall 2026 league fees",
                amount_due_cents=15000,
                due_date=now + timedelta(days=10),
                paid=False,
            )
        ]
        self._stats = [
            StatLine(
                player_id="p1",
                player_name="J. Bouchard",
                team_id="t1",
                games_played=8,
                goals=6,
                assists=9,
                penalty_minutes=4,
            )
        ]

    async def get_teams(self) -> list[Team]:
        return list(self._teams)

    async def get_games(
        self, *, since: datetime | None = None, team_id: str | None = None
    ) -> list[Game]:
        games = self._games
        if since is not None:
            games = [g for g in games if g.starts_at >= since]
        return list(games)

    async def get_roster(self, team_id: str) -> list[RosterPlayer]:
        return list(self._roster.get(team_id, []))

    async def get_payment_statuses(
        self, *, team_id: str | None = None
    ) -> list[PaymentStatus]:
        invoices = self._invoices
        if team_id is not None:
            invoices = [i for i in invoices if i.team_id == team_id]
        return list(invoices)

    async def get_stats(self, *, team_id: str | None = None) -> list[StatLine]:
        stats = self._stats
        if team_id is not None:
            stats = [s for s in stats if s.team_id == team_id]
        return list(stats)

    async def aclose(self) -> None:
        return None


def build_dash_client(config: Config) -> DashClient:
    if config.dash_use_mock_client:
        return MockDashClient()
    return RealDashClient(config)
