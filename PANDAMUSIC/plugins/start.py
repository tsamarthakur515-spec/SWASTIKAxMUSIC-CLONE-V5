from .. import bot, cdx, rgx, console
from ..modules.database import add_served_user
from ..modules.formatters import smallcaps
from ..modules.custom_emojis import E, tg_emoji
from ..modules.bot_api import (
    bot_api_send_photo,
    bot_api_send_message,
    bot_api_edit_message,
    bot_api_answer_callback,
    resolve_token,
)
from .maintenance import block_if_maintenance, block_cb_if_maintenance

import asyncio
import html as html_lib
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    from pyrogram.enums import ButtonStyle
    _PRIMARY = ButtonStyle.PRIMARY
    _SUCCESS = ButtonStyle.SUCCESS
    _DANGER = ButtonStyle.DANGER
except Exception:
    _PRIMARY = "primary"
    _SUCCESS = "success"
    _DANGER = "danger"

E_TITLE = "6111778259374971023"
E_START = "6147614817952735246"
E_HELP_INSIDE = "6154314112236001069"
E_CMD_BTN = "5823571441118876120"
E_START_STICKER = "6154300385520522693"


def _client_token(client) -> str | None:
    return resolve_token(client=client)


def _btn(text: str, style=None, **kwargs) -> InlineKeyboardButton:
    if style is not None:
        try:
            return InlineKeyboardButton(text, style=style, **kwargs)
        except TypeError:
            pass
        try:
            return InlineKeyboardButton(text, style=str(getattr(style, "name", style)).lower(), **kwargs)
        except TypeError:
            pass
    try:
        return InlineKeyboardButton(text, **kwargs)
    except TypeError:
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(text, **kwargs)


ADD_GROUP_ADMIN = (
    "delete_messages+manage_video_chats+pin_messages+"
    "invite_users+ban_users+change_info+promote_members"
)


def add_group_url(bot_username: str) -> str:
    return f"https://t.me/{bot_username}?startgroup=s&admin={ADD_GROUP_ADMIN}"


MUSIC_COMMANDS = [
    ("play", "/play"), ("vplay", "/vplay"), ("pause", "/pause"),
    ("resume", "/resume"), ("skip", "/skip"), ("end", "/end"),
]
TOOLS_COMMANDS = [
    ("stats", "/stats"), ("active", "/active"),
    ("welcome", "/welcome"), ("setwelcome", "/setwelcome"),
    ("resetwelcome", "/resetwelcome"), ("broadcast", "/broadcast"),
]
MODERATION_COMMANDS = [
    ("mute", "/mute"), ("unmute", "/unmute"), ("ban", "/ban"),
    ("unban", "/unban"), ("kick", "/kick"), ("tagall", "/tagall"),
    ("noabuse", "/noabuse"),
]
CHATBOT_COMMANDS = [("chaton", "/chaton"), ("chatoff", "/chatoff")]
LOCKS_COMMANDS = [("lock", "/lock"), ("unlock", "/unlock"), ("locks", "/locks")]
FUN_COMMANDS = [
    ("couple", "/couple"), ("riddle", "/riddle"),
    ("dice", "/dice"), ("slots", "/slots"), ("coinflip", "/coinflip"),
]

