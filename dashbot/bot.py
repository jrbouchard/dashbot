from __future__ import annotations

import logging

import discord
from discord.ext import commands

from dashbot.config import Config
from dashbot.dash.client import DashClient
from dashbot.db.session import Database

logger = logging.getLogger("dashbot")

INITIAL_COGS = (
    "dashbot.cogs.admin",
    "dashbot.cogs.games",
    "dashbot.cogs.surveys",
    "dashbot.cogs.payments",
    "dashbot.cogs.stats",
)


class NCIBot(commands.Bot):
    """Discord bot for Nor Cal Inline: schedules, surveys, payment reminders, stats."""

    def __init__(self, config: Config, db: Database, dash_client: DashClient):
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.db = db
        self.dash_client = dash_client
        self._scheduler_started = False

    async def setup_hook(self) -> None:
        for cog in INITIAL_COGS:
            await self.load_extension(cog)
            logger.info("Loaded cog %s", cog)

        if self.config.discord_guild_id:
            guild = discord.Object(id=self.config.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(
                "Synced slash commands to guild %s", self.config.discord_guild_id
            )
        else:
            await self.tree.sync()
            logger.info("Synced slash commands globally (may take up to an hour)")

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (id=%s)", self.user, self.user.id if self.user else None)
        if not self._scheduler_started:
            from dashbot.scheduler import start_scheduler

            start_scheduler(self)
            self._scheduler_started = True
