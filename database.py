import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")
DB_NAME = "kairo_memory.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabel antrean Nagging Reminder
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            event_id TEXT PRIMARY KEY,
            summary TEXT,
            category TEXT,
            location TEXT,
            start_time TEXT,
            remind_at TEXT,
            is_acknowledged INTEGER DEFAULT 0,
            ping_count INTEGER DEFAULT 0
        )
    ''')
    # Tabel Memori Pribadi Universal (Fakta, Kebiasaan, Lokasi, Kontak)
    c.execute('''
        CREATE TABLE IF NOT EXISTS memory (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Pengetahuan awal universal yang bisa terus bertambah otomatis
    default_memories = {
        "kampus": "STMIK Widya Cipta Dharma (STMIK WICIDA), Samarinda",
        "jurusan": "Teknik Informatika",
        "zona_waktu": "WITA (Asia/Makassar)"
    }
    for k, v in default_memories.items():
        c.execute("INSERT OR IGNORE INTO memory (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

def upsert_reminder(event_id: str, summary: str, category: str, location: str, start_time_iso: str, lead_minutes: int = 30):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    start_dt = datetime.fromisoformat(start_time_iso)
    remind_dt = start_dt - timedelta(minutes=lead_minutes)
    c.execute('''
        INSERT INTO reminders (event_id, summary, category, location, start_time, remind_at, is_acknowledged, ping_count)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0)
        ON CONFLICT(event_id) DO UPDATE SET
            summary=excluded.summary,
            category=excluded.category,
            location=excluded.location,
            start_time=excluded.start_time,
            remind_at=excluded.remind_at,
            is_acknowledged=0,
            ping_count=0
    ''', (event_id, summary, category, location, start_dt.isoformat(), remind_dt.isoformat()))
    conn.commit()
    conn.close()

def delete_reminder(event_id: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM reminders WHERE event_id = ?", (event_id,))
    conn.commit()
    conn.close()

def acknowledge_all_active() -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE reminders SET is_acknowledged = 1 WHERE ping_count > 0 AND is_acknowledged = 0")
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected

def acknowledge_event(event_id: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE reminders SET is_acknowledged = 1 WHERE event_id = ?", (event_id,))
    conn.commit()
    conn.close()

def get_due_reminders():
    now = datetime.now(WITA)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT event_id, summary, category, location, start_time, remind_at, ping_count FROM reminders WHERE is_acknowledged = 0")
    rows = c.fetchall()
    due = []
    for row in rows:
        event_id, summary, category, location, start_time_str, remind_at_str, ping_count = row
        start_dt = datetime.fromisoformat(start_time_str)
        remind_dt = datetime.fromisoformat(remind_at_str)
        # Aktif dari waktu remind_at hingga maksimal 45 menit setelah jadwal dimulai
        if remind_dt <= now <= (start_dt + timedelta(minutes=45)):
            due.append(row)
    conn.close()
    return due

def increment_ping(event_id: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE reminders SET ping_count = ping_count + 1 WHERE event_id = ?", (event_id,))
    conn.commit()
    conn.close()

def get_memory_context() -> str:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT key, value FROM memory")
    rows = c.fetchall()
    conn.close()
    return "\n".join([f"- {k}: {v}" for k, v in rows])

def save_memory(key: str, value: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO memory (key, value) VALUES (?, ?)", (key.lower(), value))
    conn.commit()
    conn.close()