# ---------------------------------------------------------------
# Clone menu UI — create / check / delete with progressive captions
# ---------------------------------------------------------------

print("[clone_ui] loading...", flush=True)

import asyncio
import re
import traceback

from pyrogram import filters
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
ID_FIND = re.compile(r"^\d{5,15}$")

# uid -> {chat_id, message_id, is_photo, mode: create|delete}
_ui_pending: dict = {}
# uid -> True after UI handled a paste so clone.py does not also clone
_ui_consumed: dict = {}


def clear_ui_pending(uid: int):
    _ui_pending.pop(uid, None)


def mark_ui_consumed(uid: int):
    _ui_consumed[uid] = True


def clear_ui_consumed(uid: int):
    _ui_consumed.pop(uid, None)


def was_ui_consumed(uid: int) -> bool:
    return bool(_ui_consumed.get(uid))


def get_ui_mode(uid: int):
    p = _ui_pending.get(uid)
    return (p or {}).get("mode")


def _running_on_clone(client) -> bool:
    try:
        from ..modules.clones import is_clone_client
        return bool(is_clone_client(client))
    except Exception:
        return False


def _clear_cmd_pending(uid: int):
    """Stop /clone text-paste handler from also firing."""
    try:
        from . import clone as clone_mod

        if hasattr(clone_mod, "_pending_token"):
            clone_mod._pending_token.pop(uid, None)
    except Exception:
        pass


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
        f"{smallcaps('send your botfather token here in one line to create a clone.')}\n\n"
        f"{smallcaps('example')}:\n"
        f"<code>123456789:AAHxxxxxxxx</code>\n\n"
        f"{smallcaps('use check clone or delete clone buttons below.')}"
    )
    return f"<blockquote expandable>{tg_emoji(E.SPARKLES, '✨')} {body}</blockquote>"


def delete_menu_caption() -> str:
    body = (
        f"{smallcaps('delete clone')}\n\n"
        f"{smallcaps('send bot token or bot id of the clone you want to remove.')}\n\n"
        f"{smallcaps('this will only delete — it will not create a new clone.')}\n\n"
        f"{smallcaps('example token')}:\n"
        f"<code>123456789:AAHxxxxxxxx</code>\n\n"
        f"{smallcaps('example id')}:\n"
        f"<code>123456789</code>"
    )
    return f"<blockquote expandable>{tg_emoji(E.FIRE, '🔥')} {body}</blockquote>"


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
                    smallcaps("delete clone"),
                    _DANGER,
                    callback_data="clone_del_menu",
                    icon_custom_emoji_id=E_CMD,
                )
            ],
            [
                _btn(
                    smallcaps("« back"),
                    _PRIMARY,
                    callback_data="help_menu",
                    icon_custom_emoji_id=E_HELP,
                )
            ],
        ]
    )


def delete_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
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


def _looks_like_bot_id(t: str) -> bool:
    t = re.sub(r"\s+", "", (t or "").strip())
    return bool(ID_FIND.match(t))


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
    return await bot_api_edit_message(
        chat_id=chat_id,
        message_id=message_id,
        text=caption,
        caption=caption,
        is_photo=is_photo,
        bot_token=token,
    )


def _set_pending(uid, msg, mode: str):
    _ui_pending[uid] = {
        "chat_id": msg.chat.id,
        "message_id": msg.id,
        "is_photo": bool(getattr(msg, "photo", None)),
        "mode": mode,  # MUST be "create" or "delete"
    }
    _clear_cmd_pending(uid)
    print(f"[clone_ui] pending uid={uid} mode={mode}", flush=True)


@bot.on_callback_query(rgx(r"^clone_menu$"))
async def clone_menu_cb(client, query):
    if not query.from_user:
        return
    if _running_on_clone(client):
        await _answer(query, "Clone panel sirf main bot pe hai.", show_alert=True, client=client)
        return
    data = (getattr(query, "data", None) or "").strip()
    if data != "clone_menu":
        return
    msg = query.message
    clear_ui_consumed(query.from_user.id)
    _set_pending(query.from_user.id, msg, "create")
    await _edit_ui(
        client,
        msg.chat.id,
        msg.id,
        bool(getattr(msg, "photo", None)),
        clone_menu_caption(),
        clone_menu_markup(),
    )
    await _answer(query, client=client)


