# ---------------------------------------------------------------
# Clone menu UI — HELP → CLONE → token paste → progressive edits
# ---------------------------------------------------------------

print("[clone_ui] loading...", flush=True)

import asyncio
import re
import traceback

from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import bot, rgx, console
from ..modules.formatters import smallcaps
from ..modules.custom_emojis import E, tg_emoji
from ..modules.bot_api import bot_api_edit_message, bot_api_answer_callback, resolve_token

try:
    from pyrogram.enums import ButtonStyle

    _PRIMARY = ButtonStyle.PRIMARY
    _SUCCESS = ButtonStyle.SUCCESS
    _DANGER = ButtonStyle.DANGER
except Exception:
    _PRIMARY = "primary"
    _SUCCESS = "success"
    _DANGER = "danger"

E_HELP = "6154314112236001069"
E_CMD = "5823571441118876120"

TOKEN_FIND = re.compile(r"(\d{5,15}:[A-Za-z0-9_-]{20,100})")

# uid -> {chat_id, message_id, is_photo, client_token}
_ui_pending: dict = {}


def _btn(text: str, style=None, **kwargs) -> InlineKeyboardButton:
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


def clone_menu_caption() -> str:
    body = (
        f"{smallcaps('clone bot')}\n\n"
        f"{smallcaps('send your botfather token here in one line.')}\n\n"
        f"{smallcaps('example')}:\n"
        f"<code>123456789:AAHxxxxxxxx</code>\n\n"
        f"{smallcaps('or tap check clone to see your running clones.')}"
    )
    return f"<blockquote expandable>{tg_emoji(E.SPARKLES, '✨')} {body}</blockquote>"


def clone_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _btn(
                    smallcaps("check clone"),
                    _SUCCESS,
                    callback_data="check_clone",
                    icon_custom_emoji_id=E_CMD,
                )
            ],
            [
                _btn(
                    smallcaps("« back"),
                    _DANGER,
                    callback_data="help_menu",
                    icon_custom_emoji_id=E_HELP,
                )
            ],
        ]
    )


def clone_close_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _btn(
                    smallcaps("close"),
                    _DANGER,
                    callback_data="clone_close",
                    icon_custom_emoji_id=E_CMD,
                )
            ]
        ]
    )


def _looks_like_token(t: str) -> bool:
    t = re.sub(r"\s+", "", (t or "").strip())
    if not t or ":" not in t:
        return False
    left, right = t.split(":", 1)
    return left.isdigit() and 5 <= len(left) <= 15 and len(right) >= 20


async def _answer(query, text="", show_alert=False, client=None):
    try:
        await query.answer(text, show_alert=show_alert)
    except Exception:
        try:
            await bot_api_answer_callback(
                query.id,
                text=text,
                show_alert=show_alert,
                bot_token=resolve_token(client=client),
            )
        except Exception:
            pass


async def _edit_ui(client, chat_id, message_id, is_photo, caption, markup):
    token = resolve_token(client=client)
    ok = await bot_api_edit_message(
        chat_id=chat_id,
        message_id=message_id,
        text=caption,
        caption=caption,
        reply_markup=markup,
        is_photo=is_photo,
        bot_token=token,
    )
    if ok:
        return True
    # try without markup
    return await bot_api_edit_message(
        chat_id=chat_id,
        message_id=message_id,
        text=caption,
        caption=caption,
        is_photo=is_photo,
        bot_token=token,
    )


@bot.on_callback_query(rgx("clone_menu"))
async def clone_menu_cb(client, query):
    if not query.from_user:
        return
    uid = query.from_user.id
    msg = query.message
    _ui_pending[uid] = {
        "chat_id": msg.chat.id,
        "message_id": msg.id,
        "is_photo": bool(getattr(msg, "photo", None)),
    }
    await _edit_ui(
        client,
        msg.chat.id,
        msg.id,
        bool(getattr(msg, "photo", None)),
        clone_menu_caption(),
        clone_menu_markup(),
    )
    await _answer(query, client=client)