CMD_USAGE = {
    "play": f"{smallcaps('command')}: /play\n\n{smallcaps('use')}:\n• /play {smallcaps('song name')}\n• /play {smallcaps('youtube link')}\n• {smallcaps('reply to audio with')} /play\n\n{smallcaps('plays audio in voice chat.')}",
    "vplay": f"{smallcaps('command')}: /vplay\n\n{smallcaps('use')}:\n• /vplay {smallcaps('song name')}\n• /vplay {smallcaps('youtube link')}\n• {smallcaps('reply to video with')} /vplay\n\n{smallcaps('plays video in voice chat.')}",
    "pause": f"{smallcaps('command')}: /pause\n\n{smallcaps('use')}: /pause\n\n{smallcaps('pauses the current stream.')}",
    "resume": f"{smallcaps('command')}: /resume\n\n{smallcaps('use')}: /resume\n\n{smallcaps('resumes the paused stream.')}",
    "skip": f"{smallcaps('command')}: /skip\n\n{smallcaps('use')}: /skip\n\n{smallcaps('skips to the next track in queue.')}",
    "end": f"{smallcaps('command')}: /end\n\n{smallcaps('use')}: /end\n\n{smallcaps('stops streaming and clears the queue.')}",
    "stats": f"{smallcaps('command')}: /stats\n\n{smallcaps('use')}: /stats\n\n{smallcaps('shows system and bot statistics.')}",
    "active": f"{smallcaps('command')}: /active\n\n{smallcaps('use')}: /active\n\n{smallcaps('shows active voice chats. (owner only)')}",
    "broadcast": f"{smallcaps('command')}: /broadcast\n\n{smallcaps('use')}: /broadcast {smallcaps('message')}\n\n{smallcaps('broadcasts message to served users/chats. (owner only)')}",
    "couple": f"{smallcaps('command')}: /couple\n\n{smallcaps('use')}: /couple\n\n{smallcaps('picks 2 random members and makes couple of the day image.')}\n{smallcaps('shows their profile photos with chemistry %.')}\n\n{smallcaps('anyone in the group can use this.')}\n{smallcaps('bot must be admin to list members.')}",
    "mute": f"{smallcaps('command')}: /mute\n\n{smallcaps('use')}:\n• {smallcaps('reply to user')}: /mute {smallcaps('reason')}\n• /mute @user {smallcaps('reason')}\n\n{smallcaps('mutes a user in the group. (admin only)')}",
    "unmute": f"{smallcaps('command')}: /unmute\n\n{smallcaps('use')}:\n• {smallcaps('reply to user')}: /unmute\n• /unmute @user\n\n{smallcaps('unmutes a user in the group. (admin only)')}",
    "ban": f"{smallcaps('command')}: /ban\n\n{smallcaps('use')}:\n• {smallcaps('reply to user')}: /ban {smallcaps('reason')}\n• /ban @user {smallcaps('reason')}\n\n{smallcaps('bans a user from the group. (admin only)')}",
    "unban": f"{smallcaps('command')}: /unban\n\n{smallcaps('use')}:\n• {smallcaps('reply to user')}: /unban\n• /unban @user\n\n{smallcaps('unbans a user in the group. (admin only)')}",
    "kick": f"{smallcaps('command')}: /kick\n\n{smallcaps('use')}:\n• {smallcaps('reply to user')}: /kick {smallcaps('reason')}\n• /kick @user {smallcaps('reason')}\n\n{smallcaps('kicks a user from the group. (admin only)')}",
    "tagall": f"{smallcaps('command')}: /tagall\n\n{smallcaps('use')}:\n• /tagall {smallcaps('your message')}\n• {smallcaps('reply to a message with')} /tagall\n\n{smallcaps('tags all group members with your message.')}\n{smallcaps('example')}: /tagall hi everyone\n\n{smallcaps('admin / owner / sudo only.')}\n{smallcaps('bot must be admin to list members.')}",
    "chaton": f"{smallcaps('command')}: /chaton\n\n{smallcaps('use')}: /chaton\n\n{smallcaps('enables chatbot in this chat.')}\n{smallcaps('group: admin only. private: anyone.')}\n{smallcaps('then mention bot or say its name to chat.')}",
    "chatoff": f"{smallcaps('command')}: /chatoff\n\n{smallcaps('use')}: /chatoff\n\n{smallcaps('disables chatbot in this chat.')}\n{smallcaps('group: admin only.')}",
    "noabuse": f"{smallcaps('command')}: /noabuse\n\n{smallcaps('use')}:\n• /noabuse on\n• /noabuse off\n\n{smallcaps('auto deletes abusive messages in group.')}\n{smallcaps('admin only. bot needs delete messages right.')}",
    "welcome": f"{smallcaps('command')}: /welcome\n\n{smallcaps('use')}:\n• /welcome on\n• /welcome off\n\n{smallcaps('enable or disable welcome messages.')}\n{smallcaps('admin only.')}",
    "setwelcome": f"{smallcaps('command')}: /setwelcome\n\n{smallcaps('use')}:\n• /setwelcome {smallcaps('text')}\n• {smallcaps('reply to photo/video with')} /setwelcome\n• {smallcaps('reply to text with')} /setwelcome\n\n{smallcaps('placeholders')}:\n{{name}} {{fullname}} {{id}} {{mention}} {{username}} {{chat}}\n\n{smallcaps('button format')}:\n[Button Text](buttonurl:https://t.me/example)\n\n{smallcaps('sets custom welcome message with optional photo/video and buttons.')}\n{smallcaps('admin only.')}",
    "resetwelcome": f"{smallcaps('command')}: /resetwelcome\n\n{smallcaps('use')}: /resetwelcome\n\n{smallcaps('resets welcome message to default.')}\n{smallcaps('admin only.')}",
    "lock": f"{smallcaps('command')}: /lock\n\n{smallcaps('use')}:\n• /lock url\n• /lock photo\n• /lock video\n• /lock all\n\n{smallcaps('locks a content type in the group.')}\n{smallcaps('locked messages from non-admins are auto-deleted.')}\n{smallcaps('admin / owner / sudo only.')}\n\n{smallcaps('types')}: all url photo video document sticker gif voice videonote audio contact location poll game forward bot command text invitelink phone email emoji media",
    "unlock": f"{smallcaps('command')}: /unlock\n\n{smallcaps('use')}:\n• /unlock url\n• /unlock photo\n• /unlock all\n\n{smallcaps('unlocks a content type.')}\n{smallcaps('admin / owner / sudo only.')}",
    "locks": f"{smallcaps('command')}: /locks\n\n{smallcaps('use')}: /locks\n\n{smallcaps('shows all active locks in this group.')}\n{smallcaps('admin / owner / sudo only.')}",
    "riddle": f"{smallcaps('command')}: /riddle\n\n{smallcaps('use')}: /riddle\n\n{smallcaps('sends a random riddle quiz.')}",
    "dice": f"{smallcaps('command')}: /dice\n\n{smallcaps('use')}: /dice\n\n{smallcaps('rolls a dice.')}",
    "slots": f"{smallcaps('command')}: /slots\n\n{smallcaps('use')}: /slots\n\n{smallcaps('virtual slot machine. costs coins.')}",
    "coinflip": f"{smallcaps('command')}: /coinflip\n\n{smallcaps('use')}: /coinflip\n\n{smallcaps('heads or tails.')}",
}