@bot.on_callback_query(rgx(r"^(clone_del_menu|delete_clone_menu)$"))
async def delete_clone_menu_cb(client, query):
    if not query.from_user:
        return
    if _running_on_clone(client):
        await _answer(query, "Clone panel sirf main bot pe hai.", show_alert=True, client=client)
        return
    data = (getattr(query, "data", None) or "").strip()
    if data not in ("clone_del_menu", "delete_clone_menu"):
        return
    msg = query.message
    # FORCE delete mode — never create from this screen
    clear_ui_consumed(query.from_user.id)
    _set_pending(query.from_user.id, msg, "delete")
    await _edit_ui(
        client,
        msg.chat.id,
        msg.id,
        bool(getattr(msg, "photo", None)),
        delete_menu_caption(),
        delete_menu_markup(),
    )
    await _answer(query, client=client)


@bot.on_callback_query(rgx(r"^check_clone$"))
async def check_clone_cb(client, query):
    if not query.from_user:
        return
    if _running_on_clone(client):
        await _answer(query, "Check clone sirf main bot pe hai.", show_alert=True, client=client)
        return
    uid = query.from_user.id
    # listing only — clear any create/delete paste wait
    clear_ui_pending(uid)
    _clear_cmd_pending(uid)
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
                lines.append(
                    f"{i}. {online} {tag}\n   {smallcaps('id')}: <code>{bid}</code>"
                )
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


@bot.on_callback_query(rgx(r"^clone_close$"))
async def clone_close_cb(client, query):
    if query.from_user:
        clear_ui_pending(query.from_user.id)
        _clear_cmd_pending(query.from_user.id)
    try:
        await query.message.delete()
    except Exception:
        try:
            await query.message.edit_text(smallcaps("closed"))
        except Exception:
            pass
    await _answer(query, client=client)


async def _do_create(client, uid, token, chat_id, message_id, is_photo, pending):
    empty_kb = InlineKeyboardMarkup([])

    await _edit_ui(
        client,
        chat_id,
        message_id,
        is_photo,
        f"<blockquote expandable>{tg_emoji(E.LIGHTNING, '⚡')} {smallcaps('cloning your bot.......')}</blockquote>",
        empty_kb,
    )
    await asyncio.sleep(1.0)

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
            _set_pending_raw(uid, pending, "create")
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

    await asyncio.sleep(0.5)
    uname = (entry.get("username") or "").strip()
    bot_id = entry.get("bot_id")
    who = f"@{uname}" if uname else str(bot_id)
    body = (
        f"{smallcaps('bot started')}\n\n"
        f"{smallcaps('username')} : <b>{who}</b>\n"
        f"{smallcaps('userid')} : <code>{bot_id}</code>"
    )
    caption = f"<blockquote expandable>{tg_emoji(E.CHECK, '✅')} {body}</blockquote>"
    await _edit_ui(client, chat_id, message_id, is_photo, caption, clone_close_markup())


def _set_pending_raw(uid, pending, mode):
    _ui_pending[uid] = {**pending, "mode": mode}
    _clear_cmd_pending(uid)


