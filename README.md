# 🎯 Valorant Discord Bot

A free Discord bot that pulls Valorant stats and lets server admins link Discord users to their Valorant accounts.

---

## ✨ Features

| Command | Who can use | Description |
|---|---|---|
| `/link @user Name Tag region` | Admin only | Link a Discord user to a Valorant account |
| `/unlink @user` | Admin only | Remove a linked account |
| `/linked-accounts` | Admin only | List all linked accounts in the server |
| `/stats [@user]` | Anyone | Full profile — level, rank, peak rank |
| `/rank [@user]` | Anyone | Current rank, RR, last game RR change |
| `/match [@user] [mode]` | Anyone | Last 5 matches with K/D/A, ACS, map |
| `/leaderboard` | Anyone | Server rank leaderboard sorted by Elo |

---

## 🚀 Setup (step by step)

### 1. Create the Discord bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → give it a name
3. Go to **Bot** → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - **Server Members Intent**
   - **Message Content Intent**
5. Copy the **Token** — you'll need it shortly
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot` + `applications.commands`
   - Bot permissions: `Send Messages`, `Embed Links`, `Use Slash Commands`
7. Copy the generated URL and open it to invite the bot to your server

### 2. Clone and install

```bash
git clone <your-repo>
cd valorant-bot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env and paste your Discord token
```

Your `.env` should look like:
```
DISCORD_TOKEN=MTAxxxxxxxxxxxxxxxxxx.xxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
HENRIK_API_KEY=          # optional, leave blank
```

### 4. Run

```bash
python bot.py
```

You should see:
```
✅ Logged in as YourBot#1234 (123456789)
📡 Synced 7 slash command(s)
```

> **Note:** Slash commands may take up to 1 hour to appear globally. To speed this up during development, sync to a specific guild — see bot.py comments.

---

## 🔧 Admin usage

Admins (anyone with **Manage Server** permission) can link accounts:

```
/link @Tushar TusharGG 1337 ap
```

This validates the account exists on the Henrik API, then saves the mapping to the local SQLite database.

To update a link, just run `/link` again — it will overwrite the old entry.

---

## 🌍 Regions

| Code | Region |
|---|---|
| `ap` | Asia-Pacific (India, SEA, OCE) |
| `eu` | Europe |
| `na` | North America |
| `latam` | Latin America |
| `br` | Brazil |
| `kr` | Korea |

---

## 📦 Project structure

```
valorant-bot/
├── bot.py              # Entry point, bot setup
├── database.py         # SQLite helpers
├── valorant_api.py     # Henrik Dev API wrapper
├── cogs/
│   ├── admin.py        # /link /unlink /linked-accounts
│   └── stats.py        # /stats /rank /match /leaderboard
├── data/
│   └── bot.db          # Auto-created SQLite database
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🆓 Why it's free

- **discord.py** — open source, free
- **Henrik Dev API** — unofficial Valorant API, no Riot approval needed, free tier available at [docs.henrikdev.gg](https://docs.henrikdev.gg/)
- **SQLite** — built into Python, no external database
- **Hosting** — run on any machine, or deploy free to [Railway](https://railway.app), [Render](https://render.com), or [fly.io](https://fly.io)

---

## ☁️ Deploying to Render (free, 24/7)

The bot includes a built-in health-check HTTP server (`keep_alive.py`) that lets Render know it's alive, and lets UptimeRobot ping it to prevent the free tier from sleeping.

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "initial commit"
# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/valorant-bot.git
git push -u origin main
```

> Make sure `.env` and `data/` are in `.gitignore` — they are by default.

---

### Step 2 — Create the Render service

1. Go to [render.com](https://render.com) and sign up (free)
2. Click **New → Web Service**
3. Connect your GitHub account and select the `valorant-bot` repo
4. Render will auto-detect `render.yaml` — confirm the settings:
   - **Runtime**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `python bot.py`
   - **Region**: Singapore (best for India/AP)
   - **Plan**: Free
5. Click **Create Web Service**

---

### Step 3 — Add environment variables

In the Render dashboard → your service → **Environment**:

| Key | Value |
|---|---|
| `DISCORD_TOKEN` | Your bot token from Discord Developer Portal |
| `HENRIK_API_KEY` | *(optional)* Your Henrik Dev API key |

Click **Save Changes** — Render will redeploy automatically.

---

### Step 4 — Note your Render URL

After the first deploy, Render gives you a URL like:
```
https://valorant-discord-bot.onrender.com
```

Your health endpoint will be live at:
```
https://valorant-discord-bot.onrender.com/health
```

---

### Step 5 — Set up UptimeRobot to keep it awake

Render free tier sleeps after **15 minutes** of no HTTP traffic. UptimeRobot pings it every 5 minutes for free.

1. Go to [uptimerobot.com](https://uptimerobot.com) and sign up (free)
2. Click **Add New Monitor**
3. Fill in:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: `Valorant Bot`
   - **URL**: `https://valorant-discord-bot.onrender.com/health`
   - **Monitoring Interval**: 5 minutes
4. Click **Create Monitor**

That's it — UptimeRobot pings `/health` every 5 min, Render never sleeps, your bot stays online 24/7 for free.

---

### What `/health` returns

```json
{
  "status": "ok",
  "uptime_seconds": 3600,
  "bot_ready": true,
  "bot_user": "YourBot#1234",
  "guilds": 3
}
```

You can open this URL in your browser anytime to confirm the bot is alive.
