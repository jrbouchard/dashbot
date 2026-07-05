from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from dashbot.dash.models import Game
from dashbot.db.models import GuildConfig

logger = logging.getLogger("dashbot.games")


def _format_game_line(game: Game) -> str:
    ts = int(game.starts_at.timestamp())
    where = f" @ {game.location}" if game.location else ""
    if game.is_final:
        return f"<t:{ts}:f> — **{game.home_team}** {game.home_score}-{game.away_score} **{game.away_team}**{where} (final)"
    return f"<t:{ts}:f> — **{game.home_team}** vs **{game.away_team}**{where}"


class Games(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="schedule", description="Show upcoming games, optionally filtered by team."
    )
    @app_commands.describe(team="Team name to filter by (optional)")
    async def schedule(
        self, interaction: discord.Interaction, team: str | None = None
    ) -> None:
        await interaction.response.defer()
        games = await self.bot.dash_client.get_games(
            since=datetime.now(timezone.utc)
        )
        if team:
            needle = team.lower()
            games = [
                g
                for g in games
                if needle in g.home_team.lower() or needle in g.away_team.lower()
            ]
        games = sorted(games, key=lambda g: g.starts_at)[:10]

        if not games:
            await interaction.followup.send("No upcoming games found.")
            return

        embed = discord.Embed(
            title="Upcoming Games" + (f" — {team}" if team else ""),
            description="\n".join(_format_game_line(g) for g in games),
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed)

    async def post_new_games(self, newly_scheduled: list[Game], newly_final: list[Game]) -> None:
        """Called by the scheduler after each Dash sync."""
        if not newly_scheduled and not newly_final:
            return

        with self.bot.db.session() as session:
            configs = session.query(GuildConfig).filter(
                GuildConfig.games_channel_id.isnot(None)
            ).all()
            channel_ids = [c.games_channel_id for c in configs]

        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue
            for game in sorted(newly_scheduled, key=lambda g: g.starts_at):
                await channel.send(f"🏒 New game scheduled: {_format_game_line(game)}")
            for game in newly_final:
                await channel.send(f"📋 Final score: {_format_game_line(game)}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Games(bot))
