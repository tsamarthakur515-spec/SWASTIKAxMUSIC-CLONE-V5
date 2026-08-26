# ---------------------------------------------------------------
# PANDAMUSIC — games.py (family-friendly)
# Economy / Friendship / RPG / Fun
# ---------------------------------------------------------------

print("[games] loading plugin...", flush=True)

import asyncio
import json
import os
import random
import secrets
import time

from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import bot, cdx, rgx, console
from ..modules.formatters import smallcaps
from ..modules.custom_emojis import tg_emoji
from ..modules.bot_api import bot_api_edit_message, bot_api_answer_callback
from .maintenance import block_if_maintenance, block_cb_if_maintenance

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DB = os.path.join(_BASE, "games_db.json")
_RNG = secrets.SystemRandom()

# Games menu buttons emoji
E_GAMES = "6154314112236001069"
# Games main caption emojis
E_GAMES_T1 = "6152030379340470754"
E_GAMES_T2 = "6154418140638877189"
E_GAMES_T3 = "6151949350487470820"
# Games INNER category caption emojis
E_IN1 = "6149920283382783110"
E_IN2 = "6147765446750773814"
E_IN3 = "6147748799457534087"
E_IN4 = "6147682648371241032"
E_IN5 = "6147746063563367109"
E_IN6 = "6111504695728020416"
E_IN7 = "6113756310858111612"
E_IN8 = "6111778259374971023"

SHOP = {
    "sword": {"price": 1500, "name": "🗡️ Sword", "atk": 15, "slot": "weapon"},
    "shield": {"price": 1200, "name": "🛡️ Shield", "def": 12, "slot": "armor"},
    "armor": {"price": 2000, "name": "🥋 Armor", "def": 20, "slot": "armor"},
    "potion": {"price": 500, "name": "🧪 Potion", "heal": 50, "slot": "flex"},
    "boots": {"price": 800, "name": "👢 Boots", "spd": 10, "slot": "flex"},
}

RIDDLES = [
    ("I have cities but no houses, forests but no trees, water but no fish. What am I?", "map"),
    ("What has keys but can't open locks?", "piano"),
    ("What gets wetter the more it dries?", "towel"),
    ("What has a head and a tail but no body?", "coin"),
    ("What can travel around the world while staying in a corner?", "stamp"),
    ("What has hands but cannot clap?", "clock"),
]

SLOT_ICONS = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]


def _load() -> dict:
    try:
        if os.path.exists(_DB):
            with open(_DB, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"users": {}, "friends": {}}


