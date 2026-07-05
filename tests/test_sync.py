from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dashbot.dash.client import MockDashClient
from dashbot.sync import get_due_payment_reminders, sync_games


@pytest.mark.asyncio
async def test_sync_games_first_run_reports_all_as_new(db):
    client = MockDashClient()
    newly_scheduled, newly_final = await sync_games(db, client)
    assert len(newly_scheduled) == 2
    assert len(newly_final) == 1  # one mock game already has a final score


@pytest.mark.asyncio
async def test_sync_games_second_run_reports_nothing_new(db):
    client = MockDashClient()
    await sync_games(db, client)
    newly_scheduled, newly_final = await sync_games(db, client)
    assert newly_scheduled == []
    assert newly_final == []


@pytest.mark.asyncio
async def test_sync_games_detects_newly_final_result(db, monkeypatch):
    client = MockDashClient()
    # First sync sees the game with no score yet.
    unfinished_game = client._games[0]
    object.__setattr__(unfinished_game, "home_score", None)
    object.__setattr__(unfinished_game, "away_score", None)
    await sync_games(db, client)

    # Now the game has finished.
    object.__setattr__(unfinished_game, "home_score", 4)
    object.__setattr__(unfinished_game, "away_score", 2)
    _, newly_final = await sync_games(db, client)

    assert any(g.id == unfinished_game.id for g in newly_final)


@pytest.mark.asyncio
async def test_payment_reminder_respects_cooldown(db):
    client = MockDashClient()
    first_due = await get_due_payment_reminders(db, client)
    assert len(first_due) == 1

    second_due = await get_due_payment_reminders(db, client)
    assert second_due == []