def _cmd_rows(commands, per_row=2):
    rows, row, styles = [], [], [_PRIMARY, _SUCCESS, _DANGER]
    for i, (key, _label) in enumerate(commands):
        kw = {"callback_data": f"cmdhelp|{key}", "icon_custom_emoji_id": E_CMD_BTN}
        row.append(_btn(smallcaps(key), styles[i % 3], **kw))
        if len(row) == per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def _back_row():
    return [
        _btn(smallcaps("COMMANDS"), _SUCCESS, callback_data="help_menu", icon_custom_emoji_id=E_CMD_BTN),
        _btn(smallcaps("« BACK"), _DANGER, callback_data="home_menu", icon_custom_emoji_id=E_CMD_BTN),
    ]


def start_markup(bot_username: str) -> InlineKeyboardMarkup:
    owner = getattr(console, "OWNER_USERNAME", "") or ""
    support = getattr(console, "SUPPORT_CHAT", "") or ""
    channel = getattr(console, "SUPPORT_CHANNEL", "") or ""
    if owner:
        owner_btn = _btn(smallcaps("owner"), _PRIMARY, url=f"https://t.me/{owner}", icon_custom_emoji_id=E_START)
    elif getattr(console, "OWNER_ID", 0):
        owner_btn = _btn(smallcaps("owner"), _PRIMARY, url=f"tg://user?id={console.OWNER_ID}", icon_custom_emoji_id=E_START)
    else:
        owner_btn = _btn(smallcaps("owner"), _PRIMARY, callback_data="about_menu", icon_custom_emoji_id=E_START)
    if support:
        support_btn = _btn(smallcaps("support"), _SUCCESS, url=f"https://t.me/{support}", icon_custom_emoji_id=E_START)
    else:
        support_btn = _btn(smallcaps("support"), _SUCCESS, callback_data="support_alert", icon_custom_emoji_id=E_START)
    if channel:
        update_btn = _btn(smallcaps("update"), _PRIMARY, url=f"https://t.me/{channel}", icon_custom_emoji_id=E_START)
    else:
        update_btn = _btn(smallcaps("update"), _PRIMARY, callback_data="update_alert", icon_custom_emoji_id=E_START)

    add_url = add_group_url(bot_username)

    return InlineKeyboardMarkup([
        [_btn(smallcaps("➕ add me in your group ➕"), _PRIMARY, url=add_url, icon_custom_emoji_id=E_START)],
        [_btn("🎵 #MUSIC BOT", _SUCCESS, url=add_url, icon_custom_emoji_id=E_START)],
        [owner_btn, _btn(smallcaps("about"), _SUCCESS, callback_data="about_menu", icon_custom_emoji_id=E_START)],
        [support_btn, update_btn],
        [_btn(smallcaps("help and commands"), _PRIMARY, callback_data="help_menu", icon_custom_emoji_id=E_START)],
        [_btn(smallcaps("source"), _DANGER, callback_data="repo_alert", icon_custom_emoji_id=E_START)],
    ])


