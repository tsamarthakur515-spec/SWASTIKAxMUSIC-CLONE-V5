# ---------------------------------------------------------------
# SWASTIKA MUSIC — ping.py
# Loading emoji → final photo · smallcaps · custom status badges
# ---------------------------------------------------------------

print("[ping] loading plugin...", flush=True)

import asyncio
import io
import time
from typing import Optional, Union

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import bot, console, cdx
from ..modules.custom_emojis import tg_emoji, CE_CLOSE
from ..modules.formatters import smallcaps

try:
    from pyrogram.enums import ButtonStyle

    _SUCCESS = ButtonStyle.SUCCESS
    _PRIMARY = ButtonStyle.PRIMARY
    _DANGER = ButtonStyle.DANGER
except Exception:
    _SUCCESS = "success"
    _PRIMARY = "primary"
    _DANGER = "danger"

try:
    import aiohttp
except Exception:
    aiohttp = None

# Line icon
CE_PING = "6111504695728020416"
# Loading
CE_LOAD = "6089090515540644835"
# Extra badges (user provided)
CE_OK = "6154273803967929315"      # excellent / online
CE_GOOD = "6154678544506034045"    # good
CE_WARN = "6152468036507934048"    # average / offline
CE_BAD = "5823633434676827622"     # slow / error

PING_IMAGE = "https://files.catbox.moe/wfqfeh.jpg"
CHANNEL_URL = "https://t.me/Swastika_update"
_VERSION = "v5.0.0"

_PHOTO_BYTES: Optional[bytes] = None


def em(emoji_id: str = CE_PING, fallback: str = "⚡") -> str:
    return tg_emoji(emoji_id, fallback)


def load_em(fallback: str = "✨") -> str:
    return tg_emoji(CE_LOAD, fallback)


def q(line: str) -> str:
    return f"<blockquote>{line}</blockquote>"


def _boot_ts() -> float:
    return float(getattr(console, "_boot_", None) or time.time())


def _get_uptime() -> str:
    elapsed = max(0, int(time.time() - _boot_ts()))
    days, rem = divmod(elapsed, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def _latency_label(ms: int) -> str:
    if ms <= 0:
        return f"{em(CE_WARN, '⚪')} N/A"
    if ms < 80:
        return f"{em(CE_OK, '🟢')} Excellent"
    if ms < 150:
        return f"{em(CE_GOOD, '🟡')} Good"
    if ms < 300:
        return f"{em(CE_WARN, '🟠')} Average"
    return f"{em(CE_BAD, '🔴')} Slow"


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


def _owner_url() -> str:
    owner = (getattr(console, "OWNER_USERNAME", None) or "").lstrip("@")
    if owner:
        return f"https://t.me/{owner}"
    oid = getattr(console, "OWNER_ID", 0) or 0
    if oid:
        return f"tg://user?id={oid}"
    return "https://t.me/tsamarthakur515"


def _support_url() -> Optional[str]:
    chat = (getattr(console, "SUPPORT_CHAT", None) or "").lstrip("@")
    if not chat:
        return None
    if chat.startswith("http"):
        return chat
    if chat.startswith("+"):
        return f"https://t.me/{chat}"
    return f"https://t.me/{chat}"


def _channel_url() -> str:
    ch = (getattr(console, "SUPPORT_CHANNEL", None) or "").lstrip("@")
    if ch:
        if ch.startswith("http"):
            return ch
        return f"https://t.me/{ch}"
    return CHANNEL_URL


def _ping_keyboard() -> InlineKeyboardMarkup:
    row1 = [
        _btn(smallcaps("owner"), style=_SUCCESS, emoji_id=CE_PING, url=_owner_url())
    ]
    support = _support_url()
    if support:
        row1.append(
            _btn(smallcaps("support"), style=_PRIMARY, emoji_id=CE_PING, url=support)
        )
    rows = [row1]
    row2 = [
        _btn(
            smallcaps("updates"),
            style=_PRIMARY,
            emoji_id=CE_PING,
            url=_channel_url(),
        ),
        _btn(smallcaps("close"), style=_DANGER, emoji_id=CE_CLOSE, callback_data="close"),
    ]
    rows.append(row2)
    return InlineKeyboardMarkup(rows)


async def _get_latency(client) -> int:
    try:
        t0 = time.perf_counter()
        await asyncio.wait_for(client.get_me(), timeout=1.5)
        return int(round((time.perf_counter() - t0) * 1000))
    except Exception as e:
        print(f"[ping] latency skip: {e}", flush=True)
        return 0


async def _db_status() -> str:
    try:
        from ..modules.database import _ok, _pool

        if not _ok() or _pool is None:
            return f"{em(CE_WARN, '⚪')} Offline"
        async with _pool.acquire() as conn:
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=1.0)
        return f"{em(CE_OK, '🟢')} Online"
    except Exception:
        return f"{em(CE_BAD, '🔴')} Error"


