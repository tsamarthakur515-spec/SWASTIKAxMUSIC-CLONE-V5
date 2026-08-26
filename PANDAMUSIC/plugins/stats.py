# ---------------------------------------------------------------
# SWASTIKA MUSIC — stats.py
# /stats — GENERAL & OVERALL buttons (premium UI + custom emojis)
# ---------------------------------------------------------------

print("[stats] loading plugin...", flush=True)

import os
import platform
import shutil
import sys

import psutil

try:
    import pyrogram
except Exception:
    pyrogram = None
try:
    import pytgcalls
except Exception:
    pytgcalls = None
try:
    import ntgcalls
except Exception:
    ntgcalls = None

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import bot, call, console, cdx, rgx
from ..modules.database import (
    count_served_chats,
    count_served_users,
    count_sudoers,
    add_served_user,
    add_served_chat,
)
from ..modules.formatters import smallcaps
from ..modules.custom_emojis import tg_emoji
from .maintenance import block_if_maintenance

try:
    from pyrogram.enums import ButtonStyle
    _PRIMARY = ButtonStyle.PRIMARY
    _SUCCESS = ButtonStyle.SUCCESS
    _DANGER = ButtonStyle.DANGER
except Exception:
    _PRIMARY = "primary"
    _SUCCESS = "success"
    _DANGER = "danger"

# User provided custom emoji IDs
E_TITLE   = "6111778259374971023"   # Swastika Music v5 title emoji (everywhere)
E_MUSIC   = "6222160271796871446"
E_STAR    = "6222119723010629429"
E_DIAMOND = "6114147788537204268"
E_FIRE    = "6113735965598028355"
E_CHART   = "6113675681437061434"
E_HEADPH  = "6113641540742028885"
E_HEART   = "6115962158816693929"
E_STAR2   = "6113929148932034466"
E_TROPHY  = "6113857813820216054"
E_MUSIC2  = "6113782179446132587"
E_CALEND  = "6159137390574178597"
E_ROCKET  = "6125196652035711334"
E_SPARK   = "6125056206605130177"
E_CROWN   = "6159134001844983300"
E_GEM     = "6172201280929273675"   # OVERALL main emoji
E_CHECK   = "6088909942230619591"   # GENERAL main emoji
E_BOLT    = "6089078549761758735"
E_GLOW    = "6089264504665806086"
E_WAVE    = "6089398065263810456"

# Button emojis
E_BTN_GENERAL = "5453969464980691485"
E_BTN_OVERALL = "5192886348746355902"
E_BTN_CLOSE   = "5454317078158795717"


def _btn(text, style=None, emoji_id=None, **kwargs):
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = str(emoji_id)
    if style is not None:
        try:
            return InlineKeyboardButton(text, style=style, **kwargs)
        except TypeError:
            pass
        try:
            return InlineKeyboardButton(
                text, style=str(getattr(style, "name", style)).lower(), **kwargs
            )
        except TypeError:
            pass
    try:
        return InlineKeyboardButton(text, **kwargs)
    except TypeError:
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(text, **kwargs)


def stats_home_markup():
    return InlineKeyboardMarkup(
        [
            [
                _btn(smallcaps("GENERAL"), _PRIMARY, emoji_id=E_BTN_GENERAL, callback_data="stats_general"),
                _btn(smallcaps("OVERALL"), _SUCCESS, emoji_id=E_BTN_OVERALL, callback_data="stats_overall"),
            ],
            [_btn(smallcaps("CLOSE"), _DANGER, emoji_id=E_BTN_CLOSE, callback_data="close")],
        ]
    )


def stats_back_markup():
    return InlineKeyboardMarkup(
        [
            [
                _btn(smallcaps("GENERAL"), _PRIMARY, emoji_id=E_BTN_GENERAL, callback_data="stats_general"),
                _btn(smallcaps("OVERALL"), _SUCCESS, emoji_id=E_BTN_OVERALL, callback_data="stats_overall"),
            ],
            [_btn(smallcaps("CLOSE"), _DANGER, emoji_id=E_BTN_CLOSE, callback_data="close")],
        ]
    )


def _gib(bytes_val: float) -> str:
    return f"{bytes_val / (1024 ** 3):.2f}"


