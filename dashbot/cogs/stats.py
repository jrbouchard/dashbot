from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Show player stats, optionally filtered by team.")
    @app_commands.describe(team="Team name to filter by (optional)")
    async def stats(
        self, interaction: discord.Interaction, team: str | None = None
    ) -> None:
        await interaction.response.defer()
        team_id = None
        if team:
            teams = await self.bot.dash_client.get_teams()
            needle = team.lower()
            matches = [t for t in teams if needle in t.name.lower()]
            if not matches:
                await interaction.followup.send(f"No team matching '{team}'.")
                return
            team_id = matches[0].id

        stat_lines = await self.bot.dash_client.get_stats(team_id=team_id)
        stat_lines = sorted(stat_lines, key=lambda s: s.points, reverse=True)[:15]

        if not stat_lines:
            await interaction.followup.send("No stats available yet.")
            return

        rows = [
            f"**{s.player_name}** — GP {s.games_played}, G {s.goals}, A {s.assists}, "
            f"P {s.points}, PIM {s.penalty_minutes}"
            for s in stat_lines
        ]
        embed = discord.Embed(
            title="Player Stats" + (f" — {team}" if team else " — Top Scorers"),
            description="\n".join(rows),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Stats(bot))