def _ping_photo_url() -> str:
    url = getattr(console, "PING_IMAGE_URL", None) or PING_IMAGE
    if url and str(url).startswith("http"):
        return str(url)
    return PING_IMAGE


async def _load_photo() -> Union[str, io.BytesIO]:
    global _PHOTO_BYTES
    url = _ping_photo_url()

    if _PHOTO_BYTES:
        bio = io.BytesIO(_PHOTO_BYTES)
        bio.name = "ping.jpg"
        return bio

    if aiohttp is not None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if data and len(data) > 1000:
                            _PHOTO_BYTES = data
                            bio = io.BytesIO(data)
                            bio.name = "ping.jpg"
                            print(f"[ping] image downloaded {len(data)} bytes", flush=True)
                            return bio
        except Exception as e:
            print(f"[ping] download fail: {e}", flush=True)

    return url


async def _build_caption(client, ms: int, uptime: str, db: str) -> str:
    me = getattr(client, "me", None)
    if me is None:
        try:
            me = await client.get_me()
        except Exception:
            me = None
    uname = (getattr(me, "username", None) or "Swastika_musics_bot").lstrip("@")
    label = _latency_label(ms)
    ms_text = f"{ms}ms" if ms > 0 else "—"
    channel = _channel_url()

    lines = [
        q(f"{em()} <b>{smallcaps('swastika music v5')}</b>"),
        q(f"{em()} <b>@{uname}</b> — {smallcaps('system live')}"),
        q(f"{em()} <b>{smallcaps('version')}</b> : <code>{_VERSION}</code>"),
        q(f"{em()} <b>{smallcaps('latency')}</b> : <code>{ms_text}</code> · {label}"),
        q(f"{em()} <b>{smallcaps('uptime')}</b> : <code>{uptime}</code>"),
        q(f"{em()} <b>{smallcaps('status')}</b> : {db}"),
        q(
            f'{em()} <a href="{channel}"><b>{smallcaps("powered by swastika music")}</b></a>'
        ),
    ]
    return "\n".join(lines)


@bot.on_message(cdx("ping") & filters.incoming)
async def ping_command(client, message: Message):
    print("[ping] command received", flush=True)

    chat_id = message.chat.id

    try:
        await message.delete()
    except Exception:
        pass

    loading = None
    try:
        loading = await client.send_message(
            chat_id=chat_id,
            text=(
                f"{load_em()} <b>{smallcaps('ping')}</b>"
                f"{smallcaps('......')}"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        print(f"[ping] loading send fail: {e}", flush=True)

    t0 = time.perf_counter()
    photo_task = asyncio.create_task(_load_photo())
    ms_task = asyncio.create_task(_get_latency(client))
    db_task = asyncio.create_task(_db_status())

    ms, db, photo = await asyncio.gather(ms_task, db_task, photo_task)

    elapsed = time.perf_counter() - t0
    wait_more = max(0.0, 1.25 - elapsed)
    if wait_more:
        await asyncio.sleep(wait_more)

    if loading is not None:
        try:
            await loading.delete()
        except Exception:
            pass

    uptime = _get_uptime()
    final = await _build_caption(client, ms, uptime, db)
    keyboard = _ping_keyboard()

    try:
        await client.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=final,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        print(f"[ping] ok photo ms={ms} db={db}", flush=True)
        return
    except Exception as e:
        print(f"[ping] send_photo+kb failed: {e}", flush=True)

    try:
        plain_row1 = [InlineKeyboardButton(smallcaps("owner"), url=_owner_url())]
        support = _support_url()
        if support:
            plain_row1.append(
                InlineKeyboardButton(smallcaps("support"), url=support)
            )
        plain_kb = InlineKeyboardMarkup(
            [
                plain_row1,
                [
                    InlineKeyboardButton(smallcaps("updates"), url=_channel_url()),
                    InlineKeyboardButton(smallcaps("close"), callback_data="close"),
                ],
            ]
        )
        if isinstance(photo, io.BytesIO):
            photo.seek(0)
        await client.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=final,
            reply_markup=plain_kb,
            parse_mode=ParseMode.HTML,
        )
        print(f"[ping] ok plain photo ms={ms}", flush=True)
        return
    except Exception as e2:
        print(f"[ping] plain photo failed: {e2}", flush=True)

    try:
        if isinstance(photo, io.BytesIO):
            photo.seek(0)
        await client.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=final,
            parse_mode=ParseMode.HTML,
        )
        print(f"[ping] ok photo no-kb ms={ms}", flush=True)
        return
    except Exception as e3:
        print(f"[ping] photo no-kb failed: {e3}", flush=True)

    try:
        await client.send_message(
            chat_id=chat_id,
            text=final,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        print(f"[ping] ok text ms={ms}", flush=True)
    except Exception as e4:
        print(f"[ping] text failed: {e4}", flush=True)


print("[ping] plugin loaded OK", flush=True)
