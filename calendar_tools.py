import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import database

SCOPES = ['https://www.googleapis.com/auth/calendar']
WITA = ZoneInfo("Asia/Makassar")

ACCOUNTS = {
    "personal": {"token": "token_personal.json", "env": "TOKEN_PERSONAL_JSON", "email": "hyukayn@gmail.com"},
    "kerja": {"token": "token_kerja.json", "env": "TOKEN_KERJA_JSON", "email": "angelpinkwon9@gmail.com"},
    "kampus": {"token": "token_kampus.json", "env": "TOKEN_KAMPUS_JSON", "email": "2443088@wicida.ac.id"},
}

def get_calendar_service(account_type: str = "personal"):
    account_type = account_type.lower()
    if account_type not in ACCOUNTS:
        account_type = "personal"

    token_file = ACCOUNTS[account_type]["token"]
    env_name = ACCOUNTS[account_type]["env"]
    expected_email = ACCOUNTS[account_type]["email"]
    creds = None

    # 1. Cek jika token disimpan di Environment Variable (untuk server Render)
    if os.getenv(env_name):
        creds = Credentials.from_authorized_user_info(json.loads(os.getenv(env_name)), SCOPES)
    # 2. Jika tidak, cek file lokal (untuk di laptop)
    elif os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print(f"\n🔑 SILAKAN LOGIN DI BROWSER UNTUK AKUN [{account_type.upper()}]: {expected_email}")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        if not os.getenv(env_name):
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def init_all_calendars():
    """Memastikan ketiga akun sudah login saat bot pertama kali dijalankan."""
    for acc_name in ACCOUNTS.keys():
        get_calendar_service(acc_name)

def search_calendar_events(query: str, start_date_iso: str, end_date_iso: str, account_filter: str) -> str:
    """
    Mencari jadwal di Google Calendar. Isi parameter string kosong "" jika tidak diperlukan filter.
    account_filter: 'all', 'personal', 'kerja', atau 'kampus'.
    """
    now = datetime.now(WITA)
    time_min = start_date_iso if start_date_iso else (now - timedelta(days=30)).isoformat()
    time_max = end_date_iso if end_date_iso else (now + timedelta(days=30)).isoformat()
    if not account_filter:
        account_filter = "all"

    target_accounts = ACCOUNTS.keys() if account_filter == "all" or account_filter not in ACCOUNTS else [account_filter]
    output = []

    for acc in target_accounts:
        service = get_calendar_service(acc)
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            q=query if query else None,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        for ev in events:
            start = ev['start'].get('dateTime', ev['start'].get('date'))
            loc = ev.get('location', '-')
            desc = ev.get('description', '-')
            output.append(f"[Akun: {acc.upper()}] ID: {ev['id']} | Judul: {ev.get('summary')} | Waktu: {start} | Lokasi: {loc} | Deskripsi: {desc}")

    if not output:
        return "Tidak ditemukan jadwal yang cocok di ketiga kalender."
    return "\n".join(output)

def create_calendar_event(
    summary: str,
    start_time_iso: str,
    end_time_iso: str,
    description: str,
    account_type: str,
    category: str,
    location: str,
    color_id: str,
    lead_reminder_minutes: int,
    force_create: bool
) -> str:
    """
    Membuat jadwal baru ke akun kalender yang sesuai dan menyetel Nagging Reminder.
    account_type: 'kampus', 'kerja', atau 'personal'.
    color_id: '11' (Merah), '9' (Biru), '2' (Hijau), '6' (Oranye), '3' (Ungu).
    """
    if not account_type:
        account_type = "personal"
    if not color_id:
        color_id = "9"

    if not force_create:
        all_conflicts = []
        for acc in ACCOUNTS.keys():
            srv = get_calendar_service(acc)
            items = srv.events().list(
                calendarId='primary',
                timeMin=start_time_iso,
                timeMax=end_time_iso,
                singleEvents=True
            ).execute().get('items', [])
            for c in items:
                all_conflicts.append(f"[{acc.upper()}] {c.get('summary')} ({c['start'].get('dateTime')})")

        if all_conflicts:
            return f"BENTROK_LINTAS_KALENDER: Jam tersebut bentrok dengan: {', '.join(all_conflicts)}. Tanya user apakah tetap lanjut (force_create=True) atau digeser."

    service = get_calendar_service(account_type)
    event_body = {
        'summary': summary,
        'location': location,
        'description': description,
        'colorId': color_id,
        'start': {'dateTime': start_time_iso, 'timeZone': 'Asia/Makassar'},
        'end': {'dateTime': end_time_iso, 'timeZone': 'Asia/Makassar'},
    }

    created = service.events().insert(calendarId='primary', body=event_body).execute()
    event_id = created['id']

    label_summary = f"[{account_type.upper()}] {summary}"
    database.upsert_reminder(event_id, label_summary, category, location, start_time_iso, lead_reminder_minutes)
    return f"BERHASIL_DIBUAT: '{summary}' tersimpan di kalender [{account_type.upper()} ({ACCOUNTS[account_type]['email']})] pada {start_time_iso}."

def update_calendar_event(
    event_id: str,
    account_type: str,
    summary: str,
    start_time_iso: str,
    end_time_iso: str,
    location: str,
    description: str,
    category: str,
    lead_reminder_minutes: int
) -> str:
    """Mengubah detail jadwal berdasarkan event_id dan account_type ('personal', 'kerja', atau 'kampus'). Isi "" pada parameter teks yang tidak berubah."""
    service = get_calendar_service(account_type)
    event = service.events().get(calendarId='primary', eventId=event_id).execute()

    if summary:
        event['summary'] = summary
    if location:
        event['location'] = location
    if description:
        event['description'] = description
    if start_time_iso:
        event['start'] = {'dateTime': start_time_iso, 'timeZone': 'Asia/Makassar'}
    if end_time_iso:
        event['end'] = {'dateTime': end_time_iso, 'timeZone': 'Asia/Makassar'}

    updated = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
    new_start = updated['start'].get('dateTime')

    label_summary = f"[{account_type.upper()}] {updated.get('summary')}"
    database.upsert_reminder(event_id, label_summary, category, updated.get('location', ''), new_start, lead_reminder_minutes)
    return f"BERHASIL_DIUPDATE: Jadwal '{updated.get('summary')}' di kalender [{account_type.upper()}] telah diperbarui."

def delete_calendar_event(event_id: str, account_type: str) -> str:
    """Menghapus jadwal dari Google Calendar berdasarkan event_id dan account_type ('personal', 'kerja', atau 'kampus')."""
    service = get_calendar_service(account_type)
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    database.delete_reminder(event_id)
    return f"BERHASIL_DIHAPUS: Jadwal ID {event_id} di kalender [{account_type.upper()}] telah dibatalkan dan dihapus."

def save_personal_memory(key: str, value: str) -> str:
    """Menyimpan fakta pribadi, kebiasaan, target, atau informasi dosen/klien baru ke memori jangka panjang KAIRO."""
    database.save_memory(key, value)
    return f"Memori KAIRO diperbarui: {key} -> {value}"