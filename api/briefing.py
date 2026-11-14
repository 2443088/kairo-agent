import os
import sys
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram.ext import Application
from google import genai
import calendar_tools

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CRON_SECRET = os.getenv("CRON_SECRET", "kairo_secret_123")
WITA = ZoneInfo("Asia/Makassar")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

@app.route("/api/briefing", methods=["GET"])
def cron_briefing():
    if request.args.get("key") != CRON_SECRET:
        return "Unauthorized", 401

    now = datetime.now(WITA)
    start_day = now.replace(hour=0, minute=0, second=0).isoformat()
    end_day = now.replace(hour=23, minute=59, second=59).isoformat()
    agenda_raw = calendar_tools.search_calendar_events(
        query="",
        start_date_iso=start_day,
        end_date_iso=end_day,
        account_filter="all"
    )
    prompt = (
        f"Hari ini {now.strftime('%A, %d %B %Y')}. Ini daftar jadwal dari Google Calendar user hari ini:\n"
        f"{agenda_raw}\n\n"
        "Buatkan pesan Morning Briefing yang singkat, hangat, dan memotivasi untuk user."
    )
    resp = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)

    async def send_brief():
        ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
        async with ptb_app:
            await ptb_app.bot.send_message(
                chat_id=ALLOWED_USER_ID,
                text=f"☀️ **Morning Briefing dari KAIRO**\n\n{resp.text}",
                parse_mode="Markdown"
            )

    asyncio.run(send_brief())
    return jsonify({"briefing": "sent"}), 200