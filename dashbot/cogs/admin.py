from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from dashbot.db.models import GuildConfig

CHANNEL_KINDS = ("games", "payments", "surveys", "stats")


class Admin(commands.Cog):
    """Server setup: which channel each kind of notification goes to."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="set-channel", description="Route a category of bot posts to a channel."
    )
    @app_commands.describe(kind="Which kind of notification", channel="Target channel")
    @app_commands.choices(
        kind=[app_commands.Choice(name=k, value=k) for k in CHANNEL_KINDS]
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(
        self,
        interaction: discord.Interaction,
        kind: app_commands.Choice[str],
        channel: discord.TextChannel,
    ) -> None:
        assert interaction.guild_id is not None
        with self.bot.db.session() as session:
            config = session.get(GuildConfig, interaction.guild_id)
            if config is None:
                config = GuildConfig(guild_id=interaction.guild_id)
                session.add(config)
            setattr(config, f"{kind.value}_channel_id", channel.id)

        await interaction.response.send_message(
            f"{kind.value.capitalize()} notifications will now post to {channel.mention}.",
            ephemeral=True,
        )

    @set_channel.error
    async def set_channel_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the Manage Server permission to do that.", ephemeral=True
            )
            return
        raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
