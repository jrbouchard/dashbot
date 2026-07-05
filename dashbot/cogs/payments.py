from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from dashbot.dash.models import PaymentStatus
from dashbot.db.models import GuildConfig

logger = logging.getLogger("dashbot.payments")


def _format_amount(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _format_invoice_line(invoice: PaymentStatus) -> str:
    due = f"<t:{int(invoice.due_date.timestamp())}:D>" if invoice.due_date else "no due date"
    return f"**{invoice.team_name}** — {invoice.description}: {_format_amount(invoice.amount_due_cents)} due {due}"


class Payments(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="payment-status", description="Show outstanding league payments."
    )
    @app_commands.describe(team="Team name to filter by (optional)")
    async def payment_status(
        self, interaction: discord.Interaction, team: str | None = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        invoices = await self.bot.dash_client.get_payment_statuses()
        unpaid = [i for i in invoices if not i.paid]
        if team:
            needle = team.lower()
            unpaid = [i for i in unpaid if needle in i.team_name.lower()]

        if not unpaid:
            await interaction.followup.send("Nothing outstanding. \U0001f3d2")
            return

        embed = discord.Embed(
            title="Outstanding Payments",
            description="\n".join(_format_invoice_line(i) for i in unpaid),
            color=discord.Color.red(),
        )
        embed.set_footer(text="Pay through Dash — this bot cannot take payments.")
        await interaction.followup.send(embed=embed)

    async def send_reminders(self, due: list[PaymentStatus]) -> None:
        """Called by the scheduler with invoices that just became due for a reminder."""
        if not due:
            return

        with self.bot.db.session() as session:
            configs = session.query(GuildConfig).filter(
                GuildConfig.payments_channel_id.isnot(None)
            ).all()
            channel_ids = [c.payments_channel_id for c in configs]

        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue
            for invoice in due:
                await channel.send(
                    f"\U0001f4b8 Payment reminder: {_format_invoice_line(invoice)}\n"
                    "Please log into Dash to pay."
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Payments(bot))
