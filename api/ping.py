import os
import sys
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
import database

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
CRON_SECRET = os.getenv("CRON_SECRET", "kairo_secret_123")
WITA = ZoneInfo("Asia/Makassar")

@app.route("/api/ping", methods=["GET"])
def cron_ping():
    if request.args.get("key") != CRON_SECRET:
        return "Unauthorized", 401

    due_list = database.get_due_reminders()
    if not due_list:
        return jsonify({"pinged": 0}), 200

    async def send_pings():
        ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
        async with ptb_app:
            for event_id, summary, category, location, start_time_str, remind_at_str, ping_count in due_list:
                start_dt = datetime.fromisoformat(start_time_str)
                jam_str = start_dt.strftime("%H:%M WITA")
                loc_text = f"\n📍 Lokasi: {location}" if location else ""

                if ping_count == 0:
                    header = f"⏰ **PENGINGAT KAIRO ({category})**"
                    nudge = "Waktunya bersiap-siap nih!"
                elif ping_count == 1:
                    header = f"🔔 **PING KE-2 — BELUM DIRESPONS!**"
                    nudge = "Hei, jangan sampai ke-skip ya, jadwal ini sudah dekat."
                else:
                    header = f"🚨 **PANGGILAN KE-{ping_count + 1}!**"
                    nudge = "Saya bakal terus nge-ping tiap 5 menit sampai kamu klik tombol di bawah atau balas 'oke'!"

                text = (
                    f"{header}\n\n"
                    f"📌 **{summary}**\n"
                    f"🕒 Pukul: **{jam_str}**{loc_text}\n\n"
                    f"_{nudge}_"
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Oke, Saya Sadar & Siap!", callback_data=f"ack_{event_id}")]
                ])
                await ptb_app.bot.send_message(
                    chat_id=ALLOWED_USER_ID,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                database.increment_ping(event_id)

    asyncio.run(send_pings())
    return jsonify({"pinged": len(due_list)}), 200