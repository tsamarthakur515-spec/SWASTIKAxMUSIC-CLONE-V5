"""
Broadcast / Gcast — sudo only.

Telegram limits:
- Private: bot can ONLY message users who already pressed /start.
- Groups: bot must be a member with send permission.

Targets come from served_users / served_chats (DB + in-memory).
"""

import asyncio
from pyrogram.errors import (
    FloodWait,
    UserIsBlocked,
    ChatWriteForbidden,
    PeerIdInvalid,
    InputUserDeactivated,
    UserDeactivated,
    ChatAdminRequired,
    ChannelPrivate,
    Forbidden,
)

from .. import bot, cdx, sudoers
from ..modules.database import get_served_chats, get_served_users

# Errors that mean "never retry this target"
_SKIP_ERRORS = (
    UserIsBlocked,
    ChatWriteForbidden,
    PeerIdInvalid,
    InputUserDeactivated,
    UserDeactivated,
    ChatAdminRequired,
    ChannelPrivate,
    Forbidden,
)


async def _deliver(target_id: int, message, use_copy: bool, from_chat_id, msg_id, text):
    """Send one message. Raises on failure."""
    if use_copy:
        # Copy keeps media + caption; more reliable than forward across chats
        await bot.copy_message(
            chat_id=target_id,
            from_chat_id=from_chat_id,
            message_id=msg_id,
        )
    else:
        await bot.send_message(chat_id=target_id, text=text)


async def _send_to_targets(message, targets: list):
    """
    Broadcast reply-media or text to targets.
    Returns (sent, failed, skipped_self).
    """
    sent = 0
    failed = 0

    if message.reply_to_message:
        use_copy = True
        from_chat_id = message.chat.id
        msg_id = message.reply_to_message.id
        text = None
    else:
        if len(message.command) < 2:
            return -1, -1, 0
        use_copy = False
        from_chat_id = msg_id = None
        text = message.text.split(None, 1)[1]

    # Unique targets only
    seen = set()
    unique = []
    for t in targets:
        try:
            tid = int(t)
        except (TypeError, ValueError):
            continue
        if tid in seen:
            continue
        seen.add(tid)
        unique.append(tid)

    for i, target_id in enumerate(unique):
        try:
            await _deliver(target_id, message, use_copy, from_chat_id, msg_id, text)
            sent += 1
        except FloodWait as e:
            wait = min(int(getattr(e, "value", 5) or 5), 60)
            await asyncio.sleep(wait)
            try:
                await _deliver(target_id, message, use_copy, from_chat_id, msg_id, text)
                sent += 1
            except Exception:
                failed += 1
        except _SKIP_ERRORS:
            failed += 1
        except Exception:
            failed += 1

        # Pace large broadcasts (Telegram flood protection)
        if (i + 1) % 15 == 0:
            await asyncio.sleep(1.2)
        else:
            await asyncio.sleep(0.05)

    return sent, failed, 0


def _empty_help(kind: str) -> str:
    return (
        f"**⚠️ Broadcast targets empty ({kind}).**\n\n"
        f"Telegram rule:\n"
        f"• **Users** — sirf woh jinhone bot pe `/start` kiya ho\n"
        f"• **Groups** — jahan bot member hai aur message aa chuka ho\n\n"
        f"**Fix:**\n"
        f"1. Users se bolo bot pe `/start` karein\n"
        f"2. Groups mein bot add + admin + `/play` chalao\n"
        f"3. `/stats` se CHATS / USERS check karo\n"
        f"4. Phir `/broadcast` try karo"
    )


