import discord
from discord.ext import commands

import config

DELETE_MESSAGE_SECONDS = 24 * 3600  # löscht beim Bannen alle Nachrichten der letzten 24h


class AutobanChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setautobanchannel")
    @commands.has_permissions(administrator=True)
    async def set_autoban_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        config.set_guild_config(ctx.guild.id, "autoban_channel", channel.id)
        await ctx.send(
            f"✅ {channel.mention} ist jetzt der Autoban-Channel. "
            f"Schreibt jemand dort rein, wird er **sofort permanent gebannt** "
            f"(ohne Möglichkeit auf Entbannung) und seine Nachrichten der letzten 24h werden gelöscht.\n"
            f"Nutze `!setupautoban` um die Hinweis-Nachricht in den Channel zu posten."
        )

    @commands.command(name="setupautoban")
    @commands.has_permissions(administrator=True)
    async def setup_autoban(self, ctx: commands.Context, channel: discord.TextChannel = None):
        guild_config = config.get_guild_config(ctx.guild.id)
        target = channel or ctx.guild.get_channel(guild_config.get("autoban_channel")) or ctx.channel

        if not guild_config.get("autoban_channel"):
            config.set_guild_config(ctx.guild.id, "autoban_channel", target.id)

        count = guild_config.get("autoban_count", 0)

        embed = discord.Embed(
            title="🚨 ⚠️ WICHTIGER HINWEIS ⚠️ 🚨",
            description=(
                "**Dieser Kanal dient lediglich dazu, gehackte Spam-Accounts automatisch zu bannen!**\n\n"
                "Das bedeutet:\n"
                "**Wer hier reinschreibt, wird ohne Möglichkeit auf Entbannung permanent von diesem Discord gebannt!**\n\n"
                "🚫 **ALSO NICHT HIER REINSCHREIBEN!!!** 🚫\n\n"
                "Wer hier dennoch reinschreibt, ist selbst schuld."
            ),
            color=discord.Color.from_str("#E74C3C"),
        )
        embed.add_field(
            name="📊 Statistik",
            value=f"Bereits **{count}** gehackte Discord-Nutzer wurden durch dieses System gebannt.",
            inline=False
        )

        await target.send(embed=embed)

        if target.id != ctx.channel.id:
            await ctx.send(f"✅ Hinweis-Nachricht wurde in {target.mention} gepostet.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        guild_config = config.get_guild_config(message.guild.id)
        autoban_channel_id = guild_config.get("autoban_channel")
        if not autoban_channel_id or message.channel.id != autoban_channel_id:
            return

        member = message.author

        try:
            await message.guild.ban(
                member,
                reason="Autoban-Channel: hat in den Fallen-Channel geschrieben",
                delete_message_seconds=DELETE_MESSAGE_SECONDS,
            )
            banned = True
        except (discord.Forbidden, discord.HTTPException):
            banned = False

        new_count = guild_config.get("autoban_count", 0)
        if banned:
            new_count += 1
            config.set_guild_config(message.guild.id, "autoban_count", new_count)

        embed = discord.Embed(
            title="🔨 Autoban ausgelöst" if banned else "⚠️ Autoban fehlgeschlagen",
            description=(
                f"**{member}** ({member.id}) hat in den Autoban-Channel geschrieben.\n"
                + (
                    f"➡️ Wurde **permanent gebannt**, Nachrichten der letzten 24h wurden gelöscht.\n"
                    f"📊 Bereits **{new_count}** Nutzer wurden durch dieses System gebannt."
                    if banned else
                    "➡️ Konnte NICHT gebannt werden – bitte Bot-Berechtigungen prüfen "
                    "(Rolle muss über der Zielrolle stehen, `Ban Members` benötigt)."
                )
            ),
            color=discord.Color.from_str("#E74C3C") if banned else discord.Color.from_str("#F39C12"),
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
