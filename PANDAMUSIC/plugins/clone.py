# ---------------------------------------------------------------
# PANDAMUSIC — clone.py
# ALWAYS replies — never silent fail
# ---------------------------------------------------------------

print("[clone] loading plugin...", flush=True)

import re
import traceback

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from .. import bot, console

try:
    from ..modules.clones import (
        db_list_clones,
        get_running_clones,
        is_bot_token,
        start_clone_client,
        stop_clone_client,
        user_can_clone,
    )

    _CLONE_OK = True
    print("[clone] modules.clones imported OK", flush=True)
except Exception as _e:
    _CLONE_OK = False
    print(f"[clone] modules.clones IMPORT FAIL: {_e}", flush=True)
    traceback.print_exc()

    def is_bot_token(text):
        return bool(re.match(r"^\d{5,15}:[A-Za-z0-9_-]{20,}$", (text or "").strip()))

    async def user_can_clone(_uid):
        return True, ""

    async def start_clone_client(*a, **k):
        raise RuntimeError("clones module load nahi hua — bot rebuild karo")

    async def stop_clone_client(*a, **k):
        return False

    async def db_list_clones(*a, **k):
        return []

    def get_running_clones():
        return []


_pending_token = {}
TOKEN_RE = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{20,}$")


def _is_owner(uid):
    return bool(uid and uid == getattr(console, "OWNER_ID", 0))


def _extract_token(message):
    """Parse token from /clone <token> even if split oddly."""
    text = (message.text or message.caption or "").strip()
    if not text:
        return ""
    parts = text.split(None, 1)
    if len(parts) < 2:
        return ""
    rest = parts[1].strip()
    first = rest.split()[0].strip()
    if TOKEN_RE.match(first) or is_bot_token(first):
        return first
    if TOKEN_RE.match(rest) or is_bot_token(rest):
        return rest
    return first if ":" in first else ""


async def _safe_reply(message, text):
    try:
        return await message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"[clone] reply fail: {e}", flush=True)
        try:
            return await message.reply_text(re.sub(r"<[^>]+>", "", text))
        except Exception:
            return None


async def _safe_edit(status, text):
    try:
        return await status.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"[clone] edit fail: {e}", flush=True)
        try:
            return await status.edit_text(re.sub(r"<[^>]+>", "", text))
        except Exception:
            try:
                return await status.reply_text(text, parse_mode=ParseMode.HTML)
            except Exception:
                return None


@bot.on_message(filters.command(["clone", "clonebot"], prefixes=["/", "!", "."]) & filters.private)
async def clone_cmd(client, message: Message):
    print(f"[clone] /clone from {getattr(message.from_user, 'id', None)}", flush=True)
    try:
        if not message.from_user:
            return await _safe_reply(message, "❌ User not found.")

        uid = message.from_user.id
        token = _extract_token(message)

        if not token:
            _pending_token[uid] = True
            return await _safe_reply(
                message,
                "✨ <b>Swastika Clone</b>\n\n"
                "Apna bot banane ke liye:\n"
                "1. @BotFather → /newbot\n"
                "2. Token copy karo\n"
                "3. Yahan bhejo:\n"
                "   <code>/clone 123456:AAHxxxx</code>\n\n"
                "Ya abhi seedha <b>BOT_TOKEN</b> is chat me paste karo.\n\n"
                "• /myclones — list\n"
                "• /delclone ID — delete\n\n"
                "BotFather: https://t.me/BotFather",
            )

        await _run_clone(client, message, token)
    except Exception as e:
        print(f"[clone] clone_cmd ERROR: {e}", flush=True)
        traceback.print_exc()
        await _safe_reply(message, f"❌ Clone error:\n<code>{str(e)[:400]}</code>")


@bot.on_message(
    filters.private
    & filters.text
    & ~filters.command(
        ["start", "help", "clone", "clonebot", "myclones", "delclone", "clones"],
        prefixes=["/", "!", "."],
    )
)
async def clone_token_paste(client, message: Message):
    if not message.from_user:
        return
    uid = message.from_user.id
    if not _pending_token.get(uid):
        return
    text = (message.text or "").strip()
    if not (TOKEN_RE.match(text) or is_bot_token(text)):
        if ":" in text and len(text) > 20:
            return await _safe_reply(
                message,
                "❌ Token format galat.\n<code>123456789:AAHxxxx...</code>",
            )
        return
    _pending_token.pop(uid, None)
    print(f"[clone] token paste from {uid}", flush=True)
    await _run_clone(client, message, text)


