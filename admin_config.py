import discord
from discord.ext import commands

import config


class AdminConfig(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="botconfig")
    @commands.has_permissions(administrator=True)
    async def show_bot_config(self, ctx: commands.Context):
        gc = config.get_guild_config(ctx.guild.id)

        def ch(cid):
            channel = ctx.guild.get_channel(cid) if cid else None
            return channel.mention if channel else "❌ nicht gesetzt"

        def rl(rid):
            role = ctx.guild.get_role(rid) if rid else None
            return role.mention if role else "❌ nicht gesetzt"

        embed = discord.Embed(title="⚙️ TYTAN Bot – Konfiguration", color=discord.Color.from_str("#5865F2"))
        embed.add_field(name="Verify-Channel", value=ch(gc.get("verify_channel")), inline=True)
        embed.add_field(name="Verify-Rolle", value=rl(gc.get("verify_role")), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Twitch-Channel", value=ch(gc.get("twitch_channel")), inline=True)
        embed.add_field(name="Twitch-User", value=f"`{gc.get('twitch_username')}`", inline=True)
        embed.add_field(name="Stream-Rolle", value=rl(gc.get("twitch_role")), inline=True)
        embed.add_field(name="Giveaway-Channel", value=ch(gc.get("giveaway_channel")), inline=True)
        embed.add_field(name="Giveaway-Rolle", value=rl(gc.get("giveaway_role")), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Autoban-Channel", value=ch(gc.get("autoban_channel")), inline=True)
        embed.add_field(name="Automod-Log-Channel", value=ch(gc.get("automod_log_channel")), inline=True)
        embed.add_field(name="Verbotene Wörter", value=str(len(gc.get("badwords", []))), inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="commands")
    @commands.has_permissions(administrator=True)
    async def list_commands(self, ctx: commands.Context):
        embed = discord.Embed(
            title="📋 Alle Admin-Commands",
            color=discord.Color.from_str("#5865F2"),
            description="Alle Commands benötigen Administrator-Rechte."
        )
        embed.add_field(
            name="✅ Verify",
            value="`!setverifyrole @Rolle`\n`!setupverify [#channel]`",
            inline=False
        )
        embed.add_field(
            name="🔔 Reaction Roles",
            value="`!setupreactionroles [#channel]`",
            inline=False
        )
        embed.add_field(
            name="🟣 Twitch",
            value="`!settwitchchannel #channel`\n`!settwitchuser <name>`\n`!setstreamrole @Rolle`",
            inline=False
        )
        embed.add_field(
            name="🎉 Giveaway",
            value=(
                "`!giveaway start <dauer> <gewinner> <preis>`\n"
                "`!giveaway end <message_id>`\n"
                "`!giveaway reroll <message_id>`\n"
                "`!giveaway list`\n"
                "`!setgiveawaychannel #channel`\n"
                "`!setgiveawayrole @Rolle`"
            ),
            inline=False
        )
        embed.add_field(
            name="🛡️ Automod",
            value=(
                "`!setautomodlogchannel #channel`\n"
                "`!addbadword <wort>` / `!removebadword <wort>`\n"
                "`!addwhitelist <domain>` / `!removewhitelist <domain>`\n"
                "`!automodstatus`\n"
                "`!resetviolations @user`"
            ),
            inline=False
        )
        embed.add_field(
            name="🚫 Autoban-Channel",
            value="`!setautobanchannel #channel`",
            inline=False
        )
        embed.add_field(
            name="⚙️ Übersicht",
            value="`!botconfig` – zeigt die aktuelle Konfiguration",
            inline=False
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminConfig(bot))
