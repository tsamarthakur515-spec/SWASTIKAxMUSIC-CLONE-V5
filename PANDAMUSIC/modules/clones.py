"""
PANDAMUSIC — Clone bots manager

- New Handler instances (not shared objects)
- /start uses same full menu as main bot (no minimal override)
- Essential: only cloneping + fallback start if copy fails
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple

from pyrogram import Client

from .. import bot, console

log = console.logs(__name__)

_clone_clients: Dict[int, Dict[str, Any]] = {}
_mem_clones: List[Dict[str, Any]] = []

TOKEN_RE = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{20,100}$")


def _clone_limit() -> int:
    try:
        from os import getenv

        return max(1, int(getenv("CLONE_LIMIT", "3") or 3))
    except Exception:
        return 3


def _table() -> str:
    p = getattr(console, "TABLE_PREFIX", "pmv2_") or "pmv2_"
    return f"{p}clones"


def is_bot_token(text: str) -> bool:
    t = (text or "").strip()
    if not t or " " in t or "\n" in t:
        return False
    if TOKEN_RE.match(t):
        return True
    if ":" in t:
        left, right = t.split(":", 1)
        if left.isdigit() and 5 <= len(left) <= 15 and len(right) >= 20:
            return True
    return False


async def ensure_clone_table() -> bool:
    try:
        from . import database as db

        if not db._ok():
            return False
        t = _table()
        async with db._pool.acquire() as conn:
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {t} (
                    bot_id    BIGINT PRIMARY KEY,
                    owner_id  BIGINT NOT NULL,
                    bot_token TEXT   NOT NULL,
                    username  TEXT,
                    name      TEXT,
                    added_at  TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS {t}_owner_idx ON {t}(owner_id);
                """
            )
        return True
    except Exception as e:
        log.warning("clone table: %s", e)
        return False


async def db_list_clones(owner_id: Optional[int] = None) -> List[Dict[str, Any]]:
    try:
        from . import database as db

        if not db._ok():
            if owner_id is None:
                return list(_mem_clones)
            return [c for c in _mem_clones if int(c.get("owner_id", 0)) == int(owner_id)]
        t = _table()
        async with db._pool.acquire() as conn:
            if owner_id is None:
                rows = await conn.fetch(
                    f"SELECT bot_id, owner_id, bot_token, username, name FROM {t}"
                )
            else:
                rows = await conn.fetch(
                    f"SELECT bot_id, owner_id, bot_token, username, name FROM {t} WHERE owner_id=$1",
                    int(owner_id),
                )
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning("db_list_clones: %s", e)
        if owner_id is None:
            return list(_mem_clones)
        return [c for c in _mem_clones if int(c.get("owner_id", 0)) == int(owner_id)]


