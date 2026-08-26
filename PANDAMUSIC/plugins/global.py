from .. import bot, console
from ..modules.database import add_served_chat, add_served_user

from pyrogram import enums, filters
from pyrogram.types import ChatMemberUpdated


@bot.on_chat_member_updated()
async def bot_added_to_group(client, event: ChatMemberUpdated):
    """Track group when bot is added / present; refresh admin cache."""
    try:
        chat_id = event.chat.id
        if chat_id >= 0:
            return

        # Always keep group in served list if bot is still a member
        me = client.me or await client.get_me()
        new = event.new_chat_member
        old = event.old_chat_member

        # Bot joined or still in chat
        bot_joined = (
            new
            and new.user
            and new.user.id == me.id
            and new.status
            in (
                enums.ChatMemberStatus.MEMBER,
                enums.ChatMemberStatus.ADMINISTRATOR,
                enums.ChatMemberStatus.OWNER,
            )
        )
        bot_left = (
            new
            and new.user
            and new.user.id == me.id
            and new.status
            in (
                enums.ChatMemberStatus.LEFT,
                enums.ChatMemberStatus.BANNED,
            )
        )

        if bot_left:
            return

        if bot_joined or (new is None and old is None):
            await add_served_chat(chat_id)
        else:
            # Any membership change in a group bot is in — still track chat
            await add_served_chat(chat_id)

        if event.from_user and not event.from_user.is_bot:
            await add_served_user(event.from_user.id)

        if chat_id not in console.chat_admins:
            console.chat_admins[chat_id] = {}

        try:
            owners = filters.user()
            admins = filters.user()
            async for m in client.get_chat_members(
                chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS
            ):
                if m.status == enums.ChatMemberStatus.OWNER:
                    if m.user.id not in owners:
                        owners.add(m.user.id)
                if m.user.id not in admins:
                    admins.add(m.user.id)

            console.chat_admins[chat_id]["owners"] = owners
            console.chat_admins[chat_id]["admins"] = admins
        except Exception:
            pass
    except Exception:
        pass
