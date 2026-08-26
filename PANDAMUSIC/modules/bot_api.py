"""
Telegram Bot API helpers — bypass broken kurigram KeyboardButtonUrl / Callback.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx

from .. import console


def _btn_to_api(btn) -> dict:
    d: dict[str, Any] = {"text": getattr(btn, "text", "") or ""}
    if getattr(btn, "url", None):
        d["url"] = btn.url
    if getattr(btn, "callback_data", None):
        data = btn.callback_data
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")
        d["callback_data"] = str(data)
    if getattr(btn, "icon_custom_emoji_id", None):
        d["icon_custom_emoji_id"] = str(btn.icon_custom_emoji_id)
    style = getattr(btn, "style", None)
    if style is not None:
        name = getattr(style, "name", None) or str(style)
        name = str(name).lower()
        if name in ("primary", "success", "danger"):
            d["style"] = name
    return d


def markup_to_api(markup) -> Optional[dict]:
    if markup is None:
        return None
    rows = []
    for row in getattr(markup, "inline_keyboard", []) or []:
        rows.append([_btn_to_api(b) for b in row])
    return {"inline_keyboard": rows}


def fix_html_for_bot_api(text: str) -> str:
    if not text:
        return text
    text = re.sub(
        r"<tg-emoji\s+emoji-id='([^']+)'>",
        r'<tg-emoji emoji-id="\1">',
        text,
    )
    return text


def strip_html(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"<tg-emoji[^>]*>|</tg-emoji>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text


async def _post(method: str, payload: dict) -> bool:
    token = getattr(console, "BOT_TOKEN", None)
    if not token:
        print("[bot_api] BOT_TOKEN missing", flush=True)
        return False
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, data=payload)
            data = r.json()
            if not data.get("ok"):
                print(f"[bot_api] {method} fail: {data}", flush=True)
                return False
            return True
    except Exception as e:
        print(f"[bot_api] {method} error: {e}", flush=True)
        return False


async def bot_api_send_photo(
    chat_id: int,
    photo: str,
    caption: str = "",
    reply_markup=None,
    parse_mode: str = "HTML",
) -> bool:
    api_markup = markup_to_api(reply_markup)
    markup_json = json.dumps(api_markup) if api_markup else None

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "photo": photo,
        "caption": fix_html_for_bot_api(caption or ""),
        "parse_mode": parse_mode,
    }
    if markup_json:
        payload["reply_markup"] = markup_json
    if await _post("sendPhoto", payload):
        return True

    payload2: dict[str, Any] = {
        "chat_id": chat_id,
        "photo": photo,
        "caption": strip_html(caption or "")[:1024],
    }
    if markup_json:
        payload2["reply_markup"] = markup_json
    return await _post("sendPhoto", payload2)


async def bot_api_send_message(
    chat_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    api_markup = markup_to_api(reply_markup)
    markup_json = json.dumps(api_markup) if api_markup else None

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": fix_html_for_bot_api(text),
        "parse_mode": parse_mode,
        "disable_web_page_preview": str(disable_web_page_preview).lower(),
    }
    if markup_json:
        payload["reply_markup"] = markup_json
    if await _post("sendMessage", payload):
        return True

    payload2: dict[str, Any] = {
        "chat_id": chat_id,
        "text": strip_html(text)[:4096],
        "disable_web_page_preview": "true",
    }
    if markup_json:
        payload2["reply_markup"] = markup_json
    return await _post("sendMessage", payload2)


async def bot_api_edit_message(
    chat_id: int,
    message_id: int,
    text: str = "",
    caption: str = "",
    reply_markup=None,
    is_photo: bool = False,
    parse_mode: str = "HTML",
) -> bool:
    """Edit caption (photo msg) or text — used for /start menu buttons."""
    api_markup = markup_to_api(reply_markup)
    markup_json = json.dumps(api_markup) if api_markup else None

    if is_photo or caption:
        body = fix_html_for_bot_api(caption or text)
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": body,
            "parse_mode": parse_mode,
        }
        if markup_json:
            payload["reply_markup"] = markup_json
        if await _post("editMessageCaption", payload):
            return True
        # plain caption
        payload["caption"] = strip_html(body)[:1024]
        payload.pop("parse_mode", None)
        if await _post("editMessageCaption", payload):
            return True

    body = fix_html_for_bot_api(text or caption)
    payload2: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": body,
        "parse_mode": parse_mode,
        "disable_web_page_preview": "true",
    }
    if markup_json:
        payload2["reply_markup"] = markup_json
    if await _post("editMessageText", payload2):
        return True

    payload2["text"] = strip_html(body)[:4096]
    payload2.pop("parse_mode", None)
    return await _post("editMessageText", payload2)


async def bot_api_answer_callback(callback_query_id: str, text: str = "", show_alert: bool = False) -> bool:
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
    if show_alert:
        payload["show_alert"] = "true"
    return await _post("answerCallbackQuery", payload)
