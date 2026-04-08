"""
keep_alive.py
─────────────
Starts a tiny aiohttp web server on PORT (set by Render automatically).
Exposes two routes:
  GET /         → plain "alive" for browser checks
  GET /health   → JSON status used by UptimeRobot
"""

import asyncio
import os
import time
from aiohttp import web

START_TIME = time.time()


async def index(request: web.Request) -> web.Response:
    return web.Response(text="✅ Valorant bot is alive.")


async def health(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    uptime = int(time.time() - START_TIME)
    return web.json_response({
        "status":  "ok",
        "uptime_seconds": uptime,
        "bot_ready": bot.is_ready(),
        "bot_user":  str(bot.user) if bot.user else None,
        "guilds":    len(bot.guilds) if bot.is_ready() else 0,
    })


def build_app(bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/",       index)
    app.router.add_get("/health", health)
    return app


async def start_web_server(bot) -> None:
    port = int(os.environ.get("PORT", 8080))
    app  = build_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Health server running on port {port}")
