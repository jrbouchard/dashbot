"""Environment-based configuration. No secrets ever live in code or git."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            "Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Config:
    discord_token: str
    discord_guild_id: int | None

    dash_company: str
    dash_api_base_url: str
    dash_api_key: str | None
    dash_use_mock_client: bool

    database_url: str
    dash_sync_interval_minutes: int

    @classmethod
    def load(cls) -> "Config":
        guild_id = os.environ.get("DISCORD_GUILD_ID") or None
        return cls(
            discord_token=_require("DISCORD_TOKEN"),
            discord_guild_id=int(guild_id) if guild_id else None,
            dash_company=os.environ.get("DASH_COMPANY", ""),
            dash_api_base_url=os.environ.get(
                "DASH_API_BASE_URL", "https://api.daysmartrecreation.com"
            ),
            dash_api_key=os.environ.get("DASH_API_KEY") or None,
            dash_use_mock_client=_bool(os.environ.get("DASH_USE_MOCK_CLIENT")),
            database_url=os.environ.get("DATABASE_URL", "sqlite:///dashbot.db"),
            dash_sync_interval_minutes=int(
                os.environ.get("DASH_SYNC_INTERVAL_MINUTES", "15")
            ),
        )