def help_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn(smallcaps("MUSIC"), _PRIMARY, callback_data="music_menu", icon_custom_emoji_id=E_HELP_INSIDE),
            _btn(smallcaps("TOOLS"), _SUCCESS, callback_data="tools_menu", icon_custom_emoji_id=E_HELP_INSIDE),
        ],
        [
            _btn(smallcaps("MODERATION"), _DANGER, callback_data="moderation_menu", icon_custom_emoji_id=E_HELP_INSIDE),
            _btn(smallcaps("CHATBOT"), _SUCCESS, callback_data="chatbot_menu", icon_custom_emoji_id=E_HELP_INSIDE),
        ],
        [
            _btn(smallcaps("LOCKS"), _PRIMARY, callback_data="locks_menu", icon_custom_emoji_id=E_HELP_INSIDE),
            _btn(smallcaps("GAMES"), _SUCCESS, callback_data="games_menu", icon_custom_emoji_id=E_HELP_INSIDE),
        ],
        [
            _btn(smallcaps("FUN"), _PRIMARY, callback_data="fun_menu", icon_custom_emoji_id=E_HELP_INSIDE),
            _btn(smallcaps("CLONE"), _SUCCESS, callback_data="clone_menu", icon_custom_emoji_id=E_HELP_INSIDE),
        ],
        [
            _btn(smallcaps("« BACK"), _DANGER, callback_data="home_menu", icon_custom_emoji_id=E_HELP_INSIDE),
        ],
    ])


def music_menu_markup() -> InlineKeyboardMarkup:
    rows = _cmd_rows(MUSIC_COMMANDS, per_row=2)
    rows.append(_back_row())
    return InlineKeyboardMarkup(rows)


def tools_menu_markup() -> InlineKeyboardMarkup:
    rows = _cmd_rows(TOOLS_COMMANDS, per_row=2)
    rows.append(_back_row())
    return InlineKeyboardMarkup(rows)


def moderation_menu_markup() -> InlineKeyboardMarkup:
    rows = _cmd_rows(MODERATION_COMMANDS, per_row=2)
    rows.append(_back_row())
    return InlineKeyboardMarkup(rows)


def chatbot_menu_markup() -> InlineKeyboardMarkup:
    rows = _cmd_rows(CHATBOT_COMMANDS, per_row=2)
    rows.append(_back_row())
    return InlineKeyboardMarkup(rows)


def locks_menu_markup() -> InlineKeyboardMarkup:
    rows = _cmd_rows(LOCKS_COMMANDS, per_row=2)
    rows.append(_back_row())
    return InlineKeyboardMarkup(rows)


