"""
Fantrax Standings Discord Bot
- /standings slash command
- Auto-posts standings on a configurable schedule
- Calls the Fantrax API directly (no broken library dependency)
"""

import os
import logging
from pathlib import Path

# Load .env file if present
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8-sig").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import tasks
import requests as _requests

# ─────────────────────────────────────────
# CONFIGURATION — edit these or set as env vars
# ─────────────────────────────────────────
DISCORD_TOKEN     = os.getenv("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN")
FANTRAX_LEAGUE_ID = os.getenv("FANTRAX_LEAGUE_ID", "YOUR_LEAGUE_ID")

# Session cookie from your browser (required for private leagues).
# See README for how to grab this value.
FANTRAX_COOKIE    = os.getenv("FANTRAX_COOKIE", "")

# Channel ID where auto-posts go (right-click channel → Copy Channel ID)
AUTO_POST_CHANNEL_ID = int(os.getenv("AUTO_POST_CHANNEL_ID", "0"))

# Schedule: days of week (0=Mon…6=Sun) and UTC time for the auto-post
SCHEDULE_DAYS   = [0]    # Monday by default
SCHEDULE_HOUR   = 12     # noon UTC = 8am EDT / 5am PDT
SCHEDULE_MINUTE = 0

# ─────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Column order returned by the STANDINGS view (positional, no headers in API response)
# [W, L, T, GB, Streak, PF, PA, ?]
COL_W      = 0
COL_L      = 1
COL_T      = 2
COL_GB     = 3
COL_STREAK = 4
COL_PF     = 5
COL_PA     = 6


def _build_session() -> _requests.Session:
    session = _requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Referer": f"https://www.fantrax.com/fantasy/league/{FANTRAX_LEAGUE_ID}/standings",
    })
    if FANTRAX_COOKIE:
        for part in FANTRAX_COOKIE.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                session.cookies.set(name.strip(), value.strip(), domain="www.fantrax.com")
    return session