async def _run_clone(client, message: Message, token: str):
    uid = message.from_user.id
    token = token.strip()

    status = await _safe_reply(message, "⏳ Clone start ho raha hai... thoda wait karo.")
    if status is None:
        return

    if not _CLONE_OK:
        return await _safe_edit(
            status,
            "❌ Clone module load nahi hua.\n"
            "Panel pe <b>Rebuild / Restart</b> karo.",
        )

    if not is_bot_token(token):
        return await _safe_edit(
            status,
            "❌ Invalid token format.\nExample: <code>123456789:AAHxxxx...</code>",
        )

    ok, reason = await user_can_clone(uid)
    if not ok:
        return await _safe_edit(status, f"❌ {reason}")

    try:
        entry = await start_clone_client(token, uid)
    except Exception as e:
        print(f"[clone] start_clone_client: {e}", flush=True)
        traceback.print_exc()
        return await _safe_edit(
            status,
            f"❌ Clone fail:\n<code>{str(e)[:500]}</code>\n\n"
            "• @BotFather se <b>naya</b> token lo\n"
            "• Main Swastika bot ka token mat use karo\n"
            "• Token me space / extra text mat rakho",
        )

    try:
        await message.delete()
    except Exception:
        pass

    uname = entry.get("username") or ""
    mention = f"@{uname}" if uname else f"<code>{entry['bot_id']}</code>"
    await _safe_edit(
        status,
        f"✅ <b>Clone ready!</b>\n\n"
        f"🤖 {mention}\n"
        f"📛 {entry.get('name') or 'Clone'}\n"
        f"🆔 <code>{entry['bot_id']}</code>\n"
        f"🔧 Handlers: <code>{entry.get('handlers', '?')}</code>\n\n"
        f"Ab ye karo:\n"
        f"1. Clone bot ko group me add karo\n"
        f"2. Admin + manage video chats do\n"
        f"3. Clone pe <code>/cloneping</code>\n"
        f"4. Phir group me <code>/play song</code>\n\n"
        f"/myclones · /delclone {entry['bot_id']}",
    )


@bot.on_message(filters.command(["myclones", "myclone"], prefixes=["/", "!", "."]))
async def myclones_cmd(client, message: Message):
    try:
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
            return await _safe_reply(
                message,
                "📭 Koi clone nahi.\n<code>/clone TOKEN</code> se banao.",
            )
        lines = ["🌟 <b>Your Clones</b>\n"]
        for i, (bid, r) in enumerate(seen.items(), 1):
            un = r.get("username") or ""
            tag = f"@{un}" if un else f"<code>{bid}</code>"
            online = "🟢" if bid in running_ids else "🔴"
            lines.append(f"{i}. {online} {tag}\n   🆔 <code>{bid}</code> · /delclone {bid}")
        await _safe_reply(message, "\n".join(lines))
    except Exception as e:
        await _safe_reply(message, f"❌ {e}")


@bot.on_message(filters.command(["delclone", "removeclone", "rmclone"], prefixes=["/", "!", "."]))
async def delclone_cmd(client, message: Message):
    try:
        if not message.from_user:
            return
        uid = message.from_user.id
        args = message.command or []
        if len(args) < 2:
            return await _safe_reply(message, "Usage: <code>/delclone BOT_ID</code>")
        raw = args[1].strip().lstrip("@")
        target_id = int(raw) if raw.isdigit() else None
        if not target_id:
            return await _safe_reply(message, "❌ Numeric BOT_ID do.")
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
            return await _safe_reply(message, "❌ Clone not found.")
        if owner_of != uid and not _is_owner(uid):
            return await _safe_reply(message, "❌ Ye clone tumhara nahi.")
        await stop_clone_client(target_id)
        await _safe_reply(message, f"✅ Clone removed.\n🆔 <code>{target_id}</code>")
    except Exception as e:
        await _safe_reply(message, f"❌ {e}")


@bot.on_message(filters.command(["clones", "allclones"], prefixes=["/", "!", "."]))
async def all_clones_cmd(client, message: Message):
    if not message.from_user or not _is_owner(message.from_user.id):
        return await _safe_reply(message, "❌ Owner only.")
    rows = await db_list_clones()
    running = {c["bot_id"]: c for c in get_running_clones()}
    if not rows and not running:
        return await _safe_reply(message, "📭 No clones.")
    lines = ["👑 <b>All Clones</b>\n"]
    seen = set()
    for r in rows:
        bid = int(r["bot_id"])
        seen.add(bid)
        un = r.get("username") or ""
        tag = f"@{un}" if un else str(bid)
        online = "🟢" if bid in running else "🔴"
        lines.append(f"{online} {tag} · owner <code>{r['owner_id']}</code> · <code>{bid}</code>")
    for bid, c in running.items():
        if bid not in seen:
            un = c.get("username") or ""
            tag = f"@{un}" if un else str(bid)
            lines.append(f"🟢 {tag} · owner <code>{c['owner_id']}</code> · <code>{bid}</code>")
    await _safe_reply(message, "\n".join(lines))


print("[clone] plugin loaded OK — handlers registered", flush=True)
