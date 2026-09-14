import json
import os
from threading import Lock

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

os.makedirs(DATA_DIR, exist_ok=True)

_lock = Lock()

# Standard-Rollen-IDs (können pro Server per Command überschrieben werden)
DEFAULT_ROLES = {
    "stream_role": 1501627799520149578,
    "giveaway_role": 1501627755371036873,
    "umfrage_role": 1501628031796510931,
    "social_role": 1342841415851573291,
}

DEFAULT_GUILD_CONFIG = {
    "verify_channel": None,
    "verify_role": None,
    "reaction_role_channel": None,
    "reaction_role_message": None,
    "twitch_channel": None,
    "twitch_username": "atlaxx_tv",
    "twitch_role": DEFAULT_ROLES["stream_role"],
    "twitch_last_stream_id": None,
    "giveaway_channel": None,
    "giveaway_role": DEFAULT_ROLES["giveaway_role"],
    "autoban_channel": None,
    "autoban_count": 0,
    "automod_log_channel": None,
    "badwords": [],
    "ad_whitelist": [
        "discord.com", "discord.gg", "tenor.com", "giphy.com",
        "youtube.com", "youtu.be", "twitch.tv", "twitter.com",
        "x.com", "tiktok.com", "instagram.com", "media.discordapp.net",
        "cdn.discordapp.com", "spotify.com"
    ],
}


def _load():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_guild_config(guild_id: int) -> dict:
    with _lock:
        data = _load()
        gid = str(guild_id)
        if gid not in data:
            data[gid] = dict(DEFAULT_GUILD_CONFIG)
            _save(data)
        else:
            # fehlende Keys nachziehen (z.B. nach Updates)
            changed = False
            for k, v in DEFAULT_GUILD_CONFIG.items():
                if k not in data[gid]:
                    data[gid][k] = v
                    changed = True
            if changed:
                _save(data)
        return data[gid]


def set_guild_config(guild_id: int, key: str, value):
    with _lock:
        data = _load()
        gid = str(guild_id)
        if gid not in data:
            data[gid] = dict(DEFAULT_GUILD_CONFIG)
        data[gid][key] = value
        _save(data)


def update_guild_config(guild_id: int, updates: dict):
    with _lock:
        data = _load()
        gid = str(guild_id)
        if gid not in data:
            data[gid] = dict(DEFAULT_GUILD_CONFIG)
        data[gid].update(updates)
        _save(data)
