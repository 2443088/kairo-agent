# ⚡ KAIRO — Autonomous Personal Life & Habit AI Agent

**KAIRO** is a 24/7 serverless personal AI assistant integrated with Telegram and Google Calendar. Designed to eliminate scheduling friction, KAIRO accepts natural text, voice notes, and schedule images—automatically classifying activities across multiple Google accounts, generating rich calendar entries, and enforcing habit accountability through persistent nagging reminders.

---

## ✨ Key Features

- **Multimodal Natural Input:** Schedule, edit, or delete events via casual text, Telegram voice notes (audio), or photos of class/event schedules powered by **Google Gemini (`gemini-2.5-flash` / `gemini-3.5-flash-lite`)**.
- **Intelligent Multi-Calendar Routing:** Automatically routes events to the appropriate Google Calendar account based on semantic context:
  - **Academic / Campus:** Lectures, thesis consultations, seminars, and university deadlines.
  - **Work / Projects:** App development, design sprints, client meetings, and project milestones.
  - **Personal / Habits:** Workouts, reading sessions, sleep schedules, and personal routines.
- **Persistent Nagging Reminders:** Triggers automated Telegram alerts prior to scheduled events (accounting for travel vs. remote preparation time) and repeats notifications every 5 minutes with interactive inline confirmation buttons until acknowledged.
- **Automated Daily Morning Briefing:** Delivers a curated daily agenda summary and motivational briefing every morning at 07:00 WITA (UTC+8).
- **Long-Term Personal Memory:** Stores user preferences, routines, and contextual facts in cloud key-value storage to personalize future scheduling decisions.

---

## 🏗️ System Architecture

Built on a **100% serverless, zero-cost cloud architecture**:

```text
[Telegram User] ──(Text / Voice / Photo)──▶ [Telegram Bot API Webhook]
                                                      │
                                                      ▼
[cron-job.org] ──(5-min Ping & 07:00 Brief)──▶ [Vercel Serverless Flask App]
                                                      │
                         ┌────────────────────────────┼────────────────────────────┐
                         ▼                            ▼                            ▼
              [Google Gemini API]         [Google Calendar API v3]          [Upstash Redis]
           (Intent & Tool Calling)         (3x OAuth2 Accounts)         (State, Memory & Logs)

```

| Layer | Technology | Role |
| --- | --- | --- |
| **Interface** | `python-telegram-bot` (Webhook) | Handles text, voice notes, images, and inline callback buttons. |
| **AI Brain** | `google-genai` (Gemini API) | Performs multimodal parsing, context routing, and autonomous tool execution. |
| **Calendar Engine** | Google Calendar API v3 | Manages CRUD operations across three isolated OAuth2 accounts. |
| **State & Memory** | Upstash Redis (REST API) | Persists active reminder states, ping counters, conversation history, and user memory. |
| **Compute & Cron** | Vercel + `cron-job.org` | Hosts serverless Python endpoints (`/api/webhook`, `/api/ping`, `/api/briefing`). |

---

## 📂 Project Structure

```text
kairo-agent/
├── app.py               # Main Flask entrypoint (Telegram webhook, ping worker, morning briefing)
├── calendar_tools.py    # Multi-account Google Calendar v3 tools & personal memory functions
├── database.py          # Upstash Redis REST API wrapper for reminders, history, and memory
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation

```

---

## ⚙️ Environment Variables

To deploy this project, configure the following environment variables in your hosting provider:

| Variable | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot token issued by `@BotFather` |
| `ALLOWED_USER_ID` | Authorized Telegram user ID for single-user security |
| `GEMINI_API_KEY` | Google AI Studio API key |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST endpoint URL |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis authentication token |
| `TOKEN_PERSONAL_JSON` | Serialized OAuth2 credentials JSON for Personal calendar |
| `TOKEN_KERJA_JSON` | Serialized OAuth2 credentials JSON for Work calendar |
| `TOKEN_KAMPUS_JSON` | Serialized OAuth2 credentials JSON for Campus calendar |
| `CRON_SECRET` | Secret token authenticating scheduled cron requests |

---

## 📄 License

This project is licensed under the [MIT License](./LICENSE) — Copyright (c) 2026 **Angel Pink Wong**. Free to use for learning, educational reference, and further development.
