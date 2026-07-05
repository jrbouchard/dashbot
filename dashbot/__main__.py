from __future__ import annotations

import asyncio
import logging

from dashbot.bot import NCIBot
from dashbot.config import Config
from dashbot.dash.client import build_dash_client
from dashbot.db.session import Database


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    config = Config.load()
    db = Database(config.database_url)
    dash_client = build_dash_client(config)
    bot = NCIBot(config, db, dash_client)

    try:
        await bot.start(config.discord_token)
    finally:
        await dash_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
