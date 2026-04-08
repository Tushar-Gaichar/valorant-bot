import discord
from discord import app_commands
from discord.ext import commands
from valorant_api import ValorantAPI

REGIONS = ["ap", "eu", "na", "latam", "br", "kr"]


def is_admin():
    """Check: user has Manage Server or Administrator permission."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_guild:
            return True
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to use this command.",
            ephemeral=True,
        )
        return False
    return app_commands.check(predicate)


class AdminCog(commands.Cog, name="Admin"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api = ValorantAPI()

    # ── /link ─────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="link",
        description="[Admin] Link a Discord user to their Valorant account."
    )
    @app_commands.describe(
        member="The Discord user to link",
        riot_name="Valorant username (no #tag)",
        riot_tag="Tag line e.g. EUW or 1234",
        region="Server region (default: ap)",
    )
    @app_commands.choices(region=[
        app_commands.Choice(name=r.upper(), value=r) for r in REGIONS
    ])
    @is_admin()
    async def link(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        riot_name: str,
        riot_tag: str,
        region: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        chosen_region = region.value if region else "ap"

        # Validate the account exists
        data = await self.api.get_account(riot_name, riot_tag)
        if data.get("status") != 200:
            err = data.get("errors", [{}])[0].get("message", "Unknown error")
            await interaction.followup.send(
                f"❌ Could not verify **{riot_name}#{riot_tag}** — {err}", ephemeral=True
            )
            return

        acc = data["data"]
        self.bot.db.link(
            guild_id=interaction.guild_id,
            discord_id=member.id,
            riot_name=acc["name"],
            riot_tag=acc["tag"],
            region=chosen_region,
            linked_by=interaction.user.id,
        )

        embed = discord.Embed(
            title="✅ Account linked",
            color=0x43B581,
        )
        embed.add_field(name="Discord", value=member.mention, inline=True)
        embed.add_field(name="Valorant", value=f"**{acc['name']}#{acc['tag']}**", inline=True)
        embed.add_field(name="Region", value=chosen_region.upper(), inline=True)
        if acc.get("card", {}).get("small"):
            embed.set_thumbnail(url=acc["card"]["small"])
        embed.set_footer(text=f"Linked by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed, ephemeral=False)

    # ── /unlink ───────────────────────────────────────────────────────────────

    @app_commands.command(
        name="unlink",
        description="[Admin] Unlink a Discord user from their Valorant account."
    )
    @app_commands.describe(member="The Discord user to unlink")
    @is_admin()
    async def unlink(self, interaction: discord.Interaction, member: discord.Member):
        removed = self.bot.db.unlink(interaction.guild_id, member.id)
        if removed:
            await interaction.response.send_message(
                f"✅ Unlinked **{member.display_name}** from their Valorant account.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"⚠️ **{member.display_name}** has no linked account in this server.",
                ephemeral=True,
            )

    # ── /linked-accounts ──────────────────────────────────────────────────────

    @app_commands.command(
        name="linked-accounts",
        description="[Admin] List all Discord ↔ Valorant links in this server."
    )
    @is_admin()
    async def linked_accounts(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        rows = self.bot.db.list_accounts(interaction.guild_id)

        if not rows:
            await interaction.followup.send(
                "No accounts linked yet. Use `/link` to add one.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🔗 Linked accounts — {interaction.guild.name}",
            color=0x5865F2,
            description=f"{len(rows)} account(s) linked",
        )

        for row in rows[:25]:  # embed field limit
            try:
                member = await interaction.guild.fetch_member(int(row["discord_id"]))
                name = member.display_name
            except Exception:
                name = f"<@{row['discord_id']}>"

            embed.add_field(
                name=name,
                value=f"`{row['riot_name']}#{row['riot_tag']}` · {row['region'].upper()}",
                inline=True,
            )

        if len(rows) > 25:
            embed.set_footer(text=f"Showing first 25 of {len(rows)} accounts")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
