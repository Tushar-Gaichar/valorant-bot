import discord
import os
from discord import app_commands
from discord.ext import commands
from valorant_api import ValorantAPI

REGIONS = ["ap", "eu", "na", "latam", "br", "kr"]


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_guild:
            return True

        await interaction.response.send_message(
            "❌ You need **Manage Server** permission.",
            ephemeral=True
        )
        return False

    return app_commands.check(predicate)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api = ValorantAPI(api_key=os.getenv("HENRIK_API_KEY"))

    # ── /link ─────────────────────────────────────────

    @app_commands.command(
        name="link",
        description="Link a Discord user to Valorant account"
    )
    @app_commands.describe(
        member="Discord user",
        riot_name="Valorant username",
        riot_tag="Tag (e.g. 1234)",
        region="Server region"
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

        print(f"➡️ /link called: {riot_name}#{riot_tag}")

        # API CALL
        try:
            data = await self.api.get_account(riot_name, riot_tag)
            print("API response:", data)
        except Exception as e:
            print("API ERROR:", e)
            await interaction.followup.send(
                "❌ Failed to contact Valorant API.",
                ephemeral=True
            )
            return

        if data.get("status") != 200:
            err = data.get("errors", [{}])[0].get("message", "Unknown error")
            await interaction.followup.send(
                f"❌ Could not verify **{riot_name}#{riot_tag}** — {err}",
                ephemeral=True
            )
            return

        acc = data["data"]

        # DATABASE
        try:
            self.bot.db.link(
                guild_id=interaction.guild_id,
                discord_id=member.id,
                riot_name=acc["name"],
                riot_tag=acc["tag"],
                region=chosen_region,
                linked_by=interaction.user.id,
            )
        except Exception as e:
            print("DB ERROR:", e)
            await interaction.followup.send(
                "❌ Database error.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="✅ Account linked",
            color=0x43B581
        )
        embed.add_field(name="Discord", value=member.mention)
        embed.add_field(name="Valorant", value=f"{acc['name']}#{acc['tag']}")
        embed.add_field(name="Region", value=chosen_region.upper())

        await interaction.followup.send(embed=embed)

    # ── /unlink ──────────────────────────────────────

    @app_commands.command(name="unlink", description="Unlink user")
    @is_admin()
    async def unlink(self, interaction: discord.Interaction, member: discord.Member):
        try:
            removed = self.bot.db.unlink(interaction.guild_id, member.id)
        except Exception as e:
            print("DB ERROR:", e)
            await interaction.response.send_message(
                "❌ Database error.",
                ephemeral=True
            )
            return

        if removed:
            await interaction.response.send_message(
                f"✅ Unlinked {member.display_name}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "⚠️ No linked account found.",
                ephemeral=True
            )

    # ── /linked-accounts ─────────────────────────────

    @app_commands.command(name="linked-accounts", description="List links")
    @is_admin()
    async def linked_accounts(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            rows = self.bot.db.list_accounts(interaction.guild_id)
        except Exception as e:
            print("DB ERROR:", e)
            await interaction.followup.send("❌ Database error.", ephemeral=True)
            return

        if not rows:
            await interaction.followup.send("No accounts linked.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔗 Linked Accounts",
            description=f"{len(rows)} accounts",
            color=0x5865F2
        )

        for row in rows[:25]:
            embed.add_field(
                name=f"<@{row['discord_id']}>",
                value=f"{row['riot_name']}#{row['riot_tag']} ({row['region']})",
                inline=True
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))