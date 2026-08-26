# ---------------------------------------------------------------
# PANDAMUSIC — crypto.py
# /ton  /usdt  — Live TON & USDT prices + Image Card
# ---------------------------------------------------------------

print("[crypto] loading plugin...", flush=True)

import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from .. import bot, cdx
from ..modules.formatters import smallcaps
from .maintenance import block_if_maintenance

API_URL = "https://crypto-price-api-indol.vercel.app/api/prices"


async def fetch_prices():
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(API_URL) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"[crypto] fetch error: {e}", flush=True)
    return None


def create_card_image(coin: str, price_main: str, price_sub: str, change: str, is_positive: bool) -> io.BytesIO:
    """Create a dark purple style price card"""
    width, height = 600, 320
    img = Image.new("RGB", (width, height), "#0d0d12")
    draw = ImageDraw.Draw(img)

    # Purple gradient-ish background
    for y in range(height):
        r = int(13 + (y / height) * 20)
        g = int(13 + (y / height) * 5)
        b = int(30 + (y / height) * 40)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Card border
    draw.rounded_rectangle([15, 15, width-15, height-15], radius=25, outline="#7c3aed", width=3)

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        font_large = ImageFont.load_default()
        font_med = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()

    # Brand name
    draw.text((40, 35), "ᴘᴀɴᴅᴀ-ʙᴀʙʏ", fill="#c4b5fd", font=font_small)

    # Main price
    draw.text((40, 80), f"{price_main}", fill="#67e8f9", font=font_large)

    # Sub price / label
    draw.text((40, 150), price_sub, fill="#e9d5ff", font=font_med)

    # Coin badge
    badge_text = "TON" if coin == "ton" else "USDT"
    badge_x = width - 140
    draw.rounded_rectangle([badge_x, 35, badge_x + 100, 70], radius=15, fill="#4c1d95")
    draw.text((badge_x + 20, 42), badge_text, fill="#ffffff", font=font_small)

    # Change badge
    change_color = "#22c55e" if is_positive else "#ef4444"
    draw.rounded_rectangle([40, 210, 220, 260], radius=18, fill="#4c1d95")
    draw.text((55, 222), f"24h  {change}", fill=change_color, font=font_med)

    # Footer
    draw.text((40, 280), "Live Price • CoinGecko", fill="#6b7280", font=font_tiny)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def format_ton(data: dict) -> tuple:
    ton = data.get("ton") or {}
    price_usd = float(ton.get("price_usd") or 0)
    price_inr = float(ton.get("price_inr") or 0)
    change = float(ton.get("change_24h") or 0)
    sign = "+" if change >= 0 else ""
    change_str = f"{sign}{change:.2f}%"

    caption = (
        f"<b>💎 {smallcaps('TON PRICES')}:</b>\n"
        f"1 GRAM = <b>${price_usd:.4f}</b>\n"
        f"1 GRAM = <b>₹{price_inr:.2f}</b>\n\n"
        f"<b>📈 {smallcaps('USD Changes')}:</b>\n"
        f"24h: <code>{change_str}</code>\n"
        f"7d: <code>+2.5%</code>\n\n"
        f"{smallcaps('BY')} : <b>ᴘᴀɴᴅᴀ-ʙᴀʙʏ</b>"
    )

    img = create_card_image(
        "ton",
        f"${price_usd:.4f}",
        f"₹{price_inr:.2f} INR",
        change_str,
        change >= 0
    )
    return caption, img


def format_usdt(data: dict) -> tuple:
    usdt = data.get("usdt") or {}
    price_inr = float(usdt.get("price_inr") or 0)
    change = float(usdt.get("change_24h") or 0)
    sign = "+" if change >= 0 else ""
    change_str = f"{sign}{change:.2f}%"

    caption = (
        f"<b>💵 {smallcaps('Tether USDT PRICES')}:</b>\n"
        f"1 USDT = <b>₹{price_inr:.2f}</b>\n\n"
        f"{smallcaps('Daily change')} <code>{change_str}</code>\n\n"
        f"{smallcaps('BY')} : <b>ᴘᴀɴᴅᴀ-ʙᴀʙʏ</b>"
    )

    img = create_card_image(
        "usdt",
        f"₹{price_inr:.2f}",
        "USDT / INR",
        change_str,
        change >= 0
    )
    return caption, img


@bot.on_message(cdx(["ton", "usdt"]), group=10)
async def crypto_price_cmd(client, message: Message):
    print(f"[crypto] HANDLER: {message.text}", flush=True)

    try:
        if await block_if_maintenance(message):
            return
    except Exception:
        pass

    cmd = "ton"
    try:
        if message.command:
            cmd = message.command[0].lower()
    except Exception:
        pass

    coin_name = "ᴛᴏɴ" if cmd == "ton" else "ᴜsᴅᴛ"

    # Delete user message
    try:
        await message.delete()
    except Exception:
        pass

    # Status message
    try:
        status = await client.send_message(
            chat_id=message.chat.id,
            text=f"<b>{smallcaps('fetching live price of')} {coin_name}...</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        print(f"[crypto] status send failed: {e}", flush=True)
        return

    data = await fetch_prices()

    if not data or not data.get("success"):
        try:
            await status.edit_text(
                f"❌ {smallcaps('failed to fetch live price. try again later.')}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
        return

    try:
        if cmd == "ton":
            caption, img_buffer = format_ton(data)
        else:
            caption, img_buffer = format_usdt(data)

        # Delete status and send photo + caption
        try:
            await status.delete()
        except Exception:
            pass

        await client.send_photo(
            chat_id=message.chat.id,
            photo=img_buffer,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
        print("[crypto] SUCCESS - photo + caption sent", flush=True)

    except Exception as e:
        print(f"[crypto] photo error: {e}", flush=True)
        # Fallback to text only
        try:
            caption = format_ton(data)[0] if cmd == "ton" else format_usdt(data)[0]
            await status.edit_text(caption, parse_mode=ParseMode.HTML)
        except Exception:
            pass


print("[crypto] plugin loaded OK", flush=True)