async def _do_delete(client, uid, raw, chat_id, message_id, is_photo, pending):
    """ONLY delete — never start_clone_client."""
    empty_kb = InlineKeyboardMarkup([])
    print(f"[clone_ui] DELETE path uid={uid} raw_len={len(raw)}", flush=True)

    await _edit_ui(
        client,
        chat_id,
        message_id,
        is_photo,
        f"<blockquote expandable>{tg_emoji(E.FIRE, '🔥')} {smallcaps('deleting your bot.......')}</blockquote>",
        empty_kb,
    )
    await asyncio.sleep(0.9)

    await _edit_ui(
        client,
        chat_id,
        message_id,
        is_photo,
        f"<blockquote expandable>{tg_emoji(E.LIGHTNING, '⚡')} {smallcaps('removing clone.....')}</blockquote>",
        empty_kb,
    )

    target_id = None
    try:
        from ..modules.clones import (
            db_list_clones,
            get_running_clones,
            stop_clone_client,
        )

        raw = re.sub(r"\s+", "", raw.strip())

        if _looks_like_token(raw):
            for r in await db_list_clones(uid):
                if (r.get("bot_token") or "").strip() == raw:
                    target_id = int(r["bot_id"])
                    break
            if target_id is None:
                # token prefix is usually the bot id
                try:
                    maybe = int(raw.split(":", 1)[0])
                    for r in await db_list_clones(uid):
                        if int(r["bot_id"]) == maybe:
                            target_id = maybe
                            break
                    if target_id is None:
                        for c in get_running_clones():
                            if int(c["bot_id"]) == maybe and int(c["owner_id"]) == uid:
                                target_id = maybe
                                break
                except Exception:
                    pass
        elif _looks_like_bot_id(raw):
            target_id = int(raw)

        if not target_id:
            await _edit_ui(
                client,
                chat_id,
                message_id,
                is_photo,
                f"<blockquote expandable>❌ {smallcaps('invalid token or bot id')}</blockquote>",
                delete_menu_markup(),
            )
            _set_pending_raw(uid, pending, "delete")
            return

        owner_of = None
        for r in await db_list_clones():
            if int(r["bot_id"]) == target_id:
                owner_of = int(r["owner_id"])
                break
        if owner_of is None:
            for c in get_running_clones():
                if int(c["bot_id"]) == target_id:
                    owner_of = int(c["owner_id"])
                    break

        if owner_of is None:
            await _edit_ui(
                client,
                chat_id,
                message_id,
                is_photo,
                f"<blockquote expandable>❌ {smallcaps('clone not found')}</blockquote>",
                delete_menu_markup(),
            )
            _set_pending_raw(uid, pending, "delete")
            return

        if owner_of != uid and uid != getattr(console, "OWNER_ID", 0):
            await _edit_ui(
                client,
                chat_id,
                message_id,
                is_photo,
                f"<blockquote expandable>❌ {smallcaps('this clone is not yours')}</blockquote>",
                delete_menu_markup(),
            )
            return

        # ONLY stop/delete — never start_clone_client
        await stop_clone_client(target_id)
        print(f"[clone_ui] DELETED bot_id={target_id}", flush=True)
    except Exception as e:
        print(f"[clone_ui] delete fail: {e}", flush=True)
        traceback.print_exc()
        await _edit_ui(
            client,
            chat_id,
            message_id,
            is_photo,
            f"<blockquote expandable>❌ {smallcaps('delete fail')}\n<code>{str(e)[:300]}</code></blockquote>",
            delete_menu_markup(),
        )
        return

    await asyncio.sleep(0.4)
    body = (
        f"{smallcaps('bot deleted')}\n\n"
        f"{smallcaps('userid')} : <code>{target_id}</code>\n\n"
        f"{smallcaps('clone removed successfully.')}"
    )
    caption = f"<blockquote expandable>{tg_emoji(E.CHECK, '✅')} {body}</blockquote>"
    await _edit_ui(client, chat_id, message_id, is_photo, caption, clone_close_markup())


@bot.on_callback_query(rgx(r"^(help_menu|home_menu)$"), group=1)
async def _clear_clone_ui_on_leave(client, query):
    if query.from_user:
        clear_ui_pending(query.from_user.id)
        clear_ui_consumed(query.from_user.id)
        _clear_cmd_pending(query.from_user.id)


@bot.on_message(filters.private & filters.text & filters.incoming, group=-6)
async def clone_ui_token_paste(client, message: Message):
    """group=-6 runs before clone.py (-5/-4) so delete mode wins."""
    if not message.from_user:
        return
    if _running_on_clone(client):
        return
    uid = message.from_user.id
    pending = _ui_pending.get(uid)
    if not pending:
        return

    mode = pending.get("mode")
    if mode not in ("create", "delete"):
        print(f"[clone_ui] bad mode={mode!r} — ignore", flush=True)
        return

    text_raw = (message.text or "").strip()
    # Accept "/clone TOKEN" and "/delclone ID" on the same screen
    text_raw = re.sub(
        r"(?i)^/(clone|clonebot|delclone|removeclone|rmclone)(@\w+)?\s*",
        "",
        text_raw,
    ).strip()
    compact = re.sub(r"\s+", "", text_raw)

    m = TOKEN_FIND.search(compact)
    token = m.group(1) if m else compact

    if mode == "create":
        if not _looks_like_token(token):
            return
    else:
        # delete — token OR numeric bot id only
        if not (_looks_like_token(token) or _looks_like_bot_id(compact)):
            return
        token = token if _looks_like_token(token) else compact

    # consume pending + block clone.py /clone handler
    _ui_pending.pop(uid, None)
    _clear_cmd_pending(uid)
    mark_ui_consumed(uid)

    chat_id = pending["chat_id"]
    message_id = pending["message_id"]
    is_photo = pending.get("is_photo", True)

    try:
        await message.delete()
    except Exception:
        pass

    print(f"[clone_ui] paste mode={mode} uid={uid}", flush=True)

    if mode == "delete":
        await _do_delete(client, uid, token, chat_id, message_id, is_photo, pending)
    else:
        await _do_create(client, uid, token, chat_id, message_id, is_photo, pending)


print("[clone_ui] loaded OK", flush=True)