def _save(data: dict):
    try:
        with open(_DB, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[games] save error: {e}", flush=True)


def _uid(u) -> str:
    return str(u)


def _user(data: dict, user_id: int) -> dict:
    key = _uid(user_id)
    if key not in data["users"]:
        data["users"][key] = {
            "coins": 1000, "bank": 0, "xp": 0, "wins": 0, "losses": 0, "kills": 0,
            "inventory": {}, "hp": 100, "last_daily": 0, "streak": 0, "last_claim": 0,
            "protect_until": 0, "alive": True, "last_kill": 0, "last_rob": 0, "last_slots": 0,
        }
    u = data["users"][key]
    for k, v in {"coins": 1000, "inventory": {}, "hp": 100, "alive": True, "protect_until": 0,
                 "wins": 0, "losses": 0, "kills": 0, "xp": 0, "streak": 0, "last_daily": 0,
                 "last_claim": 0, "last_kill": 0, "last_rob": 0, "last_slots": 0}.items():
        u.setdefault(k, v)
    return u


def _name(user) -> str:
    return (user.first_name or "User").replace("<", "").replace(">", "")


def _mention(user) -> str:
    return f'<a href="tg://user?id={user.id}">{_name(user)}</a>'


def _is_dead(u: dict) -> bool:
    return (not u.get("alive", True)) or int(u.get("hp", 100)) <= 0


def _rank(data: dict, user_id: int) -> int:
    users = data.get("users") or {}
    ranked = sorted(users.items(), key=lambda x: int(x[1].get("coins", 0)), reverse=True)
    uid = str(user_id)
    for i, (k, _) in enumerate(ranked, 1):
        if k == uid:
            return i
    return len(ranked) + 1


def _gear(inv: dict):
    weapon, armor, flex = "None", "None", []
    for key, qty in (inv or {}).items():
        if qty <= 0:
            continue
        info = SHOP.get(key, {})
        name = info.get("name", key)
        slot = info.get("slot", "flex")
        if slot == "weapon" and weapon == "None":
            weapon = f"{name} x{qty}"
        elif slot == "armor" and armor == "None":
            armor = f"{name} x{qty}"
        else:
            flex.append(f"{name} x{qty}")
    return weapon, armor, flex


def _spin_slots():
    roll = _RNG.randint(1, 100)
    if roll <= 70:
        a, b, c = _RNG.sample(SLOT_ICONS, 3)
        return a, b, c, 0, "💨 No luck — try again"
    if roll <= 92:
        icon = _RNG.choice(["🍒", "🍋", "🔔", "⭐"])
        other = _RNG.choice([x for x in SLOT_ICONS if x != icon])
        pos = _RNG.randint(0, 2)
        reels = [icon, icon, other]
        if pos == 1:
            reels = [icon, other, icon]
        elif pos == 2:
            reels = [other, icon, icon]
        return reels[0], reels[1], reels[2], 70, "✨ Pair! +$70"
    if roll <= 99:
        icon = _RNG.choice(["🍒", "🍋", "🔔", "⭐", "7️⃣"])
        return icon, icon, icon, 200, f"🎉 Triple {icon}! +$200"
    return "💎", "💎", "💎", 500, "💎 JACKPOT! +$500"


async def _target_user(client, message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if message.command and len(message.command) > 1:
        try:
            return await client.get_users(message.command[1])
        except Exception:
            return None
    return None


def _btn(text, **kwargs):
    kwargs.setdefault("icon_custom_emoji_id", E_GAMES)
    try:
        return InlineKeyboardButton(text, **kwargs)
    except TypeError:
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(text, **kwargs)


def games_menu_markup():
    return InlineKeyboardMarkup([
        [_btn("Social", callback_data="games_social"), _btn("Economy", callback_data="games_economy")],
        [_btn("RPG", callback_data="games_rpg"), _btn("AI & Fun", callback_data="games_fun")],
        [_btn("Back", callback_data="help_menu")],
    ])


def games_back_markup():
    return InlineKeyboardMarkup([[
        _btn("Games", callback_data="games_menu"),
        _btn("Help", callback_data="help_menu"),
    ]])


def games_menu_caption() -> str:
    body = (
        f"{tg_emoji(E_GAMES_T1, '🎮')} {smallcaps('games menu')}\n\n"
        f"{tg_emoji(E_GAMES_T2, '✨')} {smallcaps('pick a category below.')}\n"
        f"{tg_emoji(E_GAMES_T3, '💰')} {smallcaps('all games use virtual coins — fun only, no real money.')}"
    )
    return f"<blockquote expandable>{body}</blockquote>"


def social_caption() -> str:
    body = (
        f"{tg_emoji(E_IN1, '💍')} {smallcaps('social & friends')}\n\n"
        f"{tg_emoji(E_IN2, '✨')} <b>/friend @user</b>\n↳ {smallcaps('send a friend request / add friend.')}\n\n"
        f"{tg_emoji(E_IN3, '✨')} <b>/friends</b>\n↳ {smallcaps('see your friends list.')}\n\n"
        f"{tg_emoji(E_IN4, '✨')} <b>/unfriend @user</b>\n↳ {smallcaps('remove a friend.')}\n\n"
        f"{tg_emoji(E_IN5, '✨')} <b>/buddy</b>\n↳ {smallcaps('random buddy match suggestion.')}"
    )
    return f"<blockquote expandable>{body}</blockquote>"


def economy_caption() -> str:
    body = (
        f"{tg_emoji(E_IN6, '💰')} {smallcaps('economy & shop')}\n\n"
        f"{tg_emoji(E_IN7, '✨')} <b>/bal</b> — {smallcaps('own profile')}\n"
        f"{tg_emoji(E_IN8, '✨')} <b>/bal @user</b> — {smallcaps('see their profile')}\n"
        f"{tg_emoji(E_IN1, '✨')} <b>/shop</b> — {smallcaps('buy items')}\n"
        f"{tg_emoji(E_IN2, '✨')} <b>/buy [item]</b> — {smallcaps('purchase from shop')}\n"
        f"{tg_emoji(E_IN3, '✨')} <b>/give [amt] @user</b> — {smallcaps('transfer (10% tax)')}\n"
        f"{tg_emoji(E_IN4, '✨')} <b>/claim</b> — {smallcaps('group bonus (2k)')}\n"
        f"{tg_emoji(E_IN5, '✨')} <b>/daily</b> — {smallcaps('daily streak rewards')}\n"
        f"{tg_emoji(E_IN6, '✨')} <b>/ranking</b> — {smallcaps('top richest players')}"
    )
    return f"<blockquote expandable>{body}</blockquote>"


def rpg_caption() -> str:
    body = (
        f"{tg_emoji(E_IN7, '⚔️')} {smallcaps('rpg & battle')}\n\n"
        f"{tg_emoji(E_IN8, '✨')} <b>/kill</b> ({smallcaps('reply')})\n↳ {smallcaps('game ko + random loot')}\n\n"
        f"{tg_emoji(E_IN1, '✨')} <b>/battle @user</b>\n↳ {smallcaps('friendly duel. winner gains coins & xp!')}\n\n"
        f"{tg_emoji(E_IN2, '✨')} <b>/rob [amt]</b>\n↳ {smallcaps('steal up to their balance (risk of fail)')}\n\n"
        f"{tg_emoji(E_IN3, '✨')} <b>/protect</b>\n↳ {smallcaps('buy 24h shield (800 coins).')}\n\n"
        f"{tg_emoji(E_IN4, '✨')} <b>/revive</b>\n↳ {smallcaps('restore hp for 500 coins.')}"
    )
    return f"<blockquote expandable>{body}</blockquote>"


def fun_caption() -> str:
    body = (
        f"{tg_emoji(E_IN5, '🧠')} {smallcaps('ai & fun')}\n\n"
        f"{tg_emoji(E_IN6, '✨')} <b>/riddle</b> — {smallcaps('random riddle quiz')}\n"
        f"{tg_emoji(E_IN7, '✨')} <b>/dice</b> — {smallcaps('roll a dice')}\n"
        f"{tg_emoji(E_IN8, '✨')} <b>/slots</b> — {smallcaps('virtual slot machine')}\n"
        f"{tg_emoji(E_IN1, '✨')} <b>/coinflip</b> — {smallcaps('heads or tails')}\n\n"
        f"{tg_emoji(E_IN2, '✨')} {smallcaps('chatbot: use')} <b>/chaton</b> {smallcaps('from help menu.')}"
    )
    return f"<blockquote expandable>{body}</blockquote>"


async def _edit(query, text, markup):
    """Edit games menus — Bot API first (kurigram broken)."""
    msg = query.message
    chat_id = msg.chat.id
    message_id = msg.id
    is_photo = bool(getattr(msg, "photo", None))

    ok = await bot_api_edit_message(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        caption=text,
        reply_markup=markup,
        is_photo=is_photo,
    )
    if ok:
        print("[games] menu edit via Bot API OK", flush=True)
        return

    try:
        if is_photo:
            await msg.edit_caption(
                caption=text, reply_markup=markup, parse_mode=ParseMode.HTML
            )
        else:
            await msg.edit_text(
                text, reply_markup=markup, parse_mode=ParseMode.HTML
            )
        return
    except Exception as e:
        print(f"[games] pyrogram edit failed: {e}", flush=True)

    try:
        await msg.edit_caption(caption=text, parse_mode=ParseMode.HTML)
    except Exception:
        try:
            await msg.edit_text(text, parse_mode=ParseMode.HTML)
        except Exception as e2:
            print(f"[games] edit no-kb failed: {e2}", flush=True)


async def _answer(query, text="", show_alert=False):
    try:
        await query.answer(text, show_alert=show_alert)
    except Exception:
        try:
            await bot_api_answer_callback(query.id, text=text, show_alert=show_alert)
        except Exception:
            pass


# ── Menu callbacks ─────────────────────────────────────────────

@bot.on_callback_query(rgx("^games_menu$"))
async def games_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit(query, games_menu_caption(), games_menu_markup())
    await _answer(query)


@bot.on_callback_query(rgx("^games_social$"))
async def games_social_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit(query, social_caption(), games_back_markup())
    await _answer(query)


@bot.on_callback_query(rgx("^games_economy$"))
async def games_economy_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit(query, economy_caption(), games_back_markup())
    await _answer(query)


@bot.on_callback_query(rgx("^games_rpg$"))
async def games_rpg_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit(query, rpg_caption(), games_back_markup())
    await _answer(query)


@bot.on_callback_query(rgx("^games_fun$"))
async def games_fun_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit(query, fun_caption(), games_back_markup())
    await _answer(query)


# ── Economy ────────────────────────────────────────────────────

@bot.on_message(cdx(["bal", "balance", "wallet"]))
async def bal_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    target = message.from_user
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif message.command and len(message.command) > 1:
        try:
            target = await client.get_users(message.command[1])
        except Exception:
            return await message.reply_text("❌ User not found.")
    if target.is_bot:
        return await message.reply_text("❌ Bots have no wallet.")
    data = _load()
    u = _user(data, target.id)
    _save(data)
    rank = _rank(data, target.id)
    alive = not _is_dead(u)
    status = "❤️ Alive" if alive else "💀 Dead"
    kills = int(u.get("kills") or 0)
    coins = int(u.get("coins") or 0)
    weapon, armor, flex = _gear(u.get("inventory") or {})
    flex_txt = "\n".join(f"• {x}" for x in flex) if flex else "(No flex items owned)"
    text = (
        f"👤 User: {_mention(target)}\n👛 Balance: ${coins:,}\n🏆 Rank: #{rank}\n"
        f"❤️ Status: {status}\n⚔️ Kills: {kills}\n\n🎒 <b>Active Gear:</b>\n"
        f"🗡️ Weapon: {weapon}\n🛡️ Armor: {armor}\n\n💎 <b>Flex Collection:</b>\n{flex_txt}"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)


@bot.on_message(cdx("shop"))
async def shop_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    lines = ["🛒 <b>SHOP</b>\n", "Use <code>/buy itemname</code>\n"]
    for key, item in SHOP.items():
        lines.append(f"• <b>{item['name']}</b> (<code>{key}</code>) — ${item['price']:,}")
    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@bot.on_message(cdx("buy"))
async def buy_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/buy sword</code>", parse_mode=ParseMode.HTML)
    item_key = message.command[1].lower().strip()
    if item_key not in SHOP:
        return await message.reply_text("❌ Item not found. Use /shop")
    data = _load()
    u = _user(data, message.from_user.id)
    price = SHOP[item_key]["price"]
    if u["coins"] < price:
        return await message.reply_text(f"❌ Not enough coins. Need ${price:,}.")
    u["coins"] -= price
    inv = u.setdefault("inventory", {})
    inv[item_key] = inv.get(item_key, 0) + 1
    _save(data)
    await message.reply_text(f"✅ Bought <b>{SHOP[item_key]['name']}</b> for ${price:,}!", parse_mode=ParseMode.HTML)


@bot.on_message(cdx(["give", "pay", "transfer"]))
async def give_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/give 100 @user</code> or reply with /give 100", parse_mode=ParseMode.HTML)
    try:
        amount = int(message.command[1].replace(",", ""))
    except ValueError:
        return await message.reply_text("❌ Invalid amount.")
    if amount <= 0:
        return await message.reply_text("❌ Amount must be positive.")
    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif len(message.command) > 2:
        try:
            target = await client.get_users(message.command[2])
        except Exception:
            target = None
    if not target:
        return await message.reply_text("❌ Reply to a user or mention them.")
    if target.id == message.from_user.id:
        return await message.reply_text("❌ You cannot give coins to yourself.")
    if target.is_bot:
        return await message.reply_text("❌ Cannot give to bots.")
    data = _load()
    sender = _user(data, message.from_user.id)
    receiver = _user(data, target.id)
    tax = max(1, int(amount * 0.10))
    total = amount + tax
    if sender["coins"] < total:
        return await message.reply_text(f"❌ Need ${total:,} (amount + 10% tax). You have ${sender['coins']:,}.")
    sender["coins"] -= total
    receiver["coins"] += amount
    _save(data)
    await message.reply_text(
        f"✅ {_mention(message.from_user)} sent <b>${amount:,}</b> to {_mention(target)}\n💸 Tax: ${tax:,}",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx("daily"))
async def daily_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    data = _load()
    u = _user(data, message.from_user.id)
    now = time.time()
    last = float(u.get("last_daily") or 0)
    if now - last < 86400:
        left = int(86400 - (now - last))
        h, m = divmod(left // 60, 60)
        return await message.reply_text(f"⏳ Daily already claimed. Next in {h}h {m}m.")
    if now - last < 172800:
        u["streak"] = int(u.get("streak") or 0) + 1
    else:
        u["streak"] = 1
    reward = min(500 + (u["streak"] * 50), 2000)
    u["coins"] += reward
    u["xp"] += 10
    u["last_daily"] = now
    _save(data)
    await message.reply_text(
        f"🎁 <b>Daily claimed!</b>\n🪙 +${reward:,}\n🔥 Streak: {u['streak']}\n⭐ +10 XP",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx("claim"))
async def claim_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if message.chat.type.name == "PRIVATE":
        return await message.reply_text("❌ /claim only works in groups.")
    data = _load()
    u = _user(data, message.from_user.id)
    now = time.time()
    last = float(u.get("last_claim") or 0)
    if now - last < 3600:
        left = int(3600 - (now - last))
        return await message.reply_text(f"⏳ Claim cooldown: {left // 60}m left.")
    u["coins"] += 2000
    u["last_claim"] = now
    _save(data)
    await message.reply_text("🎉 Group bonus claimed! +<b>$2,000</b>", parse_mode=ParseMode.HTML)


@bot.on_message(cdx(["ranking", "rich", "top"]))
async def ranking_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    data = _load()
    users = data.get("users") or {}
    ranked = sorted(users.items(), key=lambda x: int(x[1].get("coins", 0)), reverse=True)[:10]
    if not ranked:
        return await message.reply_text("No players yet.")
    lines = ["🏆 <b>TOP 10 RICHEST</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, u) in enumerate(ranked):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} <code>{uid}</code> — ${int(u.get('coins', 0)):,}")
    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ── Friendship ─────────────────────────────────────────────────

@bot.on_message(cdx(["friend", "addfriend"]))
async def friend_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    target = await _target_user(client, message)
    if not target:
        return await message.reply_text("Usage: reply or <code>/friend @user</code>", parse_mode=ParseMode.HTML)
    if target.id == message.from_user.id:
        return await message.reply_text("❌ That's you!")
    if target.is_bot:
        return await message.reply_text("❌ Bots can't be friends.")
    data = _load()
    a, b = sorted([str(message.from_user.id), str(target.id)])
    key = f"{a}:{b}"
    friends = data.setdefault("friends", {})
    if friends.get(key):
        return await message.reply_text("✅ You are already friends!")
    friends[key] = {"since": int(time.time())}
    _save(data)
    await message.reply_text(
        f"🤝 {_mention(message.from_user)} and {_mention(target)} are now friends!",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx(["unfriend", "removefriend"]))
async def unfriend_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    target = await _target_user(client, message)
    if not target:
        return await message.reply_text("Usage: reply or <code>/unfriend @user</code>", parse_mode=ParseMode.HTML)
    data = _load()
    a, b = sorted([str(message.from_user.id), str(target.id)])
    key = f"{a}:{b}"
    friends = data.setdefault("friends", {})
    if key not in friends:
        return await message.reply_text("❌ You are not friends.")
    del friends[key]
    _save(data)
    await message.reply_text(f"👋 Unfriended {_mention(target)}.", parse_mode=ParseMode.HTML)


@bot.on_message(cdx(["friends", "friendlist"]))
async def friends_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    data = _load()
    me = str(message.from_user.id)
    friends = data.get("friends") or {}
    ids = []
    for key in friends:
        parts = key.split(":")
        if me in parts:
            other = parts[0] if parts[1] == me else parts[1]
            ids.append(other)
    if not ids:
        return await message.reply_text("🙂 No friends yet. Use /friend @user")
    lines = [f"👥 <b>Friends ({len(ids)})</b>\n"]
    for i, uid in enumerate(ids[:20], 1):
        lines.append(f"{i}. <code>{uid}</code>")
    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@bot.on_message(cdx(["buddy", "match"]))
async def buddy_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    tips = [
        "Be kind — good friends share /daily rewards vibes!",
        "Team up in /battle for fun practice.",
        "Gift coins with /give to surprise a friend.",
        "Play /slots together and compare luck!",
    ]
    await message.reply_text(
        f"🎲 <b>Buddy tip</b>\n\n{random.choice(tips)}\n\nUse <code>/friend @user</code> to add someone!",
        parse_mode=ParseMode.HTML,
    )


# ── RPG ────────────────────────────────────────────────────────

@bot.on_message(cdx("kill"))
async def kill_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if not (message.reply_to_message and message.reply_to_message.from_user):
        return await message.reply_text("Reply to a user with <code>/kill</code>", parse_mode=ParseMode.HTML)
    target = message.reply_to_message.from_user
    killer = message.from_user
    if target.id == killer.id:
        return await message.reply_text("❌ You can't target yourself.")
    if target.is_bot:
        return await message.reply_text("❌ Can't target bots.")
    data = _load()
    k = _user(data, killer.id)
    v = _user(data, target.id)
    now = time.time()
    if now - float(k.get("last_kill") or 0) < 30:
        left = int(30 - (now - float(k["last_kill"])))
        return await message.reply_text(f"⏳ Wait {left}s before next /kill.")
    if _is_dead(k):
        return await message.reply_text("💀 <b>You are already dead!</b>\nUse /revive to come back.", parse_mode=ParseMode.HTML)
    if v.get("protect_until", 0) > now:
        return await message.reply_text("🛡️ Target is protected!")
    if _is_dead(v):
        return await message.reply_text(
            f"💀 {_mention(target)} is <b>already dead!</b>\nThey need /revive first.",
            parse_mode=ParseMode.HTML,
        )
    if random.random() > 0.55:
        k["last_kill"] = now
        fine = min(k["coins"], random.randint(20, 80))
        k["coins"] -= fine
        _save(data)
        return await message.reply_text(
            f"😅 Missed! {_mention(killer)} failed and lost <b>${fine}</b>", parse_mode=ParseMode.HTML,
        )
    loot = min(random.randint(50, 250), max(0, v["coins"]))
    v["coins"] = max(0, v["coins"] - loot)
    k["coins"] += loot
    k["xp"] += 10
    k["wins"] += 1
    k["kills"] = int(k.get("kills") or 0) + 1
    v["losses"] += 1
    v["hp"] = 0
    v["alive"] = False
    k["last_kill"] = now
    _save(data)
    await message.reply_text(
        f"📝 {_mention(killer)} kill {_mention(target)}!\n\n"
        f"😈 Killer: {_mention(killer)}\n💀 Victim: {_mention(target)}\n💵 Loot: ${loot}",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx(["battle", "fight", "duel"]))
async def battle_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    target = await _target_user(client, message)
    if not target:
        return await message.reply_text("Usage: reply or <code>/battle @user</code>", parse_mode=ParseMode.HTML)
    if target.id == message.from_user.id:
        return await message.reply_text("❌ Can't battle yourself.")
    if target.is_bot:
        return await message.reply_text("❌ Can't battle bots.")
    data = _load()
    a = _user(data, message.from_user.id)
    b = _user(data, target.id)
    if _is_dead(a):
        return await message.reply_text("💀 You are already dead! Use /revive first.")
    if _is_dead(b):
        return await message.reply_text(f"💀 {_mention(target)} is already dead! They need /revive.", parse_mode=ParseMode.HTML)
    a_roll = random.randint(1, 100) + min(20, a.get("xp", 0) // 50)
    b_roll = random.randint(1, 100) + min(20, b.get("xp", 0) // 50)
    if a_roll >= b_roll:
        win, lose, winner = a, b, message.from_user
        a["wins"] += 1
        b["losses"] += 1
    else:
        win, lose, winner = b, a, target
        b["wins"] += 1
        a["losses"] += 1
    gain = min(100, lose["coins"])
    lose["coins"] = max(0, lose["coins"] - gain)
    win["coins"] += gain
    win["xp"] += 15
    lose["hp"] = max(0, lose["hp"] - random.randint(5, 20))
    if lose["hp"] <= 0:
        lose["alive"] = False
        lose["hp"] = 0
    _save(data)
    await message.reply_text(
        f"⚔️ <b>BATTLE</b>\n\n{_mention(message.from_user)} rolled <b>{a_roll}</b>\n"
        f"{_mention(target)} rolled <b>{b_roll}</b>\n\n🏆 Winner: {_mention(winner)} (+${gain}, +15 XP)",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx("rob"))
async def rob_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage:\n• Reply: <code>/rob 100</code>\n• Mention: <code>/rob 100 @user</code>",
            parse_mode=ParseMode.HTML,
        )
    try:
        amount = int(str(message.command[1]).replace(",", "").replace("$", ""))
    except ValueError:
        return await message.reply_text("❌ Invalid amount. Example: <code>/rob 100</code>", parse_mode=ParseMode.HTML)
    if amount <= 0:
        return await message.reply_text("❌ Amount must be positive.")
    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif len(message.command) > 2:
        try:
            target = await client.get_users(message.command[2])
        except Exception:
            target = None
    if not target:
        return await message.reply_text("❌ Reply to a user or use <code>/rob 100 @user</code>", parse_mode=ParseMode.HTML)
    if target.id == message.from_user.id:
        return await message.reply_text("❌ You can't rob yourself.")
    if target.is_bot:
        return await message.reply_text("❌ Can't rob bots.")
    data = _load()
    thief = _user(data, message.from_user.id)
    victim = _user(data, target.id)
    now = time.time()
    if now - float(thief.get("last_rob") or 0) < 20:
        left = int(20 - (now - float(thief["last_rob"])))
        return await message.reply_text(f"⏳ Wait {left}s before next /rob.")
    if victim.get("protect_until", 0) > now:
        return await message.reply_text("🛡️ Target is protected!")
    victim_bal = int(victim.get("coins") or 0)
    if victim_bal <= 0:
        return await message.reply_text(f"❌ {_mention(target)} has <b>$0</b> — nothing to rob.", parse_mode=ParseMode.HTML)
    steal = min(amount, victim_bal)
    capped = steal < amount
    success = random.random() < 0.45
    thief["last_rob"] = now
    if success:
        victim["coins"] = victim_bal - steal
        thief["coins"] = int(thief.get("coins") or 0) + steal
        _save(data)
        extra = f"\nℹ️ Asked ${amount:,} but target only had ${victim_bal:,}." if capped else ""
        await message.reply_text(
            f"🕵️ <b>ROB SUCCESS</b>\n\n😈 Robber: {_mention(message.from_user)}\n"
            f"💀 Victim: {_mention(target)}\n💵 Stolen: <b>${steal:,}</b>{extra}",
            parse_mode=ParseMode.HTML,
        )
    else:
        fine = min(int(thief.get("coins") or 0), max(50, steal // 2))
        thief["coins"] = int(thief.get("coins") or 0) - fine
        _save(data)
        await message.reply_text(
            f"🚨 <b>ROB FAILED</b>\n\n{_mention(message.from_user)} got caught!\n💸 Fine: <b>${fine:,}</b>",
            parse_mode=ParseMode.HTML,
        )


@bot.on_message(cdx("protect"))
async def protect_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    cost = 800
    data = _load()
    u = _user(data, message.from_user.id)
    if u["coins"] < cost:
        return await message.reply_text(f"❌ Need ${cost}.")
    u["coins"] -= cost
    u["protect_until"] = time.time() + 86400
    _save(data)
    await message.reply_text("🛡️ Shield active for 24 hours!")


@bot.on_message(cdx("revive"))
async def revive_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    cost = 500
    data = _load()
    u = _user(data, message.from_user.id)
    if not _is_dead(u) and int(u.get("hp", 100)) >= 100:
        return await message.reply_text("✅ You are already full HP.")
    if u["coins"] < cost:
        return await message.reply_text(f"❌ Need ${cost}.")
    u["coins"] -= cost
    u["hp"] = 100
    u["alive"] = True
    _save(data)
    await message.reply_text("✨ Revived! HP restored to 100.")


# ── Fun ────────────────────────────────────────────────────────

@bot.on_message(cdx("dice"))
async def dice_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    try:
        await message.reply_dice(emoji="🎲")
    except Exception:
        n = _RNG.randint(1, 6)
        await message.reply_text(f"🎲 You rolled <b>{n}</b>", parse_mode=ParseMode.HTML)


@bot.on_message(cdx("slots"))
async def slots_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    cost = 50
    data = _load()
    u = _user(data, message.from_user.id)
    now = time.time()
    last = float(u.get("last_slots") or 0)
    if now - last < 8:
        left = int(8 - (now - last))
        return await message.reply_text(f"⏳ Wait {left}s before next /slots.")
    if int(u.get("coins") or 0) < cost:
        return await message.reply_text(f"❌ Need ${cost} to play. You have ${u.get('coins', 0):,}.")
    spin_msg = await message.reply_text("🎰")
    u["coins"] = int(u["coins"]) - cost
    u["last_slots"] = now
    a, b, c, win, result = _spin_slots()
    if win > 0:
        u["coins"] = int(u["coins"]) + win
    _save(data)
    frames = ["🎰 Spinning...", "🎰 | ❓ | ❓ | ❓ |", f"🎰 | {a} | ❓ | ❓ |", f"🎰 | {a} | {b} | ❓ |", f"🎰 | {a} | {b} | {c} |"]
    for fr in frames:
        try:
            await spin_msg.edit_text(fr)
        except Exception:
            pass
        await asyncio.sleep(0.55)
    net = win - cost
    net_txt = f"(+${net})" if net > 0 else (f"(${net})" if net < 0 else "($0)")
    final = f"🎰 | {a} | {b} | {c} |\n{result}\n💳 Bet: ${cost} {net_txt}\n👛 Balance: ${u['coins']:,}"
    try:
        await spin_msg.edit_text(final)
    except Exception:
        await message.reply_text(final)


@bot.on_message(cdx(["coinflip", "flip"]))
async def coinflip_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    side = _RNG.choice(["Heads", "Tails"])
    await message.reply_text(f"🪙 <b>{side}</b>!", parse_mode=ParseMode.HTML)


@bot.on_message(cdx("riddle"))
async def riddle_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    q, a = random.choice(RIDDLES)
    await message.reply_text(
        f"🧩 <b>Riddle</b>\n\n{q}\n\n<code>Reply with your answer!</code>\n(Answer: spoiler — ||{a}||)",
        parse_mode=ParseMode.HTML,
    )


print("[games] plugin loaded OK", flush=True)
