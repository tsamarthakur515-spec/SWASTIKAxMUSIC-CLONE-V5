# Override /kill: always success MURDER message, no miss
print("[kill_fix] loading...", flush=True)

import random
import time

from pyrogram import StopPropagation
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from .. import bot, cdx
from .maintenance import block_if_maintenance
from . import games as G


@bot.on_message(cdx("kill"), group=-5)
async def kill_cmd_override(client, message: Message):
    if await block_if_maintenance(message):
        raise StopPropagation
    if not message.from_user:
        raise StopPropagation

    target = await G._target_user(client, message)
    if not target:
        await message.reply_text(
            "Usage: reply or <code>/kill @user</code>",
            parse_mode=ParseMode.HTML,
        )
        raise StopPropagation

    killer = message.from_user

    if target.id == killer.id:
        await message.reply_text("❌ You can't target yourself.")
        raise StopPropagation
    if target.is_bot:
        await message.reply_text("❌ Can't target bots.")
        raise StopPropagation

    data = G._load()
    k = G._user(data, killer.id)
    v = G._user(data, target.id)

    now = time.time()
    if now - float(k.get("last_kill") or 0) < 30:
        left = int(30 - (now - float(k["last_kill"])))
        await message.reply_text(f"⏳ Wait {left}s before next /kill.")
        raise StopPropagation

    if G._is_dead(k):
        await message.reply_text(
            "💀 <b>You are already dead!</b>\nUse /revive to come back.",
            parse_mode=ParseMode.HTML,
        )
        raise StopPropagation

    if v.get("protect_until", 0) > now:
        await message.reply_text("🛡️ Target is protected!")
        raise StopPropagation

    if G._is_dead(v):
        await message.reply_text(
            f"{G._mention(target)} ᴀʟʀᴅʏ ᴅᴇᴀᴅ",
            parse_mode=ParseMode.HTML,
        )
        raise StopPropagation

    loot = random.randint(50, 250)
    loot = min(loot, max(0, int(v.get("coins") or 0)))
    v["coins"] = max(0, int(v.get("coins") or 0) - loot)
    k["coins"] = int(k.get("coins") or 0) + loot
    k["xp"] = int(k.get("xp") or 0) + 10
    k["wins"] = int(k.get("wins") or 0) + 1
    k["kills"] = int(k.get("kills") or 0) + 1
    v["losses"] = int(v.get("losses") or 0) + 1
    v["hp"] = 0
    v["alive"] = False
    k["last_kill"] = now
    G._save(data)

    text = (
        f"🔪 <b>𝐌𝐔𝐑𝐃𝐄𝐑!</b>\n\n"
        f"📝 {G._mention(killer)} kill {G._mention(target)}!\n\n"
        f"😈 Killer: {G._mention(killer)}\n"
        f"💀 Victim: {G._mention(target)}\n"
        f"💵 Loot: ${loot}"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)
    raise StopPropagation


print("[kill_fix] loaded OK", flush=True)