def _count_modules() -> int:
    try:
        from ..plugins import ALL_PLUGINS
        return len(ALL_PLUGINS)
    except Exception:
        try:
            plugin_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "plugins"
            )
            return len(
                [
                    f
                    for f in os.listdir(plugin_dir)
                    if f.endswith(".py") and not f.startswith("_")
                ]
            )
        except Exception:
            return 0


def _assistant_count() -> int:
    try:
        from ..modules.clients import assistants
        return len(assistants) or (1 if console.STRING1 else 0)
    except Exception:
        return 1 if console.STRING1 else 0


async def build_overall_text(username: str) -> str:
    users = await count_served_users()
    chats = await count_served_chats()
    sudos = await count_sudoers()
    modules = _count_modules()
    assistants_n = _assistant_count()
    duration = getattr(console, "DURATION_LIMIT", 60)

    return (
        f"{tg_emoji(E_TITLE, '✨')} <b>𝗦𝘄𝗮𝘀𝘁𝗶𝗸𝗮 𝗠𝘂𝘀𝗶𝗰 𝘃𝟱</b>\n"
        f"{tg_emoji(E_GEM, '💠')} <b>@{username}</b> — {smallcaps('overall stats')}\n\n"
        f"{tg_emoji(E_GEM, '💠')} {smallcaps('assistants')} : <code>{assistants_n}</code>\n"
        f"{tg_emoji(E_GEM, '💠')} {smallcaps('blocked')} : <code>0</code>\n"
        f"{tg_emoji(E_GEM, '💠')} {smallcaps('chats')} : <code>{chats}</code>\n"
        f"{tg_emoji(E_GEM, '💠')} {smallcaps('users')} : <code>{users}</code>\n"
        f"{tg_emoji(E_GEM, '💠')} {smallcaps('modules')} : <code>{modules}</code>\n"
        f"{tg_emoji(E_GEM, '💠')} {smallcaps('sudoers')} : <code>{sudos}</code>\n\n"
        f"{tg_emoji(E_GEM, '💠')} {smallcaps('auto leaving assistant')} : <code>False</code>\n"
        f"{tg_emoji(E_GEM, '💠')} {smallcaps('play duration limit')} : <code>{duration}</code> {smallcaps('minutes')}\n\n"
        f"{tg_emoji(E_TITLE, '✨')} <i>{smallcaps('powered by swastika music')}</i>"
    )


async def build_general_text(username: str) -> str:
    users = await count_served_users()
    chats = await count_served_chats()
    sudos = await count_sudoers()
    modules = _count_modules()

    plat = platform.system()
    vm = psutil.virtual_memory()
    ram = f"{_gib(vm.used)} / {_gib(vm.total)} GiB"
    try:
        physical = psutil.cpu_count(logical=False) or 0
    except Exception:
        physical = 0
    total_cores = psutil.cpu_count(logical=True) or 0
    try:
        freq = psutil.cpu_freq()
        cpu_mhz = f"{int(freq.current)} MHz" if freq else "N/A"
    except Exception:
        cpu_mhz = "N/A"

    py_ver = platform.python_version()
    pyro_ver = getattr(pyrogram, "__version__", "N/A") if pyrogram else "N/A"
    pytg_ver = getattr(pytgcalls, "__version__", "N/A") if pytgcalls else "N/A"

    du = shutil.disk_usage("/")
    storage_avail = _gib(du.total)
    storage_used = _gib(du.used)
    storage_left = _gib(du.free)

    return (
        f"{tg_emoji(E_TITLE, '✨')} <b>𝗦𝘄𝗮𝘀𝘁𝗶𝗸𝗮 𝗠𝘂𝘀𝗶𝗰 𝘃𝟱</b>\n"
        f"{tg_emoji(E_CHECK, '✅')} <b>@{username}</b> — {smallcaps('general stats')}\n\n"
        f"{tg_emoji(E_CHECK, '✅')} <b>{smallcaps('system info')}</b>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('modules')} : <code>{modules}</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('platform')} : <code>{plat}</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('ram')} : <code>{ram}</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('physical cores')} : <code>{physical}</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('total cores')} : <code>{total_cores}</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('cpu frequency')} : <code>{cpu_mhz}</code>\n\n"
        f"{tg_emoji(E_CHECK, '✅')} <b>{smallcaps('software')}</b>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('python')} : <code>{py_ver}</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('pyrogram')} : <code>{pyro_ver}</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('py-tgcalls')} : <code>{pytg_ver}</code>\n\n"
        f"{tg_emoji(E_CHECK, '✅')} <b>{smallcaps('storage')}</b>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('available')} : <code>{storage_avail}</code> GiB\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('used')} : <code>{storage_used}</code> GiB\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('left')} : <code>{storage_left}</code> GiB\n\n"
        f"{tg_emoji(E_CHECK, '✅')} <b>{smallcaps('bot stats')}</b>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('served chats')} : <code>{chats}</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('served users')} : <code>{users}</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('blocked users')} : <code>0</code>\n"
        f"{tg_emoji(E_CHECK, '✅')} {smallcaps('sudo users')} : <code>{sudos}</code>\n\n"
        f"{tg_emoji(E_TITLE, '✨')} <i>{smallcaps('powered by swastika music')}</i>"
    )


