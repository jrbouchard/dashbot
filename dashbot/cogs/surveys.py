from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from dashbot.db.models import Survey, SurveyResponse

RESPONSE_LABELS = {"yes": "Yes, I'm in", "no": "No, sitting out", "maybe": "Not sure yet"}
RESPONSE_STYLES = {
    "yes": discord.ButtonStyle.success,
    "no": discord.ButtonStyle.danger,
    "maybe": discord.ButtonStyle.secondary,
}


class SurveyView(discord.ui.View):
    """Persistent Yes/No/Maybe buttons for a single survey."""

    def __init__(self, bot: commands.Bot, survey_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.survey_id = survey_id
        for value, label in RESPONSE_LABELS.items():
            button = discord.ui.Button(
                label=label,
                style=RESPONSE_STYLES[value],
                custom_id=f"survey:{survey_id}:{value}",
            )
            button.callback = self._make_callback(value)
            self.add_item(button)

    def _make_callback(self, value: str):
        async def callback(interaction: discord.Interaction) -> None:
            with self.bot.db.session() as session:
                existing = (
                    session.query(SurveyResponse)
                    .filter_by(survey_id=self.survey_id, discord_user_id=interaction.user.id)
                    .one_or_none()
                )
                if existing is not None:
                    existing.response = value
                    existing.responded_at = datetime.now(timezone.utc)
                    existing.discord_display_name = str(interaction.user)
                else:
                    session.add(
                        SurveyResponse(
                            survey_id=self.survey_id,
                            discord_user_id=interaction.user.id,
                            discord_display_name=str(interaction.user),
                            response=value,
                            responded_at=datetime.now(timezone.utc),
                        )
                    )
            await interaction.response.send_message(
                f"Recorded: **{RESPONSE_LABELS[value]}**. Change your mind anytime by clicking again.",
                ephemeral=True,
            )

        return callback


class Surveys(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        # Re-register persistent views for any surveys still open, so buttons
        # keep working across bot restarts.
        with self.bot.db.session() as session:
            open_survey_ids = [
                s.id for s in session.query(Survey).filter_by(closed=False).all()
            ]
        for survey_id in open_survey_ids:
            self.bot.add_view(SurveyView(self.bot, survey_id))

    survey_group = app_commands.Group(
        name="survey", description="Create and manage player surveys"
    )

    @survey_group.command(name="create", description="Post a returning-player survey.")
    @app_commands.describe(title="Survey question, e.g. 'Returning for Fall 2026?'")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create(self, interaction: discord.Interaction, title: str) -> None:
        assert interaction.guild_id is not None
        with self.bot.db.session() as session:
            survey = Survey(
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                title=title,
                created_at=datetime.now(timezone.utc),
            )
            session.add(survey)
            session.flush()
            survey_id = survey.id

        view = SurveyView(self.bot, survey_id)
        embed = discord.Embed(title=title, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        with self.bot.db.session() as session:
            db_survey = session.get(Survey, survey_id)
            assert db_survey is not None
            db_survey.message_id = message.id

        self.bot.add_view(view, message_id=message.id)

    @survey_group.command(name="results", description="Show tallied responses for a survey.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def results(self, interaction: discord.Interaction, survey_id: int) -> None:
        with self.bot.db.session() as session:
            survey = session.get(Survey, survey_id)
            if survey is None:
                await interaction.response.send_message("No survey with that ID.", ephemeral=True)
                return
            responses = (
                session.query(SurveyResponse).filter_by(survey_id=survey_id).all()
            )

        by_value: dict[str, list[str]] = {k: [] for k in RESPONSE_LABELS}
        for r in responses:
            by_value.setdefault(r.response, []).append(r.discord_display_name)

        embed = discord.Embed(title=f"Results: {survey.title}", color=discord.Color.gold())
        for value, label in RESPONSE_LABELS.items():
            names = by_value.get(value, [])
            embed.add_field(
                name=f"{label} ({len(names)})",
                value="\n".join(names) if names else "—",
                inline=True,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @survey_group.command(name="close", description="Stop accepting new responses for a survey.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def close(self, interaction: discord.Interaction, survey_id: int) -> None:
        with self.bot.db.session() as session:
            survey = session.get(Survey, survey_id)
            if survey is None:
                await interaction.response.send_message("No survey with that ID.", ephemeral=True)
                return
            survey.closed = True
        await interaction.response.send_message("Survey closed.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Surveys(bot))
