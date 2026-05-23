import json
import logging
import os
import time
import asyncio
from datetime import datetime, timezone, timedelta, time as dtime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("BOT_TOKEN", "8863961057:AAEQIO5p-T_-jNCiqyXPkImhVIPZtACxTH0")
CHAT_ID = 5389459772
DATA_FILE = Path("study_data.json")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TZ = timezone(timedelta(hours=7))

WEEKDAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday"
]

DAY_MAP = {
    "Mon": "Monday",
    "Tue": "Tuesday",
    "Wed": "Wednesday",
    "Thu": "Thursday",
    "Fri": "Friday",
    "Sat": "Saturday",
    "Sun": "Sunday",
}

DAILY_JOB_NAME = "daily_job"

# =========================
# DATA
# =========================

def default_data():
    return {
        "xp": 0,
        "level": 1,
        "today_total": 0,
        "total_time": 0,
        "start_time": None,
        "subjects_today": [],
        "current_index": 0,
        "schedule": {d: [] for d in WEEKDAYS},
        "last_day": "",
        "mode": None,
        "temp_day": None,
        "notify_hour": 18,
        "notify_minute": 45,
        "main_msg_id": None,
    }

data = default_data()

# =========================
# LOAD / SAVE
# =========================

def load():
    global data
    if DATA_FILE.exists():
        try:
            loaded = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            base = default_data()
            base.update(loaded)
            data = base
        except:
            data = default_data()

def save():
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

# =========================
# TIME
# =========================

def today():
    return WEEKDAYS[datetime.now(TZ).weekday()]

def reset_day():
    now = datetime.now(TZ).date().isoformat()
    if data.get("last_day") != now:
        data["today_total"] = 0
        data["subjects_today"] = []
        data["current_index"] = 0
        data["start_time"] = None
        data["last_day"] = now
        save()

# =========================
# XP
# =========================

def xp_need(lv):
    return lv * lv * 100

def add_xp(mins):
    data["xp"] += mins * 10
    while data["xp"] >= xp_need(data["level"]):
        data["xp"] -= xp_need(data["level"])
        data["level"] += 1

# =========================
# SUBJECT
# =========================

def current_subject():
    i = data["current_index"]
    lst = data["subjects_today"]
    return lst[i] if 0 <= i < len(lst) else None

# =========================
# EXAM COUNTDOWN
# =========================

def exam_countdown():
    now = datetime.now(TZ)

    target = datetime(2027, 6, 12, 0, 0, 0, tzinfo=TZ)

    diff = target - now

    if diff.total_seconds() < 0:
        return "🎉 Đã tới kỳ thi!"

    days = diff.days
    seconds = diff.seconds

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{days} ngày {hours} giờ {minutes} phút {secs} giây"

# =========================
# UI
# =========================

def menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Study", callback_data="study")],
        [InlineKeyboardButton("📅 TKB", callback_data="tkb")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("➕ Add", callback_data="add")],
        [InlineKeyboardButton("🗑 Remove", callback_data="remove")],
        [InlineKeyboardButton("⏰ Set Time", callback_data="settime")],
    ])

def back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])

def start_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶ Start", callback_data="start")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ])

def finish_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⛔ Finish", callback_data="finish")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ])

def day_select_kb(action):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Mon", callback_data=f"{action}_Mon"),
         InlineKeyboardButton("Tue", callback_data=f"{action}_Tue")],
        [InlineKeyboardButton("Wed", callback_data=f"{action}_Wed"),
         InlineKeyboardButton("Thu", callback_data=f"{action}_Thu")],
        [InlineKeyboardButton("Fri", callback_data=f"{action}_Fri"),
         InlineKeyboardButton("Sat", callback_data=f"{action}_Sat")],
        [InlineKeyboardButton("Sun", callback_data=f"{action}_Sun")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ])

# =========================
# MAIN MESSAGE
# =========================

async def show_main(app, text=None, kb=None):
    if text is None:
        text = "🧠 STUDY BOT"
    if kb is None:
        kb = menu_kb()

    msg_id = data.get("main_msg_id")

    if msg_id is None:
        msg = await app.bot.send_message(CHAT_ID, text, reply_markup=kb)
        data["main_msg_id"] = msg.message_id
        save()
    else:
        try:
            await app.bot.edit_message_text(
                chat_id=CHAT_ID,
                message_id=msg_id,
                text=text,
                reply_markup=kb
            )
        except:
            msg = await app.bot.send_message(CHAT_ID, text, reply_markup=kb)
            data["main_msg_id"] = msg.message_id
            save()

# =========================
# SCHEDULER (FIXED)
# =========================

