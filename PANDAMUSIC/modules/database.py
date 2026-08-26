"""
PANDAMUSIC — PostgreSQL Database Layer (asyncpg)

TABLE_PREFIX — har bot ka apna prefix.
DB OPTIONAL: connection fail pe bot in-memory mode me chalta hai.
"""

import asyncio
import random
from typing import List, Optional, Set

import asyncpg

from .. import console

log = console.logs(__name__)

_pool: Optional[asyncpg.Pool] = None
assistantdict = {}

_mem_users: Set[int] = set()
_mem_chats: Set[int] = set()

_P = console.TABLE_PREFIX

T_ASSISTANTS = f"{_P}assistants"
T_USERS = f"{_P}served_users"
T_CHATS = f"{_P}served_chats"
T_ADMINS_ONLY = f"{_P}admins_only"
T_SUDOERS = f"{_P}sudoers"


async def _try_pool(host: str, port: int, user: str, password: str, database: str):
    """Create pool for one host:port. Raises on failure."""
    return await asyncpg.create_pool(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        min_size=1,
        max_size=8,
        command_timeout=30,
        timeout=15,
        ssl="require",
        statement_cache_size=0,
    )


async def init_db():
    """Connect to PostgreSQL. Tries configured port then 5432/6543 fallbacks."""
    global _pool
    _pool = None

    host = (console.DB_HOST or "").strip().strip('"').strip("'")
    user = (console.DB_USER or "").strip().strip('"').strip("'")
    password = (console.DB_PASSWORD or "").strip().strip('"').strip("'")
    database = (console.DB_NAME or "postgres").strip().strip('"').strip("'") or "postgres"
    cfg_port = int(getattr(console, "DB_PORT", 5432) or 5432)

    if not host or not user:
        log.warning(
            "⚠️ DB_HOST / DB_USER missing — running WITHOUT database (in-memory only)."
        )
        return

    # Prefer config port, then common Supabase ports
    ports = []
    for p in (cfg_port, 5432, 6543):
        if p not in ports:
            ports.append(p)

    last_err = None
    for port in ports:
        try:
            log.info(f"🔄 DB connecting → {host}:{port} user={user} db={database}")
            _pool = await _try_pool(host, port, user, password, database)
            # quick health check
            async with _pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            log.info(f"✅ PostgreSQL connected ({host}:{port}, prefix='{_P}')")
            break
        except Exception as e:
            last_err = e
            log.warning(f"⚠️ DB {host}:{port} failed: {type(e).__name__}: {e}")
            if _pool is not None:
                try:
                    await _pool.close()
                except Exception:
                    pass
            _pool = None

    if _pool is None:
        log.warning(
            f"⚠️ DB connection failed (last: {last_err}) — "
            "running WITHOUT database (in-memory only).\n"
            "  → Supabase dashboard me project Unpause / Restore karo\n"
            "  → Settings → Database se naya host/password copy karke Config.env update karo"
        )
        return

    try:
        await _create_tables()
    except Exception as e:
        log.warning(f"⚠️ Table create failed: {e}")

    try:
        async with _pool.acquire() as conn:
            urows = await conn.fetch(f"SELECT user_id FROM {T_USERS} WHERE user_id > 0")
            crows = await conn.fetch(f"SELECT chat_id FROM {T_CHATS} WHERE chat_id < 0")
        for r in urows:
            _mem_users.add(int(r["user_id"]))
        for r in crows:
            _mem_chats.add(int(r["chat_id"]))
        log.info(f"✅ Cache warmed — users={len(_mem_users)} chats={len(_mem_chats)}")
    except Exception as e:
        log.warning(f"⚠️ Cache warm failed: {e}")


