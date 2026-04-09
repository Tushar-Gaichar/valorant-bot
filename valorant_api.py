import aiohttp
import asyncio
from typing import Optional

BASE = "https://api.henrikdev.xyz/valorant"


class ValorantAPI:
    def __init__(self, api_key: Optional[str] = None):
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = api_key

    async def _get(self, url: str) -> dict:
        print("🌐 Request:", url)

        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:

                    try:
                        data = await resp.json()
                    except Exception:
                        return {
                            "status": resp.status,
                            "errors": [{"message": "Invalid API response"}]
                        }

                    if resp.status == 404:
                        return {"status": 404, "errors": [{"message": "Player not found"}]}

                    if resp.status == 429:
                        return {"status": 429, "errors": [{"message": "Rate limit hit"}]}

                    return data

        except asyncio.TimeoutError:
            return {"status": 408, "errors": [{"message": "Request timed out"}]}

        except Exception as e:
            print("HTTP ERROR:", e)
            return {"status": 500, "errors": [{"message": "Internal API error"}]}

    async def get_account(self, name: str, tag: str) -> dict:
        return await self._get(f"{BASE}/v1/account/{name}/{tag}")

    async def get_mmr(self, region: str, name: str, tag: str) -> dict:
        return await self._get(f"{BASE}/v2/mmr/{region}/{name}/{tag}")

    async def get_matches(self, region: str, name: str, tag: str,
                      mode: str = "competitive", count: int = 5) -> dict:
        return await self._get(f"{BASE}/v3/matches/{region}/{name}/{tag}?mode={mode}&size={count}")

    async def get_lifetime_stats(self, region: str, name: str, tag: str):
        return await self._get(f"{BASE}/v1/lifetime/matches/{region}/{name}/{tag}")

    async def get_mmr_history(self, region: str, name: str, tag: str, count: int = 10) -> dict:
        return await self._get(
            f"{BASE}/v1/mmr-history/{region}/{name}/{tag}?size={count}"
        )

# ── Helper Functions ─────────────────────────────────────────

RANK_EMOJIS = {
    "Iron": "🩶",
    "Bronze": "🥉",
    "Silver": "🥈",
    "Gold": "🥇",
    "Platinum": "💎",
    "Diamond": "💠",
    "Ascendant": "🌿",
    "Immortal": "🔮",
    "Radiant": "✨",
    "Unranked": "❓",
}


def get_rank_emoji(tier_name: str) -> str:
    for name, emoji in RANK_EMOJIS.items():
        if name.lower() in tier_name.lower():
            return emoji
    return "❓"


MAP_NAMES = {
    "/Game/Maps/Ascent/Ascent": "Ascent",
    "/Game/Maps/Bonsai/Bonsai": "Split",
    "/Game/Maps/Canyon/Canyon": "Fracture",
    "/Game/Maps/Duality/Duality": "Bind",
    "/Game/Maps/Foxtrot/Foxtrot": "Breeze",
    "/Game/Maps/Jam/Jam": "Lotus",
    "/Game/Maps/Juliett/Juliett": "Sunset",
    "/Game/Maps/Pitt/Pitt": "Pearl",
    "/Game/Maps/Port/Port": "Icebox",
    "/Game/Maps/Triad/Triad": "Haven",
}


def friendly_map(map_path: str) -> str:
    return MAP_NAMES.get(map_path, map_path.split("/")[-1])


def win_loss_color(won: bool) -> int:
    return 0x43B581 if won else 0xF04747