async def db_save_clone(
    bot_id: int, owner_id: int, bot_token: str, username: str = "", name: str = ""
) -> None:
    entry = {
        "bot_id": int(bot_id),
        "owner_id": int(owner_id),
        "bot_token": bot_token,
        "username": username or "",
        "name": name or "",
    }
    _mem_clones[:] = [c for c in _mem_clones if int(c.get("bot_id", 0)) != int(bot_id)]
    _mem_clones.append(entry)
    try:
        from . import database as db

        if not db._ok():
            return
        await ensure_clone_table()
        t = _table()
        async with db._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {t}(bot_id, owner_id, bot_token, username, name)
                VALUES($1, $2, $3, $4, $5)
                ON CONFLICT(bot_id) DO UPDATE SET
                    owner_id=EXCLUDED.owner_id,
                    bot_token=EXCLUDED.bot_token,
                    username=EXCLUDED.username,
                    name=EXCLUDED.name
                """,
                int(bot_id),
                int(owner_id),
                bot_token,
                username or "",
                name or "",
            )
    except Exception as e:
        log.warning("db_save_clone: %s", e)


async def db_delete_clone(bot_id: int) -> bool:
    global _mem_clones
    _mem_clones = [c for c in _mem_clones if int(c.get("bot_id", 0)) != int(bot_id)]
    try:
        from . import database as db

        if db._ok():
            t = _table()
            async with db._pool.acquire() as conn:
                await conn.execute(f"DELETE FROM {t} WHERE bot_id=$1", int(bot_id))
        return True
    except Exception as e:
        log.warning("db_delete_clone: %s", e)
        return True


def _clone_handler(handler) -> Any:
    """Create a NEW handler instance (sharing objects breaks multi-client)."""
    cls = type(handler)
    callback = getattr(handler, "callback", None)
    if callback is None:
        return None
    filters_ = getattr(handler, "filters", None)
    for args in ((callback, filters_), (callback,)):
        try:
            return cls(*args)
        except TypeError:
            continue
        except Exception:
            continue
    try:
        return cls(callback=callback, filters=filters_)
    except Exception:
        pass
    try:
        return cls(callback)
    except Exception as e:
        log.warning("clone_handler skip %s: %s", cls.__name__, e)
        return None


def _copy_handlers(source: Client, target: Client) -> int:
    count = 0
    try:
        dispatcher = getattr(source, "dispatcher", None)
        if dispatcher is None:
            return 0
        groups = getattr(dispatcher, "groups", None) or {}
        for group_id, handlers in list(groups.items()):
            for handler in list(handlers):
                new_h = _clone_handler(handler)
                if new_h is None:
                    continue
                try:
                    target.add_handler(new_h, group_id)
                    count += 1
                except Exception as e:
                    log.warning("add_handler skip: %s", e)
    except Exception as e:
        log.error("_copy_handlers failed: %s", e)
    return count


def _attach_cloneping(client: Client) -> None:
    from pyrogram import filters
    from pyrogram.handlers import MessageHandler

    async def _ping(c, m):
        try:
            me = await c.get_me()
            un = f"@{me.username}" if me.username else str(me.id)
            await m.reply_text(f"✅ Clone online — {un}\n🆔 `{me.id}`")
        except Exception as e:
            try:
                await m.reply_text(f"✅ Clone alive\n{e}")
            except Exception:
                pass

    try:
        client.add_handler(
            MessageHandler(
                _ping, filters.command(["cloneping", "cping"], ["/", "!", "."])
            ),
            group=-1,
        )
    except Exception as e:
        log.warning("cloneping attach: %s", e)


def _attach_start_fallback(client: Client) -> None:
    """Only when plugin handlers failed to copy — still try real start menu."""
    from pyrogram import filters
    from pyrogram.handlers import MessageHandler

    async def _start(c, m):
        # Prefer real start menu from plugins
        try:
            from ..plugins.start import start_message_private

            return await start_message_private(c, m)
        except Exception as e1:
            log.warning("clone start→plugin fail: %s", e1)
        try:
            me = await c.get_me()
            un = f"@{me.username}" if me.username else str(me.id)
            await m.reply_text(
                f"✅ {un} online\n\n"
                f"Use /play in a group with video chat admin.\n"
                f"/cloneping — status"
            )
        except Exception as e2:
            try:
                await m.reply_text(f"Clone online\n{e2}")
            except Exception:
                pass

    try:
        client.add_handler(
            MessageHandler(
                _start, filters.command(["start", "help"], ["/", "!", "."])
            ),
            group=0,
        )
    except Exception as e:
        log.warning("start fallback attach: %s", e)


async def start_clone_client(
    token: str,
    owner_id: int,
    bot_id: int = 0,
    username: str = "",
    name: str = "",
) -> Dict[str, Any]:
    """Start clone, copy plugin handlers from main bot, keep client running."""
    token = (token or "").strip()
    if not is_bot_token(token):
        raise RuntimeError("Invalid bot token format. Example: 123456789:AAHxxxx...")

    if console.BOT_TOKEN and token == str(console.BOT_TOKEN).strip():
        raise RuntimeError("Ye main bot ka token hai — clone nahi banega.")

    for bid, ent in list(_clone_clients.items()):
        if ent.get("token") == token or (bot_id and bid == int(bot_id)):
            log.info("Clone already running id=%s", bid)
            return ent

    if not console.API_ID or not console.API_HASH:
        raise RuntimeError("API_ID / API_HASH missing in config.")

    session = f"clone_{token.split(':', 1)[0]}"
    client = Client(
        session,
        api_id=int(console.API_ID),
        api_hash=str(console.API_HASH),
        bot_token=token,
        in_memory=True,
        workers=8,
    )

    try:
        await client.start()
    except Exception as e:
        err = str(e).lower()
        if "unauthorized" in err or "access_token" in err or "token" in err:
            raise RuntimeError(
                f"Token invalid / revoked. @BotFather se naya token lo.\nDetail: {e}"
            ) from e
        raise RuntimeError(f"Telegram start fail: {e}") from e

    try:
        me = await client.get_me()
    except Exception as e:
        try:
            await client.stop()
        except Exception:
            pass
        raise RuntimeError(f"get_me fail (token invalid?): {e}") from e

    if not getattr(me, "is_bot", True):
        try:
            await client.stop()
        except Exception:
            pass
        raise RuntimeError("Ye user account token nahi — sirf BotFather bot token use karo.")

    bot_id = int(me.id)
    username = me.username or username or ""
    name = (
        ((me.first_name or "") + (" " + me.last_name if me.last_name else "")).strip()
        or name
        or "CloneBot"
    )

    if bot_id in _clone_clients:
        try:
            await client.stop()
        except Exception:
            pass
        return _clone_clients[bot_id]

    # Copy ALL main-bot plugin handlers (includes full /start menu)
    n = _copy_handlers(bot, client)
    _attach_cloneping(client)

    # Only if copy failed — attach start that still tries real menu
    if n == 0:
        log.warning("Clone %s: 0 handlers copied — attaching start fallback", bot_id)
        _attach_start_fallback(client)

    try:
        client.me = me  # type: ignore
        client.username = username  # type: ignore
        client.id = bot_id  # type: ignore
        client.name = name  # type: ignore
    except Exception:
        pass

    entry = {
        "client": client,
        "token": token,
        "owner_id": int(owner_id),
        "bot_id": bot_id,
        "username": username,
        "name": name,
        "handlers": n,
    }
    _clone_clients[bot_id] = entry
    await db_save_clone(bot_id, int(owner_id), token, username, name)

    log.info(
        "Clone started @%s id=%s owner=%s handlers_copied=%s",
        username,
        bot_id,
        owner_id,
        n,
    )
    return entry


async def stop_clone_client(bot_id: int) -> bool:
    entry = _clone_clients.pop(int(bot_id), None)
    if entry:
        client = entry.get("client")
        try:
            if client is not None:
                await client.stop()
        except Exception as e:
            log.warning("stop clone %s: %s", bot_id, e)
    await db_delete_clone(int(bot_id))
    return entry is not None


def get_running_clones() -> List[Dict[str, Any]]:
    return [
        {
            "bot_id": v["bot_id"],
            "owner_id": v["owner_id"],
            "username": v.get("username") or "",
            "name": v.get("name") or "",
            "handlers": v.get("handlers", True),
        }
        for v in _clone_clients.values()
    ]


async def start_all_saved_clones() -> int:
    await ensure_clone_table()
    rows = await db_list_clones()
    started = 0
    for row in rows:
        token = (row.get("bot_token") or "").strip()
        owner_id = int(row.get("owner_id") or 0)
        if not token or not owner_id:
            continue
        try:
            await start_clone_client(
                token,
                owner_id,
                bot_id=int(row.get("bot_id") or 0),
                username=row.get("username") or "",
                name=row.get("name") or "",
            )
            started += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            log.error("Failed saved clone %s: %s", row.get("bot_id"), e)
    log.info("Clones online: %s", started)
    return started


async def user_can_clone(owner_id: int) -> Tuple[bool, str]:
    owner_id = int(owner_id)
    if owner_id == getattr(console, "OWNER_ID", 0):
        return True, ""
    rows = await db_list_clones(owner_id)
    running = sum(1 for c in _clone_clients.values() if int(c["owner_id"]) == owner_id)
    n = max(len(rows), running)
    limit = _clone_limit()
    if n >= limit:
        return (
            False,
            f"Limit full — max {limit} clone(s). /delclone se purana hatao.",
        )
    return True, ""


async def validate_bot_token(token: str) -> Optional[Dict[str, Any]]:
    token = (token or "").strip()
    if not is_bot_token(token):
        return None
    parts = token.split(":", 1)
    try:
        bid = int(parts[0])
    except Exception:
        bid = 0
    return {"id": bid, "username": "", "name": "", "token": token}
