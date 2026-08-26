# ---------------------------------------------------------------
# SWASTIKAMUSIC — logger.py
# Logs: bot added / bot kicked → LOG_GROUP
# ---------------------------------------------------------------

print("[logger] loading plugin...", flush=True)

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from pyrogram.handlers import RawUpdateHandler
from pyrogram.types import ChatMemberUpdated, Message

from .. import bot, console

# Optional raw types (version-safe)
try:
    from pyrogram.raw.types import UpdateMyChatMember, PeerChannel, PeerChat
except Exception:
    UpdateMyChatMember = None
    PeerChannel = None
    PeerChat = None


async def _send_log(text: str):
    log_id = getattr(console, "LOG_GROUP_ID", 0)
    if not log_id:
        print("[logger] LOG_GROUP_ID missing/0 — skip", flush=True)
        return
    try:
        await bot.send_message(
            log_id,
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        print("[logger] log sent OK", flush=True)
    except Exception as e:
        print(f"[logger] send failed: {e}", flush=True)


async def _group_link(chat) -> str:
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}"
    try:
        link = await bot.export_chat_invite_link(chat.id)
        return link or "N/A"
    except Exception:
        return "N/A (private / no invite permission)"


def _format_user(user) -> tuple:
    if not user:
        return "Unknown", "None", "?"
    name = getattr(user, "first_name", None) or "User"
    ln = getattr(user, "last_name", None)
    if ln:
        name = f"{name} {ln}"
    un = getattr(user, "username", None)
    username = f"@{un}" if un else "None"
    uid = getattr(user, "id", "?")
    return name, username, uid


async def _log_kick(chat_id, group_name, by_name, by_user, by_id, action="ᴋɪᴄᴋᴇᴅ"):
    text = (
        f"🚫 <b>ʙᴏᴛ {action} ғʀᴏᴍ ɢʀᴏᴜᴘ</b>\n\n"
        f"👤 <b>ʙʏ</b> : {by_name}\n"
        f"🔗 <b>ᴜsᴇʀɴᴀᴍᴇ</b> : {by_user}\n"
        f"🆔 <b>ᴜsᴇʀ ɪᴅ</b> : <code>{by_id}</code>\n\n"
        f"💬 <b>ɢʀᴏᴜᴘ</b> : {group_name}\n"
        f"🆔 <b>ᴄʜᴀᴛ ɪᴅ</b> : <code>{chat_id}</code>"
    )
    await _send_log(text)


@bot.on_message(filters.new_chat_members & filters.group, group=50)
async def log_bot_added(_, message: Message):
    try:
        me = bot.me or await bot.get_me()
    except Exception as e:
        print(f"[logger] get_me failed on add: {e}", flush=True)
        return

    if not any(m.id == me.id for m in (message.new_chat_members or [])):
        return

    chat = message.chat
    by_name, by_user, by_id = _format_user(message.from_user)
    link = await _group_link(chat)

    text = (
        "🤖 <b>ʙᴏᴛ ᴀᴅᴅᴇᴅ ɪɴ ɴᴇᴡ ɢʀᴏᴜᴘ</b>\n\n"
        f"👤 <b>ᴀᴅᴅᴇᴅ ʙʏ</b> : {by_name}\n"
        f"🔗 <b>ᴜsᴇʀɴᴀᴍᴇ</b> : {by_user}\n"
        f"🆔 <b>ᴜsᴇʀ ɪᴅ</b> : <code>{by_id}</code>\n\n"
        f"💬 <b>ɢʀᴏᴜᴘ</b> : {chat.title or 'Unknown Group'}\n"
        f"🆔 <b>ᴄʜᴀᴛ ɪᴅ</b> : <code>{chat.id}</code>\n"
        f"🔗 <b>ʟɪɴᴋ</b> : {link}"
    )
    await _send_log(text)


@bot.on_chat_member_updated(group=-1)
async def log_bot_kicked_cmu(_, update: ChatMemberUpdated):
    try:
        new = update.new_chat_member
        if not new or not getattr(new, "user", None):
            return

        me = bot.me or await bot.get_me()
        uid = new.user.id
        if uid != me.id and not getattr(new.user, "is_self", False):
            return

        status = new.status
        status_s = str(status).upper()
        is_out = status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED) or (
            "LEFT" in status_s or "BANNED" in status_s
        )
        print(f"[logger] CMU self status={status} out={is_out}", flush=True)
        if not is_out:
            return

        chat = update.chat
        if chat and getattr(chat, "type", None) == ChatType.PRIVATE:
            return

        group_name = getattr(chat, "title", None) or "Unknown Group"
        chat_id = getattr(chat, "id", "?")
        by_name, by_user, by_id = _format_user(update.from_user)
        action = (
            "ᴋɪᴄᴋᴇᴅ"
            if (status == ChatMemberStatus.BANNED or "BANNED" in status_s)
            else "ʀᴇᴍᴏᴠᴇᴅ"
        )
        await _log_kick(chat_id, group_name, by_name, by_user, by_id, action)
    except Exception as e:
        print(f"[logger] cmu error: {e}", flush=True)


async def _raw_my_chat_member(client, update, users, chats):
    try:
        if UpdateMyChatMember is None or not isinstance(update, UpdateMyChatMember):
            return

        new_part = update.new_participant
        part_name = type(new_part).__name__ if new_part else ""
        print(f"[logger] RAW UpdateMyChatMember new={part_name}", flush=True)

        # Accept banned / left participant types by name (cross-version)
        if not any(x in part_name for x in ("Banned", "Left")):
            return

        peer = update.peer
        if PeerChannel and isinstance(peer, PeerChannel):
            chat_id = int(f"-100{peer.channel_id}")
        elif PeerChat and isinstance(peer, PeerChat):
            chat_id = -peer.chat_id
        else:
            # last resort from peer attributes
            cid = getattr(peer, "channel_id", None)
            hid = getattr(peer, "chat_id", None)
            if cid is not None:
                chat_id = int(f"-100{cid}")
            elif hid is not None:
                chat_id = -hid
            else:
                return

        group_name = "Unknown Group"
        if chats:
            for ch in chats.values():
                t = getattr(ch, "title", None)
                if t:
                    group_name = t
                    break

        by_name, by_user, by_id = "Unknown", "None", "?"
        kicked_by = getattr(new_part, "kicked_by", None)
        if kicked_by and users and kicked_by in users:
            by_name, by_user, by_id = _format_user(users[kicked_by])
            by_id = kicked_by
        elif users:
            for uid, u in users.items():
                if getattr(u, "bot", False):
                    continue
                by_name, by_user, by_id = _format_user(u)
                by_id = uid
                break

        action = "ᴋɪᴄᴋᴇᴅ" if "Banned" in part_name else "ʀᴇᴍᴏᴠᴇᴅ"
        await _log_kick(chat_id, group_name, by_name, by_user, by_id, action)
    except Exception as e:
        print(f"[logger] raw error: {e}", flush=True)


try:
    bot.add_handler(RawUpdateHandler(_raw_my_chat_member), group=-1)
    print("[logger] raw handler registered", flush=True)
except Exception as e:
    print(f"[logger] raw handler register failed: {e}", flush=True)

print("[logger] plugin loaded OK", flush=True)