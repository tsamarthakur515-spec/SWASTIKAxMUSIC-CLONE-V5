# ---------------------------------------------------------------
# PANDAMUSIC — welcome.py
# /welcome on|off  |  /setwelcome  |  /resetwelcome
# Custom text + photo/video + premium emoji + colored buttons
# ---------------------------------------------------------------

print("[welcome] loading plugin...", flush=True)

import asyncio
import json
import os
import random
import re
import traceback

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import bot, console
from ..modules.custom_emojis import E, tg_emoji

try:
    from pyrogram.enums import ButtonStyle
    _PRIMARY = ButtonStyle.PRIMARY
    _SUCCESS = ButtonStyle.SUCCESS
    _DANGER = ButtonStyle.DANGER
except Exception:
    _PRIMARY = "primary"
    _SUCCESS = "success"
    _DANGER = "danger"

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DB_PATH = os.path.join(_BASE_DIR, "welcome_db.json")

DEFAULT_IMAGES = [
    "https://files.catbox.moe/nacfzm.jpg",
    "https://files.catbox.moe/x4lzbx.jpg",
    "https://files.catbox.moe/g6cmb2.jpg",
    "https://files.catbox.moe/3hxb96.jpg",
]

_S1 = tg_emoji(E.STAR_W1, "⭐")
_S2 = tg_emoji(E.STAR_W2, "⭐")
_S3 = tg_emoji(E.STAR_W3, "⭐")
_S4 = tg_emoji(E.STAR_W4, "⭐")
_S5 = tg_emoji(E.STAR_W5, "⭐")
_S6 = tg_emoji(E.STAR_W6, "⭐")

DEFAULT_TEXT = (
    "{emoji:6127214608059996162} ᴡᴇʟᴄᴏᴍᴇ ɴᴇᴡ ᴍᴇᴍʙᴇʀ ɪɴ ᴏᴜʀ ɢʀᴏᴜᴘ\n"
    "{emoji:6125264332130359953}\n\n"
    "{emoji:6138696515931085230} ηαмє ↬ {fullname}\n"
    "{emoji:6127558265573218459}\n\n"
    "{emoji:6125230925874731296} υѕєяηαмє↬ {username}\n"
    "{emoji:6136164675659766791}\n\n"
    "{emoji:6125024672955245388} υѕєя ι∂ ↬ {id}\n"
    "{emoji:6199693070238227698}\n\n"
    "{emoji:6125098305874564832} gяσυρ ↬ {chat}\n"
    "{emoji:6127296324107769784}\n\n"
    "[𝐉𝐎𝐈𝐍](buttonurl:https://t.me/Swastika_update:6327599386746425095)"
)

# [Text](buttonurl:URL)
# [Text](buttonurl:URL:success|danger|primary)
# [Text](buttonurl:URL:success:EMOJI_ID)
_BTN_RE = re.compile(
    r"\[([^\]]+)\]\(\s*buttonurl\s*:\s*(https?://[^\s\):]+|t\.me/[^\s\):]+|[^\s\):]+)"
    r"(?:\s*:\s*(success|danger|primary))?"
    r"(?:\s*:\s*(\d+))?\s*\)",
    re.IGNORECASE,
)
_BTN_ATTEMPT_RE = re.compile(r"button\s*url", re.IGNORECASE)

# {emoji:ID} or {ce:ID} — flexible spaces
_EMOJI_RE = re.compile(
    r"\{\s*(?:emoji|ce)\s*:\s*(\d{10,25})\s*\}",
    re.IGNORECASE,
)

_STYLE_MAP = {
    "success": _SUCCESS,
    "danger": _DANGER,
    "primary": _PRIMARY,
}