async def _create_tables():
    async with _pool.acquire() as conn:
        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {T_ASSISTANTS} (
                chat_id   BIGINT PRIMARY KEY,
                assistant INT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS {T_USERS} (
                user_id  BIGINT PRIMARY KEY,
                added_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS {T_CHATS} (
                chat_id  BIGINT PRIMARY KEY,
                added_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS {T_ADMINS_ONLY} (
                chat_id BIGINT  PRIMARY KEY,
                value   BOOLEAN DEFAULT TRUE
            );

            CREATE TABLE IF NOT EXISTS {T_SUDOERS} (
                id      TEXT     PRIMARY KEY DEFAULT 'sudo',
                sudoers BIGINT[] DEFAULT '{{}}'
            );
        """
        )
    log.info(f"✅ Tables ready — prefix '{_P}'")


def _ok() -> bool:
    return _pool is not None


async def get_client(assistant: int):
    from .. import app

    mapping = {1: app.one, 2: app.two, 3: app.three, 4: app.four, 5: app.five}
    return mapping.get(int(assistant))


async def set_assistant(chat_id: int):
    from .clients import assistants

    ran = random.choice(assistants)
    assistantdict[chat_id] = ran
    if _ok():
        async with _pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {T_ASSISTANTS}(chat_id, assistant) VALUES($1, $2)
                   ON CONFLICT(chat_id) DO UPDATE SET assistant=EXCLUDED.assistant""",
                chat_id,
                ran,
            )
    return await get_client(ran)


async def get_assistant(chat_id: int):
    from .clients import assistants

    assistant = assistantdict.get(chat_id)
    if not assistant:
        if _ok():
            async with _pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT assistant FROM {T_ASSISTANTS} WHERE chat_id=$1", chat_id
                )
            if row and row["assistant"] in assistants:
                assistantdict[chat_id] = row["assistant"]
                return await get_client(row["assistant"])
        return await set_assistant(chat_id)
    if assistant in assistants:
        return await get_client(assistant)
    return await set_assistant(chat_id)


async def set_calls_assistant(chat_id: int) -> int:
    from .clients import assistants

    ran = random.choice(assistants)
    assistantdict[chat_id] = ran
    if _ok():
        async with _pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {T_ASSISTANTS}(chat_id, assistant) VALUES($1, $2)
                   ON CONFLICT(chat_id) DO UPDATE SET assistant=EXCLUDED.assistant""",
                chat_id,
                ran,
            )
    return ran


async def group_assistant(self, chat_id: int):
    from .clients import assistants

    assistant = assistantdict.get(chat_id)
    if not assistant:
        if _ok():
            async with _pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT assistant FROM {T_ASSISTANTS} WHERE chat_id=$1", chat_id
                )
            if row and row["assistant"] in assistants:
                assistantdict[chat_id] = row["assistant"]
                assistant = row["assistant"]
            else:
                assistant = await set_calls_assistant(chat_id)
        else:
            assistant = await set_calls_assistant(chat_id)
    elif assistant not in assistants:
        assistant = await set_calls_assistant(chat_id)

    mapping = {1: self.one, 2: self.two, 3: self.three, 4: self.four, 5: self.five}
    return mapping.get(int(assistant), self.one)


async def is_served_user(user_id: int) -> bool:
    if not user_id or user_id <= 0:
        return False
    if user_id in _mem_users:
        return True
    if not _ok():
        return False
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT 1 FROM {T_USERS} WHERE user_id=$1", user_id
        )
    if row is not None:
        _mem_users.add(user_id)
        return True
    return False


async def add_served_user(user_id: int):
    if not user_id or user_id <= 0:
        return
    _mem_users.add(int(user_id))
    if not _ok():
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO {T_USERS}(user_id) VALUES($1) ON CONFLICT DO NOTHING",
                user_id,
            )
    except Exception as e:
        log.warning(f"add_served_user DB error: {e}")


async def get_served_users() -> list:
    ids: Set[int] = set(_mem_users)
    if _ok():
        try:
            async with _pool.acquire() as conn:
                rows = await conn.fetch(
                    f"SELECT user_id FROM {T_USERS} WHERE user_id > 0"
                )
            for r in rows:
                uid = int(r["user_id"])
                ids.add(uid)
                _mem_users.add(uid)
        except Exception as e:
            log.warning(f"get_served_users DB error: {e}")
    return [{"user_id": uid} for uid in ids if uid > 0]


async def count_served_users() -> int:
    users = await get_served_users()
    return len(users)


async def is_served_chat(chat_id: int) -> bool:
    if not chat_id:
        return False
    if chat_id in _mem_chats:
        return True
    if not _ok():
        return False
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT 1 FROM {T_CHATS} WHERE chat_id=$1", chat_id
        )
    if row is not None:
        _mem_chats.add(chat_id)
        return True
    return False


async def add_served_chat(chat_id: int):
    if not chat_id:
        return
    cid = int(chat_id)
    if cid < 0:
        _mem_chats.add(cid)
    if not _ok():
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO {T_CHATS}(chat_id) VALUES($1) ON CONFLICT DO NOTHING",
                cid,
            )
    except Exception as e:
        log.warning(f"add_served_chat DB error: {e}")


async def get_served_chats() -> list:
    ids: Set[int] = set(c for c in _mem_chats if c < 0)
    if _ok():
        try:
            async with _pool.acquire() as conn:
                rows = await conn.fetch(
                    f"SELECT chat_id FROM {T_CHATS} WHERE chat_id < 0"
                )
            for r in rows:
                cid = int(r["chat_id"])
                ids.add(cid)
                _mem_chats.add(cid)
        except Exception as e:
            log.warning(f"get_served_chats DB error: {e}")
    return [{"chat_id": cid} for cid in ids if cid < 0]


async def count_served_chats() -> int:
    chats = await get_served_chats()
    return len(chats)


async def is_admins_only(chat_id: int) -> bool:
    if not _ok():
        return True
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT value FROM {T_ADMINS_ONLY} WHERE chat_id=$1", chat_id
        )
    if not row:
        return True
    return bool(row["value"])


async def set_admins_only(chat_id: int, value: bool) -> bool:
    if not _ok():
        return bool(value)
    async with _pool.acquire() as conn:
        await conn.execute(
            f"""INSERT INTO {T_ADMINS_ONLY}(chat_id, value) VALUES($1, $2)
               ON CONFLICT(chat_id) DO UPDATE SET value=EXCLUDED.value""",
            chat_id,
            bool(value),
        )
    return bool(value)


async def get_sudoers_list() -> List[int]:
    if not _ok():
        return [console.OWNER_ID] if console.OWNER_ID else []
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT sudoers FROM {T_SUDOERS} WHERE id='sudo'"
        )
    if not row or not row["sudoers"]:
        return [console.OWNER_ID] if console.OWNER_ID else []
    sudos = list(row["sudoers"])
    if console.OWNER_ID and console.OWNER_ID not in sudos:
        sudos.append(console.OWNER_ID)
    return sudos


async def add_sudo(user_id: int):
    sudos = await get_sudoers_list()
    if user_id not in sudos:
        sudos.append(user_id)
    if _ok():
        async with _pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {T_SUDOERS}(id, sudoers) VALUES('sudo', $1)
                   ON CONFLICT(id) DO UPDATE SET sudoers=EXCLUDED.sudoers""",
                sudos,
            )
    try:
        if user_id not in console.sudoers:
            console.sudoers.add(user_id)
    except Exception:
        pass


async def remove_sudo(user_id: int) -> bool:
    if user_id == console.OWNER_ID:
        return False
    sudos = await get_sudoers_list()
    if user_id not in sudos:
        return False
    sudos = [x for x in sudos if x != user_id]
    if console.OWNER_ID and console.OWNER_ID not in sudos:
        sudos.append(console.OWNER_ID)
    if _ok():
        async with _pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {T_SUDOERS}(id, sudoers) VALUES('sudo', $1)
                   ON CONFLICT(id) DO UPDATE SET sudoers=EXCLUDED.sudoers""",
                sudos,
            )
    try:
        if hasattr(console.sudoers, "discard"):
            console.sudoers.discard(user_id)
        elif hasattr(console.sudoers, "remove"):
            try:
                console.sudoers.remove(user_id)
            except Exception:
                pass
    except Exception:
        pass
    return True


async def count_sudoers() -> int:
    try:
        return len(await get_sudoers_list())
    except Exception:
        return 1 if console.OWNER_ID else 0
