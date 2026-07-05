from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from dashbot.sync import get_due_payment_reminders, sync_games

logger = logging.getLogger("dashbot.scheduler")


async def run_sync_cycle(bot) -> None:
    try:
        newly_scheduled, newly_final = await sync_games(bot.db, bot.dash_client)
        games_cog = bot.get_cog("Games")
        if games_cog is not None:
            await games_cog.post_new_games(newly_scheduled, newly_final)

        due = await get_due_payment_reminders(bot.db, bot.dash_client)
        payments_cog = bot.get_cog("Payments")
        if payments_cog is not None:
            await payments_cog.send_reminders(due)
    except Exception:
        logger.exception("Dash sync cycle failed")


def start_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_sync_cycle,
        "interval",
        minutes=bot.config.dash_sync_interval_minutes,
        args=[bot],
        id="dash_sync_cycle",
    )
    # Also run once immediately on startup rather than waiting a full interval.
    scheduler.add_job(run_sync_cycle, args=[bot], id="dash_sync_cycle_initial")
    scheduler.start()
    return scheduler
