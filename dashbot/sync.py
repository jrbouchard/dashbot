"""Pulls data from Dash and figures out what's new since the last sync.

Cogs call these functions instead of talking to DashClient/the DB directly,
so "what counts as new" lives in one place.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dashbot.dash.client import DashClient
from dashbot.dash.models import Game, PaymentStatus
from dashbot.db.models import PaymentReminderState, SyncedGame
from dashbot.db.session import Database

# Don't re-DM someone about the same unpaid invoice more than once a day.
PAYMENT_REMINDER_COOLDOWN = timedelta(hours=24)


async def sync_games(db: Database, dash_client: DashClient) -> tuple[list[Game], list[Game]]:
    """Returns (newly_scheduled_games, newly_finalized_games)."""
    since = datetime.now(timezone.utc) - timedelta(days=7)
    games = await dash_client.get_games(since=since)

    newly_scheduled: list[Game] = []
    newly_final: list[Game] = []

    with db.session() as session:
        for game in games:
            existing = session.get(SyncedGame, game.id)
            if existing is None:
                session.add(
                    SyncedGame(
                        dash_game_id=game.id,
                        starts_at=game.starts_at,
                        home_team=game.home_team,
                        away_team=game.away_team,
                        league=game.league,
                        home_score=game.home_score,
                        away_score=game.away_score,
                        announced=True,
                        result_announced=game.is_final,
                    )
                )
                newly_scheduled.append(game)
                if game.is_final:
                    newly_final.append(game)
                continue

            if game.is_final and not existing.result_announced:
                newly_final.append(game)
                existing.result_announced = True

            existing.home_score = game.home_score
            existing.away_score = game.away_score

    return newly_scheduled, newly_final


async def get_due_payment_reminders(
    db: Database, dash_client: DashClient
) -> list[PaymentStatus]:
    """Returns unpaid invoices that haven't been reminded about recently."""
    invoices = await dash_client.get_payment_statuses()
    unpaid = [invoice for invoice in invoices if not invoice.paid]

    due: list[PaymentStatus] = []
    # SQLite drops tzinfo on round-trip, so keep this comparison naive-UTC
    # throughout rather than mixing aware/naive datetimes.
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with db.session() as session:
        for invoice in unpaid:
            state = session.get(PaymentReminderState, invoice.id)
            if state is None:
                state = PaymentReminderState(dash_invoice_id=invoice.id, reminder_count=0)
                session.add(state)

            if (
                state.last_reminded_at is None
                or now - state.last_reminded_at >= PAYMENT_REMINDER_COOLDOWN
            ):
                due.append(invoice)
                state.last_reminded_at = now
                state.reminder_count += 1

    return due
