from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GuildConfig(Base):
    """Per-Discord-server channel routing, set via admin slash commands."""

    __tablename__ = "guild_config"

    guild_id: Mapped[int] = mapped_column(primary_key=True)
    games_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payments_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    surveys_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stats_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SyncedGame(Base):
    """Tracks which Dash games we've already posted notifications for."""

    __tablename__ = "synced_game"

    dash_game_id: Mapped[str] = mapped_column(String, primary_key=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    home_team: Mapped[str] = mapped_column(String)
    away_team: Mapped[str] = mapped_column(String)
    league: Mapped[str | None] = mapped_column(String, nullable=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    announced: Mapped[bool] = mapped_column(Boolean, default=False)
    result_announced: Mapped[bool] = mapped_column(Boolean, default=False)


class Survey(Base):
    """A 'are you returning next season' (or similar) poll posted to Discord."""

    __tablename__ = "survey"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(Integer)
    channel_id: Mapped[int] = mapped_column(Integer)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed: Mapped[bool] = mapped_column(Boolean, default=False)


class SurveyResponse(Base):
    __tablename__ = "survey_response"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("survey.id"))
    discord_user_id: Mapped[int] = mapped_column(Integer)
    discord_display_name: Mapped[str] = mapped_column(String)
    response: Mapped[str] = mapped_column(String)  # "yes" | "no" | "maybe"
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaymentReminderState(Base):
    """Prevents re-sending the same payment reminder every sync cycle."""

    __tablename__ = "payment_reminder_state"

    dash_invoice_id: Mapped[str] = mapped_column(String, primary_key=True)
    last_reminded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)
