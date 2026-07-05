# dashbot

Discord bot for Nor Cal Inline (NCI) that replaces Dash for everything
*except* actually collecting payment. It reads league data (schedules,
rosters, payment status, stats) from Dash's official API and handles
game notifications, returning-player surveys, and payment reminders/alerts
inside Discord.

Dash remains the system of record and the only place players actually pay —
this bot never touches money, it just surfaces what's in Dash and lets
players interact with the league socially in Discord instead.

## How it's organized

- `dashbot/dash/` — client for Dash's API (`DashClient` interface, a
  `RealDashClient` implementation, and a `MockDashClient` with sample data
  for local development before a Dash API key exists).
- `dashbot/db/` — SQLite-backed state: which Discord channel each
  notification type goes to, which games/payment reminders have already
  been announced, and survey responses.
- `dashbot/cogs/` — Discord slash commands and scheduled notification logic,
  one file per feature area (games, surveys, payments, stats, admin).
- `dashbot/sync.py` — pulls from Dash and decides what's new since the last
  check; called on a timer by `dashbot/scheduler.py`.

## Important: Dash API endpoints are best-guess and need verification

Dash's API reference is only visible once logged into a Dash admin account,
so `dashbot/dash/client.py` was written against the public JSON:API
conventions Dash documents, **not** the actual endpoint paths/field names.
Before this bot can talk to the real API:

1. Get a Dash service account with the "API Key Management" permission from
   NCI's Dash admin.
2. Log in and open the API reference to confirm the real paths for
   teams/games/rosters/invoices/stats and their attribute names.
3. Update the `*_PATH` constants and `_parse_*` functions at the top of
   `dashbot/dash/client.py` to match. Nothing else needs to change — every
   cog only depends on the plain dataclasses in `dashbot/dash/models.py`.

Until then, develop against `MockDashClient` (see setup below).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # or requirements.txt for prod-only

cp .env.example .env
```

Fill in `.env`:

- `DISCORD_TOKEN` — from the [Discord Developer Portal](https://discord.com/developers/applications),
  under your application's Bot tab. Needs the `applications.commands` and
  `bot` scopes when inviting it to the server (Send Messages, Embed Links,
  Manage Messages if you want it cleaning up old survey posts).
- `DISCORD_GUILD_ID` — NCI's server ID. Set this during development so slash
  commands sync instantly to that server instead of waiting up to an hour
  for a global sync.
- `DASH_API_KEY` / `DASH_COMPANY` — from your Dash service account. Leave
  `DASH_API_KEY` blank and set `DASH_USE_MOCK_CLIENT=true` to develop without
  real Dash credentials.

**Never commit `.env` or paste real tokens/keys into chat, issues, or
commits** — `.env` is already gitignored. In production, set these as
environment variables / secrets on whatever host runs the bot (not in the
repo).

Run it:

```bash
python -m dashbot
```

## Self-hosting (recommended: no cloud bill)

The bot holds an always-on connection to Discord and polls Dash on a timer,
so it needs to run continuously somewhere — but that "somewhere" can just be
a machine you already control (the same box running Jellyfin/Plex/etc. is
fine) instead of a paid cloud service.

### Option A: Docker Compose

Simplest if you're already running other self-hosted services this way.

```bash
cp .env.example .env   # fill it in first
docker compose up -d --build
```

- State (the SQLite file) lands in `./data/dashbot.db` on the host via the
  volume mount in `docker-compose.yml`, so it survives container
  rebuilds/restarts — back that file up if you want survey/reminder history
  preserved across a full re-provision.
- `restart: unless-stopped` brings it back after a host reboot or crash.
- To update after pulling new code: `docker compose up -d --build` again.
- Logs: `docker compose logs -f dashbot`.

### Option B: systemd (bare metal, no Docker)

```bash
sudo useradd --system --home /opt/dashbot dashbot
sudo git clone <this repo> /opt/dashbot
cd /opt/dashbot
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill it in
sudo chown -R dashbot:dashbot /opt/dashbot

sudo cp deploy/dashbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dashbot
```

- `deploy/dashbot.service` assumes `/opt/dashbot` — edit the paths in that
  file first if you put the repo somewhere else.
- Restarts automatically on failure and on boot (`enable`).
- Logs: `journalctl -u dashbot -f`.
- To update: `git pull`, `.venv/bin/pip install -r requirements.txt` (if
  deps changed), `sudo systemctl restart dashbot`.

Either way, `.env` and `*.db` never need to leave the host — nothing about
this bot requires a third-party server, cloud account, or recurring fee.

## Slash commands

- `/schedule [team]` — upcoming games.
- `/payment-status [team]` — outstanding invoices (ephemeral; points back to
  Dash to actually pay).
- `/stats [team]` — player stats, top scorers by default.
- `/survey create <title>` — posts a Yes/No/Maybe returning-player survey.
- `/survey results <survey_id>` — tally of responses (admin only).
- `/survey close <survey_id>` — stop accepting responses (admin only).
- `/set-channel <kind> <channel>` — route `games`/`payments`/`surveys`/`stats`
  notifications to a channel (admin only, requires Manage Server).

## Automated notifications

Every `DASH_SYNC_INTERVAL_MINUTES` (default 15), the bot:

- Posts newly-scheduled games and newly-final scores to each guild's games
  channel.
- Sends a payment reminder to each guild's payments channel for any unpaid
  invoice not already reminded about in the last 24 hours.

Run `/set-channel` for each guild before either of these will post anywhere.

## Tests

```bash
python -m pytest
```

Tests run entirely against `MockDashClient` and a temporary SQLite file, so
no Dash or Discord credentials are needed.