@bot.on_message(cdx(["ubroadcast"]) & sudoers)
async def user_broadcast(client, message):
    try:
        await message.delete()
    except Exception:
        pass

    if not message.reply_to_message and len(message.command) < 2:
        return await message.reply_text(
            "**🤖 Reply to any media/text**\n"
            "**or give text after command**\n\n"
            "`/ubroadcast your message` — **users only**\n\n"
            "Note: sirf un users ko jayega jinhone `/start` kiya ho."
        )

    status = await message.reply_text("**📤 Broadcasting to users...**")

    susers = await get_served_users()
    targets = [int(u["user_id"]) for u in susers if u.get("user_id")]

    if not targets:
        return await status.edit_text(_empty_help("users"))

    sent, failed, _ = await _send_to_targets(message, targets)
    if sent == -1:
        return await status.edit_text("**🤖 Reply to media/text or add text after command.**")

    await status.edit_text(
        f"**✅ User Broadcast Done**\n\n"
        f"👤 **Sent :** `{sent}`\n"
        f"❌ **Failed :** `{failed}`\n"
        f"📊 **Tried :** `{sent + failed}`\n\n"
        f"_Failed = blocked / never /start / deleted account_"
    )


@bot.on_message(cdx(["gbroadcast"]) & sudoers)
async def group_broadcast(client, message):
    try:
        await message.delete()
    except Exception:
        pass

    if not message.reply_to_message and len(message.command) < 2:
        return await message.reply_text(
            "**🤖 Reply to any media/text**\n"
            "**or give text after command**\n\n"
            "`/gbroadcast your message` — **groups only**"
        )

    status = await message.reply_text("**📤 Broadcasting to groups...**")

    schats = await get_served_chats()
    targets = [int(c["chat_id"]) for c in schats if c.get("chat_id")]

    if not targets:
        return await status.edit_text(_empty_help("groups"))

    sent, failed, _ = await _send_to_targets(message, targets)
    if sent == -1:
        return await status.edit_text("**🤖 Reply to media/text or add text after command.**")

    await status.edit_text(
        f"**✅ Group Broadcast Done**\n\n"
        f"💬 **Sent :** `{sent}`\n"
        f"❌ **Failed :** `{failed}`\n"
        f"📊 **Tried :** `{sent + failed}`\n\n"
        f"_Failed = bot removed / muted / no permission_"
    )


@bot.on_message(cdx(["broadcast", "gcast"]) & sudoers)
async def full_broadcast(client, message):
    try:
        await message.delete()
    except Exception:
        pass

    if not message.reply_to_message and len(message.command) < 2:
        return await message.reply_text(
            "**🤖 Reply to any media/text**\n"
            "**or give text after command**\n\n"
            "`/broadcast msg` — users + groups\n"
            "`/ubroadcast msg` — users only\n"
            "`/gbroadcast msg` — groups only\n\n"
            "Users ke liye unhone `/start` kiya hona zaroori hai."
        )

    status = await message.reply_text("**📤 Broadcasting to users + groups...**")

    susers = await get_served_users()
    user_targets = [int(u["user_id"]) for u in susers if u.get("user_id")]

    schats = await get_served_chats()
    chat_targets = [int(c["chat_id"]) for c in schats if c.get("chat_id")]

    if not user_targets and not chat_targets:
        return await status.edit_text(_empty_help("users + groups"))

    # Validate content once
    if not message.reply_to_message and len(message.command) < 2:
        return await status.edit_text("**🤖 Reply to media/text or add text after command.**")

    user_sent = user_failed = 0
    if user_targets:
        user_sent, user_failed, _ = await _send_to_targets(message, user_targets)
        if user_sent == -1:
            return await status.edit_text("**🤖 Reply to media/text or add text after command.**")

    gc_sent = gc_failed = 0
    if chat_targets:
        gc_sent, gc_failed, _ = await _send_to_targets(message, chat_targets)

    total_sent = user_sent + gc_sent
    total_failed = user_failed + gc_failed

    await status.edit_text(
        f"**✅ Full Broadcast Done**\n\n"
        f"👤 **Users Sent :** `{user_sent}`\n"
        f"❌ **Users Failed :** `{user_failed}`\n\n"
        f"💬 **Groups Sent :** `{gc_sent}`\n"
        f"❌ **Groups Failed :** `{gc_failed}`\n\n"
        f"📊 **Total Sent :** `{total_sent}`\n"
        f"📊 **Total Failed :** `{total_failed}`\n"
        f"📊 **Total Tried :** `{total_sent + total_failed}`\n\n"
        f"_Users fail = no /start or blocked | Groups fail = left/muted_"
    )
