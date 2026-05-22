from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes
)

import time
import threading
import schedule
import asyncio
from datetime import datetime

TOKEN = "8863961057:AAEK57NALeLctqmipYMP0Q2_oW4LIdzNJUM"

CHAT_ID = "5389459772"
study_schedule = {
    "Monday": ["Lý"],
    "Tuesday": ["Lý"],
    "Wednesday": [],
    "Thursday": ["Lý"],
    "Friday": ["Lý"],
    "Saturday": [],
    "Sunday": [],
}

subjects_today = []

current_subject_index = 0

current_day = datetime.now().day
current_month = datetime.now().month
current_year = datetime.now().year
study_data = {
    "start_time": None,
    "total_time": 0,
    "today_total": 0,
    "month_total": 0,
    "year_total": 0
}

async def send_study_message(app, subject_name):

    keyboard = [
        [InlineKeyboardButton("✅ Bắt đầu học", callback_data="start_study")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=f"📚 Đến giờ học {subject_name} rồi bro",
        reply_markup=reply_markup
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_subject_index
    query = update.callback_query
    await query.answer()

    if query.data == "start_study":

        study_data["start_time"] = time.time()

        keyboard = [
            [InlineKeyboardButton("✅ Hoàn thành", callback_data="finish_study")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "⏱ Đã bắt đầu học...",
            reply_markup=reply_markup
        )

    elif query.data == "finish_study":

        if study_data["start_time"] is not None:

            duration = int((time.time() - study_data["start_time"]) / 60)

            study_data["total_time"] += duration
            study_data["today_total"] += duration
            study_data["month_total"] += duration
            study_data["year_total"] += duration

            current_subject =                 subjects_today[current_subject_index]
            
            await query.message.reply_text(
            f"🎉 Hoàn thành {current_subject}\n\n"
            f"⏱ Thời gian học: {duration} phút\n"
            f"📊 Hôm nay: {study_data['today_total']} phút\n"
            f"📅 Tháng này: {study_data['month_total']} phút\n"
            f"🗓 Năm nay: {study_data['year_total']} phút\n"
            f"🧠 Tổng tất cả: {study_data['total_time']} phút"
)

            study_data["start_time"] = None

            current_subject_index += 1

            if current_subject_index < len(subjects_today):

                next_subject = subjects_today[current_subject_index]

                keyboard = [
                    [InlineKeyboardButton(
                        "✅ Bắt đầu học",
                        callback_data="start_study"
                    )]
                ]

                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.message.reply_text(
                    f"📚 Học tiếp {next_subject} nhé bro 😼",
                    reply_markup=reply_markup
                )

            else:

                await query.message.reply_text(
                    "🔥 Hết lịch học hôm nay rồi bro"
                )

                current_subject_index = 0


def check_time_reset():

    global current_day
    global current_month
    global current_year

    now = datetime.now()

    if now.day != current_day:

        study_data["today_total"] = 0
        current_day = now.day

    if now.month != current_month:

        study_data["month_total"] = 0
        current_month = now.month

    if now.year != current_year:

        study_data["year_total"] = 0
        current_year = now.year
def run_schedule(app):

    async def job():

        global subjects_today
        global current_subject_index

        today = datetime.today().strftime("%A")

        subjects_today = study_schedule.get(today, [])

        current_subject_index = 0

        if len(subjects_today) > 0:

            await send_study_message(
                app,
                subjects_today[0]
            )

    schedule.every().day.at("18:45").do(
        lambda: asyncio.run(job())
    )

    while True:

        check_time_reset()

        schedule.run_pending()

        time.sleep(1)

app = ApplicationBuilder().token(TOKEN).build()

print("Bot đã bật")

app.add_handler(CallbackQueryHandler(button_click))

threading.Thread(target=run_schedule, args=(app,)).start()

print("Bot đang chạy...")

app.run_polling()