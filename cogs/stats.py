import discord
from discord import app_commands
from discord.ext import commands
from valorant_api import ValorantAPI, get_rank_emoji, friendly_map, win_loss_color
from typing import Optional


class StatsCog(commands.Cog, name="Stats"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api = ValorantAPI()

    def _resolve_account(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member],
    ):
        """
        Return (riot_name, riot_tag, region) for the given member,
        falling back to the command user. Returns None if not linked.
        """
        target = member or interaction.user
        row = self.bot.db.get_account(interaction.guild_id, target.id)
        if row is None:
            return None, None, None, target
        return row["riot_name"], row["riot_tag"], row["region"], target

    # ── /stats ────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="stats",
        description="Show Valorant profile & rank for a linked user."
    )
    @app_commands.describe(member="Discord user (defaults to you)")
    async def stats(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        await interaction.response.defer()

        name, tag, region, target = self._resolve_account(interaction, member)
        if name is None:
            tip = "Use `/link` to link your account." if target == interaction.user \
                  else f"Ask an admin to `/link` **{target.display_name}**."
            await interaction.followup.send(
                f"❌ No Valorant account linked for **{target.display_name}**. {tip}"
            )
            return

        # Fetch account + MMR in parallel
        import asyncio
        account_task = asyncio.create_task(self.api.get_account(name, tag))
        mmr_task = asyncio.create_task(self.api.get_mmr(region, name, tag))
        acc_data, mmr_data = await asyncio.gather(account_task, mmr_task)

        if acc_data.get("status") != 200:
            await interaction.followup.send(
                f"❌ Could not fetch account data for `{name}#{tag}`."
            )
            return

        acc = acc_data["data"]
        embed = discord.Embed(
            title=f"{acc['name']}#{acc['tag']}",
            color=0x5865F2,
        )
        embed.set_author(
            name=target.display_name,
            icon_url=target.display_avatar.url,
        )

        if acc.get("card", {}).get("small"):
            embed.set_thumbnail(url=acc["card"]["small"])

        embed.add_field(name="Region", value=region.upper(), inline=True)
        embed.add_field(name="Account level", value=f"**{acc.get('account_level', '?')}**", inline=True)
        embed.add_blank_field(inline=True)

        # Rank info
        if mmr_data.get("status") == 200:
            mmr = mmr_data["data"]
            current = mmr.get("current_data", {})
            tier_name = current.get("currenttierpatched", "Unranked")
            rr = current.get("ranking_in_tier", 0)
            elo = current.get("elo", 0)
            emoji = get_rank_emoji(tier_name)

            embed.add_field(
                name="Current rank",
                value=f"{emoji} **{tier_name}**\n{rr} RR  ·  {elo} Elo",
                inline=True,
            )

            # Peak rank
            peak = mmr.get("highest_rank", {})
            if peak.get("patched_tier"):
                p_emoji = get_rank_emoji(peak["patched_tier"])
                embed.add_field(
                    name="Peak rank",
                    value=f"{p_emoji} {peak['patched_tier']} (Act {peak.get('act', '?')})",
                    inline=True,
                )
        else:
            embed.add_field(name="Rank", value="Unranked / unavailable", inline=True)

        embed.set_footer(text="Powered by HenrikDev API · /link to update")
        await interaction.followup.send(embed=embed)

    # ── /rank ─────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="rank",
        description="Show current rank and RR for a linked user."
    )
    @app_commands.describe(member="Discord user (defaults to you)")
    async def rank(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        await interaction.response.defer()

        name, tag, region, target = self._resolve_account(interaction, member)
        if name is None:
            await interaction.followup.send(
                f"❌ No Valorant account linked for **{target.display_name}**."
            )
            return

        data = await self.api.get_mmr(region, name, tag)
        if data.get("status") != 200:
            await interaction.followup.send(
                f"❌ Could not fetch rank data for `{name}#{tag}`."
            )
            return

        mmr = data["data"]
        current = mmr.get("current_data", {})
        tier_name = current.get("currenttierpatched", "Unranked")
        rr = current.get("ranking_in_tier", 0)
        elo = current.get("elo", 0)
        emoji = get_rank_emoji(tier_name)

        embed = discord.Embed(
            title=f"{emoji} {tier_name}",
            description=f"`{name}#{tag}` — {region.upper()}",
            color=0x43B581,
        )
        embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
        embed.add_field(name="RR", value=f"**{rr}** / 100", inline=True)
        embed.add_field(name="Elo", value=f"**{elo}**", inline=True)

        # RR change last 5 games
        games = mmr.get("by_season", {})
        if current.get("mmr_change_to_last_game") is not None:
            change = current["mmr_change_to_last_game"]
            sign = "+" if change >= 0 else ""
            embed.add_field(
                name="Last game RR",
                value=f"{sign}{change} RR",
                inline=True,
            )

        peak = mmr.get("highest_rank", {})
        if peak.get("patched_tier"):
            p_emoji = get_rank_emoji(peak["patched_tier"])
            embed.set_footer(
                text=f"Peak: {p_emoji} {peak['patched_tier']} · Act {peak.get('act', '?')}"
            )

        await interaction.followup.send(embed=embed)

    # ── /match ────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="match",
        description="Show the last 5 competitive matches for a linked user."
    )
    @app_commands.describe(
        member="Discord user (defaults to you)",
        mode="Game mode (default: competitive)",
    )
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

        name, tag, region, target = self._resolve_account(interaction, member)
        if name is None:
            await interaction.followup.send(
                f"❌ No Valorant account linked for **{target.display_name}**."
            )
            return

        chosen_mode = mode.value if mode else "competitive"
        data = await self.api.get_matches(region, name, tag, mode=chosen_mode, count=5)

        if data.get("status") != 200:
            await interaction.followup.send(
                f"❌ No {chosen_mode} matches found for `{name}#{tag}`."
            )
            return

        matches = data.get("data", [])
        if not matches:
            await interaction.followup.send(
                f"No recent {chosen_mode} matches found for `{name}#{tag}`."
            )
            return

        embed = discord.Embed(
            title=f"Last {len(matches)} {chosen_mode.capitalize()} matches",
            description=f"`{name}#{tag}` · {region.upper()}",
            color=0x5865F2,
        )
        embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)

        wins = 0
        total_kda_k = 0
        total_kda_d = 0
        total_kda_a = 0

        for match in matches:
            meta = match.get("metadata", {})
            players = match.get("players", {}).get("all_players", [])

            # Find our player in the match
            me = next(
                (p for p in players
                 if p.get("name", "").lower() == name.lower()
                 and p.get("tag", "").lower() == tag.lower()),
                None,
            )
            if not me:
                continue

            stats = me.get("stats", {})
            k = stats.get("kills", 0)
            d = stats.get("deaths", 1)
            a = stats.get("assists", 0)
            acs = stats.get("score", 0) // max(meta.get("rounds_played", 1), 1)

            total_kda_k += k
            total_kda_d += d
            total_kda_a += a

            won = me.get("team", "").lower() == match.get("teams", {}).get(
                me.get("team", "").lower(), {}
            ) and match.get("teams", {}).get(me.get("team", "").lower(), {}).get("has_won", False)

            # Use teams data for win detection
            team_key = me.get("team", "").lower()
            won = match.get("teams", {}).get(team_key, {}).get("has_won", False)
            if won:
                wins += 1

            agent = me.get("character", "Unknown")
            map_name = friendly_map(meta.get("map", {}).get("id", "?") if isinstance(meta.get("map"), dict) else meta.get("map", "?"))
            rounds = meta.get("rounds_played", "?")

            result = "✅ Win" if won else "❌ Loss"
            embed.add_field(
                name=f"{result} · {map_name}",
                value=(
                    f"**{agent}** · {k}/{d}/{a} KDA\n"
                    f"ACS: **{acs}** · {rounds} rounds"
                ),
                inline=False,
            )

        # Summary
        n = len(matches)
        kd = round(total_kda_k / max(total_kda_d, 1), 2)
        embed.set_footer(
            text=f"W/L: {wins}/{n - wins} · Avg K/D: {kd} over {n} games"
        )

        await interaction.followup.send(embed=embed)

    # ── /leaderboard ──────────────────────────────────────────────────────────

    @app_commands.command(
        name="leaderboard",
        description="Show ranked leaderboard for all linked server members."
    )
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()

        rows = self.bot.db.list_accounts(interaction.guild_id)
        if not rows:
            await interaction.followup.send("No accounts linked yet. Admins can use `/link` to add some.")
            return

        import asyncio
        tasks = [
            self.api.get_mmr(row["region"], row["riot_name"], row["riot_tag"])
            for row in rows
        ]
        results = await asyncio.gather(*tasks)

        players = []
        for row, mmr_data in zip(rows, results):
            if mmr_data.get("status") != 200:
                continue
            current = mmr_data["data"].get("current_data", {})
            elo = current.get("elo", 0)
            tier = current.get("currenttierpatched", "Unranked")
            rr = current.get("ranking_in_tier", 0)
            players.append({
                "discord_id": row["discord_id"],
                "riot": f"{row['riot_name']}#{row['riot_tag']}",
                "tier": tier,
                "rr": rr,
                "elo": elo,
            })

        players.sort(key=lambda x: x["elo"], reverse=True)

        embed = discord.Embed(
            title=f"🏆 {interaction.guild.name} — Valorant Leaderboard",
            color=0xFFD700,
        )

        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(players[:10]):
            prefix = medals[i] if i < 3 else f"**#{i+1}**"
            emoji = get_rank_emoji(p["tier"])
            try:
                member = await interaction.guild.fetch_member(int(p["discord_id"]))
                display = member.display_name
            except Exception:
                display = f"<@{p['discord_id']}>"

            embed.add_field(
                name=f"{prefix} {display}",
                value=f"{emoji} {p['tier']} · {p['rr']} RR · `{p['riot']}`",
                inline=False,
            )

        embed.set_footer(text=f"Showing top {min(len(players), 10)} of {len(players)} linked players")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
