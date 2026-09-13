import discord
from discord.ext import commands

import config

RULES_TEXT = """
Mit dem Beitritt zu diesem Discord Server akzeptierst du automatisch die folgenden Regeln. Bitte lies sie dir sorgfältig durch.

**§1 Allgemeines**
1️⃣ Ein freundlicher und respektvoller Umgang mit allen Usern hat höchste Priorität.
2️⃣ Den Anweisungen des Moderationsteams ist Folge zu leisten.
3️⃣ Beleidigungen, Respektlosigkeit, Diskriminierung, Hetze und Rassismus sind strengstens verboten.
4️⃣ Private Daten (Telefonnummern, Adressen, Passwörter, etc.) dürfen nicht öffentlich geteilt werden.
5️⃣ Hack- und DDoS-Angriffe gegen diesen Server sind strafbar und werden ggf. rechtlich verfolgt.
6️⃣ Unwissenheit schützt nicht vor Konsequenzen – jeder ist selbst für die Kenntnis der Regeln verantwortlich.

**§2 Inhalte**
1️⃣ Pornografische/sexuelle Inhalte, Volksverhetzung, Gewaltverherrlichung & gesetzeswidrige Inhalte sind in jeder Form verboten.
2️⃣ Beleidigungen und unhöfliches Verhalten sind zu unterlassen.
3️⃣ Trolling und Spamming sind verboten.
4️⃣ Fremdwerbung jeglicher Art ist untersagt – auch per Direktnachricht.
5️⃣ Deutsche Inhalte im englischen Bereich und umgekehrt werden kommentarlos entfernt.

**§3 Voice Chats & Voice Channels**
1️⃣ Aufzeichnen anderer User ohne Zustimmung ist verboten.
2️⃣ Ständiges Wechseln der Sprachkanäle ist verboten.
3️⃣ Soundboards sind verboten.
4️⃣ Stimmverzerrer sind verboten.

**§4 Konsequenzen**
1️⃣ Beim ersten Vergehen: Verwarnung, Mute, Kick oder temporärer Ban.
2️⃣ Wiederholtes Fehlverhalten führt zum dauerhaften Ausschluss.
3️⃣ Über Bestrafungen wird nicht öffentlich diskutiert.
4️⃣ Anliegen werden per Privatchat mit dem Team geklärt.
5️⃣ Zu Unrecht bestraft? Kontaktiere ein Teammitglied.
6️⃣ Das Umgehen von Bestrafungen ist strengstens verboten.

**§5 Sonstiges**
1️⃣ Missbrauch von Berechtigungen, Rollen oder Bots wird bestraft und kann zum Rechteverlust führen.

**§6 Änderungen am Regelwerk**
1️⃣ Änderungen sind dem Moderationsteam jederzeit vorbehalten.
2️⃣ Das Team kann auch unabhängig von diesen Regeln nach eigenem Ermessen handeln.
"""


class VerifyView(discord.ui.View):
    """Persistent View – custom_id bleibt über Restarts hinweg gültig."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verifizieren", emoji="✅", style=discord.ButtonStyle.success, custom_id="tytan_verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_config = config.get_guild_config(interaction.guild_id)
        role_id = guild_config.get("verify_role")

        if not role_id:
            await interaction.response.send_message(
                "⚠️ Es wurde noch keine Verify-Rolle konfiguriert. Bitte kontaktiere einen Admin.",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message(
                "⚠️ Die konfigurierte Verify-Rolle existiert nicht mehr. Bitte kontaktiere einen Admin.",
                ephemeral=True
            )
            return

        member = interaction.user
        if role in member.roles:
            await interaction.response.send_message("✅ Du bist bereits verifiziert!", ephemeral=True)
            return

        try:
            await member.add_roles(role, reason="Verify-Button geklickt")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Mir fehlen die Rechte, um dir die Rolle zu geben. Bitte kontaktiere einen Admin.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"🎉 Willkommen! Du wurdest erfolgreich verifiziert und hast die Rolle **{role.name}** erhalten.",
            ephemeral=True
        )


class Verify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # View einmalig registrieren, damit der Button auch nach einem Restart funktioniert
        self.bot.add_view(VerifyView())

    @commands.command(name="setverifyrole")
    @commands.has_permissions(administrator=True)
    async def set_verify_role(self, ctx: commands.Context, role: discord.Role):
        config.set_guild_config(ctx.guild.id, "verify_role", role.id)
        await ctx.send(f"✅ Verify-Rolle wurde auf {role.mention} gesetzt.")

    @commands.command(name="setupverify")
    @commands.has_permissions(administrator=True)
    async def setup_verify(self, ctx: commands.Context, channel: discord.TextChannel = None):
        target = channel or ctx.channel
        guild_config = config.get_guild_config(ctx.guild.id)

        if not guild_config.get("verify_role"):
            await ctx.send("⚠️ Bitte setze zuerst eine Verify-Rolle mit `!setverifyrole @Rolle`.")
            return

        embed = discord.Embed(
            title="📜 Server Regeln",
            description=RULES_TEXT,
            color=discord.Color.from_str("#5865F2")
        )
        embed.add_field(
            name="👥 Freunde einladen",
            value="Lade deine Freunde mit diesem Link ein:\nhttps://discord.gg/7tQh9DGN96",
            inline=False
        )
        embed.set_footer(text="Klicke unten auf ✅ Verifizieren, um Zugriff auf den Server zu erhalten.")
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        await target.send(embed=embed, view=VerifyView())
        config.set_guild_config(ctx.guild.id, "verify_channel", target.id)

        if target.id != ctx.channel.id:
            await ctx.send(f"✅ Verify-Nachricht wurde in {target.mention} gepostet.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot))
