# TYTAN Community Bot

Ein Discord-Bot für dein Community-Discord mit Verify-System, Reaction-Roles,
Twitch-Live-Ankündigung, Giveaways, Automod und Autoban-Channel.

Alle Konfigurations-Commands nutzen das Prefix `!` und sind **nur für Nutzer
mit Administrator-Berechtigung** verfügbar.

---

## 1. Discord Bot erstellen

1. Gehe zu https://discord.com/developers/applications → **New Application**.
2. Tab **Bot** → **Reset Token** → Token kopieren (später in `.env` als `DISCORD_TOKEN`).
3. Unter **Privileged Gateway Intents** aktivieren:
   - `SERVER MEMBERS INTENT`
   - `MESSAGE CONTENT INTENT`
4. Tab **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Administrator` (am einfachsten) oder mindestens:
     `Manage Roles`, `Manage Messages`, `Kick/Ban Members` (für Timeout),
     `Send Messages`, `Read Message History`, `Add Reactions`, `Embed Links`
   - Mit dem generierten Link den Bot auf deinen Server einladen.

⚠️ Wichtig: Die Bot-Rolle muss in der Rollen-Hierarchie **über** allen Rollen
stehen, die er vergeben/entfernen soll (z.B. Verify-Rolle, Ping-Rollen).

## 2. Twitch API Zugangsdaten (für Live-Ankündigung)

1. Gehe zu https://dev.twitch.tv/console/apps → **Register Your Application**.
2. OAuth Redirect URL: `http://localhost` (wird nicht wirklich genutzt).
3. Category: `Application Integration`.
4. Nach dem Erstellen: **Client ID** kopieren, **New Secret** generieren und
   kopieren → beides in `.env` eintragen.

## 3. Lokale Einrichtung (zum Testen)

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env ausfüllen (Token, Twitch Keys)
python main.py
```

## 4. Deployment auf Railway

1. Repository (z.B. auf GitHub) mit diesem Code erstellen und pushen.
2. Auf https://railway.app → **New Project → Deploy from GitHub repo**.
3. Railway erkennt automatisch `requirements.txt` + `Procfile`.
4. Unter **Variables** die Umgebungsvariablen aus `.env.example` eintragen:
   - `DISCORD_TOKEN`
   - `TWITCH_CLIENT_ID`
   - `TWITCH_CLIENT_SECRET`
   - optional `BOT_PREFIX`
5. Deploy starten – fertig, der Bot läuft dauerhaft.

**Wichtig für persistente Daten:** Die Bot-Konfiguration, Giveaways und
Automod-Verstöße werden als JSON-Dateien im `data/`-Ordner gespeichert. Damit
diese bei einem Redeploy nicht verloren gehen, unter Railway ein **Volume**
einbinden und auf den Pfad `/app/data` mounten (Railway → dein Service →
Settings → Volumes).

## 5. Erst-Konfiguration auf deinem Server

Sobald der Bot online ist, führe (als Admin) der Reihe nach aus:

```
!setverifyrole @Verified
!setupverify #regeln
!setupreactionroles #roles
!settwitchchannel #live
!settwitchuser tytan_hd        (Standard ist bereits tytan_hd)
!setstreamrole @Stream-Ping    (optional, Standard-Rolle ist schon hinterlegt)
!setgiveawaychannel #giveaways
!setautobanchannel #autoban
!setautomodlogchannel #mod-log
```

Mit `!botconfig` siehst du jederzeit die aktuelle Konfiguration, mit
`!commands` eine vollständige Übersicht aller Admin-Commands.

---

## Funktionsübersicht

### ✅ Verify-System
- `!setverifyrole @Rolle` – legt fest, welche Rolle beim Verify vergeben wird.
- `!setupverify [#channel]` – postet die (verschönerte) Regel-Nachricht mit
  Verify-Button. Der Button funktioniert dauerhaft, auch nach Bot-Neustarts.

### 🔔 Reaction Roles
- `!setupreactionroles [#channel]` – postet die Rollen-Auswahl-Nachricht
  (🔴 Stream-Ping, 🎁 Giveaway-Ping, 📊 Umfrage-Ping, 📱 Tiktok-Ping) mit den
  von dir vorgegebenen Rollen-IDs. Reaktion hinzufügen = Rolle bekommen,
  Reaktion entfernen = Rolle verlieren.

### 🟣 Twitch Live-Ankündigung
- Prüft alle 60 Sekunden automatisch, ob `twitch.tv/tytan_hd` live ist.
- Postet bei Stream-Start eine Ankündigung mit Titel, Spiel, Zuschauerzahl,
  Thumbnail und pingt die Stream-Rolle.
- `!settwitchchannel`, `!settwitchuser`, `!setstreamrole` zur Anpassung.

### 🎉 Giveaways
- `!giveaway start <dauer> <gewinner> <preis>` z.B. `!giveaway start 1h 2 Nitro`
  (Dauer-Format: `s`/`m`/`h`/`d`/`w`, z.B. `30m`, `2h`, `1d`).
- Pingt automatisch die Giveaway-Rolle, Teilnahme per 🎉-Reaktion.
- `!giveaway end <message_id>` – vorzeitig beenden.
- `!giveaway reroll <message_id>` – neuen Gewinner auslosen.
- `!giveaway list` – zeigt alle laufenden Giveaways.

### 🛡️ Automod (eskalierende Bestrafung)
Erkennt: Spam, Discord-Invite-Links, externe Werbelinks, Massen-Mentions,
verbotene Wörter (eigene Liste) und übermäßige CAPS-Schreibung.

Statt sofort zu bannen/kicken wird die Nachricht gelöscht und der User
zeitweise stummgeschaltet (Timeout) – mit steigender Dauer pro Verstoß:

| Verstoß | Timeout   |
|---------|-----------|
| 1.      | 10 Sek.   |
| 2.      | 12 Sek.   |
| 3.      | ~14 Sek.  |
| 4.      | ~17 Sek.  |
| 5.      | ~21 Sek.  |
| ...     | jeweils +20% |

Admins/Administratoren sind vom Automod ausgenommen.

- `!addbadword` / `!removebadword` – eigene Wortliste pflegen.
- `!addwhitelist` / `!removewhitelist` – erlaubte Link-Domains (Standard:
  YouTube, Twitch, Twitter/X, TikTok, Instagram, Discord, Spotify, etc.).
- `!automodstatus` – aktuelle Einstellungen anzeigen.
- `!resetviolations @user` – Verstoßzähler eines Users zurücksetzen.

### 🚫 Autoban-Channel
- `!setautobanchannel #channel` – schreibt jemand in diesen Channel, werden
  automatisch **alle seine Nachrichten der letzten 24 Stunden serverweit
  gelöscht** und eine Warn-Nachricht wird gepostet (im Automod-Log-Channel,
  falls gesetzt, sonst im selben Channel).

---

## Erweiterungsideen (optional, nicht enthalten)
- Automatisches Kicken/Bannen ab einer bestimmten Verstoßanzahl.
- Slash-Command-Variante zusätzlich zu den Prefix-Commands.
- Giveaway-Anforderungen (z.B. "nur mit Rolle X teilnahmeberechtigt").
- Datenbank (SQLite/PostgreSQL) statt JSON-Dateien für größere Server.
