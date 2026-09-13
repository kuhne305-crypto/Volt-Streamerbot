import json
import os
import random
import re
import time

import discord
from discord.ext import commands, tasks

import config

GIVEAWAY_EMOJI = "🎉"
DATA_PATH = os.path.join(config.DATA_DIR, "giveaways.json")

DURATION_RE = re.compile(r"^(\d+)([smhdw])$", re.IGNORECASE)
UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_duration(text: str) -> int:
    match = DURATION_RE.match(text.strip())
    if not match:
        raise ValueError("Ungültiges Format. Nutze z.B. `30s`, `10m`, `2h`, `1d`, `1w`.")
    amount, unit = match.groups()
    return int(amount) * UNIT_SECONDS[unit.lower()]


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds or not parts: parts.append(f"{seconds}s")
    return " ".join(parts)


def _load():
    if not os.path.exists(DATA_PATH):
        return {}
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class Giveaway(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.group(name="giveaway", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def giveaway(self, ctx: commands.Context):
        await ctx.send(
            "Nutze:\n"
            "`!giveaway start <dauer> <gewinneranzahl> <preis>`\n"
            "`!giveaway end <message_id>`\n"
            "`!giveaway reroll <message_id>`\n"
            "`!giveaway list`"
        )

    @giveaway.command(name="start")
    @commands.has_permissions(administrator=True)
    async def giveaway_start(self, ctx: commands.Context, duration: str, winners: int, *, prize: str):
        try:
            seconds = parse_duration(duration)
        except ValueError as e:
            await ctx.send(f"⚠️ {e}")
            return

        if winners < 1:
            await ctx.send("⚠️ Die Gewinneranzahl muss mindestens 1 sein.")
            return

        guild_config = config.get_guild_config(ctx.guild.id)
        target_channel_id = guild_config.get("giveaway_channel")
        target = ctx.guild.get_channel(target_channel_id) if target_channel_id else ctx.channel

        role_id = guild_config.get("giveaway_role") or config.DEFAULT_ROLES["giveaway_role"]
        role = ctx.guild.get_role(role_id)
        role_mention = role.mention if role else ""

        end_time = int(time.time()) + seconds
        end_ts = f"<t:{end_time}:R>"

        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=(
                f"**Preis:** {prize}\n"
                f"**Gewinner:** {winners}\n"
                f"**Endet:** {end_ts}\n\n"
                f"Reagiere mit {GIVEAWAY_EMOJI} um teilzunehmen!"
            ),
            color=discord.Color.from_str("#F1C40F"),
        )
        embed.set_footer(text=f"Gestartet von {ctx.author.display_name}")

        message = await target.send(
            content=role_mention if role_mention else None,
            embed=embed
        )
        await message.add_reaction(GIVEAWAY_EMOJI)

        data = _load()
        data[str(message.id)] = {
            "guild_id": ctx.guild.id,
            "channel_id": target.id,
            "prize": prize,
            "winners": winners,
            "end_time": end_time,
            "host_id": ctx.author.id,
            "ended": False,
        }
        _save(data)

        if target.id != ctx.channel.id:
            await ctx.send(f"✅ Giveaway wurde in {target.mention} gestartet.")

    @giveaway.command(name="end")
    @commands.has_permissions(administrator=True)
    async def giveaway_end(self, ctx: commands.Context, message_id: int):
        data = _load()
        entry = data.get(str(message_id))
        if not entry or entry["ended"]:
            await ctx.send("⚠️ Dieses Giveaway wurde nicht gefunden oder ist bereits beendet.")
            return
        await self._finish_giveaway(message_id, entry)
        await ctx.send("✅ Giveaway wurde beendet.")

    @giveaway.command(name="reroll")
    @commands.has_permissions(administrator=True)
    async def giveaway_reroll(self, ctx: commands.Context, message_id: int):
        data = _load()
        entry = data.get(str(message_id))
        if not entry:
            await ctx.send("⚠️ Dieses Giveaway wurde nicht gefunden.")
            return
        await self._pick_winners(message_id, entry, reroll=True)

    @giveaway.command(name="list")
    @commands.has_permissions(administrator=True)
    async def giveaway_list(self, ctx: commands.Context):
        data = _load()
        active = [
            (mid, e) for mid, e in data.items()
            if e["guild_id"] == ctx.guild.id and not e["ended"]
        ]
        if not active:
            await ctx.send("Es laufen aktuell keine Giveaways.")
            return
        lines = [f"• `{mid}` – **{e['prize']}** (endet <t:{e['end_time']}:R>)" for mid, e in active]
        await ctx.send("**Aktive Giveaways:**\n" + "\n".join(lines))

    async def _finish_giveaway(self, message_id, entry):
        data = _load()
        if str(message_id) in data:
            data[str(message_id)]["ended"] = True
            _save(data)
        await self._pick_winners(message_id, entry, reroll=False)

    async def _pick_winners(self, message_id, entry, reroll: bool):
        guild = self.bot.get_guild(entry["guild_id"])
        if guild is None:
            return
        channel = guild.get_channel(entry["channel_id"])
        if channel is None:
            return
        try:
            message = await channel.fetch_message(int(message_id))
        except discord.NotFound:
            return

        reaction = discord.utils.get(message.reactions, emoji=GIVEAWAY_EMOJI)
        entrants = []
        if reaction:
            async for user in reaction.users():
                if not user.bot:
                    entrants.append(user)

        winners_count = entry["winners"]

        if not entrants:
            await channel.send(f"😢 Niemand hat am Giveaway für **{entry['prize']}** teilgenommen.")
            return

        winners = random.sample(entrants, min(winners_count, len(entrants)))
        mentions = ", ".join(w.mention for w in winners)

        if reroll:
            await channel.send(f"🔄 **Neuer Gewinner** für **{entry['prize']}**: {mentions} 🎉")
        else:
            await channel.send(f"🎉 Glückwunsch {mentions}! Ihr habt **{entry['prize']}** gewonnen!")

            try:
                embed = message.embeds[0]
                embed.description = f"**Preis:** {entry['prize']}\n**Gewinner:** {mentions}\n\n🎉 Giveaway beendet!"
                embed.color = discord.Color.from_str("#95A5A6")
                await message.edit(embed=embed)
            except (IndexError, discord.HTTPException):
                pass

    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        data = _load()
        now = int(time.time())
        for mid, entry in list(data.items()):
            if entry["ended"]:
                continue
            if entry["end_time"] <= now:
                await self._finish_giveaway(mid, entry)

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

    @commands.command(name="setgiveawaychannel")
    @commands.has_permissions(administrator=True)
    async def set_giveaway_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        config.set_guild_config(ctx.guild.id, "giveaway_channel", channel.id)
        await ctx.send(f"✅ Giveaways werden jetzt standardmäßig in {channel.mention} gestartet.")

    @commands.command(name="setgiveawayrole")
    @commands.has_permissions(administrator=True)
    async def set_giveaway_role(self, ctx: commands.Context, role: discord.Role):
        config.set_guild_config(ctx.guild.id, "giveaway_role", role.id)
        await ctx.send(f"✅ Giveaway-Ping-Rolle wurde auf {role.mention} gesetzt.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))
