import asyncio
import os
import re
import sys
import traceback

# MUST run before any pyrogram message/callback parse
from .modules import kurigram_patch  # noqa: F401

import pyrogram
from pyrogram import filters
from pyrogram.enums import ParseMode

from . import app, bot, call, console
from .modules.database import init_db
from .plugins import import_all_plugins


def _force_load_clone_plugin() -> bool:
    """Ensure clone.py is imported even if plugin loader skipped it."""
    import importlib

    try:
        mod = importlib.import_module("PANDAMUSIC.plugins.clone")
        # re-load if needed
        importlib.reload(mod)
        console.logs(__name__).info("✅ clone plugin force-loaded")
        return True
    except Exception as e:
        console.logs(__name__).error(f"❌ clone plugin force-load failed: {e}")
        traceback.print_exc()
        return False


def _register_emergency_clone_handler():
    """Minimal /clone so command never silent if plugin broken."""

    token_re = re.compile(r"(\d{5,15}:[A-Za-z0-9_-]{20,100})")

    @bot.on_message(filters.command(["clone", "clonebot"], prefixes=["/", "!", "."]))
    async def _emergency_clone(client, message):
        print(
            f"[clone-emergency] hit from {getattr(message.from_user, 'id', None)}",
            flush=True,
        )
        try:
            # Prefer real plugin handler path if available
            try:
                from .plugins import clone as clone_mod

                if hasattr(clone_mod, "_do_clone") and hasattr(clone_mod, "_extract_token"):
                    token = clone_mod._extract_token(message)
                    if token:
                        await clone_mod._do_clone(message, token)
                        return
                    # fall through to help
            except Exception as e:
                print(f"[clone-emergency] plugin path fail: {e}", flush=True)

            text = (message.text or "") or ""
            compact = re.sub(r"\s+", "", text)
            m = token_re.search(compact)
            if not m:
                await message.reply_text(
                    "✨ <b>Clone</b>\n\n"
                    "Usage:\n<code>/clone 123456:AAHxxxx</code>\n\n"
                    "Token ek line me bhejo.",
                    parse_mode=ParseMode.HTML,
                )
                return

            token = m.group(1)
            status = await message.reply_text(
                "⏳ <b>cloning....</b>", parse_mode=ParseMode.HTML
            )
            try:
                await message.delete()
            except Exception:
                pass

            from .modules.clones import start_clone_client, user_can_clone

            uid = message.from_user.id if message.from_user else 0
            ok, reason = await user_can_clone(uid)
            if not ok:
                await status.edit_text(f"❌ {reason}")
                return

            entry = await start_clone_client(token, uid)
            uname = (entry.get("username") or "").strip()
            who = f"@{uname}" if uname else f"<code>{entry['bot_id']}</code>"
            await status.edit_text(
                f"✅ <b>Bot Cloned!</b>\n\n"
                f"🤖 Username: <b>{who}</b>\n"
                f"🆔 <code>{entry['bot_id']}</code>\n\n"
                f"/myclones · /delclone {entry['bot_id']}",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            print(f"[clone-emergency] error: {e}", flush=True)
            traceback.print_exc()
            try:
                await message.reply_text(f"❌ Clone error:\n<code>{str(e)[:400]}</code>", parse_mode=ParseMode.HTML)
            except Exception:
                pass

    console.logs(__name__).info("✅ Emergency /clone handler registered")


async def main():
    # Old session files clean
    for file in os.listdir():
        if file.endswith(".session") or file.endswith(".session-journal"):
            try:
                os.remove(file)
            except Exception:
                pass

    # Required folders
    os.makedirs("cache", exist_ok=True)
    os.makedirs("downloads", exist_ok=True)

    # PostgreSQL init (optional — bot runs even if DB is missing/fails)
    try:
        await init_db()
    except Exception as e:
        console.logs(__name__).warning(
            f"⚠️ Database init skipped: {e} — continuing without DB"
        )

    # Load sudo users
    try:
        await console.sudo_users()
    except Exception as e:
        console.logs(__name__).error(f"❌ Sudo load failed: {e}")
        sys.exit(1)

    # Start bot
    try:
        await bot.start()
    except Exception as e:
        console.logs(__name__).error(f"❌ Failed to start bot: {e}")
        sys.exit(1)

    # Start assistant(s)
    try:
        await app.start()
    except Exception as e:
        console.logs(__name__).error(f"❌ Failed to start assistant: {e}")
        sys.exit(1)

    # Start PyTgCalls
    try:
        await call.start()
    except Exception as e:
        console.logs(__name__).error(f"❌ Failed to start PyTgCalls: {e}")
        sys.exit(1)

    await call.decorators()
    await import_all_plugins()

    # Force clone plugin + emergency handler (never silent /clone)
    ok = _force_load_clone_plugin()
    if not ok:
        _register_emergency_clone_handler()
    else:
        # still register emergency as backup (group later = lower priority if both fire —
        # actually both may fire; emergency only if plugin missing)
        pass

    # Always register emergency as safety net on group 10 (runs if others don't answer)
    # Use group -5 for high priority emergency
    try:
        _register_emergency_clone_handler()
    except Exception as e:
        console.logs(__name__).error(f"emergency clone register fail: {e}")

    # Start user clone bots (same handlers + assistants)
    try:
        from .modules.clones import start_all_saved_clones

        n = await start_all_saved_clones()
        console.logs(__name__).info(f"✅ Clone bots started: {n}")
    except Exception as e:
        console.logs(__name__).warning(f"⚠️ Clone restore skipped: {e}")

    # Debug: count handlers on bot
    try:
        disp = getattr(bot, "dispatcher", None)
        groups = getattr(disp, "groups", {}) or {}
        total = sum(len(v) for v in groups.values())
        console.logs(__name__).info(f"✅ Bot handlers total: {total}")
    except Exception:
        pass

    console.logs(__name__).info("✅ Bot started successfully!")
    await pyrogram.idle()


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        console.logs(__name__).info("✅ All clients stopped. Goodbye.")
