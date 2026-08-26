# ---------------------------------------------------------------
# PANDAMUSIC — clone.py  (/clone TOKEN command)
# ---------------------------------------------------------------

print("[clone] loading plugin...", flush=True)

import re
import traceback

from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import Message

from .. import bot, console
from ..modules.formatters import smallcaps

_pending_token = {}
TOKEN_FIND = re.compile(r"(\d{5,15}:[A-Za-z0-9_-]{20,100})")
CLONE_CMD_RE = re.compile(r"(?i)^/(clone|clonebot)(@\w+)?(?:\s|$)")


def _is_owner(uid):
    return bool(uid and uid == getattr(console, "OWNER_ID", 0))


def _normalize_token(raw: str) -> str:
    return re.sub(r"\s+", "", (raw or "").strip())


def _looks_like_token(t: str) -> bool:
    t = _normalize_token(t)
    if not t or ":" not in t:
        return False
    left, right = t.split(":", 1)
    return left.isdigit() and 5 <= len(left) <= 15 and len(right) >= 20


def _ui_mode_active(uid) -> bool:
    """True if help-menu clone UI is waiting for token/id."""
    try:
        from . import clone_ui

        return bool(clone_ui.get_ui_mode(uid))
    except Exception:
        return False


def _ui_already_handled(uid) -> bool:
    """True if clone_ui already processed this paste (delete or create)."""
    try:
        from . import clone_ui

        if clone_ui.get_ui_mode(uid):
            return True
        if hasattr(clone_ui, "was_ui_consumed") and clone_ui.was_ui_consumed(uid):
            clone_ui.clear_ui_consumed(uid)
            return True
    except Exception:
        return False
    return False


def _extract_token(message: Message) -> str:
    text = (message.text or message.caption or "") or ""
    if not text.strip():
        return ""

    parts = text.strip().split(None, 1)
    if len(parts) >= 2:
        joined = _normalize_token(parts[1])
        if _looks_like_token(joined):
            return joined
        m = TOKEN_FIND.search(joined)
        if m:
            return m.group(1)

    compact = _normalize_token(text)
    m = TOKEN_FIND.search(compact)
    if m:
        return m.group(1)

    try:
        cmd = list(getattr(message, "command", None) or [])
        if len(cmd) >= 2:
            joined = _normalize_token("".join(cmd[1:]))
            if _looks_like_token(joined):
                return joined
            m = TOKEN_FIND.search(joined)
            if m:
                return m.group(1)
    except Exception:
        pass
    return ""


async def _reply(message, text):
    try:
        return await message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"[clone] reply fail: {e}", flush=True)
        try:
            return await message._client.send_message(
                message.chat.id, text, parse_mode=ParseMode.HTML
            )
        except Exception as e2:
            print(f"[clone] send_message fail: {e2}", flush=True)
            return None


async def _edit(msg, text):
    if not msg:
        return None
    try:
        return await msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception:
        try:
            return await msg.edit_text(re.sub(r"<[^>]+>", "", text))
        except Exception:
            try:
                return await msg.reply_text(text, parse_mode=ParseMode.HTML)
            except Exception:
                return None


async def _delete(message):
    try:
        await message.delete()
    except Exception:
        pass


