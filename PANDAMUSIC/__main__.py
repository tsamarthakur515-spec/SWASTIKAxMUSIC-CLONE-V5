import asyncio
import os
import sys

# MUST run before any pyrogram message/callback parse
from .modules import kurigram_patch  # noqa: F401

import pyrogram

from . import app, bot, call, console
from .modules.database import init_db
from .plugins import import_all_plugins


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

    # Start user clone bots (same handlers + assistants)
    try:
        from .modules.clones import start_all_saved_clones

        n = await start_all_saved_clones()
        console.logs(__name__).info(f"✅ Clone bots started: {n}")
    except Exception as e:
        console.logs(__name__).warning(f"⚠️ Clone restore skipped: {e}")

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
