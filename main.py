from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

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


# ================= STREAK =================
def update_streak():
    today = str(datetime.now().date())
    last = study_data["last_day"]

    if last != today:
        study_data["streak"] = study_data["streak"] + 1 if last == str(datetime.now().date()) else 1
        study_data["last_day"] = today


# ================= TKB =================
def get_sorted_subjects(day):
    raw = study_data["schedule"].get(day, [])
    return [x["subject"] for x in sorted(raw, key=lambda x: x["priority"])]


# ================= DASHBOARD =================
def build_dashboard(subject):
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


# ================= DASHBOARD =================
async def send_dashboard(app, subject):
    msg = await app.bot.send_message(
        chat_id=CHAT_ID,
        text=build_dashboard(subject),
        reply_markup=keyboard()
    )
    study_data["dashboard_message_id"] = msg.message_id
    save_data()


async def update_dashboard(app, subject):
    try:
        await app.bot.edit_message_text(
            chat_id=CHAT_ID,
            message_id=study_data["dashboard_message_id"],
            text=build_dashboard(subject),
            reply_markup=keyboard()
        )
    except:
        pass


# ================= BUTTONS =================
user_state = {}

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    idx = study_data["current_subject_index"]
    subjects = study_data["subjects_today"]

    if q.data == "start":
        study_data["start_time"] = time.time()
        study_data["waiting_start"] = False
        save_data()
        await update_dashboard(context.application, subjects[idx])

    elif q.data == "finish":
        if not study_data["start_time"]:
            return

        duration = int((time.time() - study_data["start_time"]) / 60)
        study_data["today_total"] += duration
        add_xp(duration)

        study_data["start_time"] = None

        study_data["current_subject_index"] += 1

        if study_data["current_subject_index"] >= len(subjects):
            study_data["current_subject_index"] = 0
            update_streak()

        await update_dashboard(context.application, subjects[study_data["current_subject_index"]])

        save_data()

    elif q.data == "skip":
        study_data["current_subject_index"] += 1
        if study_data["current_subject_index"] >= len(subjects):
            study_data["current_subject_index"] = 0

        await update_dashboard(context.application, subjects[study_data["current_subject_index"]])
        save_data()

    elif q.data == "tkb":
        text = "\n".join([f"{d}: " + ", ".join([x['subject'] for x in v]) for d,v in study_data["schedule"].items()])
        await q.message.reply_text(text)

    elif q.data == "set_time":
        user_state[q.from_user.id] = "waiting_time"
        await q.message.reply_text("⏰ Nhập giờ kiểu 18:45")


# ================= TEXT INPUT =================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id

    if user_state.get(uid) == "waiting_time":
        study_data["schedule_time"] = update.message.text
        save_data()
        user_state[uid] = None
        await update.message.reply_text(f"⏰ Đã set giờ: {study_data['schedule_time']}")


# ================= SCHEDULE =================
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

    schedule.every().day.at("18:45").do(lambda: asyncio.run(job()))

    while True:
        schedule.run_pending()
        time.sleep(1)


# ================= ANTI SKIP =================
def anti_skip(app):
    while True:
        time.sleep(30)

        if study_data["waiting_start"]:
            if time.time() - study_data["last_ping_time"] >= 600:
                asyncio.run(app.bot.send_message(
                    chat_id=CHAT_ID,
                    text="📢 học đi thằng lồn 😼"
                ))
                study_data["last_ping_time"] = time.time()


# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CallbackQueryHandler(button_click))
app.add_handler(CommandHandler("text", text_handler))

threading.Thread(target=run_schedule, args=(app,), daemon=True).start()
threading.Thread(target=anti_skip, args=(app,), daemon=True).start()

print("RUNNING PRO BOT 🚀")
app.run_polling()