USAGE_TEXT = (
    "❌ <b>Usage — /setwelcome</b>\n\n"
    "• <code>/setwelcome text here</code>\n"
    "• Reply to <b>photo / video / gif</b> + <code>/setwelcome</code>\n\n"
    "<b>Placeholders:</b>\n"
    "<code>{name}</code> <code>{fullname}</code> <code>{id}</code>\n"
    "<code>{mention}</code> <code>{username}</code> <code>{chat}</code>\n\n"
    "<b>Premium emoji (kahin bhi lagao):</b>\n"
    "<code>{emoji:6327599386746425095}</code>\n"
    "short: <code>{ce:6327599386746425095}</code>\n\n"
    "<b>Example caption:</b>\n"
    "<code>{emoji:6327599386746425095} Name ➤ {name}\n"
    "{emoji:6325715141643997191} Username ➤ {username}\n"
    "{emoji:6327637478811374847} User ID ➤ {id}\n"
    "{emoji:6327883808070701100} Group ➤ {chat}</code>\n\n"
    "<b>Buttons:</b>\n"
    "<code>[Join](buttonurl:https://t.me/example)</code>\n\n"
    "<b>Colored buttons:</b>\n"
    "🟢 <code>[Join](buttonurl:https://t.me/x:success)</code>\n"
    "🔴 <code>[Ban](buttonurl:https://t.me/x:danger)</code>\n"
    "🔵 <code>[Info](buttonurl:https://t.me/x:primary)</code>\n\n"
    "<b>Color + emoji icon:</b>\n"
    "<code>[Join](buttonurl:https://t.me/x:success:6327599386746425095)</code>\n\n"
    "⚠️ Bot restart ke baad /setwelcome dobara set karo"
)


def _normalize_url(url: str) -> str:
    url = (url or "").strip().rstrip(")")
    url = re.sub(r"^(https?):?/{1,2}", lambda m: m.group(1) + "://", url, flags=re.IGNORECASE)
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url.lstrip("/")
    return url


