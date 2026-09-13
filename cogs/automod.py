import json
import os
import re
import time
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord.ext import commands

import config

VIOLATIONS_PATH = os.path.join(config.DATA_DIR, "automod_violations.json")

BASE_TIMEOUT_SECONDS = 10
ESCALATION_FACTOR = 1.2  # +20% je Verstoß
MAX_TIMEOUT_SECONDS = 28 * 24 * 3600  # Discord-Limit: 28 Tage

INVITE_RE = re.compile(r"(discord\.gg/|discord(?:app)?\.com/invite/)([a-zA-Z0-9-]+)", re.IGNORECASE)
URL_RE = re.compile(r"https?://([a-zA-Z0-9.-]+)", re.IGNORECASE)

SPAM_WINDOW_SECONDS = 5
SPAM_MESSAGE_THRESHOLD = 5

CAPS_MIN_LENGTH = 10
CAPS_RATIO_THRESHOLD = 0.7

MASS_MENTION_THRESHOLD = 5


def _load_violations():
    if not os.path.exists(VIOLATIONS_PATH):
        return {}
    try:
        with open(VIOLATIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_violations(data):
    with open(VIOLATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # message history pro user für Spam-Erkennung: {user_id: deque[timestamps]}
        self._message_history = defaultdict(lambda: deque(maxlen=10))

    def _get_violation_count(self, guild_id: int, user_id: int) -> int:
        data = _load_violations()
        return data.get(str(guild_id), {}).get(str(user_id), 0)

    def _increment_violation(self, guild_id: int, user_id: int) -> int:
        data = _load_violations()
        gid, uid = str(guild_id), str(user_id)
        data.setdefault(gid, {})
        data[gid][uid] = data[gid].get(uid, 0) + 1
        _save_violations(data)
        return data[gid][uid]

    def _calc_timeout(self, violation_number: int) -> int:
        # violation_number startet bei 1 -> 10s, 2 -> 12s, 3 -> 14.4s, ...
        seconds = BASE_TIMEOUT_SECONDS * (ESCALATION_FACTOR ** (violation_number - 1))
        return min(int(round(seconds)), MAX_TIMEOUT_SECONDS)

    def _is_spam(self, message: discord.Message) -> bool:
        history = self._message_history[message.author.id]
        now = time.time()
        history.append(now)
        recent = [t for t in history if now - t <= SPAM_WINDOW_SECONDS]
        return len(recent) >= SPAM_MESSAGE_THRESHOLD

    def _contains_invite(self, content: str) -> bool:
        return bool(INVITE_RE.search(content))

    def _contains_ad_link(self, content: str, whitelist: list) -> bool:
        for match in URL_RE.finditer(content):
            domain = match.group(1).lower()
            if not any(domain == w or domain.endswith("." + w) for w in whitelist):
                return True
        return False

    def _is_mass_mention(self, message: discord.Message) -> bool:
        total = len(message.mentions) + len(message.role_mentions)
        if message.mention_everyone:
            total += MASS_MENTION_THRESHOLD  # @everyone/@here zählt schwer
        return total >= MASS_MENTION_THRESHOLD

    def _contains_badword(self, content: str, badwords: list) -> bool:
        lowered = content.lower()
        return any(word.lower() in lowered for word in badwords if word.strip())

    def _is_caps(self, content: str) -> bool:
        letters = [c for c in content if c.isalpha()]
        if len(content) < CAPS_MIN_LENGTH or len(letters) < CAPS_MIN_LENGTH:
            return False
        upper = sum(1 for c in letters if c.isupper())
        return (upper / len(letters)) >= CAPS_RATIO_THRESHOLD

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if message.author.guild_permissions.administrator:
            return

        guild_config = config.get_guild_config(message.guild.id)
        content = message.content

        reason = None
        if self._is_spam(message):
            reason = "Spam (zu viele Nachrichten in kurzer Zeit)"
        elif self._contains_invite(content):
            reason = "Verbotener Discord-Invite-Link"
        elif self._contains_ad_link(content, guild_config.get("ad_whitelist", [])):
            reason = "Externer Werbelink"
        elif self._is_mass_mention(message):
            reason = "Massen-Mentions (Spam-Pings)"
        elif self._contains_badword(content, guild_config.get("badwords", [])):
            reason = "Verbotenes Wort verwendet"
        elif self._is_caps(content):
            reason = "Übermäßige Großschreibung (CAPS)"

        if reason is None:
            return

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        violation_number = self._increment_violation(message.guild.id, message.author.id)
        timeout_seconds = self._calc_timeout(violation_number)

        try:
            await message.author.timeout(
                timedelta(seconds=timeout_seconds),
                reason=f"Automod: {reason} (Verstoß #{violation_number})"
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        embed = discord.Embed(
            title="🛡️ Automod-Verstoß",
            description=(
                f"**User:** {message.author.mention}\n"
                f"**Grund:** {reason}\n"
                f"**Verstoß Nr.:** {violation_number}\n"
                f"**Timeout:** {timeout_seconds} Sekunden"
            ),
            color=discord.Color.from_str("#E74C3C"),
        )
        embed.timestamp = discord.utils.utcnow()

        log_channel_id = guild_config.get("automod_log_channel")
        log_channel = message.guild.get_channel(log_channel_id) if log_channel_id else None

        if log_channel:
            await log_channel.send(embed=embed)
        else:
            warn_msg = await message.channel.send(embed=embed)
            try:
                await warn_msg.delete(delay=10)
            except discord.HTTPException:
                pass


class AutoModConfig(commands.Cog):
    """Konfigurations-Commands für den Automod."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setautomodlogchannel")
    @commands.has_permissions(administrator=True)
    async def set_automod_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        config.set_guild_config(ctx.guild.id, "automod_log_channel", channel.id)
        await ctx.send(f"✅ Automod-Log-Channel wurde auf {channel.mention} gesetzt.")

    @commands.command(name="addbadword")
    @commands.has_permissions(administrator=True)
    async def add_badword(self, ctx: commands.Context, *, word: str):
        guild_config = config.get_guild_config(ctx.guild.id)
        badwords = guild_config.get("badwords", [])
        if word.lower() in [w.lower() for w in badwords]:
            await ctx.send("⚠️ Dieses Wort ist bereits in der Liste.")
            return
        badwords.append(word)
        config.set_guild_config(ctx.guild.id, "badwords", badwords)
        await ctx.send(f"✅ `{word}` wurde zur Liste verbotener Wörter hinzugefügt.")

    @commands.command(name="removebadword")
    @commands.has_permissions(administrator=True)
    async def remove_badword(self, ctx: commands.Context, *, word: str):
        guild_config = config.get_guild_config(ctx.guild.id)
        badwords = [w for w in guild_config.get("badwords", []) if w.lower() != word.lower()]
        config.set_guild_config(ctx.guild.id, "badwords", badwords)
        await ctx.send(f"✅ `{word}` wurde aus der Liste entfernt (falls vorhanden).")

    @commands.command(name="addwhitelist")
    @commands.has_permissions(administrator=True)
    async def add_whitelist(self, ctx: commands.Context, domain: str):
        guild_config = config.get_guild_config(ctx.guild.id)
        whitelist = guild_config.get("ad_whitelist", [])
        domain = domain.lower().replace("https://", "").replace("http://", "").strip("/")
        if domain not in whitelist:
            whitelist.append(domain)
            config.set_guild_config(ctx.guild.id, "ad_whitelist", whitelist)
        await ctx.send(f"✅ `{domain}` wurde zur Link-Whitelist hinzugefügt.")

    @commands.command(name="removewhitelist")
    @commands.has_permissions(administrator=True)
    async def remove_whitelist(self, ctx: commands.Context, domain: str):
        guild_config = config.get_guild_config(ctx.guild.id)
        domain = domain.lower().replace("https://", "").replace("http://", "").strip("/")
        whitelist = [d for d in guild_config.get("ad_whitelist", []) if d != domain]
        config.set_guild_config(ctx.guild.id, "ad_whitelist", whitelist)
        await ctx.send(f"✅ `{domain}` wurde von der Link-Whitelist entfernt (falls vorhanden).")

    @commands.command(name="automodstatus")
    @commands.has_permissions(administrator=True)
    async def automod_status(self, ctx: commands.Context):
        guild_config = config.get_guild_config(ctx.guild.id)
        embed = discord.Embed(title="🛡️ Automod-Status", color=discord.Color.from_str("#3498DB"))
        log_channel = ctx.guild.get_channel(guild_config.get("automod_log_channel")) if guild_config.get("automod_log_channel") else None
        embed.add_field(name="Log-Channel", value=log_channel.mention if log_channel else "Nicht gesetzt", inline=False)
        embed.add_field(name="Verbotene Wörter", value=str(len(guild_config.get("badwords", []))) + " Einträge", inline=True)
        embed.add_field(name="Link-Whitelist", value=", ".join(guild_config.get("ad_whitelist", [])[:10]) or "leer", inline=False)
        embed.add_field(
            name="Eskalation",
            value=f"Start: {BASE_TIMEOUT_SECONDS}s, +{int((ESCALATION_FACTOR - 1) * 100)}% je Verstoß",
            inline=False
        )
        await ctx.send(embed=embed)

    @commands.command(name="resetviolations")
    @commands.has_permissions(administrator=True)
    async def reset_violations(self, ctx: commands.Context, member: discord.Member):
        data = _load_violations()
        gid, uid = str(ctx.guild.id), str(member.id)
        if gid in data and uid in data[gid]:
            del data[gid][uid]
            _save_violations(data)
        await ctx.send(f"✅ Automod-Verstöße von {member.mention} wurden zurückgesetzt.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))
    await bot.add_cog(AutoModConfig(bot))