def fun_menu_markup() -> InlineKeyboardMarkup:
    rows = _cmd_rows(FUN_COMMANDS, per_row=2)
    rows.append(_back_row())
    return InlineKeyboardMarkup(rows)


def cmd_help_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([_back_row()])


def about_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        _btn(smallcaps("« BACK"), _DANGER, callback_data="home_menu", icon_custom_emoji_id=E_CMD_BTN),
    ]])


def _safe_mention(user) -> str:
    if not user:
        return "User"
    name = html_lib.escape(user.first_name or "User")
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def start_caption(mention: str) -> str:
    return (
        f'{tg_emoji(E_TITLE, "✨")} <b>𝗦𝘄𝗮𝘀𝘁𝗶𝗸𝗮 𝗠𝘂𝘀𝗶𝗰 𝘃𝟱</b>\n\n'
        f'{tg_emoji(E_TITLE, "✨")} {smallcaps("hey")} {mention}\n\n'
        f'{tg_emoji(E_TITLE, "✨")} {smallcaps("i am a high quality fast music bot.")}\n'
        f'{tg_emoji(E_TITLE, "✨")} {smallcaps("add me to your group and enjoy audio / video streaming.")}\n\n'
        f'{tg_emoji(E_TITLE, "✨")} {smallcaps("use the buttons below for help, owner and support.")}'
    )


def help_list_caption() -> str:
    body = (
        f"{smallcaps('help menu')}\n\n"
        f"{smallcaps('tap a category below to see commands.')}\n\n"
        f"• music — play vplay pause resume skip end\n"
        f"• tools — stats active welcome broadcast\n"
        f"• moderation — mute ban kick tagall noabuse\n"
        f"• chatbot — chaton chatoff\n"
        f"• locks — lock unlock content types\n"
        f"• games — economy rpg social\n"
        f"• fun — couple riddle dice slots coinflip\n"
        f"• clone — create your own music bot"
    )
    return f"<blockquote expandable>{tg_emoji(E.GEAR, '⚙️')} {body}</blockquote>"


def music_list_caption() -> str:
    return f"<blockquote expandable>{tg_emoji(E.LIGHTNING, '⚡')} {smallcaps('music commands')}\n\n{smallcaps('audio and video streaming controls.')}\n{smallcaps('tap a button to see usage.')}</blockquote>"


def tools_list_caption() -> str:
    return f"<blockquote expandable>{tg_emoji(E.GEAR, '⚙️')} {smallcaps('tools')}\n\n{smallcaps('stats, active chats, welcome and broadcast.')}\n{smallcaps('tap a button to see usage.')}</blockquote>"


def moderation_list_caption() -> str:
    return f"<blockquote expandable>{tg_emoji(E.FIRE, '🔥')} {smallcaps('moderation')}\n\n{smallcaps('mute ban kick tagall and abuse filter.')}\n{smallcaps('admin only for most commands.')}\n{smallcaps('tap a button to see usage.')}</blockquote>"


def chatbot_list_caption() -> str:
    return f"<blockquote expandable>{tg_emoji(E.LIGHTNING, '⚡')} {smallcaps('chatbot commands')}\n\n{smallcaps('enable or disable ai chat in this chat.')}\n{smallcaps('tap a button to see usage.')}</blockquote>"


def locks_list_caption() -> str:
    body = (
        f"{smallcaps('locks')}\n\n"
        f"{smallcaps('lock content types in your group.')}\n"
        f"{smallcaps('example')}: /lock url\n"
        f"{smallcaps('when locked, non-admin messages are auto-deleted.')}\n\n"
        f"{smallcaps('types')}: all url photo video document sticker gif voice "
        f"videonote audio contact location poll game forward bot command text "
        f"invitelink phone email emoji media\n\n"
        f"{smallcaps('admin owner sudo only. bot needs delete messages right.')}"
    )
    return f"<blockquote expandable>{tg_emoji(E.GEAR, '⚙️')} {body}</blockquote>"


def fun_list_caption() -> str:
    return f"<blockquote expandable>{tg_emoji(E.BUTTERFLY, '🦋')} {smallcaps('fun')}\n\n{smallcaps('couple of the day, riddles, dice, slots and coinflip.')}\n{smallcaps('tap a button to see usage.')}</blockquote>"


