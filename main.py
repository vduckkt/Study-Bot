from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters

import time
import threading
import schedule
import asyncio
from datetime import datetime
import json
import os

TOKEN = "8863961057:AAG7HEOyNoAUOWxId4EcnkQal2Nrfrg1qks"
CHAT_ID = "5389459772"
DATA_FILE = "study_data.json"


# ================= INIT =================
def default_data():
    return {
        "total_time": 0,
        "today_total": 0,
        "streak": 0,
        "last_day": "",
        "start_time": None,

        "xp": 0,
        "level": 1,

        "subjects_today": [],
        "current_subject_index": 0,

        "waiting_start": False,
        "last_ping_time": 0,

        "schedule_time": "18:45",
        "dashboard_message_id": None,

        "schedule": {
            "Monday": [{"subject": "Lý", "priority": 1}],
            "Tuesday": [],
            "Wednesday": [],
            "Thursday": [],
            "Friday": [],
            "Saturday": [],
            "Sunday": []
        }
    }


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return default_data()


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(study_data, f)


study_data = load_data()


# ================= XP =================
def xp_needed(level):
    return level * level * 100


def add_xp(minutes):
    study_data["xp"] += minutes * 10

    while study_data["xp"] >= xp_needed(study_data["level"]):
        study_data["xp"] -= xp_needed(study_data["level"])
        study_data["level"] += 1


# ================= STREAK FIX =================
def update_streak():
    today = str(datetime.now().date())
    last = study_data.get("last_day", "")

    if last != today:
        yesterday = str(datetime.now().date().fromordinal(datetime.now().toordinal() - 1))

        if last == yesterday:
            study_data["streak"] += 1
        else:
            study_data["streak"] = 1

        study_data["last_day"] = today


# ================= SORT SAFE =================
def get_sorted_subjects(day):
    raw = study_data["schedule"].get(day, [])
    return [x["subject"] for x in sorted(raw, key=lambda x: x.get("priority", 999))]


# ================= UI =================
def build_dashboard(subject):
    subject = subject if subject else "😴 nghỉ"

    return f"""
📊 STUDY DASHBOARD

📚 {subject}

📅 Today: {study_data['today_total']}m
🔥 Streak: {study_data['streak']}
⭐ Lv: {study_data['level']}
✨ XP: {study_data['xp']}/{xp_needed(study_data['level'])}

🎮 Status: {"HỌC" if study_data["start_time"] else "RẢNH"}
"""


def keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶ Start", callback_data="start"),
            InlineKeyboardButton("✅ Finish", callback_data="finish"),
        ],
        [
            InlineKeyboardButton("⏭ Skip", callback_data="skip"),
            InlineKeyboardButton("📅 TKB", callback_data="tkb"),
        ],
        [
            InlineKeyboardButton("⏰ Set Time", callback_data="set_time")
        ]
    ])


# ================= DASHBOARD SAFE =================
async def send_dashboard(app, subject):
    msg = await app.bot.send_message(
        chat_id=CHAT_ID,
        text=build_dashboard(subject),
        reply_markup=keyboard()
    )
    study_data["dashboard_message_id"] = msg.message_id
    save_data()


async def update_dashboard(app, subject):
    if not study_data.get("dashboard_message_id"):
        return

    try:
        await app.bot.edit_message_text(
            chat_id=CHAT_ID,
            message_id=study_data["dashboard_message_id"],
            text=build_dashboard(subject),
            reply_markup=keyboard()
        )
    except:
        pass


# ================= BUTTON FIX =================
user_state = {}

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    subjects = study_data.get("subjects_today", [])
    idx = study_data.get("current_subject_index", 0)

    # safe guard
    if not subjects:
        await q.message.reply_text("❌ Không có lịch học")
        return

    idx = min(idx, len(subjects) - 1)
    subject = subjects[idx]

    # START
    if q.data == "start":
        study_data["start_time"] = time.time()
        study_data["waiting_start"] = False
        save_data()
        await update_dashboard(context.application, subject)

    # FINISH
    elif q.data == "finish":
        if not study_data["start_time"]:
            return

        duration = int((time.time() - study_data["start_time"]) / 60)

        study_data["today_total"] += duration
        add_xp(duration)

        study_data["start_time"] = None

        study_data["current_subject_index"] += 1
        idx = study_data["current_subject_index"]

        if idx >= len(subjects):
            study_data["current_subject_index"] = 0
            update_streak()
            await q.message.reply_text("🔥 Hết buổi học")
        else:
            await update_dashboard(context.application, subjects[idx])

        save_data()

    # SKIP
    elif q.data == "skip":
        study_data["current_subject_index"] += 1

        if study_data["current_subject_index"] >= len(subjects):
            study_data["current_subject_index"] = 0
            update_streak()

        save_data()

        idx = study_data["current_subject_index"]
        await update_dashboard(context.application, subjects[idx])

    # TKB
    elif q.data == "tkb":
        text = "📅 TKB:\n"
        for d, v in study_data["schedule"].items():
            text += f"{d}: " + ", ".join([x["subject"] for x in v]) + "\n"
        await q.message.reply_text(text)

    # SET TIME
    elif q.data == "set_time":
        user_state[q.from_user.id] = "waiting_time"
        await q.message.reply_text("⏰ Nhập giờ (vd 18:45)")


# ================= TEXT HANDLER FIX =================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id

    if user_state.get(uid) == "waiting_time":
        study_data["schedule_time"] = update.message.text
        user_state[uid] = None
        save_data()

        await update.message.reply_text(f"⏰ Đã set: {study_data['schedule_time']}")


# ================= SCHEDULE FIX =================
def run_schedule(app):

    async def job():
        today = datetime.today().strftime("%A")

        study_data["subjects_today"] = get_sorted_subjects(today)
        study_data["current_subject_index"] = 0
        study_data["waiting_start"] = True
        study_data["last_ping_time"] = time.time()

        if study_data["subjects_today"]:
            await send_dashboard(app, study_data["subjects_today"][0])

        save_data()

    schedule.every().day.at(study_data["schedule_time"]).do(lambda: asyncio.run(job()))

    while True:
        schedule.run_pending()
        time.sleep(1)


# ================= ANTI SKIP FIX =================
def anti_skip(app):
    while True:
        time.sleep(30)

        if study_data.get("waiting_start"):
            if time.time() - study_data["last_ping_time"] >= 600:
                asyncio.run(app.bot.send_message(
                    chat_id=CHAT_ID,
                    text="📢 học đi thằng lồn 😼"
                ))
                study_data["last_ping_time"] = time.time()


# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CallbackQueryHandler(button_click))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

threading.Thread(target=run_schedule, args=(app,), daemon=True).start()
threading.Thread(target=anti_skip, args=(app,), daemon=True).start()

print("RUNNING PRO BOT 🚀")
app.run_polling()
