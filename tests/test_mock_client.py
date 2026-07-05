import pytest

from dashbot.dash.client import MockDashClient


@pytest.mark.asyncio
async def test_get_teams_returns_teams():
    client = MockDashClient()
    teams = await client.get_teams()
    assert len(teams) > 0
    assert all(team.name for team in teams)


@pytest.mark.asyncio
async def test_get_games_filters_by_since():
    from datetime import datetime, timezone

    client = MockDashClient()
    all_games = await client.get_games()
    future_games = await client.get_games(since=datetime.now(timezone.utc))
    assert len(future_games) <= len(all_games)
    assert all(g.starts_at >= datetime.now(timezone.utc) for g in future_games)


@pytest.mark.asyncio
async def test_get_payment_statuses_filters_by_team():
    client = MockDashClient()
    all_invoices = await client.get_payment_statuses()
    team_id = all_invoices[0].team_id
    filtered = await client.get_payment_statuses(team_id=team_id)
    assert all(i.team_id == team_id for i in filtered)


@pytest.mark.asyncio
async def test_get_stats_points_property():
    client = MockDashClient()
    stats = await client.get_stats()
    line = stats[0]
    assert line.points == line.goals + line.assists
