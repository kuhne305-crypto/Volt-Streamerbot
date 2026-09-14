import os
import time
import logging

import aiohttp
import discord
from discord.ext import commands, tasks

import config

log = logging.getLogger("tytan-bot.twitch")

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
STREAMS_URL = "https://api.twitch.tv/helix/streams"
USERS_URL = "https://api.twitch.tv/helix/users"


class TwitchAnnounce(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self._app_token = None
        self._token_expires_at = 0
        self.check_stream.start()

    def cog_unload(self):
        self.check_stream.cancel()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _get_app_token(self):
        if self._app_token and time.time() < self._token_expires_at - 60:
            return self._app_token

        if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
            return None

        session = await self._get_session()
        params = {
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }
        async with session.post(TOKEN_URL, params=params) as resp:
            if resp.status != 200:
                log.error(f"Twitch Token Request fehlgeschlagen: {resp.status} {await resp.text()}")
                return None
            data = await resp.json()
            self._app_token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 3600)
            return self._app_token

    async def _get_stream(self, username: str):
        token = await self._get_app_token()
        if not token:
            return None

        session = await self._get_session()
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}",
        }
        async with session.get(STREAMS_URL, headers=headers, params={"user_login": username}) as resp:
            if resp.status != 200:
                log.error(f"Twitch Streams Request fehlgeschlagen: {resp.status} {await resp.text()}")
                return None
            data = await resp.json()
            streams = data.get("data", [])
            return streams[0] if streams else None

    async def _get_user_info(self, username: str):
        token = await self._get_app_token()
        if not token:
            return None
        session = await self._get_session()
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}",
        }
        async with session.get(USERS_URL, headers=headers, params={"login": username}) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            users = data.get("data", [])
            return users[0] if users else None

    @tasks.loop(seconds=60)
    async def check_stream(self):
        if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
            return

        for guild in self.bot.guilds:
            guild_config = config.get_guild_config(guild.id)
            channel_id = guild_config.get("twitch_channel")
            username = guild_config.get("twitch_username", "atlaxx_tv")
            if not channel_id:
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                continue

            stream = await self._get_stream(username)
            last_stream_id = guild_config.get("twitch_last_stream_id")

            if stream and str(stream["id"]) != str(last_stream_id):
                # Neuer Stream ist online -> Ankündigung posten
                config.set_guild_config(guild.id, "twitch_last_stream_id", stream["id"])
                await self._announce(channel, guild, guild_config, stream, username)
            elif not stream and last_stream_id:
                # Stream ist offline -> Status zurücksetzen
                config.set_guild_config(guild.id, "twitch_last_stream_id", None)

    @check_stream.before_loop
    async def before_check_stream(self):
        await self.bot.wait_until_ready()

    async def _announce(self, channel: discord.TextChannel, guild: discord.Guild, guild_config: dict, stream: dict, username: str):
        role_id = guild_config.get("twitch_role") or config.DEFAULT_ROLES["stream_role"]
        role = guild.get_role(role_id)
        role_mention = role.mention if role else ""

        user_info = await self._get_user_info(username)
        avatar_url = user_info.get("profile_image_url") if user_info else None

        thumbnail_url = stream["thumbnail_url"].replace("{width}", "1280").replace("{height}", "720")
        # Cache-Busting, damit Discord das Thumbnail nicht dauerhaft cached
        thumbnail_url += f"?t={int(time.time())}"

        embed = discord.Embed(
            title=stream.get("title", "Live auf Twitch!"),
            url=f"https://www.twitch.tv/{username}",
            description=f"**{stream.get('user_name', username)}** ist jetzt live!",
            color=discord.Color.from_str("#9146FF"),
        )
        embed.add_field(name="🎮 Spiel", value=stream.get("game_name", "Unbekannt"), inline=True)
        embed.add_field(name="👀 Zuschauer", value=str(stream.get("viewer_count", 0)), inline=True)
        embed.set_image(url=thumbnail_url)
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text="Klicke auf den Titel, um direkt zum Stream zu kommen!")

        content = f"🔴 {role_mention} **{stream.get('user_name', username)}** ist jetzt LIVE auf Twitch!" if role_mention else None

        try:
            await channel.send(content=content, embed=embed)
        except discord.Forbidden:
            log.error(f"Keine Berechtigung, in Channel {channel.id} zu posten.")


class TwitchConfig(commands.Cog):
    """Konfigurations-Commands für die Twitch-Integration."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="settwitchchannel")
    @commands.has_permissions(administrator=True)
    async def set_twitch_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        config.set_guild_config(ctx.guild.id, "twitch_channel", channel.id)
        await ctx.send(f"✅ Twitch-Live-Ankündigungen werden jetzt in {channel.mention} gepostet.")

    @commands.command(name="settwitchuser")
    @commands.has_permissions(administrator=True)
    async def set_twitch_user(self, ctx: commands.Context, username: str):
        config.set_guild_config(ctx.guild.id, "twitch_username", username.lower())
        await ctx.send(f"✅ Twitch-Username wurde auf `{username.lower()}` gesetzt.")

    @commands.command(name="setstreamrole")
    @commands.has_permissions(administrator=True)
    async def set_stream_role(self, ctx: commands.Context, role: discord.Role):
        config.set_guild_config(ctx.guild.id, "twitch_role", role.id)
        await ctx.send(f"✅ Stream-Ping-Rolle wurde auf {role.mention} gesetzt.")


async def setup(bot: commands.Bot):
    await bot.add_cog(TwitchAnnounce(bot))
    await bot.add_cog(TwitchConfig(bot))
