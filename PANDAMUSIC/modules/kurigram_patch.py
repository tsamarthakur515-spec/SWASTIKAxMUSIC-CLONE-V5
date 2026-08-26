"""
Fix broken kurigram installs + UpdateGroupCall chat_id crashes with pytgcalls.
Must be imported BEFORE bot handlers process updates.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def _peer_to_chat_id(peer):
    """Convert InputPeer / Peer* to pyrogram-style chat_id."""
    if peer is None:
        return None
    # PeerChannel / PeerChat / PeerUser and InputPeer*
    channel_id = getattr(peer, "channel_id", None)
    if channel_id is not None:
        return int(f"-100{channel_id}")
    chat_id = getattr(peer, "chat_id", None)
    if chat_id is not None:
        return -int(chat_id)
    user_id = getattr(peer, "user_id", None)
    if user_id is not None:
        return int(user_id)
    return None


def _patch_update_group_call_chat_id() -> None:
    """
    Kurigram / newer TL sometimes deliver UpdateGroupCall* without .chat_id
    (only .peer or nested call). Pyrogram dispatcher then does update.chat_id
    and crashes: AttributeError: 'UpdateGroupCall' object has no attribute 'chat_id'
    """
    try:
        from pyrogram.raw import types as raw_types
    except Exception as e:
        log.warning("kurigram_patch: raw.types import failed: %s", e)
        return

    names = (
        "UpdateGroupCall",
        "UpdateGroupCallParticipants",
        "UpdateGroupCallConnection",
        "UpdateGroupCallMessage",
        "UpdateGroupCallChain",
    )

    for name in names:
        cls = getattr(raw_types, name, None)
        if cls is None:
            continue
        if getattr(cls, "_panda_chat_id_patched", False):
            continue

        # Instance __getattr__ fallback so update.chat_id never AttributeErrors
        orig_getattribute = getattr(cls, "__getattribute__", object.__getattribute__)

        def _make_getattribute(orig):
            def __getattribute__(self, item):
                try:
                    return orig(self, item)
                except AttributeError:
                    if item != "chat_id":
                        raise
                    # Derive from peer / call / chat
                    for attr in ("peer", "chat", "call"):
                        try:
                            obj = orig(self, attr)
                        except AttributeError:
                            obj = None
                        cid = _peer_to_chat_id(obj)
                        if cid is not None:
                            try:
                                object.__setattr__(self, "chat_id", cid)
                            except Exception:
                                pass
                            return cid
                        # call may embed peer
                        if obj is not None:
                            nested = getattr(obj, "peer", None) or getattr(obj, "chat_id", None)
                            if nested is not None and not isinstance(nested, int):
                                cid = _peer_to_chat_id(nested)
                                if cid is not None:
                                    try:
                                        object.__setattr__(self, "chat_id", cid)
                                    except Exception:
                                        pass
                                    return cid
                            if isinstance(nested, int):
                                try:
                                    object.__setattr__(self, "chat_id", nested)
                                except Exception:
                                    pass
                                return nested
                    # Last resort: avoid crash — dispatcher can skip
                    return 0

            return __getattribute__

        try:
            cls.__getattribute__ = _make_getattribute(orig_getattribute)  # type: ignore
            cls._panda_chat_id_patched = True  # type: ignore
            log.info("kurigram_patch: %s.chat_id fallback patched", name)
        except Exception as e:
            log.warning("kurigram_patch: could not patch %s: %s", name, e)


def _patch_dispatcher_skip_bad_updates() -> None:
    """Skip updates that still cannot resolve a chat, instead of crashing the client."""
    try:
        from pyrogram.dispatcher import Dispatcher
    except Exception:
        return

    if getattr(Dispatcher, "_panda_handler_patched", False):
        return

    orig_handler = getattr(Dispatcher, "handler_worker", None)
    if orig_handler is None:
        return

    async def handler_worker(self, lock):
        try:
            return await orig_handler(self, lock)
        except AttributeError as e:
            if "chat_id" in str(e):
                log.warning("kurigram_patch: swallowed dispatcher chat_id error: %s", e)
                return
            raise
        except Exception as e:
            # Do not kill the whole worker loop on one bad update
            if "chat_id" in str(e) or "UpdateGroupCall" in str(e):
                log.warning("kurigram_patch: swallowed update error: %s", e)
                return
            raise

    try:
        Dispatcher.handler_worker = handler_worker  # type: ignore
        Dispatcher._panda_handler_patched = True  # type: ignore
        log.info("kurigram_patch: Dispatcher.handler_worker guarded")
    except Exception as e:
        log.warning("kurigram_patch: dispatcher patch failed: %s", e)


def apply() -> None:
    try:
        from pyrogram import raw
        from pyrogram.types.bots_and_keyboards import inline_keyboard_button as ikb
        from pyrogram.types import InlineKeyboardButton
        from pyrogram import enums, types
    except Exception as e:
        log.warning("kurigram_patch: import failed: %s", e)
        return

    # --- UpdateGroupCall chat_id (pytgcalls / kurigram) ---
    _patch_update_group_call_chat_id()
    _patch_dispatcher_skip_bad_updates()

    # --- Inject missing TL type classes if absent ---
    try:
        from pyrogram.raw.core import TLObject
    except Exception:
        TLObject = object  # type: ignore

    def _ensure_type(name: str, qual: str, fields: tuple):
        if hasattr(raw.types, name):
            return
        attrs = {"QUALNAME": qual}

        def __init__(self, **kwargs):
            for k in fields:
                setattr(self, k, kwargs.get(k))

        attrs["__init__"] = __init__
        cls = type(name, (TLObject,), attrs)
        setattr(raw.types, name, cls)
        log.info("kurigram_patch: injected raw.types.%s", name)

    _ensure_type(
        "KeyboardButtonCallback",
        "types.KeyboardButtonCallback",
        ("text", "data", "requires_password", "style"),
    )
    _ensure_type(
        "KeyboardButtonUrl",
        "types.KeyboardButtonUrl",
        ("text", "url", "style"),
    )
    _ensure_type(
        "KeyboardButton",
        "types.KeyboardButton",
        ("text", "style"),
    )

    # --- Patch InlineKeyboardButton.read (duck-typed, never AttributeError) ---
    _orig_read = ikb.InlineKeyboardButton.read

    @staticmethod
    def _safe_read(b):  # type: ignore
        try:
            return _orig_read(b)
        except AttributeError:
            pass
        except Exception:
            pass

        text = getattr(b, "text", "") or ""
        style = None
        icon = None
        raw_style = getattr(b, "style", None)
        if raw_style is not None:
            try:
                if getattr(raw_style, "bg_primary", False):
                    style = enums.ButtonStyle.PRIMARY
                elif getattr(raw_style, "bg_success", False):
                    style = enums.ButtonStyle.SUCCESS
                elif getattr(raw_style, "bg_danger", False):
                    style = enums.ButtonStyle.DANGER
                if getattr(raw_style, "icon", None):
                    icon = str(raw_style.icon)
            except Exception:
                pass

        kw = {}
        if style is not None:
            kw["style"] = style
        if icon:
            kw["icon_custom_emoji_id"] = icon

        data = getattr(b, "data", None)
        url = getattr(b, "url", None)
        if data is not None:
            if isinstance(data, bytes):
                try:
                    data = data.decode()
                except Exception:
                    data = data.decode("utf-8", errors="ignore")
            try:
                return InlineKeyboardButton(
                    text,
                    callback_data=data,
                    requires_password=getattr(b, "requires_password", None),
                    **kw,
                )
            except TypeError:
                return InlineKeyboardButton(text, callback_data=data)
        if url is not None:
            try:
                return InlineKeyboardButton(text, url=url, **kw)
            except TypeError:
                return InlineKeyboardButton(text, url=url)

        try:
            return InlineKeyboardButton(text, **kw)
        except TypeError:
            return InlineKeyboardButton(text)

    ikb.InlineKeyboardButton.read = _safe_read
    types.InlineKeyboardButton.read = _safe_read  # type: ignore
    log.info("kurigram_patch: InlineKeyboardButton.read patched")

    # --- Patch write: never pass None as callback data (bytes expected) ---
    _orig_write = ikb.InlineKeyboardButton.write

    async def _safe_write(self, client):  # type: ignore
        try:
            # Ensure callback_data is bytes-like before original write
            cd = getattr(self, "callback_data", None)
            if cd is None and getattr(self, "url", None) is None:
                # pure text button — original may still fail on broken kurigram
                pass
            elif isinstance(cd, str):
                try:
                    self.callback_data = cd.encode("utf-8")
                except Exception:
                    pass
            return await _orig_write(self, client)
        except (AttributeError, TypeError) as e:
            log.warning("kurigram_patch write fallback: %s", e)
            style = None
            try:
                if getattr(self, "style", None) or getattr(self, "icon_custom_emoji_id", None):
                    style = raw.types.KeyboardButtonStyle(
                        bg_primary=str(getattr(self.style, "name", self.style)).lower()
                        == "primary"
                        if self.style
                        else False,
                        bg_success=str(getattr(self.style, "name", self.style)).lower()
                        == "success"
                        if self.style
                        else False,
                        bg_danger=str(getattr(self.style, "name", self.style)).lower()
                        == "danger"
                        if self.style
                        else False,
                        icon=int(self.icon_custom_emoji_id)
                        if self.icon_custom_emoji_id
                        else None,
                    )
            except Exception:
                style = None

            if self.callback_data is not None:
                data = self.callback_data
                if isinstance(data, str):
                    data = data.encode("utf-8")
                elif data is None:
                    data = b""
                try:
                    return raw.types.KeyboardButtonCallback(
                        text=self.text or "",
                        data=data,
                        requires_password=self.requires_password or None,
                        style=style,
                    )
                except TypeError:
                    return raw.types.KeyboardButtonCallback(
                        text=self.text or "", data=data
                    )
            if self.url is not None:
                try:
                    return raw.types.KeyboardButtonUrl(
                        text=self.text or "", url=self.url, style=style
                    )
                except TypeError:
                    return raw.types.KeyboardButtonUrl(
                        text=self.text or "", url=self.url
                    )
            # Minimal text button
            try:
                return raw.types.KeyboardButton(text=self.text or "", style=style)
            except TypeError:
                return raw.types.KeyboardButton(text=self.text or "")

    ikb.InlineKeyboardButton.write = _safe_write
    types.InlineKeyboardButton.write = _safe_write  # type: ignore
    log.info("kurigram_patch: InlineKeyboardButton.write patched")


# Auto-apply on import
try:
    apply()
except Exception as _e:
    logging.getLogger(__name__).error("kurigram_patch apply failed: %s", _e)