@bot.on_message(cdx("stats") & filters.incoming)
async def stats_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return

    try:
        if message.from_user:
            await add_served_user(message.from_user.id)
        if message.chat and message.chat.type.name != "PRIVATE":
            await add_served_chat(message.chat.id)
    except Exception:
        pass

    try:
        await message.delete()
    except Exception:
        pass

    me = client.me or await client.get_me()
    uname = me.username or "Swastika_musics_bot"

    photo = getattr(console, "STATS_IMAGE_URL", None)

    # Premium home caption with title emoji throughout
    caption = (
        f"{tg_emoji(E_TITLE, '✨')} <b>𝗦𝘄𝗮𝘀𝘁𝗶𝗸𝗮 𝗠𝘂𝘀𝗶𝗰 𝘃𝟱</b>\n\n"
        f"{tg_emoji(E_TITLE, '✨')} {smallcaps('welcome to the stats dashboard')}\n\n"
        f"{tg_emoji(E_TITLE, '✨')} {smallcaps('tap a button below to explore')}\n"
        f"{tg_emoji(E_TITLE, '✨')} {smallcaps('live system & bot statistics')}\n\n"
        f"{tg_emoji(E_TITLE, '✨')} <b>@{uname}</b>"
    )
    markup = stats_home_markup()

    try:
        if photo:
            await message.reply_photo(
                photo=photo,
                caption=caption,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.reply_text(
                caption, reply_markup=markup, parse_mode=ParseMode.HTML
            )
    except Exception:
        await message.reply_text(
            caption, reply_markup=markup, parse_mode=ParseMode.HTML
        )


@bot.on_callback_query(rgx("stats_overall"))
async def stats_overall_cb(client, query):
    try:
        me = client.me or await client.get_me()
        uname = me.username or "Swastika_musics_bot"
        text = await build_overall_text(uname)
        try:
            await query.message.edit_caption(
                caption=text, reply_markup=stats_back_markup(), parse_mode=ParseMode.HTML
            )
        except Exception:
            await query.message.edit_text(
                text, reply_markup=stats_back_markup(), parse_mode=ParseMode.HTML
            )
    except Exception as e:
        print(f"[stats] overall error: {e}", flush=True)
    await query.answer()


@bot.on_callback_query(rgx("stats_general"))
async def stats_general_cb(client, query):
    try:
        me = client.me or await client.get_me()
        uname = me.username or "Swastika_musics_bot"
        text = await build_general_text(uname)
        try:
            await query.message.edit_caption(
                caption=text, reply_markup=stats_back_markup(), parse_mode=ParseMode.HTML
            )
        except Exception:
            await query.message.edit_text(
                text, reply_markup=stats_back_markup(), parse_mode=ParseMode.HTML
            )
    except Exception as e:
        print(f"[stats] general error: {e}", flush=True)
    await query.answer()


@bot.on_message(filters.group & filters.incoming, group=50)
async def track_served(client, message: Message):
    try:
        if message.from_user and not message.from_user.is_bot:
            await add_served_user(message.from_user.id)
        if message.chat:
            await add_served_chat(message.chat.id)
    except Exception:
        pass


print("[stats] plugin loaded OK", flush=True)
