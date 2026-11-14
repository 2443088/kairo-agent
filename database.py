import os
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

def _redis_cmd(*args):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    resp = requests.post(
        UPSTASH_URL,
        headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
        json=list(args),
        timeout=5
    )
    return resp.json().get("result")

def init_db():
    pass  # Upstash Redis tidak memerlukan inisialisasi tabel

def upsert_reminder(event_id: str, summary: str, category: str, location: str, start_time_iso: str, lead_minutes: int):
    start_dt = datetime.fromisoformat(start_time_iso)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=WITA)
    remind_dt = start_dt - timedelta(minutes=lead_minutes)

    data = {
        "event_id": event_id,
        "summary": summary,
        "category": category,
        "location": location or "",
        "start_time": start_dt.isoformat(),
        "remind_at": remind_dt.isoformat(),
        "ping_count": 0,
        "acknowledged": False
    }
    _redis_cmd("HSET", "kairo:reminders", event_id, json.dumps(data))

def get_due_reminders():
    now = datetime.now(WITA)
    raw_all = _redis_cmd("HGETALL", "kairo:reminders") or []
    due = []
    # HGETALL di REST API mengembalikan list selang-seling [key1, val1, key2, val2, ...]
    for i in range(0, len(raw_all), 2):
        item = json.loads(raw_all[i + 1])
        if item.get("acknowledged"):
            continue
        remind_dt = datetime.fromisoformat(item["remind_at"])
        start_dt = datetime.fromisoformat(item["start_time"])
        if remind_dt <= now <= (start_dt + timedelta(hours=1)):
            due.append((
                item["event_id"],
                item["summary"],
                item["category"],
                item["location"],
                item["start_time"],
                item["remind_at"],
                item["ping_count"]
            ))
    return due

def increment_ping(event_id: str):
    raw = _redis_cmd("HGET", "kairo:reminders", event_id)
    if raw:
        item = json.loads(raw)
        item["ping_count"] = item.get("ping_count", 0) + 1
        _redis_cmd("HSET", "kairo:reminders", event_id, json.dumps(item))

def acknowledge_event(event_id: str):
    raw = _redis_cmd("HGET", "kairo:reminders", event_id)
    if raw:
        item = json.loads(raw)
        item["acknowledged"] = True
        _redis_cmd("HSET", "kairo:reminders", event_id, json.dumps(item))

def acknowledge_all_active() -> int:
    now = datetime.now(WITA)
    raw_all = _redis_cmd("HGETALL", "kairo:reminders") or []
    count = 0
    for i in range(0, len(raw_all), 2):
        ev_id = raw_all[i]
        item = json.loads(raw_all[i + 1])
        remind_dt = datetime.fromisoformat(item["remind_at"])
        if not item.get("acknowledged") and item.get("ping_count", 0) > 0 and remind_dt <= now:
            item["acknowledged"] = True
            _redis_cmd("HSET", "kairo:reminders", ev_id, json.dumps(item))
            count += 1
    return count

def delete_reminder(event_id: str):
    _redis_cmd("HDEL", "kairo:reminders", event_id)

def save_memory(key: str, value: str):
    _redis_cmd("HSET", "kairo:memories", key, value)

def get_memory_context() -> str:
    raw_all = _redis_cmd("HGETALL", "kairo:memories") or []
    if not raw_all:
        return "- Belum ada catatan memori khusus."
    lines = []
    for i in range(0, len(raw_all), 2):
        lines.append(f"- {raw_all[i]}: {raw_all[i + 1]}")
    return "\n".join(lines)

def get_chat_history() -> list:
    raw = _redis_cmd("GET", "kairo:chat_history")
    return json.loads(raw) if raw else []

def save_chat_history(history_list: list):
    _redis_cmd("SET", "kairo:chat_history", json.dumps(history_list[-12:]))