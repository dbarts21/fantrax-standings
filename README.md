# Fantrax Standings Discord Bot

Posts your Fantrax fantasy baseball standings to Discord via a `/standings` slash command and/or a weekly auto-post.

---

## Quick Start

### 1. Create a Discord Application & Bot

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**
2. Name it (e.g. "Fantrax Standings"), then go to **Bot** in the left sidebar
3. Click **Add Bot** → **Reset Token** → copy the token (this is your `DISCORD_TOKEN`)
4. Under **Privileged Gateway Intents**, enable **Message Content Intent** (optional but harmless)
5. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`
6. Copy the generated URL, paste it in your browser, and add the bot to your server

### 2. Get Your Fantrax League ID

Open your Fantrax league in a browser. The URL looks like:

```
https://www.fantrax.com/fantasy/league/XXXXXXXXXXXXXXXXXX/home
```

The `XXXXXXXXXXXXXXXXXX` part is your league ID.

### 3. (Private league only) Get Your Fantrax Session Cookie

If your league is private, you need to authenticate. Run this once:

```bash
pip install selenium webdriver-manager
python get_cookie.py
```

Log in when the Chrome window opens. After ~30 seconds a file called `fantraxloggedin.cookie` is saved. Then run:

```bash
python print_cookie.py
```

Copy the output string into `FANTRAX_COOKIE` in your `.env`.

### 4. Configure `.env`

```bash
cp .env.example .env
# Edit .env with your values
```

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Bot token from Discord Developer Portal |
| `FANTRAX_LEAGUE_ID` | ✅ | League ID from the Fantrax URL |
| `FANTRAX_COOKIE` | Private leagues only | Session cookie string |
| `AUTO_POST_CHANNEL_ID` | For auto-posting | Right-click channel → Copy Channel ID |

**Enable Developer Mode in Discord:** User Settings → Advanced → Developer Mode → On

### 5. Install & Run

```bash
cd fantrax-discord-bot
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

The bot logs into Discord and syncs the `/standings` slash command. Type `/standings` in any channel to test it.

---

## Auto-Post Schedule

By default the bot auto-posts every **Monday at noon UTC** (8am EDT / 5am PDT).

To change the schedule, edit these lines in `bot.py`:

```python
SCHEDULE_DAYS   = [0]   # 0=Mon, 1=Tue, ... 6=Sun. [0,3] = Mon+Thu
SCHEDULE_HOUR   = 12    # UTC hour (noon UTC = 8am EDT)
SCHEDULE_MINUTE = 0
```

Or set via environment variables — see the config section at the top of `bot.py`.

---

## Hosting Options

| Option | Cost | Always On | Difficulty | Best For |
|---|---|---|---|---|
| **Local Mac/Linux** | Free | Only when machine is on | Easy | Testing, occasional use |
| **Raspberry Pi** | ~$35 one-time | Yes | Easy | Home always-on hosting |
| **Railway.app** | Free tier (~500 hrs/mo) | Yes | Easy | Hands-off cloud |
| **Fly.io** | Free tier | Yes | Medium | More control |
| **VPS (DigitalOcean, Vultr)** | ~$4-6/mo | Yes | Medium | Full control |

### Running on Railway (easiest cloud option)

1. Push your repo to GitHub (make sure `.env` is in `.gitignore`)
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variables in the Railway dashboard (Variables tab)
4. Railway auto-detects Python and runs `bot.py`

### Running as a background service on Mac/Linux with `nohup`

```bash
source venv/bin/activate
nohup python bot.py > bot.log 2>&1 &
echo "Bot PID: $!"
```

To stop it: `kill <PID>`

### Running as a systemd service (Linux/Raspberry Pi)

Create `/etc/systemd/system/fantrax-bot.service`:

```ini
[Unit]
Description=Fantrax Standings Discord Bot
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/fantrax-discord-bot
ExecStart=/home/pi/fantrax-discord-bot/venv/bin/python bot.py
Restart=always
EnvironmentFile=/home/pi/fantrax-discord-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable fantrax-bot
sudo systemctl start fantrax-bot
sudo systemctl status fantrax-bot
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `/standings` command doesn't appear | Wait 1 hour for Discord to propagate global commands, or restrict to a single guild for instant sync (see code comments) |
| `standings.ranks` is empty | Your league may be private — set `FANTRAX_COOKIE` |
| `FANTRAX_LEAGUE_ID` not found error | Double-check the ID from the Fantrax URL |
| Auto-post not firing | Make sure `AUTO_POST_CHANNEL_ID` is set and the bot has Send Messages permission in that channel |

---

## Sample Output

```
📊 My Fantasy Baseball League Standings

#   Team                   W   L   T    GB  Streak
────────────────────────────────────────────────────
1   Home Run Heroes        8   2   0     ─      W3
2   Strikeout Kings        7   3   0   1.0      W1
3   Double Play Dandies    6   4   0   2.0      L1
...
```