@bot.on_message(
    filters.regex(r"(?i)^/(clone|clonebot)(@\w+)?(?:\s|$)") & filters.incoming,
    group=-5,
)
async def clone_cmd(client, message: Message):
    uid = getattr(message.from_user, "id", None)
    chat_id = message.chat.id if message.chat else None
    print(
        f"[clone] CMD HIT uid={uid} chat={chat_id} text={((message.text or '')[:120])!r}",
        flush=True,
    )

    try:
        if not message.from_user:
            return await _reply(message, "❌ User not found.")

        if _ui_already_handled(message.from_user.id):
            print("[clone] skip /clone — clone_ui already handled", flush=True)
            return

        try:
            from ..modules.clones import is_clone_client
            if is_clone_client(client):
                return await _reply(
                    message,
                    "❌ Clone panel sirf <b>main bot</b> pe chalta hai.\n"
                    "Is cloned bot se naya clone / check clone nahi hoga.",
                )
        except Exception:
            pass

        chat_type = getattr(message.chat, "type", None)
        is_private = chat_type == ChatType.PRIVATE or str(chat_type).lower() in (
            "private",
            "chattype.private",
        )
        if not is_private:
            return await _reply(
                message,
                "🔒 Clone sirf <b>private chat</b> me chalta hai.\nBot ko DM karke /clone bhejo.",
            )

        token = _extract_token(message)
        print(f"[clone] token_len={len(token)} valid={_looks_like_token(token)}", flush=True)

        if not token:
            _pending_token[uid] = True
            return await _reply(
                message,
                f"✨ <b>{smallcaps('swastika clone')}</b>\n\n"
                f"{smallcaps('usage')} (token <b>{smallcaps('ek line')}</b> me):\n"
                f"<code>/clone 123456:AAHxxxx</code>\n\n"
                f"{smallcaps('or open help menu → clone button.')}\n\n"
                f"• /myclones — list\n"
                f"• /delclone ID — delete",
            )

        await _do_clone(client, message, token)
    except Exception as e:
        print(f"[clone] clone_cmd ERROR: {e}", flush=True)
        traceback.print_exc()
        await _reply(message, f"❌ Clone error:\n<code>{str(e)[:400]}</code>")


@bot.on_message(
    filters.private & filters.text & filters.incoming,
    group=-4,
)
async def clone_token_paste(client, message: Message):
    if not message.from_user:
        return
    uid = message.from_user.id

    # Menu UI (create/delete) handles the paste — do NOT clone here
    if _ui_already_handled(uid) or _ui_mode_active(uid):
        return

    if not _pending_token.get(uid):
        return

    text_raw = message.text or ""
    if CLONE_CMD_RE.match(text_raw.strip()):
        return

    text = _normalize_token(text_raw)
    m = TOKEN_FIND.search(text)
    token = m.group(1) if m else text
    if not _looks_like_token(token):
        if ":" in text:
            return await _reply(
                message,
                f"❌ {smallcaps('token incomplete / galat.')}\n"
                f"{smallcaps('poora token ek line me bhejo.')}",
            )
        return

    _pending_token.pop(uid, None)
    print(f"[clone] paste from {uid}", flush=True)
    await _do_clone(client, message, token)


async def _do_clone(client, message: Message, token: str):
    uid = message.from_user.id
    token = _normalize_token(token)

    status = await _reply(
        message, f"⏳ <b>{smallcaps('cloning your bot.......')}</b>"
    )
    await _delete(message)

    if not _looks_like_token(token):
        return await _edit(
            status,
            f"❌ {smallcaps('invalid token.')}\nExample: <code>123456789:AAHxxxx</code>",
        )

    try:
        from ..modules.clones import is_bot_token, start_clone_client, user_can_clone
    except Exception as e:
        print(f"[clone] import clones fail: {e}", flush=True)
        traceback.print_exc()
        return await _edit(
            status,
            f"❌ {smallcaps('clone module load nahi hua.')}\nPanel se <b>Rebuild</b> karo.",
        )

    if not is_bot_token(token):
        return await _edit(
            status,
            f"❌ {smallcaps('invalid token format.')}\n<code>123456789:AAHxxxx</code>",
        )

    ok, reason = await user_can_clone(uid)
    if not ok:
        return await _edit(status, f"❌ {reason}")

    await _edit(status, f"⏳ <b>{smallcaps('starting your bot.....')}</b>")

    try:
        entry = await start_clone_client(token, uid)
    except Exception as e:
        print(f"[clone] start fail: {e}", flush=True)
        traceback.print_exc()
        return await _edit(
            status,
            f"❌ Clone fail:\n<code>{str(e)[:450]}</code>\n\n"
            f"• @BotFather se naya token\n"
            f"• Main bot token mat use karo\n"
            f"• Token ek line me bhejo",
        )

    uname = (entry.get("username") or "").strip()
    bot_id = entry.get("bot_id")
    who = f"@{uname}" if uname else f"<code>{bot_id}</code>"

    text = (
        f"✅ <b>{smallcaps('bot started')}</b>\n\n"
        f"{smallcaps('username')} : <b>{who}</b>\n"
        f"{smallcaps('userid')} : <code>{bot_id}</code>"
    )
    await _edit(status, text)


