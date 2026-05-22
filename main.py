from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

import time
import threading
import schedule
import asyncio
from datetime import datetime, date
import json
import os

TOKEN = "8863961057:AAG7HEOyNoAUOWxId4EcnkQal2Nrfrg1qks"
CHAT_ID = "5389459772"

DATA_FILE = "study_data.json"

# ---------------- INIT ----------------
def default_data():
    return {
        "total_time": 0,
        "today_total": 0,
        "month_total": 0,
        "year_total": 0,
        "streak": 0,
        "last_day": "",
        "start_time": None,
        "subjects_today": [],
        "current_subject_index": 0,

        "xp": 0,
        "level": 1,

        # PRIORITY TKB SYSTEM
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


# ---------------- LEVEL SYSTEM ----------------
def xp_needed(level):
    return level * level * 100


def add_xp(minutes):
    study_data["xp"] += minutes * 10

    while study_data["xp"] >= xp_needed(study_data["level"]):
        study_data["xp"] -= xp_needed(study_data["level"])
        study_data["level"] += 1


# ---------------- STREAK ----------------
def update_streak():
    today = str(date.today())
    last = study_data["last_day"]

    if last != today:
        yesterday = str(date.fromordinal(date.today().toordinal() - 1))

        if last == yesterday:
            study_data["streak"] += 1
        else:
            study_data["streak"] = 1

        study_data["last_day"] = today


# ---------------- SORT TKB ----------------
def get_sorted_subjects(day):
    raw = study_data["schedule"].get(day, [])

    sorted_list = sorted(raw, key=lambda x: x.get("priority", 999))
    return [x["subject"] for x in sorted_list]


# ---------------- MESSAGE ----------------
async def send_study_message(app, subject_name):
    keyboard = [[InlineKeyboardButton("▶ Bắt đầu", callback_data="start_study")]]
    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=f"📚 {subject_name} tới giờ rồi",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- BUTTON ----------------
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    idx = study_data["current_subject_index"]
    subjects = study_data["subjects_today"]

    if not subjects:
        await query.message.reply_text("❌ Không có lịch học")
        return

    if query.data == "start_study":
        study_data["start_time"] = time.time()
        save_data()
        await query.message.reply_text("⏱ Bắt đầu học rồi")

    elif query.data == "finish_study":

        if study_data["start_time"] is None:
            return

        duration = int((time.time() - study_data["start_time"]) / 60)

        study_data["total_time"] += duration
        study_data["today_total"] += duration
        study_data["month_total"] += duration
        study_data["year_total"] += duration

        add_xp(duration)

        study_data["start_time"] = None

        subject = subjects[idx]

        await query.message.reply_text(
            f"🎉 {subject} xong\n"
            f"⏱ {study_data['today_total']} phút hôm nay\n"
            f"⭐ Lv {study_data['level']} | XP {study_data['xp']}"
        )

        study_data["current_subject_index"] += 1
        idx = study_data["current_subject_index"]

        if idx < len(subjects):

            next_subject = subjects[idx]

            await query.message.reply_text(
                f"📚 Tiếp: {next_subject}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("▶ Bắt đầu", callback_data="start_study")]
                ])
            )

        else:
            await query.message.reply_text("🔥 Hết hôm nay")

            study_data["current_subject_index"] = 0
            update_streak()

        save_data()


# ---------------- STATS ----------------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 STATS\n\n"
        f"⏱ Total: {study_data['total_time']}m\n"
        f"📅 Today: {study_data['today_total']}m\n"
        f"📈 Month: {study_data['month_total']}m\n"
        f"🔥 Streak: {study_data['streak']}\n"
        f"⭐ Level: {study_data['level']}\n"
        f"✨ XP: {study_data['xp']}/{xp_needed(study_data['level'])}"
    )


# ---------------- TKB COMMANDS (PRIORITY VERSION) ----------------
async def tkb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📅 TKB (priority):\n"

    for d, v in study_data["schedule"].items():
        if not v:
            text += f"{d}: ---\n"
        else:
            sorted_v = sorted(v, key=lambda x: x.get("priority", 999))
            text += f"{d}: " + ", ".join([f"{x['subject']}({x['priority']})" for x in sorted_v]) + "\n"

    await update.message.reply_text(text)


# ---------------- ADD ----------------
async def add_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = context.args[0]
    subject = context.args[1]
    priority = int(context.args[2])

    study_data["schedule"].setdefault(day, []).append({
        "subject": subject,
        "priority": priority
    })

    save_data()
    await update.message.reply_text("✅ Đã thêm môn")


# ---------------- REMOVE ----------------
async def remove_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = context.args[0]
    subject = context.args[1]

    lst = study_data["schedule"].get(day, [])

    study_data["schedule"][day] = [
        x for x in lst if x["subject"] != subject
    ]

    save_data()
    await update.message.reply_text("🗑 Đã xoá")


# ---------------- SCHEDULE ----------------
def run_schedule(app):

    async def job():
        today = datetime.today().strftime("%A")

        study_data["subjects_today"] = get_sorted_subjects(today)
        study_data["current_subject_index"] = 0

        save_data()

        if study_data["subjects_today"]:
            await send_study_message(app, study_data["subjects_today"][0])

    schedule.every().day.at("18:45").do(lambda: asyncio.run(job()))

    while True:
        schedule.run_pending()
        time.sleep(1)


# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CallbackQueryHandler(button_click))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("tkb", tkb))
app.add_handler(CommandHandler("add", add_subject))
app.add_handler(CommandHandler("remove", remove_subject))

threading.Thread

print("RUNNING BOT...")
app.run_polling()