def cmd_usage_caption(key: str) -> str:
    return f"<blockquote expandable>{tg_emoji(E.STAR, '🌟')} {CMD_USAGE.get(key, smallcaps('unknown command'))}</blockquote>"


def about_caption() -> str:
    body = f"{smallcaps('about')}\n\n{smallcaps('high quality telegram music bot.')}\n{smallcaps('supports audio and video streaming.')}\n{smallcaps('powered by pytgcalls + kurigram.')}\n\n{smallcaps('add me in your group and start playing.')}"
    return f"<blockquote expandable>{tg_emoji(E.CHECK, '✅')} {body}</blockquote>"


async def _edit_menu(query, caption: str, markup: InlineKeyboardMarkup, client=None):
    msg = query.message
    chat_id = msg.chat.id
    message_id = msg.id
    is_photo = bool(getattr(msg, "photo", None))
    token = _client_token(client) if client else None

    ok = await bot_api_edit_message(
        chat_id=chat_id,
        message_id=message_id,
        text=caption,
        caption=caption,
        reply_markup=markup,
        is_photo=is_photo,
        bot_token=token,
    )
    if ok:
        print("[start] menu edit via Bot API OK", flush=True)
        return

    try:
        if is_photo:
            await msg.edit_caption(
                caption=caption, reply_markup=markup, parse_mode=ParseMode.HTML
            )
        else:
            await msg.edit_text(
                caption, reply_markup=markup, parse_mode=ParseMode.HTML
            )
        return
    except Exception as e:
        print(f"[start] pyrogram edit failed: {e}", flush=True)

    try:
        await msg.edit_caption(caption=caption, parse_mode=ParseMode.HTML)
    except Exception:
        try:
            await msg.edit_text(caption, parse_mode=ParseMode.HTML)
        except Exception as e2:
            print(f"[start] edit no-kb failed: {e2}", flush=True)


