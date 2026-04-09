import asyncio
import os
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from valorant_api import ValorantAPI, get_rank_emoji, friendly_map


class StatsCog(commands.Cog, name="Stats"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api = ValorantAPI(api_key=os.getenv("HENRIK_API_KEY"))

    def _resolve_account(self, interaction: discord.Interaction, member: Optional[discord.Member]):
        target = member or interaction.user
        row = self.bot.db.get_account(interaction.guild_id, target.id)
        if row is None:
            return None, None, None, target
        return row["riot_name"], row["riot_tag"], row["region"], target

    # ── /stats ────────────────────────────────────────────────────────────────

    @app_commands.command(name="stats", description="Show Valorant profile & rank for a linked user.")
    @app_commands.describe(member="Discord user (defaults to you)")
    async def stats(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        await interaction.response.defer()
        try:
            name, tag, region, target = self._resolve_account(interaction, member)
            if name is None:
                tip = "Use `/link` to link your account." if target == interaction.user \
                      else f"Ask an admin to `/link` **{target.display_name}**."
                await interaction.followup.send(f"❌ No Valorant account linked for **{target.display_name}**. {tip}")
                return

            acc_data, mmr_data = await asyncio.gather(
                self.api.get_account(name, tag),
                self.api.get_mmr(region, name, tag),
            )

            if acc_data.get("status") != 200:
                err = acc_data.get("errors", [{}])[0].get("message", "unknown error")
                await interaction.followup.send(f"❌ Could not fetch account for `{name}#{tag}` — {err}")
                return

            acc = acc_data["data"]
            embed = discord.Embed(title=f"{acc['name']}#{acc['tag']}", color=0xFF4655)
            embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)

            # Player card thumbnail (will be replaced by rank image if available)
            card_url = acc.get("card", {}).get("small")
            if card_url:
                embed.set_thumbnail(url=card_url)

            embed.add_field(name="Region", value=region.upper(), inline=True)
            embed.add_field(name="Level",  value=f"**{acc.get('account_level', '?')}**", inline=True)
            embed.add_blank_field(inline=True)

            if mmr_data.get("status") == 200:
                mmr    = mmr_data["data"]
                cur    = mmr.get("current_data", {})
                tier   = cur.get("currenttierpatched", "Unranked")
                rr     = cur.get("ranking_in_tier", 0)
                elo    = cur.get("elo", 0)
                change = cur.get("mmr_change_to_last_game")

                rank_img = cur.get("images", {}).get("large") or cur.get("images", {}).get("small")
                if rank_img:
                    embed.set_thumbnail(url=rank_img)

                rr_line = f"**{rr}** RR  ·  {elo} Elo"
                if change is not None:
                    sign = "+" if change >= 0 else ""
                    rr_line += f"  ·  {sign}{change} last game"

                embed.add_field(name="Current rank", value=f"**{tier}**\n{rr_line}", inline=True)

                peak = mmr.get("highest_rank", {})
                if peak.get("patched_tier"):
                    season = peak.get("season") or peak.get("act", "?")
                    embed.add_field(name="Peak rank", value=f"**{peak['patched_tier']}**\nSeason {season}", inline=True)
            else:
                err = mmr_data.get("errors", [{}])[0].get("message", "unavailable")
                embed.add_field(name="Rank", value=f"Unavailable — {err}", inline=True)

            embed.set_footer(text="api.henrikdev.xyz  ·  /link to update")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[/stats ERROR] {e}")
            await interaction.followup.send(f"❌ Something went wrong: `{e}`")

    # ── /rank ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="rank", description="Show current rank and RR for a linked user.")
    @app_commands.describe(member="Discord user (defaults to you)")
    async def rank(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        await interaction.response.defer()
        try:
            name, tag, region, target = self._resolve_account(interaction, member)
            if name is None:
                await interaction.followup.send(f"❌ No Valorant account linked for **{target.display_name}**.")
                return

            data = await self.api.get_mmr(region, name, tag)
            if data.get("status") != 200:
                err = data.get("errors", [{}])[0].get("message", "unknown error")
                await interaction.followup.send(f"❌ Could not fetch rank for `{name}#{tag}` — {err}")
                return

            mmr    = data["data"]
            cur    = mmr.get("current_data", {})
            tier   = cur.get("currenttierpatched", "Unranked")
            rr     = cur.get("ranking_in_tier", 0)
            elo    = cur.get("elo", 0)
            change = cur.get("mmr_change_to_last_game")
            emoji  = get_rank_emoji(tier)

            rank_img = cur.get("images", {}).get("large") or cur.get("images", {}).get("small")

            embed = discord.Embed(
                title=f"{emoji} {tier}",
                description=f"`{name}#{tag}` — {region.upper()}",
                color=0xFF4655,
            )
            embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
            if rank_img:
                embed.set_thumbnail(url=rank_img)

            embed.add_field(name="RR",  value=f"**{rr}** / 100", inline=True)
            embed.add_field(name="Elo", value=f"**{elo}**",       inline=True)

            if change is not None:
                sign = "+" if change >= 0 else ""
                embed.add_field(name="Last game", value=f"{sign}{change} RR", inline=True)

            peak = mmr.get("highest_rank", {})
            if peak.get("patched_tier"):
                season  = peak.get("season") or peak.get("act", "?")
                p_emoji = get_rank_emoji(peak["patched_tier"])
                embed.set_footer(text=f"Peak: {p_emoji} {peak['patched_tier']} · Season {season}")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[/rank ERROR] {e}")
            await interaction.followup.send(f"❌ Something went wrong: `{e}`")

    # ── /match ────────────────────────────────────────────────────────────────

    @app_commands.command(name="match", description="Show the last 5 matches for a linked user.")
    @app_commands.describe(member="Discord user (defaults to you)", mode="Game mode (default: competitive)")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Competitive", value="competitive"),
        app_commands.Choice(name="Unrated",     value="unrated"),
        app_commands.Choice(name="Spike Rush",  value="spikerush"),
        app_commands.Choice(name="Deathmatch",  value="deathmatch"),
    ])
    async def match(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
        mode: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer()
        try:
            name, tag, region, target = self._resolve_account(interaction, member)
            if name is None:
                await interaction.followup.send(f"❌ No Valorant account linked for **{target.display_name}**.")
                return

            chosen_mode = mode.value if mode else "competitive"
            data = await self.api.get_matches(region, name, tag, mode=chosen_mode, count=5)

            if data.get("status") != 200:
                err = data.get("errors", [{}])[0].get("message", "unknown error")
                await interaction.followup.send(f"❌ No {chosen_mode} matches found for `{name}#{tag}` — {err}")
                return

            matches = data.get("data", [])
            if not matches:
                await interaction.followup.send(f"No recent {chosen_mode} matches found for `{name}#{tag}`.")
                return

            embed = discord.Embed(
                title=f"Last {len(matches)} {chosen_mode.capitalize()} matches",
                description=f"`{name}#{tag}` · {region.upper()}",
                color=0xFF4655,
            )
            embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)

            wins = total_k = total_d = total_a = 0

            for m in matches:
                meta    = m.get("metadata", {})
                players = m.get("players", {}).get("all_players", [])

                me = next(
                    (p for p in players
                     if p.get("name", "").lower() == name.lower()
                     and p.get("tag",  "").lower() == tag.lower()),
                    None,
                )
                if not me:
                    continue

                stats  = me.get("stats", {})
                k      = stats.get("kills",   0)
                d      = stats.get("deaths",  1)
                a      = stats.get("assists", 0)
                rounds = meta.get("rounds_played", 1)
                acs    = stats.get("score", 0) // max(rounds, 1)
                total_k += k; total_d += d; total_a += a

                team_key = me.get("team", "").lower()
                won = m.get("teams", {}).get(team_key, {}).get("has_won", False)
                if won:
                    wins += 1

                agent    = me.get("character", "Unknown")
                map_raw  = meta.get("map", "?")
                map_name = map_raw.get("name", "?") if isinstance(map_raw, dict) else friendly_map(map_raw)
                result   = "✅ Win" if won else "❌ Loss"

                embed.add_field(
                    name=f"{result} · {map_name}",
                    value=f"**{agent}** · {k}/{d}/{a} KDA · ACS **{acs}**",
                    inline=False,
                )

            n  = len(matches)
            kd = round(total_k / max(total_d, 1), 2)
            embed.set_footer(text=f"W/L: {wins}/{n - wins} · Avg K/D: {kd} over {n} games")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[/match ERROR] {e}")
            await interaction.followup.send(f"❌ Something went wrong: `{e}`")

    # ── /mmr-history ──────────────────────────────────────────────────────────

    @app_commands.command(name="mmr-history", description="Show RR gain/loss over recent competitive matches.")
    @app_commands.describe(
        member="Discord user (defaults to you)",
        count="Number of games to show (1–15, default 10)",
    )
    async def mmr_history(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
        count: int = 10,
    ):
        await interaction.response.defer()
        try:
            count = max(1, min(count, 15))

            name, tag, region, target = self._resolve_account(interaction, member)
            if name is None:
                tip = "Use `/link` to link your account." if target == interaction.user \
                      else f"Ask an admin to `/link` **{target.display_name}**."
                await interaction.followup.send(f"❌ No Valorant account linked for **{target.display_name}**. {tip}")
                return

            data = await self.api.get_mmr_history(region, name, tag)

            if data.get("status") != 200:
                err = data.get("errors", [{}])[0].get("message", "unknown error")
                await interaction.followup.send(f"❌ Could not fetch MMR history for `{name}#{tag}` — {err}")
                return

            history = data.get("data", [])[:count]
            if not history:
                await interaction.followup.send(f"No MMR history found for `{name}#{tag}`.")
                return

            total_rr = sum(e.get("mmr_change_to_last_game", 0) for e in history)
            wins     = sum(1 for e in history if e.get("mmr_change_to_last_game", 0) > 0)
            losses   = sum(1 for e in history if e.get("mmr_change_to_last_game", 0) < 0)

            latest      = history[0]
            rank_name   = latest.get("currenttier_patched", "Unranked")
            rank_img    = latest.get("images", {}).get("large") or latest.get("images", {}).get("small")
            current_rr  = latest.get("ranking_in_tier", 0)
            current_elo = latest.get("elo", 0)

            color = 0x43B581 if total_rr >= 0 else 0xF04747
            sign  = "+" if total_rr >= 0 else ""

            embed = discord.Embed(
                title=f"📈 MMR History — last {len(history)} games",
                description=(
                    f"`{name}#{tag}` · {region.upper()}\n"
                    f"**{rank_name}** · {current_rr} RR · {current_elo} Elo\n"
                    f"Net: **{sign}{total_rr} RR**  ·  {wins}W / {losses}L"
                ),
                color=color,
            )
            embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
            if rank_img:
                embed.set_thumbnail(url=rank_img)

            lines = []
            for entry in history:
                change   = entry.get("mmr_change_to_last_game", 0)
                rr_after = entry.get("ranking_in_tier", 0)
                tier     = entry.get("currenttier_patched", "?")
                map_name = entry.get("map", {}).get("name", "?")
                date_str = entry.get("date", "")

                try:
                    dt       = datetime.strptime(date_str, "%A, %B %d, %Y %I:%M %p")
                    date_fmt = dt.strftime("%b %d")
                except Exception:
                    date_fmt = date_str[:6] if date_str else "?"

                arrow = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
                csign = "+" if change >= 0 else ""
                lines.append(
                    f"{arrow} `{csign}{change:>3} RR` → **{rr_after} RR** · {tier} · {map_name} · {date_fmt}"
                )

            embed.add_field(name="Games (newest → oldest)", value="\n".join(lines), inline=False)
            embed.set_footer(text="🟢 gain  🔴 loss  ⚪ no change")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[/mmr-history ERROR] {e}")
            await interaction.followup.send(f"❌ Something went wrong: `{e}`")

    # ── /leaderboard ──────────────────────────────────────────────────────────

    @app_commands.command(name="leaderboard", description="Show ranked leaderboard for all linked server members.")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            rows = self.bot.db.list_accounts(interaction.guild_id)
            if not rows:
                await interaction.followup.send("No accounts linked yet. Admins can use `/link` to add some.")
                return

            results = await asyncio.gather(*[
                self.api.get_mmr(r["region"], r["riot_name"], r["riot_tag"]) for r in rows
            ])

            players = []
            for row, mmr_data in zip(rows, results):
                if mmr_data.get("status") != 200:
                    continue
                cur = mmr_data["data"].get("current_data", {})
                players.append({
                    "discord_id": row["discord_id"],
                    "riot":       f"{row['riot_name']}#{row['riot_tag']}",
                    "tier":       cur.get("currenttierpatched", "Unranked"),
                    "rr":         cur.get("ranking_in_tier", 0),
                    "elo":        cur.get("elo", 0),
                })

            players.sort(key=lambda x: x["elo"], reverse=True)

            embed = discord.Embed(
                title=f"🏆 {interaction.guild.name} — Valorant Leaderboard",
                color=0xFFD700,
            )

            medals = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(players[:10]):
                prefix = medals[i] if i < 3 else f"**#{i+1}**"
                emoji  = get_rank_emoji(p["tier"])
                try:
                    m       = await interaction.guild.fetch_member(int(p["discord_id"]))
                    display = m.display_name
                except Exception:
                    display = f"<@{p['discord_id']}>"

                embed.add_field(
                    name=f"{prefix} {display}",
                    value=f"{emoji} {p['tier']} · {p['rr']} RR · `{p['riot']}`",
                    inline=False,
                )

            embed.set_footer(text=f"Top {min(len(players), 10)} of {len(players)} linked players")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[/leaderboard ERROR] {e}")
            await interaction.followup.send(f"❌ Something went wrong: `{e}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
