# Override /rob: always succeed, no fail
print("[rob_fix] loading...", flush=True)

import time

from pyrogram import StopPropagation
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from .. import bot, cdx
from .maintenance import block_if_maintenance
from . import games as G


@bot.on_message(cdx("rob"), group=-5)
async def rob_cmd_override(client, message: Message):
    if await block_if_maintenance(message):
        raise StopPropagation
    if not message.from_user:
        raise StopPropagation

    if len(message.command) < 2:
        await message.reply_text(
            "Usage:\n"
            "• Reply: <code>/rob 100</code>\n"
            "• Mention: <code>/rob 100 @user</code>",
            parse_mode=ParseMode.HTML,
        )
        raise StopPropagation

    try:
        amount = int(str(message.command[1]).replace(",", "").replace("$", ""))
    except ValueError:
        await message.reply_text(
            "❌ Invalid amount. Example: <code>/rob 100</code>",
            parse_mode=ParseMode.HTML,
        )
        raise StopPropagation

    if amount <= 0:
        await message.reply_text("❌ Amount must be positive.")
        raise StopPropagation

    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif len(message.command) > 2:
        try:
            target = await client.get_users(message.command[2])
        except Exception:
            target = None

    if not target:
        await message.reply_text(
            "❌ Reply to a user or use <code>/rob 100 @user</code>",
            parse_mode=ParseMode.HTML,
        )
        raise StopPropagation
    if target.id == message.from_user.id:
        await message.reply_text("❌ You can't rob yourself.")
        raise StopPropagation
    if target.is_bot:
        await message.reply_text("❌ Can't rob bots.")
        raise StopPropagation

    data = G._load()
    thief = G._user(data, message.from_user.id)
    victim = G._user(data, target.id)

    now = time.time()
    if now - float(thief.get("last_rob") or 0) < 20:
        left = int(20 - (now - float(thief["last_rob"])))
        await message.reply_text(f"⏳ Wait {left}s before next /rob.")
        raise StopPropagation

    if victim.get("protect_until", 0) > now:
        await message.reply_text("🛡️ Target is protected!")
        raise StopPropagation

    victim_bal = int(victim.get("coins") or 0)
    if victim_bal <= 0:
        await message.reply_text(
            f"❌ {G._mention(target)} has <b>$0</b> — nothing to rob.",
            parse_mode=ParseMode.HTML,
        )
        raise StopPropagation

    steal = min(amount, victim_bal)
    capped = steal < amount

    thief["last_rob"] = now
    victim["coins"] = victim_bal - steal
    thief["coins"] = int(thief.get("coins") or 0) + steal
    G._save(data)

    extra = (
        f"\nℹ️ Asked ${amount:,} but target only had ${victim_bal:,}."
        if capped
        else ""
    )
    await message.reply_text(
        f"🕵️ <b>ROB SUCCESS</b>\n\n"
        f"😈 Robber: {G._mention(message.from_user)}\n"
        f"💀 Victim: {G._mention(target)}\n"
        f"💵 Stolen: <b>${steal:,}</b>{extra}",
        parse_mode=ParseMode.HTML,
    )
    raise StopPropagation


print("[rob_fix] loaded OK", flush=True)
