"""
Universal served user/chat tracker.

Ensures broadcast targets fill up whenever:
- anyone messages in a group the bot is in
- anyone uses /start in private
- bot sees any incoming activity
"""

from pyrogram import filters
from pyrogram.types import Message

from .. import bot, cdx
from ..modules.database import add_served_chat, add_served_user


@bot.on_message(filters.group & filters.incoming, group=5)
async def track_group_activity(client, message: Message):
    try:
        if message.chat and message.chat.id < 0:
            await add_served_chat(message.chat.id)
        if message.from_user and not message.from_user.is_bot:
            await add_served_user(message.from_user.id)
    except Exception:
        pass


@bot.on_message(filters.private & filters.incoming, group=5)
async def track_private_activity(client, message: Message):
    try:
        if message.from_user and not message.from_user.is_bot:
            await add_served_user(message.from_user.id)
    except Exception:
        pass


@bot.on_message(cdx(["play", "vplay", "start", "stats"]) & filters.incoming, group=6)
async def track_commands(client, message: Message):
    """Extra guarantee on important commands."""
    try:
        if message.from_user and not message.from_user.is_bot:
            await add_served_user(message.from_user.id)
        if message.chat and message.chat.id < 0:
            await add_served_chat(message.chat.id)
    except Exception:
        pass