def schedule_job(app):
    if not app.job_queue:
        return

    for job in app.job_queue.get_jobs_by_name(DAILY_JOB_NAME):
        job.schedule_removal()

    app.job_queue.run_daily(
        daily_job,
        time=dtime(
            hour=data["notify_hour"],
            minute=data["notify_minute"],
            tzinfo=TZ
        ),
        name=DAILY_JOB_NAME
    )

async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    await show_main(context.application, "📚 Study time!", start_btn())

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_day()
    await show_main(context.application)

# =========================
# CALLBACK ROUTER
# =========================

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    reset_day()
    d = q.data

    # HOME
    if d == "home":
        data["mode"] = None
        data["temp_day"] = None
        save()
        return await show_main(context.application)

    # STUDY
    if d == "study":
        day = today()
        data["subjects_today"] = data["schedule"][day]
        data["current_index"] = 0
        save()

        if not data["subjects_today"]:
            return await show_main(context.application, "📭 Không có lịch", back_home())

        return await show_main(context.application, f"📚 {data['subjects_today'][0]}", start_btn())

    # TKB
    if d == "tkb":
        text = "📅 TKB\n\n"
        for i in WEEKDAYS:
            text += f"{i}: " + (" → ".join(data["schedule"][i]) or "---") + "\n"
        return await show_main(context.application, text, back_home())

    # ADD / REMOVE
    if d in ["add", "remove"]:
        data["mode"] = d
        save()
        return await show_main(context.application, "📅 Chọn ngày:", day_select_kb(d))

    # DAY SELECT
    if "_" in d and (d.startswith("add_") or d.startswith("remove_")):
        action, day = d.split("_")
        full_day = DAY_MAP[day]
        data["mode"] = action
        data["temp_day"] = full_day
        save()
        return await show_main(context.application, f"✍️ Nhập môn cho {full_day}:", back_home())

    # START
    if d == "start":
        data["start_time"] = time.time()
        save()
        return await show_main(context.application, "⏱ Studying...", finish_btn())

    # FINISH
    if d == "finish":
        if not data.get("start_time"):
            return

        mins = max(1, int((time.time() - data["start_time"]) / 60))

        data["today_total"] += mins
        data["total_time"] += mins
        add_xp(mins)

        sub = current_subject()
        data["current_index"] += 1
        data["start_time"] = None

        nxt = current_subject()
        save()

        if nxt:
            return await show_main(context.application,
                f"🎉 {sub}\n⏱ +{mins}m\n➡ Next: {nxt}",
                start_btn()
            )

        return await show_main(context.application,
            f"🎉 Done\n⏱ +{mins}m",
            menu_kb()
        )

    # STATS
    if d == "stats":
        total = data["total_time"]
        hours = total // 60

        exam_time = exam_countdown()
        now_time = f"{data['notify_hour']:02d}:{data['notify_minute']:02d}"

        text = (
            f"📊 STATS\n\n"
            f"⭐ Lv: {data['level']}\n"
            f"✨ XP: {data['xp']}/{xp_need(data['level'])}\n\n"
            f"📌 THPTQG:\n⏳ {exam_time}\n\n"
            f"⏰ Notify: {now_time}\n\n"
            f"⏱ Today: {data['today_total']}m\n"
            f"⏱ Total: {total}m\n"
            f"🕒 ~{hours}h"
        )

        return await show_main(context.application, text, back_home())

    # SET TIME
    if d == "settime":
        data["mode"] = "settime"
        save()
        return await show_main(context.application, "⏰ Nhập HH:MM", back_home())

# =========================
# TEXT INPUT
# =========================

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data.get("mode"):
        return

    txt = update.message.text.strip()
    day = data.get("temp_day", today())

    if data["mode"] == "add":
        data["schedule"][day].append(txt)

    elif data["mode"] == "remove":
        lst = data["schedule"][day]
        for i, x in enumerate(lst):
            if x.lower() == txt.lower():
                lst.pop(i)
                break

    elif data["mode"] == "settime":
        try:
            h, m = map(int, txt.split(":"))

            data["notify_hour"] = h
            data["notify_minute"] = m

            save()
            schedule_job(context.application)

        except:
            await show_main(context.application, "⚠️ HH:MM sai")
            return

    data["mode"] = None
    data["temp_day"] = None
    save()

    await show_main(context.application)

# =========================
# INIT
# =========================

async def post_init(app):
    await asyncio.sleep(1)
    await show_main(app)
    schedule_job(app)

# =========================
# MAIN
# =========================

def main():
    load()

    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

    schedule_job(app)

    print("BOT RUNNING 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()