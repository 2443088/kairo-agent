import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from google import genai
from google.genai import types

import database
import calendar_tools

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CRON_SECRET = os.getenv("CRON_SECRET", "kairo_secret_123")
WITA = ZoneInfo("Asia/Makassar")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

TOOLS = [
    calendar_tools.search_calendar_events,
    calendar_tools.create_calendar_event,
    calendar_tools.update_calendar_event,
    calendar_tools.delete_calendar_event,
    calendar_tools.save_personal_memory,
]

def get_system_prompt() -> str:
    now_str = datetime.now(WITA).strftime("%A, %d %B %Y pukul %H:%M WITA (Offset: +08:00)")
    memories = database.get_memory_context()
    return f"""Kamu adalah KAIRO, AI Personal Life & Habit Agent eksklusif milik user.
Waktu sekarang: {now_str}.

Memori Personal User:
{memories}

ATURAN ROUTING 3 KALENDER (SANGAT PENTING):
User memiliki 3 akun Google Calendar. Setiap kali membuat/mencari/mengubah jadwal, tentukan `account_type` secara otomatis dari konteks chat:
1. `kampus` (2443088@wicida.ac.id) -> Semua kegiatan kuliah, seminar proposal (sempro), skripsi, bimbingan dosen, tugas kampus, atau acara di STMIK WICIDA.
2. `kerja` (angelpinkwon9@gmail.com) -> Semua pekerjaan/proyek seperti membuat aplikasi, coding proyek, desain poster, meeting klien, atau deadline kerja.
3. `personal` (hyukayn@gmail.com) -> Olahraga/workout, baca buku, jadwal tidur, istirahat, nongkrong, atau urusan pribadi lainnya.

ATURAN KERJA LAINNYA:
- DESKRIPSI NARATIF: Ubah catatan singkat user menjadi paragraf deskriptif yang rapi, hidup, dan bermakna, lalu akhiri dengan tagar relevan (contoh: #Kampus #Sempro atau #Kerja #DesainPoster atau #Personal #Workout).
- DURASI & PENGINGAT: Jika jam selesai tidak disebut: Sempro/Kuliah = 1.5 jam; Workout/Baca Buku/Kerja = 1 jam; Tidur = 8 jam. Atur `lead_reminder_minutes`: 60 menit jika perlu perjalanan keluar (kampus/meeting), 15 menit jika di rumah (workout, tidur, baca buku, kerja remote).
- EDIT & HAPUS CASUAL: Wajib panggil `search_calendar_events` lebih dulu untuk menemukan `event_id` dan `account_type`-nya sebelum memanggil `update_calendar_event` atau `delete_calendar_event`.
- Sebutkan secara singkat di balasanmu jadwal tersebut masuk ke kalender mana (Kampus / Kerja / Personal) agar user tenang."""

def is_authorized(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER_ID

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "⚡ **KAIRO Online (24/7 Cloud Mode).**\n\n"
        "Kirim saja teks santai, *voice note*, atau foto jadwal—saya akan catat ke Google Calendar dan **terus menge-ping kamu tiap 5 menit** saat waktunya tiba sampai kamu merespons.",
        parse_mode="Markdown"
    )

async def ack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    count = database.acknowledge_all_active()
    if count > 0:
        await update.message.reply_text("✅ Sip, alarm pengingat dihentikan. Selamat beraktivitas!")
    else:
        await update.message.reply_text("Tidak ada alarm yang sedang aktif saat ini.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ALLOWED_USER_ID:
        return
    await query.answer()
    if query.data.startswith("ack_"):
        event_id = query.data.replace("ack_", "")
        database.acknowledge_event(event_id)
        await query.edit_message_text(
            text=f"{query.message.text}\n\n✅ *Dikonfirmasi! KAIRO berhenti menge-ping jadwal ini.*",
            parse_mode="Markdown"
        )

async def process_with_kairo(update: Update, user_parts: list, display_text: str):
    short_replies = {"oke", "ok", "siap", "gas", "otw", "baik", "noted", "iya", "ya", "done", "sudah"}
    if display_text.lower().strip("!. ") in short_replies:
        stopped = database.acknowledge_all_active()
        if stopped > 0:
            await update.message.reply_text("✅ Mantap, pengingat dihentikan! Gas laksanakan.")
            return

    saved_hist = database.get_chat_history()
    contents = []
    for h in saved_hist:
        contents.append(types.Content(role=h["role"], parts=[types.Part.from_text(text=h["text"])]))
    contents.append(types.Content(role="user", parts=user_parts))

    fallback_models = ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
    last_error = None

    for model_name in fallback_models:
        try:
            response = ai_client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(),
                    tools=TOOLS,
                    temperature=0.3,
                )
            )
            reply_text = response.text or "✅ Beres!"
            saved_hist.append({"role": "user", "text": display_text})
            saved_hist.append({"role": "model", "text": reply_text})
            database.save_chat_history(saved_hist)
            await update.message.reply_text(reply_text)
            return
        except Exception as e:
            last_error = e
            if "503" in str(e) or "429" in str(e) or "UNAVAILABLE" in str(e):
                continue
            break

    logging.error(f"Error KAIRO: {last_error}")
    await update.message.reply_text("⚠️ Waduh, semua server AI sedang padat sebentar. Coba kirim ulang pesanmu ya!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    msg = update.message
    await context.bot.send_chat_action(chat_id=ALLOWED_USER_ID, action="typing")

    if msg.text:
        await process_with_kairo(update, [types.Part.from_text(text=msg.text)], msg.text)
    elif msg.voice or msg.audio:
        file_obj = await (msg.voice or msg.audio).get_file()
        file_bytes = await file_obj.download_as_bytearray()
        mime = "audio/ogg" if msg.voice else "audio/mp3"
        parts = [
            types.Part.from_bytes(data=bytes(file_bytes), mime_type=mime),
            types.Part.from_text(text="Dengarkan pesan suara ini dan eksekusi permintaan jadwal/pengingatnya.")
        ]
        await process_with_kairo(update, parts, "[Voice Note]")
    elif msg.photo:
        photo_file = await msg.photo[-1].get_file()
        img_bytes = await photo_file.download_as_bytearray()
        caption = msg.caption or "Baca informasi jadwal dari gambar ini dan catat ke Google Calendar."
        parts = [
            types.Part.from_bytes(data=bytes(img_bytes), mime_type="image/jpeg"),
            types.Part.from_text(text=caption)
        ]
        await process_with_kairo(update, parts, caption)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "KAIRO 24/7 Active"}), 200

@app.route("/api/webhook", methods=["GET", "POST"])
def telegram_webhook():
    if request.method == "GET":
        return jsonify({"status": "KAIRO Webhook Ready"}), 200

    data = request.get_json(force=True)
    async def run_update():
        ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
        ptb_app.add_handler(CommandHandler("start", start_cmd))
        ptb_app.add_handler(CommandHandler("oke", ack_cmd))
        ptb_app.add_handler(CallbackQueryHandler(handle_callback))
        ptb_app.add_handler(MessageHandler(filters.TEXT | filters.VOICE | filters.AUDIO | filters.PHOTO, handle_message))
        async with ptb_app:
            update = Update.de_json(data, ptb_app.bot)
            await ptb_app.process_update(update)

    asyncio.run(run_update())
    return "OK", 200

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