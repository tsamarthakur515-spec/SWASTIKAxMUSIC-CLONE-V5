import logging
import os
import sys
import time

from os import getenv
from pyrogram import filters
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s:\n%(message)s\n",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("logs.txt", maxBytes=5000000, backupCount=10),
        logging.StreamHandler(),
    ],
)

logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)


def logs(name: str) -> logging.Logger:
    return logging.getLogger(name)


def _env_int(key: str, default: int = 0) -> int:
    val = getenv(key, "")
    if val is None:
        return default
    val = str(val).strip().strip('"').strip("'")
    if not val:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _env_str(key: str, default: str = "") -> str:
    val = getenv(key, default)
    if val is None:
        return default or ""
    return str(val).strip().strip('"').strip("'")


_boot_ = time.time()
plugs = {}
chat_admins = {}
chat_links = {}
sudoers = filters.user()

# Load Config.env from CWD and from package parent (more reliable on VPS)
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
for _cfg in (
    os.path.join(os.getcwd(), "Config.env"),
    os.path.join(_root, "Config.env"),
    "Config.env",
):
    if os.path.isfile(_cfg):
        load_dotenv(_cfg, override=True)
        break


try:
    API_ID = _env_int("API_ID", 0)
    API_HASH = _env_str("API_HASH", "") or None
    BOT_TOKEN = _env_str("BOT_TOKEN", "") or None
    OWNER_ID = _env_int("OWNER_ID", 0)
    LOG_GROUP_ID = _env_int("LOG_GROUP_ID", 0)

    DB_HOST = _env_str("DB_HOST", "") or None
    DB_PORT = _env_int("DB_PORT", 6543)
    DB_USER = _env_str("DB_USER", "") or None
    DB_PASSWORD = _env_str("DB_PASSWORD", "") or None
    DB_NAME = _env_str("DB_NAME", "postgres") or "postgres"

    TABLE_PREFIX = _env_str("TABLE_PREFIX", "pmv2_") or "pmv2_"

    SHRUTI_API_URL = _env_str("SHRUTI_API_URL", "https://aruyt.up.railway.app") or "https://aruyt.up.railway.app"
    SHRUTI_API_KEY = _env_str("SHRUTI_API_KEY", "")

    GROQ_API_KEY = _env_str("GROQ_API_KEY", "") or ""
    GROQ_API_BASE = _env_str("GROQ_API_BASE", "https://api.groq.com/openai/v1") or "https://api.groq.com/openai/v1"
    GROQ_MODEL = _env_str("GROQ_MODEL", "openai/gpt-oss-20b") or "openai/gpt-oss-20b"

    # Same style as BOT_TOKEN — panel Config.env me daalo
    GITHUB_TOKEN = _env_str("GITHUB_TOKEN", "") or ""
    GITHUB_REPO = _env_str("GITHUB_REPO", "tsamarthakur515-spec/SWASTIKA-MUSIC-V5") or "tsamarthakur515-spec/SWASTIKA-MUSIC-V5"
    GITHUB_BRANCH = _env_str("GITHUB_BRANCH", "main") or "main"
except Exception as e:
    logs(__name__).error(f"Variable Error: {e}")
    sys.exit(1)


STRING1 = _env_str("STRING_SESSION", "") or None
STRING2 = _env_str("STRING_SESSION2", "") or None
STRING3 = _env_str("STRING_SESSION3", "") or None
STRING4 = _env_str("STRING_SESSION4", "") or None
STRING5 = _env_str("STRING_SESSION5", "") or None

DURATION_LIMIT = _env_int("DURATION_LIMIT", 60)
START_IMAGE_URL = _env_str(
    "START_IMAGE_URL",
    "https://graph.org/file/918101d0ad6b1207e6201.png",
) or "https://graph.org/file/918101d0ad6b1207e6201.png"
STATS_IMAGE_URL = _env_str(
    "STATS_IMAGE_URL",
    "https://files.catbox.moe/bf1vcn.jpg",
) or "https://files.catbox.moe/bf1vcn.jpg"
PING_IMAGE_URL = _env_str(
    "PING_IMAGE_URL",
    "https://files.catbox.moe/wfqfeh.jpg",
) or "https://files.catbox.moe/wfqfeh.jpg"
OWNER_USERNAME = _env_str("OWNER_USERNAME", "").lstrip("@")
SUPPORT_CHAT = _env_str("SUPPORT_CHAT", "").lstrip("@")
SUPPORT_CHANNEL = _env_str("SUPPORT_CHANNEL", "").lstrip("@")

if GROQ_API_KEY:
    logs(__name__).info(f"Groq chatbot ready | model={GROQ_MODEL}")
else:
    logs(__name__).warning("GROQ_API_KEY missing — chatbot will use fallback only")


async def sudo_users():
    from .modules.database import get_sudoers_list, add_sudo

    global sudoers

    if OWNER_ID != 0:
        if OWNER_ID not in sudoers:
            sudoers.add(OWNER_ID)
        try:
            await add_sudo(OWNER_ID)
        except Exception:
            pass

    try:
        sudousers = await get_sudoers_list()
    except Exception:
        sudousers = [OWNER_ID] if OWNER_ID else []

    for user_id in sudousers:
        if user_id and user_id not in sudoers:
            sudoers.add(user_id)

    logs(__name__).info("All Sudo Users Loaded.")
