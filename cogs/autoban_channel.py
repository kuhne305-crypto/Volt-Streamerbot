from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

import config


class AutobanChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setautobanchannel")
    @commands.has_permissions(administrator=True)
    async def set_autoban_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        config.set_guild_config(ctx.guild.id, "autoban_channel", channel.id)
        await ctx.send(
            f"✅ {channel.mention} ist jetzt der Autoban-Channel. "
            f"Schreibt jemand dort rein, werden alle seine Nachrichten der letzten 24h serverweit gelöscht "
            f"und eine Warnung wird gepostet."
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        guild_config = config.get_guild_config(message.guild.id)
        autoban_channel_id = guild_config.get("autoban_channel")
        if not autoban_channel_id or message.channel.id != autoban_channel_id:
            return

        member = message.author
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        deleted_total = 0

        for channel in message.guild.text_channels:
            perms = channel.permissions_for(message.guild.me)
            if not (perms.read_message_history and perms.manage_messages):
                continue
            try:
                deleted = await channel.purge(
                    limit=500,
                    check=lambda m, uid=member.id: m.author.id == uid,
                    after=cutoff,
                    bulk=True,
                )
                deleted_total += len(deleted)
            except (discord.Forbidden, discord.HTTPException):
                continue

        embed = discord.Embed(
            title="⚠️ Autoban-Channel ausgelöst",
            description=(
                f"{member.mention} hat in den Autoban-Channel geschrieben.\n"
                f"**{deleted_total}** Nachrichten der letzten 24h wurden serverweit gelöscht."
            ),
            color=discord.Color.from_str("#E74C3C"),
        )
        embed.timestamp = discord.utils.utcnow()

        log_channel_id = guild_config.get("automod_log_channel")
        log_channel = message.guild.get_channel(log_channel_id) if log_channel_id else message.channel

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AutobanChannel(bot))
