import html

from .custom_emojis import (
    tg_emoji,
    CE_STREAM,
    CE_TITLE,
    CE_DURATION,
    CE_REQUEST,
    CE_POWERED,
    CE_QUEUE,
    E,
)

_SMALL_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)


def smallcaps(text) -> str:
    return str(text or "").translate(_SMALL_MAP)


def panel_caption(
    title: str,
    duration: str,
    requester: str,
    header: str = "sᴛʀᴇᴀᴍɪɴɢ ɪɴ ᴠᴄ",
) -> str:
    t = html.escape(smallcaps(title))
    d = html.escape(smallcaps(str(duration or "0:00")))
    if "<a " in str(requester):
        req = requester
    else:
        req = html.escape(smallcaps(requester))

    h = f"{tg_emoji(CE_STREAM, '🔥')} {html.escape(header)}"

    return (
        f"<blockquote expandable>"
        f"{h}\n\n"
        f"{tg_emoji(CE_TITLE, '🌟')} {smallcaps('title')} : {t}\n"
        f"{tg_emoji(CE_DURATION, '🌀')} {smallcaps('duration')} : {d}\n"
        f"{tg_emoji(CE_REQUEST, '🦋')} {smallcaps('request by')} : {req}\n\n"
        f"{tg_emoji(CE_POWERED, '🐺')} ᴘᴏᴡᴇʀᴇᴅ ʙʏ : sᴡᴀsᴛɪᴋᴀ\n"
        f"{tg_emoji(E.SPARKLES, '✨')} ʏᴛ ᴍᴜsɪᴄ ᴀᴘɪ ᴘᴏᴡᴇʀᴇᴅ ʙʏ : ᴀʀᴜʏᴛ ᴀᴘɪ"
        f"</blockquote>"
    )


def queue_caption(
    position: int,
    title: str,
    duration: str,
    requester: str,
) -> str:
    header = f"{smallcaps('added to queue')} #{position}"
    t = html.escape(smallcaps(title))
    d = html.escape(smallcaps(str(duration or "0:00")))
    if "<a " in str(requester):
        req = requester
    else:
        req = html.escape(smallcaps(requester))

    return (
        f"<blockquote expandable>"
        f"{tg_emoji(CE_QUEUE, '🔥')} {html.escape(header)}\n\n"
        f"{tg_emoji(CE_TITLE, '🌟')} {smallcaps('title')} : {t}\n"
        f"{tg_emoji(CE_DURATION, '🌀')} {smallcaps('duration')} : {d}\n"
        f"{tg_emoji(CE_REQUEST, '🦋')} {smallcaps('request by')} : {req}"
        f"</blockquote>"
    )