def fetch_standings() -> dict:
    """
    Returns a dict with:
        league_name : str
        season      : str   e.g. "2026 Suk BU"
        rows        : list of dicts with keys: rank, team, w, l, t, gb, streak, pf, pa
    """
    session = _build_session()
    payload = {
        "msgs": [
            {
                "method": "getStandings",
                "data": {"leagueId": FANTRAX_LEAGUE_ID, "view": "STANDINGS"},
            }
        ]
    }
    resp = session.post(
        "https://www.fantrax.com/fxpa/req",
        params={"leagueId": FANTRAX_LEAGUE_ID},
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if "pageError" in data:
        code = data["pageError"].get("code", "UNKNOWN")
        if code in ("WARNING_NOT_LOGGED_IN", "NOT_LOGGED_IN"):
            raise PermissionError("Not logged in — your FANTRAX_COOKIE may have expired.")
        raise RuntimeError(f"Fantrax API error: {code} — {data['pageError'].get('text', '')}")

    r = data["responses"][0]["data"]

    # League name lives in miscData.heading
    season_name = r.get("miscData", {}).get("heading", "Fantasy League")

    # Find the main "Standings" table (first table)
    standings_table = next(
        (t for t in r.get("tableList", []) if t.get("caption") == "Standings"),
        None,
    )
    if standings_table is None:
        raise RuntimeError("Could not find Standings table in API response.")

    rows = []
    for row in standings_table.get("rows", []):
        fixed = row.get("fixedCells", [])
        cells = row.get("cells", [])

        rank = fixed[0]["content"] if len(fixed) > 0 else "?"
        team = fixed[1]["content"] if len(fixed) > 1 else "Unknown"

        def cell(i):
            return cells[i]["content"] if i < len(cells) else "-"

        rows.append({
            "rank":   rank,
            "team":   team,
            "w":      cell(COL_W),
            "l":      cell(COL_L),
            "t":      cell(COL_T),
            "gb":     cell(COL_GB),
            "streak": cell(COL_STREAK),
            "pf":     cell(COL_PF),
            "pa":     cell(COL_PA),
        })

    return {"league_name": season_name, "rows": rows}


def build_standings_embed() -> discord.Embed:
    data = fetch_standings()
    league_name = data["league_name"]
    rows = data["rows"]

    embed = discord.Embed(
        title=f"{league_name} Standings",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow(),
    )

    if not rows:
        embed.description = "_No standings data available yet._"
        return embed

    def display_width(s):
        """Estimate terminal display width: emoji count as 2, normal chars as 1."""
        width = 0
        for ch in s:
            cp = ord(ch)
            if (0x1F300 <= cp <= 0x1FAFF or  # misc emoji
                0x2600 <= cp <= 0x27BF or     # misc symbols
                0xFE00 <= cp <= 0xFE0F):      # variation selectors
                width += 2
            elif cp == 0x200D:                # zero-width joiner
                width += 0
            else:
                width += 1
        return width

    NAME_WIDTH = 26

    def pad_name(s):
        """Pad name to NAME_WIDTH accounting for emoji double-width."""
        w = display_width(s)
        if w >= NAME_WIDTH:
            return s
        return s + " " * (NAME_WIDTH - w)

    header = f" # | {'Team':<{NAME_WIDTH}} | W | L | GB"
    divider = "-" * len(header)
    lines = [header, divider]

    for r in rows:
        name = r["team"]
        gb = r["gb"] if r["gb"] not in ("0", "0.0", "") else "-"
        line = f" {r['rank']:<1} | {pad_name(name)} | {r['w']} | {r['l']} | {gb}"
        lines.append(line)

    embed.description = "```\n" + "\n".join(lines) + "\n```"
    embed.set_footer(text=f"Updated {datetime.utcnow().strftime('%b %d, %Y %H:%M')} UTC")
    return embed


# ─────────────────────────────────────────
# Discord bot
# ─────────────────────────────────────────
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@tree.command(name="standings", description="Show current Fantrax league standings")
async def standings_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        embed = build_standings_embed()
        await interaction.followup.send(embed=embed)
        log.info(f"/standings used by {interaction.user} in #{interaction.channel}")
    except PermissionError as e:
        await interaction.followup.send(
            f"🔒  **Authentication error:** {e}\n"
            "Update `FANTRAX_COOKIE` in your `.env` — cookies expire every few weeks.",
            ephemeral=True,
        )
    except Exception as e:
        log.error(f"Error fetching standings: {e}", exc_info=True)
        await interaction.followup.send(
            f"⚠️  Could not fetch standings: `{e}`",
            ephemeral=True,
        )


@tasks.loop(minutes=60)
async def auto_post_standings():
    """Fires every hour; only posts on the configured day + time."""
    now = datetime.utcnow()
    if now.weekday() not in SCHEDULE_DAYS:
        return
    if now.hour != SCHEDULE_HOUR or now.minute > SCHEDULE_MINUTE + 5:
        return

    channel = client.get_channel(AUTO_POST_CHANNEL_ID)
    if channel is None:
        log.warning(f"Auto-post channel {AUTO_POST_CHANNEL_ID} not found.")
        return
    try:
        embed = build_standings_embed()
        await channel.send(embed=embed)
        log.info(f"Auto-posted standings to #{channel.name}")
    except Exception as e:
        log.error(f"Auto-post failed: {e}", exc_info=True)


@client.event
async def on_ready():
    log.info(f"Logged in as {client.user} (ID: {client.user.id})")
    try:
        synced = await tree.sync()
        log.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")

    if AUTO_POST_CHANNEL_ID:
        auto_post_standings.start()
        log.info(
            f"Auto-post enabled → channel {AUTO_POST_CHANNEL_ID}  "
            f"days={SCHEDULE_DAYS}  {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} UTC"
        )
    else:
        log.info("AUTO_POST_CHANNEL_ID not set — auto-posting disabled.")


def main():
    if DISCORD_TOKEN == "YOUR_DISCORD_BOT_TOKEN":
        raise SystemExit("ERROR: Set DISCORD_TOKEN before running.")
    if FANTRAX_LEAGUE_ID == "YOUR_LEAGUE_ID":
        raise SystemExit("ERROR: Set FANTRAX_LEAGUE_ID before running.")
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
