import discord
from discord.ext import commands

import config

# Emoji -> Config-Key (Rollen-ID wird aus der Guild-Config gelesen)
EMOJI_ROLE_MAP = {
    "🔴": ("stream_role", "Stream-Ping", "Wenn ATLAXX live geht"),
    "🎁": ("giveaway_role", "Giveaway-Ping", "Bei Gewinnspielen"),
    "📊": ("umfrage_role", "Umfrage-Ping", "Bei Abstimmungen"),
    "📱": ("social_role", "Social-Ping", "Bei neuen Social-Media-Posts"),
}


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setupreactionroles")
    @commands.has_permissions(administrator=True)
    async def setup_reaction_roles(self, ctx: commands.Context, channel: discord.TextChannel = None):
        target = channel or ctx.channel

        description_lines = "\n".join(
            f"{emoji} — **{name}** ({desc})" for emoji, (_, name, desc) in EMOJI_ROLE_MAP.items()
        )

        embed = discord.Embed(
            title="🔔 Wofür möchtest du gepingt werden?",
            description=f"Wähle deine Rollen mit den Reaktionen unten aus!\n\n{description_lines}",
            color=discord.Color.from_str("#E63946")
        )
        embed.set_footer(text="Klicke einfach auf die passende Reaktion, um die Rolle zu erhalten oder zu entfernen.")

        message = await target.send(embed=embed)
        for emoji in EMOJI_ROLE_MAP:
            await message.add_reaction(emoji)

        config.update_guild_config(ctx.guild.id, {
            "reaction_role_channel": target.id,
            "reaction_role_message": message.id,
        })

        if target.id != ctx.channel.id:
            await ctx.send(f"✅ Reaction-Role-Nachricht wurde in {target.mention} gepostet.")

    async def _handle_reaction(self, payload: discord.RawReactionActionEvent, adding: bool):
        if payload.member and payload.member.bot:
            return
        if payload.guild_id is None:
            return

        guild_config = config.get_guild_config(payload.guild_id)
        if guild_config.get("reaction_role_message") != payload.message_id:
            return

        emoji = str(payload.emoji)
        mapping = EMOJI_ROLE_MAP.get(emoji)
        if not mapping:
            return

        role_key = mapping[0]
        # twitch_role & giveaway_role sind pro Server konfigurierbar, sonst Standardwerte nutzen
        if role_key == "stream_role":
            role_id = guild_config.get("twitch_role") or config.DEFAULT_ROLES["stream_role"]
        elif role_key == "giveaway_role":
            role_id = guild_config.get("giveaway_role") or config.DEFAULT_ROLES["giveaway_role"]
        else:
            role_id = config.DEFAULT_ROLES.get(role_key)

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        role = guild.get_role(role_id)
        if role is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            return

        try:
            if adding:
                await member.add_roles(role, reason="Reaction Role")
            else:
                await member.remove_roles(role, reason="Reaction Role entfernt")
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, adding=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, adding=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
