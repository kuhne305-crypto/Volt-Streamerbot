import os
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("tytan-bot")

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", "!")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=commands.DefaultHelpCommand())

INITIAL_COGS = [
    "cogs.admin_config",
    "cogs.verify",
    "cogs.reaction_roles",
    "cogs.twitch_announce",
    "cogs.giveaway",
    "cogs.automod",
    "cogs.autoban_channel",
]


@bot.event
async def on_ready():
    log.info(f"Eingeloggt als {bot.user} (ID: {bot.user.id})")
    log.info(f"Aktiv auf {len(bot.guilds)} Server(n)")
    await bot.change_presence(activity=discord.Streaming(
        name="tytan_hd", url="https://www.twitch.tv/tytan_hd"
    ))


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 Du benötigst **Administrator-Rechte**, um diesen Command zu nutzen.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Es fehlt ein Argument: `{error.param.name}`. Nutze `!help {ctx.command}` für Details.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"⚠️ Ungültiges Argument: {error}")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        log.exception("Unbehandelter Fehler", exc_info=error)
        await ctx.send(f"❌ Es ist ein Fehler aufgetreten: `{error}`")


async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN ist nicht gesetzt! Prüfe deine .env / Environment Variables.")

    async with bot:
        for cog in INITIAL_COGS:
            try:
                await bot.load_extension(cog)
                log.info(f"Cog geladen: {cog}")
            except Exception as e:
                log.exception(f"Konnte Cog {cog} nicht laden: {e}")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
