import os
import pytz
import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError
from dotenv import load_dotenv
import db
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
import asyncio
from fastapi import FastAPI
import uvicorn
import threading

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Состояния ConversationHandler
CHOOSE_TIMEZONE, ADD_TOPIC, DELETE_TOPIC, PAUSE_TOPIC, RESUME_TOPIC = range(5)

# Доступные часовые пояса
TIMEZONES = [
    "Europe/Moscow",
    "Europe/Kiev",
    "Asia/Almaty",
    "America/New_York",
    "Asia/Tokyo",
    "Asia/Yekaterinburg",
]

# Расписание повторений
REPETITION_SCHEDULE = [
    timedelta(hours=1),
    timedelta(days=1),
    timedelta(days=4),
    timedelta(days=7),
    timedelta(days=30),
]

# FastAPI для /healthz
app = FastAPI()

@app.get("/healthz")
async def health_check():
    try:
        with db.get_db_connection():
            return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Добавить тему 📝", "Удалить тему 🗑️"],
            ["Остановить напоминания ⏸️", "Возобновить напоминания ▶️"],
            ["Мой прогресс 📊"],
        ],
        resize_keyboard=True,
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    logger.info(f"Received /start from user {user_id} in chat {chat_id}")
    try:
        timezone = db.get_user_timezone(user_id)
        db.add_user(user_id, user.username, user.first_name, timezone or "UTC", chat_id)
    except Exception as e:
        logger.error(f"Error in start for user {user_id}: {e}")
        await update.message.reply_text("Ошибка базы данных. Попробуйте позже.")
        return ConversationHandler.END
    if not timezone:
        keyboard = [[InlineKeyboardButton(tz, callback_data=f"timezone_{tz}")] for tz in TIMEZONES]
        await update.message.reply_text(
            "Выберите ваш часовой пояс 🌍:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSE_TIMEZONE
    await update.message.reply_text(
        f"Привет, {user.first_name}! Я помогу тебе запоминать темы по кривой забывания! 😊 Выбери действие:",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END

async def choose_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    timezone = query.data.replace("timezone_", "")
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User {user.id} selected timezone: {timezone} in chat {chat_id}")
    try:
        db.add_user(user.id, user.username, user.first_name, timezone, chat_id)
        await query.message.reply_text(
            f"Часовой пояс {timezone} сохранён! 😊 Выбери действие:", reply_markup=main_menu()
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error saving timezone for user {user.id}: {e}")
        await query.message.reply_text("Ошибка при сохранении часового пояса. Попробуйте снова.")
        return ConversationHandler.END

async def add_topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started adding topic")
    await update.message.reply_text(
        "Напиши название темы (например, 'Рецепт котлет') 📝:",
        reply_markup=ReplyKeyboardMarkup([["Назад 🔙"]], resize_keyboard=True),
    )
    return ADD_TOPIC

async def add_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    logger.info(f"User {user_id} adding topic: {text}")
    if text == "Назад 🔙":
        await update.message.reply_text("Выбери действие:", reply_markup=main_menu())
        return ConversationHandler.END
    if not text:
        await update.message.reply_text("Название темы не может быть пустым! Попробуй снова 📝:")
        return ADD_TOPIC
    try:
        topic_id = db.add_topic(user_id, text)
        timezone = db.get_user_timezone(user_id)
        if not timezone:
            logger.error(f"No timezone set for user {user_id}")
            await update.message.reply_text("Ошибка: не установлен часовой пояс. Начните заново с /start.")
            return ConversationHandler.END
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        first_reminder = now + REPETITION_SCHEDULE[0]
        reminder_id = db.schedule_reminder(topic_id, first_reminder.astimezone(pytz.UTC), status="PENDING")
        scheduler = context.bot_data.get("scheduler")
        job_id = f"reminder_{topic_id}_{reminder_id}"
        if scheduler.get_job(job_id):
            logger.warning(f"Job {job_id} already exists, removing before adding new")
            scheduler.remove_job(job_id)
        scheduler.add_job(
            send_reminder,
            DateTrigger(run_date=first_reminder),
            args=[chat_id, topic_id, text, reminder_id, context, tz],
            timezone=tz,
            id=job_id,
        )
        logger.info(f"Scheduled first reminder for topic_id {topic_id} (reminder_id {reminder_id}) at {first_reminder} (timezone: {timezone})")
        await update.message.reply_text(
            f"Тема '{text}' добавлена! 📝 Первое напоминание придёт {first_reminder.strftime('%Y-%m-%d %H:%M')} 🕒",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error adding topic for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при добавлении темы. Попробуйте снова.")
        return ConversationHandler.END

async def delete_topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started deleting topic")
    try:
        topics = db.get_all_topics(user_id)
        if not topics:
            await update.message.reply_text(
                "У тебя нет тем! 😔 Добавь новую тему.", reply_markup=main_menu()
            )
            return ConversationHandler.END
        keyboard = [
            [InlineKeyboardButton(f"{title} {'(на паузе)' if is_paused else ''} 🗑️", callback_data=f"delete_{topic_id}")]
            for topic_id, title, is_paused in topics
        ]
        await update.message.reply_text(
            "Выбери тему для удаления:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text(
            "Нажми 'Назад' для возврата в меню:", reply_markup=ReplyKeyboardMarkup([["Назад 🔙"]], resize_keyboard=True)
        )
        context.user_data["back_message_sent"] = True
        return DELETE_TOPIC
    except Exception as e:
        logger.error(f"Error getting topics for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при получении списка тем. Попробуйте позже.")
        return ConversationHandler.END

async def delete_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if update.message and update.message.text == "Назад 🔙":
        await update.message.reply_text("Выбери действие:", reply_markup=main_menu())
        context.user_data.pop("back_message_sent", None)
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    topic_id = int(query.data.replace("delete_", ""))
    logger.info(f"User {user_id} deleting topic: {topic_id}")
    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM topics WHERE topic_id = %s", (topic_id,))
                result = cur.fetchone()
                if not result or result[0] != user_id:
                    await query.message.reply_text("Эта тема не принадлежит вам!")
                    return DELETE_TOPIC
        scheduler = context.bot_data.get("scheduler")
        for job in scheduler.get_jobs():
            if job.id.startswith(f"reminder_{topic_id}_"):
                scheduler.remove_job(job.id)
                logger.info(f"Removed job {job.id} for topic {topic_id}")
        db.delete_topic(topic_id)
        topics = db.get_all_topics(user_id)
        if not topics:
            await query.message.edit_text("Тема удалена! 🗑️ У тебя больше нет тем.")
            await query.message.reply_text("Выбери действие:", reply_markup=main_menu())
            context.user_data.pop("back_message_sent", None)
            return ConversationHandler.END
        keyboard = [
            [InlineKeyboardButton(f"{title} {'(на паузе)' if is_paused else ''} 🗑️", callback_data=f"delete_{topic_id}")]
            for topic_id, title, is_paused in topics
        ]
        await query.message.edit_text(
            "Тема удалена! 🗑️ Выбери другую тему для удаления:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return DELETE_TOPIC
    except Exception as e:
        logger.error(f"Error deleting topic {topic_id}: {e}")
        await query.message.reply_text("Ошибка при удалении темы. Попробуйте снова.")
        return DELETE_TOPIC

async def pause_topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started pausing topic")
    try:
        topics = db.get_active_topics(user_id)
        if not topics:
            await update.message.reply_text(
                "У тебя нет активных тем! 😔 Добавь новую тему.", reply_markup=main_menu()
            )
            return ConversationHandler.END
        keyboard = [[InlineKeyboardButton(f"{title} ⏸️", callback_data=f"pause_{topic_id}")] for topic_id, title in topics]
        await update.message.reply_text(
            "Выбери тему для приостановки:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text(
            "Нажми 'Назад' для возврата в меню:", reply_markup=ReplyKeyboardMarkup([["Назад 🔙"]], resize_keyboard=True)
        )
        context.user_data["back_message_sent"] = True
        return PAUSE_TOPIC
    except Exception as e:
        logger.error(f"Error getting active topics for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при получении списка тем. Попробуйте позже.")
        return ConversationHandler.END

async def pause_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if update.message and update.message.text == "Назад 🔙":
        await update.message.reply_text("Выбери действие:", reply_markup=main_menu())
        context.user_data.pop("back_message_sent", None)
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    topic_id = int(query.data.replace("pause_", ""))
    logger.info(f"User {user_id} pausing topic: {topic_id}")
    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM topics WHERE topic_id = %s", (topic_id,))
                result = cur.fetchone()
                if not result or result[0] != user_id:
                    await query.message.reply_text("Эта тема не принадлежит вам!")
                    return PAUSE_TOPIC
        db.clear_unprocessed_reminders(topic_id)
        db.pause_topic(topic_id)
        topics = db.get_active_topics(user_id)
        if not topics:
            await query.message.edit_text("Тема приостановлена! ⏸️ У тебя больше нет активных тем.")
            await query.message.reply_text("Выбери действие:", reply_markup=main_menu())
            context.user_data.pop("back_message_sent", None)
            return ConversationHandler.END
        keyboard = [[InlineKeyboardButton(f"{title} ⏸️", callback_data=f"pause_{topic_id}")] for topic_id, title in topics]
        await query.message.edit_text(
            "Тема приостановлена! ⏸️ Выбери другую тему:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PAUSE_TOPIC
    except Exception as e:
        logger.error(f"Error pausing topic {topic_id}: {e}")
        await query.message.reply_text("Ошибка при приостановке темы. Попробуйте снова.")
        return PAUSE_TOPIC

async def resume_topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started resuming topic")
    try:
        topics = db.get_paused_topics(user_id)
        if not topics:
            await update.message.reply_text("У тебя нет приостановленных тем! 😔", reply_markup=main_menu())
            return ConversationHandler.END
        keyboard = [[InlineKeyboardButton(f"{title} ▶️", callback_data=f"resume_{topic_id}")] for topic_id, title in topics]
        await update.message.reply_text(
            "Выбери тему для возобновления:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text(
            "Нажми 'Назад' для возврата в меню:", reply_markup=ReplyKeyboardMarkup([["Назад 🔙"]], resize_keyboard=True)
        )
        context.user_data["back_message_sent"] = True
        return RESUME_TOPIC
    except Exception as e:
        logger.error(f"Error getting paused topics for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при получении списка тем. Попробуйте позже.")
        return ConversationHandler.END

async def resume_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if update.message and update.message.text == "Назад 🔙":
        await update.message.reply_text("Выбери действие:", reply_markup=main_menu())
        context.user_data.pop("back_message_sent", None)
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    topic_id = int(query.data.replace("resume_", ""))
    logger.info(f"User {user_id} resuming topic: {topic_id}")
    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM topics WHERE topic_id = %s", (topic_id,))
                result = cur.fetchone()
                if not result or result[0] != user_id:
                    await query.message.reply_text("Эта тема не принадлежит вам!")
                    return RESUME_TOPIC
        db.clear_unprocessed_reminders(topic_id)
        db.resume_topic(topic_id)
        timezone = db.get_user_timezone(user_id)
        if not timezone:
            logger.error(f"No timezone set for user {user_id}")
            await query.message.reply_text("Ошибка: не установлен часовой пояс. Начните заново с /start.")
            return ConversationHandler.END
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        first_reminder = now + REPETITION_SCHEDULE[0]
        reminder_id = db.schedule_reminder(topic_id, first_reminder.astimezone(pytz.UTC), status="PENDING")
        topics = db.get_all_topics(user_id)
        title = next((t[1] for t in topics if t[0] == topic_id), "Тема")
        scheduler = context.bot_data.get("scheduler")
        job_id = f"reminder_{topic_id}_{reminder_id}"
        if scheduler.get_job(job_id):
            logger.warning(f"Job {job_id} already exists, removing before adding new")
            scheduler.remove_job(job_id)
        scheduler.add_job(
            send_reminder,
            DateTrigger(run_date=first_reminder),
            args=[chat_id, topic_id, title, reminder_id, context, tz],
            timezone=tz,
            id=job_id,
        )
        logger.info(f"Scheduled first reminder for resumed topic_id {topic_id} (reminder_id {reminder_id}) at {first_reminder} (timezone: {timezone})")
        topics = db.get_paused_topics(user_id)
        if not topics:
            await query.message.edit_text("Тема возобновлена! ▶️ У тебя больше нет приостановленных тем.")
            await query.message.reply_text("Выбери действие:", reply_markup=main_menu())
            context.user_data.pop("back_message_sent", None)
            return ConversationHandler.END
        keyboard = [[InlineKeyboardButton(f"{title} ▶️", callback_data=f"resume_{topic_id}")] for topic_id, title in topics]
        await query.message.edit_text(
            "Тема возобновлена! ▶️ Выбери другую тему:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return RESUME_TOPIC
    except Exception as e:
        logger.error(f"Error resuming topic {topic_id}: {e}")
        await query.message.reply_text("Ошибка при возобновлении темы. Попробуйте снова.")
        return RESUME_TOPIC

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested progress")
    try:
        progress = db.get_user_progress(user_id)
        if not progress:
            await update.message.reply_text("У тебя нет тем! 😔 Добавь новую тему 📝.", reply_markup=main_menu())
            return
        messages = []
        current_message = "Твои темы: 📋\n"
        timezone = db.get_user_timezone(user_id)
        tz = pytz.timezone(timezone) if timezone else pytz.UTC
        for i, (title, repetitions, next_reminder, is_paused, status) in enumerate(progress, 1):
            short_title = (title[:97] + "...") if len(title) > 100 else title
            status_text = " (на паузе)" if is_paused else " (в ожидании)" if status == "AWAITING" else ""
            next_time = (
                next_reminder.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                if next_reminder and not is_paused and status != "AWAITING"
                else "Нет напоминаний"
            )
            line = f"{i}. {short_title}{status_text}: {repetitions} повторений, следующее — {next_time} 🕒\n\n"
            if len(current_message + line) > 4000:
                messages.append(current_message)
                current_message = ""
            current_message += line
        if current_message:
            messages.append(current_message)
        for message in messages:
            await update.message.reply_text(message, reply_markup=main_menu())
    except Exception as e:
        logger.error(f"Error getting progress for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при получении прогресса. Попробуйте позже.", reply_markup=main_menu())

async def send_reminder(
    chat_id: int, topic_id: int, topic_title: str, reminder_id: int, context: ContextTypes.DEFAULT_TYPE, tz: pytz.timezone
) -> None:
    logger.info(f"Attempting to send reminder for topic {topic_id} (reminder_id {reminder_id}) to chat {chat_id}")
    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM reminders WHERE reminder_id = %s", (reminder_id,)
                )
                result = cur.fetchone()
                if not result or result[0] in ("SENT", "PROCESSED"):
                    logger.info(f"Reminder {reminder_id} already sent or processed, skipping")
                    return
                cur.execute(
                    "UPDATE reminders SET status = 'SENT' WHERE reminder_id = %s", (reminder_id,)
                )
                conn.commit()
        short_title = (topic_title[:97] + "...") if len(topic_title) > 97 else topic_title
        text = f"Пора повторить тему '{short_title}'! 📚"
        keyboard = [[InlineKeyboardButton("Повторил ✅", callback_data=f"repeated_{topic_id}_{reminder_id}")]]
        await context.bot.send_message(
            chat_id=chat_id, text=text.strip(), reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Reminder {reminder_id} successfully sent to chat {chat_id}")
    except Exception as e:
        logger.error(f"Error sending reminder {reminder_id} to chat {chat_id}: {e}")

async def handle_repeated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        _, topic_id, reminder_id = query.data.split("_")
        topic_id, reminder_id = int(topic_id), int(reminder_id)
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        logger.info(f"User {user_id} marked reminder as repeated: {topic_id}_{reminder_id}")
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM reminders WHERE reminder_id = %s", (reminder_id,)
                )
                result = cur.fetchone()
                if not result or result[0] == "PROCESSED":
                    await query.message.reply_text("Это напоминание уже обработано! 😊")
                    return
                cur.execute(
                    "UPDATE reminders SET status = 'PROCESSED' WHERE reminder_id = %s", (reminder_id,)
                )
                conn.commit()
        timezone = db.get_user_timezone(user_id)
        if not timezone:
            logger.error(f"No timezone set for user {user_id}")
            await query.message.reply_text("Ошибка: не установлен часовой пояс. Начните заново с /start.")
            return
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        repetition_count = db.get_reminder_repetition_count(reminder_id)
        if repetition_count + 1 < len(REPETITION_SCHEDULE):
            next_repetition = repetition_count + 1
            next_time = now + REPETITION_SCHEDULE[next_repetition]
            topics = db.get_active_topics(user_id)
            title = next((t[1] for t in topics if t[0] == topic_id), "Тема")
            new_reminder_id = db.schedule_reminder(topic_id, next_time.astimezone(pytz.UTC), status="PENDING")
            scheduler = context.bot_data.get("scheduler")
            job_id = f"reminder_{topic_id}_{new_reminder_id}"
            if scheduler.get_job(job_id):
                logger.warning(f"Job {job_id} already exists, removing before adding new")
                scheduler.remove_job(job_id)
            scheduler.add_job(
                send_reminder,
                DateTrigger(run_date=next_time),
                args=[chat_id, topic_id, title, new_reminder_id, context, tz],
                timezone=tz,
                id=job_id,
            )
            logger.info(f"Scheduled next reminder for topic {topic_id} (reminder_id {new_reminder_id}) at {next_time} (timezone: {timezone})")
            await query.message.reply_text(
                f"Молодец, что повторил! 💪 Следующее напоминание придёт: {next_time.strftime('%Y-%m-%d %H:%M')} 🕒"
            )
        else:
            await query.message.reply_text("Поздравляю, ты освоил эту тему! 🎉")
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logger.error(f"Error processing repetition for reminder {reminder_id}: {e}")
        await query.message.reply_text("Ошибка при обработке напоминания. Попробуйте снова.")

async def process_overdue_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Checking for overdue reminders")
    try:
        reminders = db.get_overdue_reminders()
        logger.info(f"Found {len(reminders)} overdue reminders")
        for reminder in reminders:
            reminder_id = reminder["reminder_id"]
            topic_id = reminder["topic_id"]
            user_id = reminder["user_id"]
            title = reminder["title"]
            chat_id = reminder["chat_id"]
            scheduled_time = reminder["scheduled_time"]
            delay = datetime.now(pytz.UTC) - scheduled_time
            delay_minutes = int(delay.total_seconds() // 60)
            logger.info(f"Processing overdue reminder_id {reminder_id} for topic {topic_id} (user {user_id}), scheduled for {scheduled_time}, delayed by {delay_minutes} minutes")
            if chat_id:
                with db.get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT status FROM reminders WHERE reminder_id = %s", (reminder_id,)
                        )
                        result = cur.fetchone()
                        if not result or result[0] in ("SENT", "PROCESSED"):
                            logger.info(f"Reminder {reminder_id} already sent or processed, skipping")
                            continue
                timezone = db.get_user_timezone(user_id)
                if timezone:
                    tz = pytz.timezone(timezone)
                    await send_reminder(chat_id, topic_id, title, reminder_id, context, tz)
    except Exception as e:
        logger.error(f"Error processing overdue reminders: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено. Выбери действие:", reply_markup=main_menu())
    context.user_data.pop("back_message_sent", None)
    return ConversationHandler.END

async def test_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    logger.info(f"User {user_id} triggered /test in chat {chat_id}")
    try:
        topics = db.get_active_topics(user_id)
        if not topics:
            await update.message.reply_text(
                "Нет активных тем! Добавь тему с помощью 'Добавить тему 📝'.", reply_markup=main_menu()
            )
            return
        topic_id, title = topics[0]
        timezone = db.get_user_timezone(user_id)
        if not timezone:
            logger.error(f"No timezone set for user {user_id}")
            await update.message.reply_text("Ошибка: не установлен часовой пояс. Начните заново с /start.")
            return
        tz = pytz.timezone(timezone)
        test_time = datetime.now(tz) + timedelta(seconds=10)
        reminder_id = db.schedule_reminder(topic_id, test_time.astimezone(pytz.UTC), status="TESTING")
        scheduler = context.bot_data.get("scheduler")
        job_id = f"reminder_{topic_id}_{reminder_id}"
        if scheduler.get_job(job_id):
            logger.warning(f"Job {job_id} already exists, removing before adding new")
            scheduler.remove_job(job_id)
        scheduler.add_job(
            send_reminder,
            DateTrigger(run_date=test_time),
            args=[chat_id, topic_id, title, reminder_id, context, tz],
            timezone=tz,
            id=job_id,
        )
        logger.info(f"Scheduled test reminder for topic_id {topic_id} (reminder_id {reminder_id}) at {test_time} (timezone: {timezone})")
        await update.message.reply_text("Тестовое напоминание запланировано через 10 секунд!", reply_markup=main_menu())
    except Exception as e:
        logger.error(f"Error in test_reminder for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при создании тестового напоминания.", reply_markup=main_menu())

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
    if isinstance(context.error, TelegramError):
        logger.error(f"Telegram error: {context.error.message}")
    try:
        if update and update.message:
            await update.message.reply_text("Произошла ошибка. Попробуйте снова.", reply_markup=main_menu())
    except Exception as e:
        logger.error(f"Error sending error message: {e}")

async def main() -> None:
    logger.info("Starting bot...")
    try:
        db.init_db()
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            raise ValueError("BOT_TOKEN not found in .env")
        bot_app = Application.builder().token(bot_token).build()
        scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        bot_app.bot_data["scheduler"] = scheduler
        scheduler.add_job(
            process_overdue_reminders,
            IntervalTrigger(seconds=30),
            args=[bot_app],
            id="overdue_reminder_check",
            timezone=pytz.UTC,
        )
        scheduler.add_job(
            db.update_awaiting_reminders,
            IntervalTrigger(minutes=30),
            id="awaiting_reminder_check",
            timezone=pytz.UTC,
        )
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", start),
                MessageHandler(filters.Regex(r"Добавить тему"), add_topic_start),
                MessageHandler(filters.Regex(r"Удалить тему"), delete_topic_start),
                MessageHandler(filters.Regex(r"Остановить напоминания"), pause_topic_start),
                MessageHandler(filters.Regex(r"Возобновить напоминания"), resume_topic_start),
                MessageHandler(filters.Regex(r"Мой прогресс"), show_progress),
            ],
            states={
                CHOOSE_TIMEZONE: [CallbackQueryHandler(choose_timezone, pattern=r"^timezone_.*$")],
                ADD_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_topic)],
                DELETE_TOPIC: [
                    MessageHandler(filters.Regex(r"Назад 🔙"), delete_topic),
                    CallbackQueryHandler(delete_topic, pattern=r"^delete_.*$"),
                ],
                PAUSE_TOPIC: [
                    MessageHandler(filters.Regex(r"Назад 🔙"), pause_topic),
                    CallbackQueryHandler(pause_topic, pattern=r"^pause_.*$"),
                ],
                RESUME_TOPIC: [
                    MessageHandler(filters.Regex(r"Назад 🔙"), resume_topic),
                    CallbackQueryHandler(resume_topic, pattern=r"^resume_.*$"),
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            per_message=True,
        )
        bot_app.add_handler(conv_handler)
        bot_app.add_handler(CommandHandler("test", test_reminder))
        bot_app.add_handler(CallbackQueryHandler(handle_repeated, pattern=r"^repeated_.*$"))
        bot_app.add_error_handler(error_handler)
        scheduler.start()
        port = int(os.getenv("PORT", 10000))
        def run_fastapi():
            uvicorn.run(app, host="0.0.0.0", port=port)
        threading.Thread(target=run_fastapi, daemon=True).start()
        await bot_app.initialize()
        await bot_app.start()
        logger.info("Application started")
        await bot_app.updater.start_polling()
        while True:
            await asyncio.sleep(3600)
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        logger.info("Shutting down...")
        if "bot_app" in locals():
            await bot_app.stop()
            await bot_app.shutdown()
        if "scheduler" in locals():
            scheduler.shutdown()

if __name__ == "__main__":
    logger.info("Starting bot...")
    asyncio.run(main())