@bot.on_callback_query(rgx("check_clone"))
async def check_clone_cb(client, query):
    if not query.from_user:
        return
    uid = query.from_user.id
    try:
        from ..modules.clones import db_list_clones, get_running_clones

        rows = await db_list_clones(uid)
        running_ids = {
            c["bot_id"] for c in get_running_clones() if c["owner_id"] == uid
        }
        seen = {}
        for r in rows:
            seen[int(r["bot_id"])] = r
        for c in get_running_clones():
            if c["owner_id"] == uid:
                seen[int(c["bot_id"])] = {**seen.get(int(c["bot_id"]), {}), **c}

        if not seen:
            body = (
                f"{smallcaps('your clones')}\n\n"
                f"{smallcaps('no clones yet.')}\n"
                f"{smallcaps('send a bot token to create one.')}"
            )
        else:
            lines = [f"{smallcaps('your clones')}\n"]
            for i, (bid, r) in enumerate(seen.items(), 1):
                un = r.get("username") or ""
                tag = f"@{un}" if un else str(bid)
                online = "🟢" if bid in running_ids else "🔴"
                lines.append(f"{i}. {online} {tag}\n   {smallcaps('id')}: <code>{bid}</code>")
            body = "\n".join(lines)

        caption = f"<blockquote expandable>{tg_emoji(E.STAR, '🌟')} {body}</blockquote>"
        markup = InlineKeyboardMarkup(
            [
                [
                    _btn(
                        smallcaps("« back"),
                        _DANGER,
                        callback_data="clone_menu",
                        icon_custom_emoji_id=E_HELP,
                    )
                ]
            ]
        )
        msg = query.message
        await _edit_ui(
            client,
            msg.chat.id,
            msg.id,
            bool(getattr(msg, "photo", None)),
            caption,
            markup,
        )
    except Exception as e:
        print(f"[clone_ui] check fail: {e}", flush=True)
        traceback.print_exc()
    await _answer(query, client=client)


@bot.on_callback_query(rgx("clone_close"))
async def clone_close_cb(client, query):
    try:
        await query.message.delete()
    except Exception:
        try:
            await query.message.edit_text(smallcaps("closed"))
        except Exception:
            pass
    await _answer(query, client=client)


@bot.on_message(filters.private & filters.text & filters.incoming, group=-3)
async def clone_ui_token_paste(client, message: Message):
    if not message.from_user:
        return
    uid = message.from_user.id
    pending = _ui_pending.get(uid)
    if not pending:
        return

    text = re.sub(r"\s+", "", (message.text or "").strip())
    m = TOKEN_FIND.search(text)
    token = m.group(1) if m else text
    if not _looks_like_token(token):
        return  # not a token — ignore (other handlers may use it)

    _ui_pending.pop(uid, None)
    chat_id = pending["chat_id"]
    message_id = pending["message_id"]
    is_photo = pending.get("is_photo", True)

    # delete user token message
    try:
        await message.delete()
    except Exception:
        pass

    empty_kb = InlineKeyboardMarkup([])

    # 1) cloning...
    await _edit_ui(
        client,
        chat_id,
        message_id,
        is_photo,
        f"<blockquote expandable>{tg_emoji(E.LIGHTNING, '⚡')} {smallcaps('cloning your bot.......')}</blockquote>",
        empty_kb,
    )
    await asyncio.sleep(1.0)

    # 2) starting...
    await _edit_ui(
        client,
        chat_id,
        message_id,
        is_photo,
        f"<blockquote expandable>{tg_emoji(E.SPARKLES, '✨')} {smallcaps('starting your bot.....')}</blockquote>",
        empty_kb,
    )

    try:
        from ..modules.clones import is_bot_token, start_clone_client, user_can_clone

        if not is_bot_token(token):
            await _edit_ui(
                client,
                chat_id,
                message_id,
                is_photo,
                f"<blockquote expandable>❌ {smallcaps('invalid token format')}</blockquote>",
                clone_menu_markup(),
            )
            _ui_pending[uid] = pending
            return

        ok, reason = await user_can_clone(uid)
        if not ok:
            await _edit_ui(
                client,
                chat_id,
                message_id,
                is_photo,
                f"<blockquote expandable>❌ {smallcaps(reason)}</blockquote>",
                clone_menu_markup(),
            )
            return

        entry = await start_clone_client(token, uid)
    except Exception as e:
        print(f"[clone_ui] start fail: {e}", flush=True)
        traceback.print_exc()
        await _edit_ui(
            client,
            chat_id,
            message_id,
            is_photo,
            f"<blockquote expandable>❌ {smallcaps('clone fail')}\n<code>{str(e)[:300]}</code></blockquote>",
            clone_menu_markup(),
        )
        return

    await asyncio.sleep(0.6)

    uname = (entry.get("username") or "").strip()
    bot_id = entry.get("bot_id")
    who = f"@{uname}" if uname else str(bot_id)
    body = (
        f"{smallcaps('bot started')}\n\n"
        f"{smallcaps('username')} : <b>{who}</b>\n"
        f"{smallcaps('userid')} : <code>{bot_id}</code>"
    )
    caption = f"<blockquote expandable>{tg_emoji(E.CHECK, '✅')} {body}</blockquote>"
    await _edit_ui(
        client, chat_id, message_id, is_photo, caption, clone_close_markup()
    )


print("[clone_ui] loaded OK", flush=True)