async def _safe_reply(message, photo, caption, buttons, client=None):
    chat_id = message.chat.id
    token = _client_token(client) if client else None

    if photo:
        try:
            return await message.reply_photo(
                photo=photo, caption=caption, reply_markup=buttons, parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"[start] pyrogram photo+kb: {e}", flush=True)

    try:
        return await message.reply_text(
            caption, reply_markup=buttons, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        print(f"[start] pyrogram text+kb: {e}", flush=True)

    print(f"[start] Bot API fallback token={'clone' if token and token != console.BOT_TOKEN else 'main'}", flush=True)
    if photo:
        ok = await bot_api_send_photo(
            chat_id, photo=photo, caption=caption, reply_markup=buttons, bot_token=token
        )
        if ok:
            print("[start] Bot API photo+buttons OK", flush=True)
            return True
    ok = await bot_api_send_message(
        chat_id, text=caption, reply_markup=buttons, bot_token=token
    )
    if ok:
        print("[start] Bot API text+buttons OK", flush=True)
        return True

    if photo:
        try:
            return await message.reply_photo(
                photo=photo, caption=caption, parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
    return await message.reply_text(caption, parse_mode=ParseMode.HTML)


@bot.on_message(cdx(["start", "help"]))
async def start_message_private(client, message):
    if await block_if_maintenance(message):
        return
    try:
        await add_served_user(message.from_user.id)
    except Exception:
        pass

    is_start = message.command and message.command[0].lower() == "start"

    if is_start:
        try:
            sticker_msg = await message.reply(
                text=f'<tg-emoji emoji-id="{E_START_STICKER}">⭐</tg-emoji>',
                parse_mode=ParseMode.HTML,
            )
            await asyncio.sleep(1.3)
            await sticker_msg.delete()
        except Exception:
            pass

    mention = _safe_mention(message.from_user)
    photo = console.START_IMAGE_URL
    caption = start_caption(mention)
    try:
        me = client.me or await client.get_me()
        bot_username = me.username or ""
    except Exception:
        bot_username = getattr(client, "username", "") or ""
    buttons = start_markup(bot_username)
    if message.command and message.command[0].lower() == "help":
        caption = help_list_caption()
        buttons = help_menu_markup()

    try:
        await _safe_reply(message, photo, caption, buttons, client=client)
    except Exception as e:
        print(f"[start] all reply paths failed: {e}", flush=True)

    if is_start:
        try:
            full_name = message.from_user.first_name + " " + (message.from_user.last_name or "")
            username = f"@{message.from_user.username}" if message.from_user.username else "N/A"
            user_id = message.from_user.id
            log_message = f"🚀 **{message.from_user.mention} Just Started the Bot!**\n\n🧑 **Full Name:** {full_name}\n🔗 **Username:** {username}\n🆔 **Telegram ID:** `{user_id}`"
            if console.LOG_GROUP_ID:
                await client.send_message(console.LOG_GROUP_ID, text=log_message, disable_web_page_preview=True)
        except Exception:
            pass


async def _answer(query, text="", show_alert=False, client=None):
    try:
        await query.answer(text, show_alert=show_alert)
    except Exception:
        try:
            await bot_api_answer_callback(
                query.id, text=text, show_alert=show_alert, bot_token=_client_token(client)
            )
        except Exception:
            pass


@bot.on_callback_query(rgx("repo_alert"))
async def repo_alert_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _answer(query, smallcaps("repo private hai") + " 🔒", show_alert=True, client=client)


@bot.on_callback_query(rgx("support_alert"))
async def support_alert_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _answer(query, smallcaps("support chat set nahi hai config me"), show_alert=True, client=client)


@bot.on_callback_query(rgx("update_alert"))
async def update_alert_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _answer(query, smallcaps("update chat set nahi hai config me"), show_alert=True, client=client)


@bot.on_callback_query(rgx("about_menu"))
async def about_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit_menu(query, about_caption(), about_markup(), client=client)
    await _answer(query, client=client)


@bot.on_callback_query(rgx("help_menu"))
async def help_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit_menu(query, help_list_caption(), help_menu_markup(), client=client)
    await _answer(query, client=client)


@bot.on_callback_query(rgx("music_menu"))
async def music_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit_menu(query, music_list_caption(), music_menu_markup(), client=client)
    await _answer(query, client=client)


@bot.on_callback_query(rgx("tools_menu"))
async def tools_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit_menu(query, tools_list_caption(), tools_menu_markup(), client=client)
    await _answer(query, client=client)


@bot.on_callback_query(rgx("moderation_menu"))
async def moderation_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit_menu(query, moderation_list_caption(), moderation_menu_markup(), client=client)
    await _answer(query, client=client)


@bot.on_callback_query(rgx("chatbot_menu"))
async def chatbot_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit_menu(query, chatbot_list_caption(), chatbot_menu_markup(), client=client)
    await _answer(query, client=client)


@bot.on_callback_query(rgx("locks_menu"))
async def locks_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit_menu(query, locks_list_caption(), locks_menu_markup(), client=client)
    await _answer(query, client=client)


@bot.on_callback_query(rgx("fun_menu"))
async def fun_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    await _edit_menu(query, fun_list_caption(), fun_menu_markup(), client=client)
    await _answer(query, client=client)


@bot.on_callback_query(rgx(r"^cmdhelp\|"))
async def cmd_help_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    try:
        key = query.data.split("|", 1)[1].strip().lower()
    except Exception:
        return await _answer(query, "Invalid.", show_alert=True, client=client)
    if key not in CMD_USAGE:
        return await _answer(query, "Unknown command.", show_alert=True, client=client)
    await _edit_menu(query, cmd_usage_caption(key), cmd_help_markup(), client=client)
    await _answer(query, client=client)


@bot.on_callback_query(rgx("home_menu"))
async def home_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    mention = _safe_mention(query.from_user)
    try:
        me = client.me or await client.get_me()
        uname = me.username or ""
    except Exception:
        uname = getattr(client, "username", "") or ""
    await _edit_menu(query, start_caption(mention), start_markup(uname), client=client)
    await _answer(query, client=client)