def _load_db() -> dict:
    try:
        if os.path.exists(_DB_PATH):
            with open(_DB_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_db(data: dict):
    try:
        with open(_DB_PATH, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[welcome] save error: {e}", flush=True)


def _default_cfg():
    return {
        "enabled": True,
        "text": None,
        "media": None,
        "media_type": None,
        "buttons": [],
    }


def _chat_cfg(chat_id: int) -> dict:
    db = _load_db()
    key = str(chat_id)
    if key not in db:
        db[key] = _default_cfg()
        _save_db(db)
    cfg = db[key]
    if cfg.get("photo") and not cfg.get("media"):
        cfg["media"] = cfg["photo"]
        cfg["media_type"] = "photo"
    return cfg


def _set_chat_cfg(chat_id: int, **kwargs):
    db = _load_db()
    key = str(chat_id)
    cfg = db.get(key) or _default_cfg()
    cfg.update(kwargs)
    db[key] = cfg
    _save_db(db)


def is_enabled(chat_id: int) -> bool:
    return bool(_chat_cfg(chat_id).get("enabled", True))


def parse_custom_emojis(text: str) -> str:
    """{emoji:ID} / {ce:ID} → <tg-emoji> HTML tags."""
    if not text:
        return text or ""

    def _repl(m):
        return f'<tg-emoji emoji-id="{m.group(1)}">⭐</tg-emoji>'

    return _EMOJI_RE.sub(_repl, text)


def parse_buttons(text: str):
    if not text:
        return text, [], 0
    buttons = []
    for m in _BTN_RE.finditer(text):
        btn = {
            "text": m.group(1).strip(),
            "url": _normalize_url(m.group(2)),
        }
        style = (m.group(3) or "").lower()
        if style in _STYLE_MAP:
            btn["style"] = style
        emoji_id = m.group(4)
        if emoji_id:
            btn["emoji_id"] = emoji_id
        buttons.append(btn)
    clean = _BTN_RE.sub("", text).strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    total_attempts = len(_BTN_ATTEMPT_RE.findall(text))
    unparsed = max(0, total_attempts - len(buttons))
    return clean, buttons, unparsed


def _make_button(b: dict) -> InlineKeyboardButton:
    text = b.get("text") or "Button"
    url = b.get("url") or "https://t.me"
    style = b.get("style")
    emoji_id = b.get("emoji_id")

    # Visual color hint in text if style set (works on all clients)
    if style == "success" and not text.startswith(("🟢", "✅")):
        text = f"🟢 {text}"
    elif style == "danger" and not text.startswith(("🔴", "⛔", "❌")):
        text = f"🔴 {text}"
    elif style == "primary" and not text.startswith(("🔵", "ℹ️")):
        text = f"🔵 {text}"

    kwargs = {"url": url}
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = str(emoji_id)

    style_obj = _STYLE_MAP.get(style) if style else None
    if style_obj is not None:
        try:
            return InlineKeyboardButton(text, style=style_obj, **kwargs)
        except TypeError:
            pass
        try:
            return InlineKeyboardButton(text, style=str(style), **kwargs)
        except TypeError:
            pass
    try:
        return InlineKeyboardButton(text, **kwargs)
    except TypeError:
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(text, url=url)


def build_markup(buttons: list):
    if not buttons:
        return None
    rows, row = [], []
    for b in buttons:
        row.append(_make_button(b))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def format_welcome(template: str, user, chat_title: str) -> str:
    name = user.first_name or "User"
    last = user.last_name or ""
    fullname = f"{name} {last}".strip()
    mention = f'<a href="tg://user?id={user.id}">{name}</a>'
    username = f"@{user.username}" if user.username else "N/A"
    text = template or DEFAULT_TEXT
    # Placeholders first
    text = text.replace("{name}", name)
    text = text.replace("{fullname}", fullname)
    text = text.replace("{id}", str(user.id))
    text = text.replace("{mention}", mention)
    text = text.replace("{username}", username)
    text = text.replace("{chat}", chat_title or "Group")
    text = text.replace("{chat_title}", chat_title or "Group")
    # Always convert emoji placeholders (even if already partially HTML)
    text = parse_custom_emojis(text)
    return text


async def is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        if user_id and user_id == getattr(console, "OWNER_ID", 0):
            return True
        if user_id in getattr(console, "sudoers", []):
            return True
    except Exception:
        pass
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


async def _send(client, chat_id, text):
    try:
        return await client.send_message(chat_id, text, parse_mode=ParseMode.HTML)
    except Exception:
        try:
            return await client.send_message(chat_id, text)
        except Exception as e:
            print(f"[welcome] send error: {e}", flush=True)


async def _delete_later(msg, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def _send_welcome(client, chat_id, caption, media, media_type, markup):
    kwargs = dict(caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    try:
        if media and media_type == "video":
            return await client.send_video(chat_id, video=media, **kwargs)
        if media and media_type == "animation":
            return await client.send_animation(chat_id, animation=media, **kwargs)
        if media and media_type == "photo":
            return await client.send_photo(chat_id, photo=media, **kwargs)
        try:
            return await client.send_photo(
                chat_id, photo=random.choice(DEFAULT_IMAGES), **kwargs
            )
        except Exception:
            return await client.send_message(
                chat_id, caption, parse_mode=ParseMode.HTML, reply_markup=markup
            )
    except Exception as e:
        print(f"[welcome] _send_welcome error: {e}", flush=True)
        traceback.print_exc()
        # Fallback without parse_mode if HTML fails
        try:
            return await client.send_message(chat_id, caption, reply_markup=markup)
        except Exception:
            return None


@bot.on_message(filters.command(["welcome"], ["/", "!", "."]) & ~filters.private & filters.incoming, group=0)
async def welcome_toggle(client, msg: Message):
    chat_id = msg.chat.id
    try:
        await msg.delete()
    except Exception:
        pass
    if not msg.from_user:
        return
    if not await is_admin(client, chat_id, msg.from_user.id):
        return await _send(client, chat_id, "❌ <b>Only admins can use this!</b>")
    args = msg.command or []
    if len(args) < 2 or args[1].lower() not in ("on", "off"):
        status = "✅ ON" if is_enabled(chat_id) else "❌ OFF"
        return await _send(
            client,
            chat_id,
            f"<b>👋 Welcome Status:</b> {status}\n\n"
            f"➻ /welcome on\n"
            f"➻ /welcome off\n"
            f"➻ /setwelcome — text / photo / video + emoji + buttons\n"
            f"➻ /resetwelcome — reset default",
        )
    if args[1].lower() == "on":
        _set_chat_cfg(chat_id, enabled=True)
        await _send(client, chat_id, "✅ <b>Welcome messages ENABLED!</b>")
    else:
        _set_chat_cfg(chat_id, enabled=False)
        await _send(client, chat_id, "❌ <b>Welcome messages DISABLED!</b>")


@bot.on_message(filters.command(["setwelcome"], ["/", "!", "."]) & ~filters.private & filters.incoming, group=0)
async def set_welcome(client, msg: Message):
    chat_id = msg.chat.id
    try:
        await msg.delete()
    except Exception:
        pass
    if not msg.from_user:
        return
    if not await is_admin(client, chat_id, msg.from_user.id):
        return await _send(client, chat_id, "❌ <b>Only admins can set welcome!</b>")

    media = None
    media_type = None
    raw_text = None

    if msg.reply_to_message:
        r = msg.reply_to_message
        if r.video:
            media = r.video.file_id
            media_type = "video"
            raw_text = r.caption or ""
        elif r.animation:
            media = r.animation.file_id
            media_type = "animation"
            raw_text = r.caption or ""
        elif r.photo:
            media = r.photo.file_id
            media_type = "photo"
            raw_text = r.caption or ""
        elif r.text:
            raw_text = r.text
        elif r.caption:
            raw_text = r.caption
        parts = (msg.text or "").split(None, 1)
        if len(parts) > 1 and parts[1].strip():
            extra = parts[1].strip()
            raw_text = (extra + "\n" + raw_text) if raw_text else extra

    if raw_text is None:
        parts = (msg.text or "").split(None, 1)
        if len(parts) > 1:
            raw_text = parts[1]

    if not raw_text and not media:
        return await _send(client, chat_id, USAGE_TEXT)

    clean, buttons, unparsed = parse_buttons(raw_text or "")
    # Convert emoji placeholders → HTML before saving
    if clean:
        clean = parse_custom_emojis(clean)

    _set_chat_cfg(
        chat_id,
        enabled=True,
        text=clean or None,
        media=media,
        media_type=media_type,
        photo=None,
        buttons=buttons,
    )

    media_label = media_type or "None"
    warn = ""
    if unparsed:
        warn = (
            f"\n\n⚠️ <b>{unparsed} button parse nahi hua</b>\n"
            f"Format: <code>[Text](buttonurl:https://t.me/x)</code>\n"
            f"Color: <code>:success</code> / <code>:danger</code> / <code>:primary</code>"
        )

    # Preview with HTML so admin sees real emojis
    preview = (clean or DEFAULT_TEXT)[:400]
    await _send(
        client,
        chat_id,
        f"✅ <b>Welcome set!</b>\n\n"
        f"Media: <code>{media_label}</code>\n"
        f"Buttons: <b>{len(buttons)}</b>\n"
        f"Preview:\n{preview}{warn}",
    )


@bot.on_message(filters.command(["resetwelcome"], ["/", "!", "."]) & ~filters.private & filters.incoming, group=0)
async def reset_welcome(client, msg: Message):
    chat_id = msg.chat.id
    try:
        await msg.delete()
    except Exception:
        pass
    if not msg.from_user:
        return
    if not await is_admin(client, chat_id, msg.from_user.id):
        return await _send(client, chat_id, "❌ <b>Only admins can reset welcome!</b>")
    _set_chat_cfg(chat_id, text=None, media=None, media_type=None, photo=None, buttons=[], enabled=True)
    await _send(client, chat_id, "✅ <b>Welcome reset to default!</b>")


@bot.on_message(filters.new_chat_members & filters.group, group=99)
async def welcome_new_member(client, message: Message):
    chat_id = message.chat.id
    if not is_enabled(chat_id):
        return
    cfg = _chat_cfg(chat_id)
    chat_title = message.chat.title or "this group"
    try:
        me = client.me or await client.get_me()
    except Exception:
        me = None
    for user in message.new_chat_members:
        if me and user.id == me.id:
            continue
        if user.is_bot:
            continue
        template = cfg.get("text") or DEFAULT_TEXT
        # Parse buttons from template if using default (so JOIN button works)
        if not cfg.get("text"):
            clean, buttons, _ = parse_buttons(DEFAULT_TEXT)
            caption = format_welcome(clean, user, chat_title)
            markup = build_markup(buttons)
        else:
            caption = format_welcome(template, user, chat_title)
            buttons = cfg.get("buttons") or []
            markup = build_markup(buttons)
        media = cfg.get("media") or cfg.get("photo")
        media_type = cfg.get("media_type") or ("photo" if media else None)
        try:
            wel = await _send_welcome(client, chat_id, caption, media, media_type, markup)
            if wel:
                asyncio.create_task(_delete_later(wel, 300))
        except Exception:
            print("[welcome] send failed:", flush=True)
            traceback.print_exc()


print("[welcome] plugin loaded OK", flush=True)