@bot.on_message(
    filters.regex(r"(?i)^/(myclones|myclone)(@\w+)?(?:\s|$)") & filters.incoming,
    group=-5,
)
async def myclones_cmd(client, message: Message):
    try:
        from ..modules.clones import db_list_clones, get_running_clones

        if not message.from_user:
            return
        uid = message.from_user.id
        rows = await db_list_clones(uid)
        running_ids = {c["bot_id"] for c in get_running_clones() if c["owner_id"] == uid}
        seen = {}
        for r in rows:
            seen[int(r["bot_id"])] = r
        for c in get_running_clones():
            if c["owner_id"] == uid:
                seen[int(c["bot_id"])] = {**seen.get(int(c["bot_id"]), {}), **c}
        if not seen:
            return await _reply(message, f"📭 {smallcaps('koi clone nahi.')}\n<code>/clone TOKEN</code>")
        lines = [f"🌟 <b>{smallcaps('your clones')}</b>\n"]
        for i, (bid, r) in enumerate(seen.items(), 1):
            un = r.get("username") or ""
            tag = f"@{un}" if un else f"<code>{bid}</code>"
            online = "🟢" if bid in running_ids else "🔴"
            lines.append(f"{i}. {online} {tag}\n   /delclone {bid}")
        await _reply(message, "\n".join(lines))
    except Exception as e:
        await _reply(message, f"❌ {e}")


@bot.on_message(
    filters.regex(r"(?i)^/(delclone|removeclone|rmclone)(@\w+)?(?:\s|$)") & filters.incoming,
    group=-5,
)
async def delclone_cmd(client, message: Message):
    try:
        from ..modules.clones import db_list_clones, get_running_clones, stop_clone_client

        if not message.from_user:
            return
        uid = message.from_user.id
        parts = (message.text or "").strip().split()
        if len(parts) < 2:
            return await _reply(message, "Usage: <code>/delclone BOT_ID</code>")
        raw = parts[1].strip().lstrip("@")
        if not raw.isdigit():
            return await _reply(message, "❌ Numeric BOT_ID do.")
        target_id = int(raw)
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
            return await _reply(message, "❌ Clone not found.")
        if owner_of != uid and not _is_owner(uid):
            return await _reply(message, "❌ Ye clone tumhara nahi.")
        await stop_clone_client(target_id)
        await _reply(message, f"✅ Clone removed.\n🆔 <code>{target_id}</code>")
    except Exception as e:
        await _reply(message, f"❌ {e}")


@bot.on_message(
    filters.regex(r"(?i)^/(clones|allclones)(@\w+)?(?:\s|$)") & filters.incoming,
    group=-5,
)
async def all_clones_cmd(client, message: Message):
    if not message.from_user or not _is_owner(message.from_user.id):
        return await _reply(message, "❌ Owner only.")
    try:
        from ..modules.clones import db_list_clones, get_running_clones

        rows = await db_list_clones()
        running = {c["bot_id"]: c for c in get_running_clones()}
        if not rows and not running:
            return await _reply(message, "📭 No clones.")
        lines = ["👑 <b>All Clones</b>\n"]
        seen = set()
        for r in rows:
            bid = int(r["bot_id"])
            seen.add(bid)
            un = r.get("username") or ""
            tag = f"@{un}" if un else str(bid)
            online = "🟢" if bid in running else "🔴"
            lines.append(f"{online} {tag} · owner <code>{r['owner_id']}</code>")
        for bid, c in running.items():
            if bid not in seen:
                un = c.get("username") or ""
                tag = f"@{un}" if un else str(bid)
                lines.append(f"🟢 {tag} · owner <code>{c['owner_id']}</code>")
        await _reply(message, "\n".join(lines))
    except Exception as e:
        await _reply(message, f"❌ {e}")


print("[clone] plugin loaded OK", flush=True)
