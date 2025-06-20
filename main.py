import os
import pytz
import logging
import asyncio
from datetime import datetime, timedelta, time
from typing import Optional
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
from cachetools import TTLCache
from telegram.error import TelegramError, Conflict
from dotenv import load_dotenv
import db
import uvicorn
import threading
import uuid
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import Response
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("telegram").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

INSTANCE_ID = str(uuid.uuid4())[:8]
logger.info(f"Starting bot instance {INSTANCE_ID}")

CHOOSE_TIMEZONE, ADD_TOPIC, DELETE_TOPIC, PAUSE_TOPIC, RESUME_TOPIC = range(5)

TIMEZONES = [
    "Europe/Moscow",
    "Europe/Kiev",
    "Asia/Almaty",
    "America/New_York",
    "Asia/Tokyo",
    "Asia/Yekaterinburg",
]

REPETITION_SCHEDULE = [
    timedelta(hours=1),
    timedelta(days=1),
    timedelta(days=4),
    timedelta(days=7),
    timedelta(days=30),
    timedelta(days=90),
    timedelta(days=180),
]

app = FastAPI()
db_status_cache = TTLCache(maxsize=1, ttl=900)  # Кэш на 15 минут
user_timezone_cache = TTLCache(maxsize=100, ttl=3600)  # Кэш для timezone на 1 час
user_chat_id_cache = TTLCache(maxsize=100, ttl=3600)  # Кэш для chat_id на 1 час

@app.get("/healthz")
async def health_check_get(request: Request) -> None:
    logger.warning(f"Instance {INSTANCE_ID}: Blocked unexpected GET health check from {request.client.host}")
    raise HTTPException(status_code=403, detail="GET not allowed, use HEAD")

@app.head("/healthz")
async def health_check_head(request: Request) -> Response:
    logger.info(f"Instance {INSTANCE_ID}: Received HEAD health check request from {request.client.host}")
    try:
        cached_status = db_status_cache.get("db_status")
        if cached_status is not None:
            logger.info(f"Instance {INSTANCE_ID}: Using cached DB status: {cached_status}")
            return Response(status_code=200 if cached_status["status"] == "ok" else 500)
        conn = db.get_db_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    logger.info(f"Instance {INSTANCE_ID}: Health check OK")
                    status = {"status": "ok", "instance_id": INSTANCE_ID}
                    db_status_cache["db_status"] = status
                    return Response(status_code=200)
        except Exception as e:
            logger.error(f"Instance {INSTANCE_ID}: Health check failed: {e}")
            status = {"status": "error", "message": str(e)}
            db_status_cache["db_status"] = status
            return Response(status_code=500)
        finally:
            db.release_db_connection(conn)
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Unexpected error in health check: {e}")
        return Response(status_code=500)

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Добавить тему 📝", "Удалить тему 🗑️"],
            ["Остановить напоминания ⏸️", "Возобновить напоминания ▶️"],
            ["Мой прогресс 📊"],
        ],
        resize_keyboard=True,
    )

def adjust_reminder_time(scheduled_time: datetime, tz: pytz.BaseTzInfo) -> datetime:
    """Переносит напоминания с 00:00–08:00 на 08:00 того же дня."""
    local_time = scheduled_time.astimezone(tz)
    local_hour = local_time.hour
    if 0 <= local_hour < 8:
        logger.info(f"Adjusting reminder time from {local_time} to 08:00")
        adjusted_local = local_time.replace(hour=8, minute=0, second=0, microsecond=0)
        return adjusted_local.astimezone(pytz.UTC)
    return scheduled_time

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id: int = user.id
    chat_id: int = update.effective_chat.id
    logger.info(f"Instance {INSTANCE_ID}: Received /start command from user {user_id} in chat {chat_id} with message: {update.message.text}")
    try:
        timezone: Optional[str] = db.get_user_timezone(user_id)
        db.add_user(user_id, user.username, user.first_name, timezone or "UTC", chat_id)
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error in start for user {user_id}: {e}")
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
    timezone: str = query.data.replace("timezone_", "")
    user = update.effective_user
    chat_id: int = update.effective_chat.id
    logger.info(f"Instance {INSTANCE_ID}: User {user.id} selected timezone: {timezone} in chat {chat_id}")
    try:
        db.add_user(user.id, user.username, user.first_name, timezone, chat_id)
        user_timezone_cache[user.id] = timezone
        user_chat_id_cache[user.id] = chat_id
        await query.message.reply_text(
            f"Часовой пояс {timezone} сохранён! 😊 Выбери действие:", reply_markup=main_menu()
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error saving timezone for user {user.id}: {e}")
        await query.message.reply_text("Ошибка при сохранении часового пояса. Попробуйте снова.")
        return ConversationHandler.END

async def add_topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id: int = update.effective_user.id
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} started adding topic")
    await update.message.reply_text(
        "Напиши название темы (например, 'Рецепт котлет') 📝:",
        reply_markup=ReplyKeyboardMarkup([["Назад 🔙"]], resize_keyboard=True),
    )
    return ADD_TOPIC

async def add_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text: str = update.message.text.strip()
    user_id: int = update.effective_user.id
    chat_id: int = update.effective_chat.id
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} sent message '{text}' in chat {chat_id}")
    if text == "Назад 🔙":
        await update.message.reply_text("Выбери действие:", reply_markup=main_menu())
        return ConversationHandler.END
    if not text:
        await update.message.reply_text("Название темы не может быть пустым! Попробуй снова 📝:")
        return ADD_TOPIC
    if len(text) > 500:
        await update.message.reply_text("Название темы слишком длинное! Максимум 500 символов.")
        return ADD_TOPIC
    try:
        topic_id: int = db.add_topic(user_id, text)
        timezone: Optional[str] = user_timezone_cache.get(user_id) or db.get_user_timezone(user_id)
        if not timezone:
            logger.error(f"Instance {INSTANCE_ID}: No timezone set for user {user_id}")
            await update.message.reply_text("Ошибка: не установлен часовой пояс. Начните заново с /start.")
            return ConversationHandler.END
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        first_reminder = now + REPETITION_SCHEDULE[0]
        first_reminder = adjust_reminder_time(first_reminder.astimezone(pytz.UTC), tz)
        reminder_id: int = db.schedule_reminder(topic_id, first_reminder, repetition_count=0)
        scheduler: AsyncIOScheduler = context.bot_data.get("scheduler")
        job_id: str = f"reminder_{topic_id}_{reminder_id}"
        if scheduler.get_job(job_id):
            logger.warning(f"Instance {INSTANCE_ID}: Job {job_id} already exists, removing before adding new")
            scheduler.remove_job(job_id)
        scheduler.add_job(
            send_reminder,
            DateTrigger(run_date=first_reminder),
            args=[chat_id, topic_id, text, reminder_id, context, tz],
            timezone=pytz.UTC,
            id=job_id,
        )
        logger.info(f"Instance {INSTANCE_ID}: Scheduled reminder for topic_id {topic_id} (reminder_id {reminder_id})")
        await update.message.reply_text(
            f"Тема '{text}' добавлена! 📝 Первое напоминание: {first_reminder.astimezone(tz).strftime('%Y-%m-%d %H:%M')} 🕒",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error adding topic for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при добавлении темы. Попробуйте снова.")
        return ConversationHandler.END

async def delete_topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id: int = update.effective_user.id
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} started deleting topic")
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
        logger.error(f"Instance {INSTANCE_ID}: Error getting topics for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при получении списка тем. Попробуйте позже.")
        return ConversationHandler.END

async def delete_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id: int = update.effective_user.id
    if update.message and update.message.text == "Назад 🔙":
        await update.message.reply_text("Выбери действие:", reply_markup=main_menu())
        context.user_data.pop("back_message_sent", None)
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    topic_id: int = int(query.data.replace("delete_", ""))
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} deleting topic {topic_id}")
    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM topics WHERE topic_id = %s", (topic_id,))
                result = cur.fetchone()
                if not result or result[0] != user_id:
                    await query.message.reply_text("Эта тема не принадлежит вам!")
                    return DELETE_TOPIC
        scheduler: AsyncIOScheduler = context.bot_data.get("scheduler")
        jobs = [job for job in scheduler.get_jobs() if job.id.startswith(f"reminder_{topic_id}_")]
        for job in jobs:
            scheduler.remove_job(job.id)
            logger.info(f"Instance {INSTANCE_ID}: Removed job {job.id} for topic {topic_id}")
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
        logger.error(f"Instance {INSTANCE_ID}: Error deleting topic {topic_id}: {e}")
        await query.message.reply_text("Ошибка при удалении темы. Попробуйте снова.")
        return DELETE_TOPIC

async def pause_topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id: int = update.effective_user.id
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} started pausing topic")
    try:
        topics = db.get_active_topics(user_id)
        if not topics:
            await update.message.reply_text(
                "У тебя нет активных тем! 😔 Добавь новую тему.", reply_markup=main_menu()
            )
            return ConversationHandler.END
        keyboard = [
            [InlineKeyboardButton(f"{title} ⏸️", callback_data=f"pause_{topic_id}")]
            for topic_id, title in topics
        ]
        await update.message.reply_text(
            "Выбери тему для приостановки:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text(
            "Нажми 'Назад' для возврата в меню:", reply_markup=ReplyKeyboardMarkup([["Назад 🔙"]], resize_keyboard=True)
        )
        context.user_data["back_message_sent"] = True
        return PAUSE_TOPIC
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error getting active topics for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при получении списка тем. Попробуйте позже.")
        return ConversationHandler.END

async def pause_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id: int = update.effective_user.id
    if update.message and update.message.text == "Назад 🔙":
        await update.message.reply_text("Выбери действие:", reply_markup=main_menu())
        context.user_data.pop("back_message_sent", None)
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    topic_id: int = int(query.data.replace("pause_", ""))
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} pausing topic {topic_id}")
    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM topics WHERE topic_id = %s", (topic_id,))
                result = cur.fetchone()
                if not result or result[0] != user_id:
                    await query.message.reply_text("Эта тема не принадлежит вам!")
                    return PAUSE_TOPIC
        scheduler: AsyncIOScheduler = context.bot_data.get("scheduler")
        jobs = [job for job in scheduler.get_jobs() if job.id.startswith(f"reminder_{topic_id}_")]
        for job in jobs:
            scheduler.remove_job(job.id)
            logger.info(f"Instance {INSTANCE_ID}: Removed job {job.id} for topic {topic_id}")
        db.clear_unprocessed_reminders(topic_id)
        db.pause_topic(topic_id)
        topics = db.get_active_topics(user_id)
        if not topics:
            await query.message.edit_text("Тема приостановлена! ⏸️ У тебя больше нет активных тем.")
            await query.message.reply_text("Выбери действие:", reply_markup=main_menu())
            context.user_data.pop("back_message_sent", None)
            return ConversationHandler.END
        keyboard = [
            [InlineKeyboardButton(f"{title} ⏸️", callback_data=f"pause_{topic_id}")]
            for topic_id, title in topics
        ]
        await query.message.edit_text(
            "Тема приостановлена! ⏸️ Выбери другую тему:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PAUSE_TOPIC
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error pausing topic {topic_id}: {e}")
        await query.message.reply_text("Ошибка при приостановке темы. Попробуйте снова.")
        return PAUSE_TOPIC

async def resume_topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id: int = update.effective_user.id
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} started resuming topic")
    try:
        topics = db.get_paused_topics(user_id)
        if not topics:
            await update.message.reply_text("У тебя нет приостановленных тем! 😔", reply_markup=main_menu())
            return ConversationHandler.END
        keyboard = [
            [InlineKeyboardButton(f"{title} ▶️", callback_data=f"resume_{topic_id}")]
            for topic_id, title in topics
        ]
        await update.message.reply_text(
            "Выбери тему для возобновления:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text(
            "Нажми 'Назад' для возврата в меню:", reply_markup=ReplyKeyboardMarkup([["Назад 🔙"]], resize_keyboard=True)
        )
        context.user_data["back_message_sent"] = True
        return RESUME_TOPIC
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error getting paused topics for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при получении списка тем. Попробуйте позже.")
        return ConversationHandler.END

async def resume_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id: int = update.effective_user.id
    chat_id: int = update.effective_chat.id
    if update.message and update.message.text == "Назад 🔙":
        await update.message.reply_text("Выбери действие:", reply_markup=main_menu())
        context.user_data.pop("back_message_sent", None)
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    topic_id: int = int(query.data.replace("resume_", ""))
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} resuming topic {topic_id}")
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
        timezone: Optional[str] = user_timezone_cache.get(user_id) or db.get_user_timezone(user_id)
        if not timezone:
            logger.error(f"Instance {INSTANCE_ID}: No timezone set for user {user_id}")
            await query.message.reply_text("Ошибка: не установлен часовой пояс. Начните заново с /start.")
            return ConversationHandler.END
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        first_reminder = now + REPETITION_SCHEDULE[0]
        first_reminder = adjust_reminder_time(first_reminder.astimezone(pytz.UTC), tz)
        reminder_id: int = db.schedule_reminder(topic_id, first_reminder, repetition_count=0)
        scheduler: AsyncIOScheduler = context.bot_data.get("scheduler")
        topics = db.get_all_topics(user_id)
        title: str = next((t[1] for t in topics if t[0] == topic_id), "Тема")
        job_id: str = f"reminder_{topic_id}_{reminder_id}"
        if scheduler.get_job(job_id):
            logger.warning(f"Instance {INSTANCE_ID}: Job {job_id} already exists, removing before adding new")
            scheduler.remove_job(job_id)
        scheduler.add_job(
            send_reminder,
            DateTrigger(run_date=first_reminder),
            args=[chat_id, topic_id, title, reminder_id, context, tz],
            timezone=pytz.UTC,
            id=job_id,
        )
        logger.info(f"Instance {INSTANCE_ID}: Scheduled reminder for topic_id {topic_id} (reminder_id {reminder_id})")
        topics = db.get_paused_topics(user_id)
        if not topics:
            await query.message.edit_text(f"Тема возобновлена! ▶️ Первое напоминание: {first_reminder.astimezone(tz).strftime('%Y-%m-%d %H:%M')} 🕒")
            await query.message.reply_text("Выбери действие:", reply_markup=main_menu())
            context.user_data.pop("back_message_sent", None)
            return ConversationHandler.END
        keyboard = [
            [InlineKeyboardButton(f"{title} ▶️", callback_data=f"resume_{topic_id}")]
            for topic_id, title in topics
        ]
        await query.message.edit_text(
            f"Тема возобновлена! ▶️ Первое напоминание: {first_reminder.astimezone(tz).strftime('%Y-%m-%d %H:%M')} 🕒 Выбери другую тему:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return RESUME_TOPIC
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error resuming topic {topic_id}: {e}")
        await query.message.reply_text("Ошибка при возобновлении темы. Попробуйте снова.")
        return RESUME_TOPIC

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id: int = update.effective_user.id
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} requested progress")
    try:
        progress = db.get_user_progress(user_id)
        if not progress:
            await update.message.reply_text("У тебя нет тем! 😔 Добавь новую тему 📝.", reply_markup=main_menu())
            return
        messages = []
        current_message = "Твои темы: 📋\n"
        timezone: Optional[str] = user_timezone_cache.get(user_id) or db.get_user_timezone(user_id)
        tz = pytz.timezone(timezone) if timezone else pytz.UTC
        for i, (title, repetitions, next_reminder, is_paused, status) in enumerate(progress, 1):
            short_title = (title[:497] + "...") if len(title) > 500 else title
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
        logger.error(f"Instance {INSTANCE_ID}: Error getting progress for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при получении прогресса. Попробуйте позже.", reply_markup=main_menu())

async def send_reminder(
    chat_id: int,
    topic_id: int,
    topic_title: str,
    reminder_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    tz: pytz.BaseTzInfo
) -> None:
    logger.info(f"Instance {INSTANCE_ID}: Sending reminder for topic {topic_id} (reminder_id {reminder_id}) to chat {chat_id}")
    try:
        if db.is_reminder_processed(reminder_id):
            logger.info(f"Instance {INSTANCE_ID}: Reminder {reminder_id} already processed, skipping")
            return
        scheduled_time = db.get_reminder_scheduled_time(reminder_id)
        if scheduled_time:
            adjusted_time = adjust_reminder_time(scheduled_time, tz)
            if adjusted_time != scheduled_time:
                logger.info(f"Instance {INSTANCE_ID}: Rescheduling reminder {reminder_id} from {scheduled_time} to {adjusted_time}")
                scheduler: AsyncIOScheduler = context.bot_data.get("scheduler")
                job_id = f"reminder_{topic_id}_{reminder_id}"
                scheduler.remove_job(job_id)
                scheduler.add_job(
                    send_reminder,
                    DateTrigger(run_date=adjusted_time),
                    args=[chat_id, topic_id, topic_title, reminder_id, context, tz],
                    timezone=pytz.UTC,
                    id=job_id,
                )
                db.schedule_reminder(topic_id, adjusted_time, db.get_reminder_repetition_count(reminder_id))
                return
        db.mark_reminder_sent(reminder_id)
        keyboard = [[InlineKeyboardButton("Повторил! ✅", callback_data=f"repeated_{topic_id}_{reminder_id}")]]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Время повторить: *{topic_title}*! 📚\nНажми 'Повторил!', когда будешь готов.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        logger.info(f"Instance {INSTANCE_ID}: Reminder {reminder_id} sent to chat {chat_id}")
    except TelegramError as e:
        logger.error(f"Instance {INSTANCE_ID}: Telegram error sending reminder {reminder_id} to chat {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error sending reminder {reminder_id}: {e}")

async def handle_repeated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Instance {INSTANCE_ID}: Received callback query: {update.callback_query.data}")
    query = update.callback_query
    await query.answer()
    try:
        _, topic_id, reminder_id = query.data.split("_")
        topic_id, reminder_id = int(topic_id), int(reminder_id)
        user_id: int = update.effective_user.id
        chat_id: int = update.effective_chat.id
        logger.info(f"Instance {INSTANCE_ID}: User {user_id} marked reminder as repeated: topic_id={topic_id}, reminder_id={reminder_id}")
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, repetition_count FROM reminders WHERE reminder_id = %s", (reminder_id,)
                )
                result = cur.fetchone()
                if not result or result[0] == "PROCESSED":
                    logger.info(f"Instance {INSTANCE_ID}: Reminder {reminder_id} already processed, skipping")
                    await query.message.reply_text("Это напоминание уже обработано! 😊")
                    return
                current_repetition: int = result[1]
                logger.info(f"Instance {INSTANCE_ID}: Current repetition_count for reminder {reminder_id} is {current_repetition}")
                cur.execute(
                    "UPDATE reminders SET status = 'PROCESSED', is_processed = TRUE WHERE reminder_id = %s", (reminder_id,)
                )
                conn.commit()
        timezone: Optional[str] = user_timezone_cache.get(user_id) or db.get_user_timezone(user_id)
        if not timezone:
            logger.error(f"Instance {INSTANCE_ID}: No timezone set for user {user_id}")
            await query.message.reply_text("Ошибка: не установлен часовой пояс. Начните заново с /start.")
            return
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        next_repetition: int = current_repetition + 1
        logger.info(f"Instance {INSTANCE_ID}: Planning next repetition {next_repetition} for topic {topic_id}")
        if next_repetition < len(REPETITION_SCHEDULE):
            next_time = now + REPETITION_SCHEDULE[next_repetition]
            next_time = adjust_reminder_time(next_time.astimezone(pytz.UTC), tz)
            topics = db.get_all_topics(user_id)
            title: str = next((t[1] for t in topics if t[0] == topic_id), "Тема")
            with db.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT reminder_id FROM reminders WHERE topic_id = %s AND status = 'PENDING' AND is_processed = FALSE",
                        (topic_id,)
                    )
                    existing_reminders = cur.fetchall()
                    if existing_reminders:
                        logger.warning(f"Instance {INSTANCE_ID}: Found {len(existing_reminders)} pending reminders for topic {topic_id}, clearing them")
                        db.clear_unprocessed_reminders(topic_id)
            new_reminder_id: int = db.schedule_reminder(topic_id, next_time, repetition_count=next_repetition)
            scheduler: AsyncIOScheduler = context.bot_data.get("scheduler")
            job_id: str = f"reminder_{topic_id}_{new_reminder_id}"
            if scheduler.get_job(job_id):
                logger.warning(f"Instance {INSTANCE_ID}: Job {job_id} already exists, removing before adding new")
                scheduler.remove_job(job_id)
            scheduler.add_job(
                send_reminder,
                DateTrigger(run_date=next_time),
                args=[chat_id, topic_id, title, new_reminder_id, context, tz],
                timezone=pytz.UTC,
                id=job_id,
            )
            logger.info(f"Instance {INSTANCE_ID}: Scheduled next reminder for topic_id {topic_id} (reminder_id {new_reminder_id})")
            await query.message.reply_text(
                f"Молодец, что повторил! 💪 Следующее напоминание: {next_time.astimezone(tz).strftime('%Y-%m-%d %H:%M')} 🕒"
            )
        else:
            logger.info(f"Instance {INSTANCE_ID}: Topic {topic_id} completed all repetitions")
            await query.message.reply_text("Поздравляю, ты освоил эту тему! 🎉")
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error processing callback query {query.data}: {e}")
        await query.message.reply_text("Ошибка при обработке кнопки. Попробуйте снова.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f"Instance {INSTANCE_ID}: Cancel command received")
    await update.message.reply_text("Действие отменено. Выбери действие:", reply_markup=main_menu())
    return ConversationHandler.END

async def test_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id: int = update.effective_user.id
    chat_id: int = update.effective_chat.id
    logger.info(f"Instance {INSTANCE_ID}: User {user_id} triggered /test_reminder in chat {chat_id}")
    try:
        topics = db.get_active_topics(user_id)
        if not topics:
            logger.info(f"Instance {INSTANCE_ID}: No active topics for user {user_id}")
            await update.message.reply_text(
                "Нет активных тем! Добавьте тему с помощью 'Добавить тему 📝'.", reply_markup=main_menu()
            )
            return
        topic_id, title = topics[0]
        current_repetition: int = db.get_topic_repetition_count(topic_id)
        logger.info(f"Instance {INSTANCE_ID}: Test reminder for topic {topic_id} with current repetition_count={current_repetition}")
        timezone: Optional[str] = user_timezone_cache.get(user_id) or db.get_user_timezone(user_id)
        if not timezone:
            logger.error(f"Instance {INSTANCE_ID}: No timezone set for user {user_id}")
            await update.message.reply_text("Ошибка: не установлен часовой пояс. Начните заново с /start.")
            return
        tz = pytz.timezone(timezone)
        test_time = datetime.now(tz) + timedelta(seconds=10)
        test_time = adjust_reminder_time(test_time.astimezone(pytz.UTC), tz)
        next_repetition: int = current_repetition + 1 if current_repetition < len(REPETITION_SCHEDULE) - 1 else current_repetition
        reminder_id: int = db.schedule_reminder(topic_id, test_time, repetition_count=next_repetition, status="TESTING")
        scheduler: AsyncIOScheduler = context.bot_data.get("scheduler")
        job_id: str = f"reminder_{topic_id}_{reminder_id}"
        if scheduler.get_job(job_id):
            logger.warning(f"Instance {INSTANCE_ID}: Job {job_id} already exists, removing before adding new")
            scheduler.remove_job(job_id)
        scheduler.add_job(
            send_reminder,
            DateTrigger(run_date=test_time),
            args=[chat_id, topic_id, title, reminder_id, context, tz],
            timezone=pytz.UTC,
            id=job_id,
        )
        logger.info(f"Instance {INSTANCE_ID}: Scheduled test reminder for topic_id {topic_id} (reminder_id {reminder_id})")
        await update.message.reply_text(
            f"Тестовое напоминание запланировано через 10 секунд! 🕒 Тема: {title}",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error in test_reminder for user {user_id}: {e}")
        await update.message.reply_text("Ошибка при создании тестового напоминания.", reply_markup=main_menu())

async def reset_polling(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id: int = update.effective_user.id
    logger.info(f"Instance {INSTANCE_ID}: Resetting polling for user {user_id}")
    try:
        await context.bot.delete_webhook(drop_pending_updates=True)
        await context.application.updater.stop()
        await asyncio.sleep(5)
        await context.application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            timeout=20,
            poll_interval=2.0
        )
        await update.message.reply_text("Polling перезапущен! Попробуйте отправить /start.")
        logger.info(f"Instance {INSTANCE_ID}: Polling reset successfully")
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error resetting polling: {e}")
        await update.message.reply_text("Ошибка при перезапуске polling. Попробуйте снова.")

async def restart_polling(bot_app: Application) -> None:
    logger.info(f"Instance {INSTANCE_ID}: Attempting to restart polling")
    try:
        await bot_app.updater.stop()
        await asyncio.sleep(5)
        await bot_app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            timeout=20,
            poll_interval=2.0
        )
        logger.info(f"Instance {INSTANCE_ID}: Polling restarted successfully")
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Failed to restart polling: {e}")
        await asyncio.sleep(60)
        await restart_polling(bot_app)

async def process_overdue_reminders(bot_app: Application) -> None:
    logger.info(f"Instance {INSTANCE_ID}: Checking for overdue reminders")
    try:
        reminders = db.get_overdue_reminders()
        if not reminders:
            logger.info(f"Instance {INSTANCE_ID}: No overdue reminders found")
            return
        for reminder in reminders:
            reminder_id: int = reminder["reminder_id"]
            topic_id: int = reminder["topic_id"]
            user_id: int = reminder["user_id"]
            title: str = reminder["title"]
            chat_id: int = user_chat_id_cache.get(user_id) or db.get_user_chat_id(user_id)
            repetition_count: int = reminder["repetition_count"]
            timezone: Optional[str] = user_timezone_cache.get(user_id) or db.get_user_timezone(user_id)
            if not chat_id or not timezone:
                logger.error(f"Instance {INSTANCE_ID}: No chat_id or timezone for user {user_id}, skipping reminder {reminder_id}")
                continue
            tz = pytz.timezone(timezone)
            scheduled_time = reminder["scheduled_time"]
            adjusted_time = adjust_reminder_time(scheduled_time, tz)
            scheduler: AsyncIOScheduler = bot_app.bot_data.get("scheduler")
            job_id: str = f"reminder_{topic_id}_{reminder_id}"
            if scheduler.get_job(job_id):
                logger.warning(f"Instance {INSTANCE_ID}: Job {job_id} already exists, skipping")
                continue
            scheduler.add_job(
                send_reminder,
                DateTrigger(run_date=adjusted_time),
                args=[chat_id, topic_id, title, reminder_id, bot_app, tz],
                timezone=pytz.UTC,
                id=job_id,
            )
            logger.info(f"Instance {INSTANCE_ID}: Scheduled overdue reminder for topic_id {topic_id} (reminder_id {reminder_id})")
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error processing overdue reminders: {e}")

async def restore_scheduled_reminders(scheduler: AsyncIOScheduler, bot_app: Application) -> None:
    logger.info(f"Instance {INSTANCE_ID}: Restoring scheduled reminders")
    try:
        reminders = db.get_all_pending_reminders()
        if not reminders:
            logger.info(f"Instance {INSTANCE_ID}: No pending reminders to restore")
            return
        for reminder in reminders:
            reminder_id: int = reminder["reminder_id"]
            topic_id: int = reminder["topic_id"]
            user_id: int = reminder["user_id"]
            title: str = reminder["title"]
            scheduled_time: datetime = reminder["scheduled_time"]
            chat_id: int = user_chat_id_cache.get(user_id) or db.get_user_chat_id(user_id)
            timezone: Optional[str] = user_timezone_cache.get(user_id) or db.get_user_timezone(user_id)
            if not chat_id or not timezone:
                logger.error(f"Instance {INSTANCE_ID}: No chat_id or timezone for user {user_id}, skipping reminder {reminder_id}")
                continue
            tz = pytz.timezone(timezone)
            adjusted_time = adjust_reminder_time(scheduled_time, tz)
            job_id: str = f"reminder_{topic_id}_{reminder_id}"
            if scheduler.get_job(job_id):
                logger.warning(f"Instance {INSTANCE_ID}: Job {job_id} already exists, skipping")
                continue
            scheduler.add_job(
                send_reminder,
                DateTrigger(run_date=adjusted_time),
                args=[chat_id, topic_id, title, reminder_id, bot_app, tz],
                timezone=pytz.UTC,
                id=job_id,
            )
            logger.info(f"Instance {INSTANCE_ID}: Restored reminder for topic_id {topic_id} (reminder_id {reminder_id})")
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error restoring scheduled reminders: {e}")

async def error_handler(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Instance {INSTANCE_ID}: Update {update} caused error {context.error}")
    if isinstance(context.error, TelegramError):
        logger.error(f"Instance {INSTANCE_ID}: Telegram error: {context.error.message}")
        if isinstance(context.error, Conflict):
            logger.warning(f"Instance {INSTANCE_ID}: Detected Conflict error, attempting to recover in 5 seconds")
            try:
                if context.application.updater and context.application.updater.running:
                    await context.application.updater.stop()
                    logger.info(f"Instance {INSTANCE_ID}: Stopped polling due to Conflict")
                await asyncio.sleep(5)
                webhook_info = await context.bot.get_webhook_info()
                if webhook_info.url:
                    logger.info(f"Instance {INSTANCE_ID}: Removing webhook {webhook_info.url}")
                    await context.bot.delete_webhook()
                await context.application.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=["message", "callback_query"],
                    timeout=20,
                    poll_interval=2.0
                )
                logger.info(f"Instance {INSTANCE_ID}: Polling restarted after Conflict error")
                if update and update.effective_message:
                    await update.message.reply_text("Связь с Telegram восстановлена! Попробуйте снова.")
            except Exception as e:
                logger.error(f"Instance {INSTANCE_ID}: Failed to recover from Conflict: {e}")
                if update and update.effective_message:
                    await update.message.reply_text("Ошибка восстановления связи. Перезапустите бота через /start.")
    try:
        if update and update.effective_message:
            await update.message.reply_text("Произошла ошибка. Попробуйте снова.", reply_markup=main_menu())
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error sending error message: {e}")

async def main() -> None:
    logger.info(f"Instance {INSTANCE_ID}: Starting bot...")
    try:
        db.init_db()
        bot_token: Optional[str] = os.getenv("BOT_TOKEN")
        if not bot_token:
            raise ValueError(f"Instance {INSTANCE_ID}: BOT_TOKEN not found in .env")
        bot_app = Application.builder().token(bot_token).build()
        scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        bot_app.bot_data["scheduler"] = scheduler
        scheduler.add_job(
            process_overdue_reminders,
            IntervalTrigger(hours=6),
            args=[bot_app],
            id="overdue_reminder_check",
            timezone=pytz.UTC,
        )
        scheduler.start()
        logger.info(f"Instance {INSTANCE_ID}: Scheduler started")
        await restore_scheduled_reminders(scheduler, bot_app)
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
                    CallbackQueryHandler(delete_topic, pattern=r"^delete_.*$"),
                    MessageHandler(filters.Regex(r"Назад 🔙"), delete_topic),
                ],
                PAUSE_TOPIC: [
                    CallbackQueryHandler(pause_topic, pattern=r"^pause_.*$"),
                    MessageHandler(filters.Regex(r"Назад 🔙"), pause_topic),
                ],
                RESUME_TOPIC: [
                    CallbackQueryHandler(resume_topic, pattern=r"^resume_.*$"),
                    MessageHandler(filters.Regex(r"Назад 🔙"), resume_topic),
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            per_message=False,
        )
        bot_app.add_handler(conv_handler)
        bot_app.add_handler(CommandHandler("test", test_reminder))
        bot_app.add_handler(CommandHandler("reset", reset_polling))
        bot_app.add_handler(CallbackQueryHandler(handle_repeated, pattern=r"^repeated_.*$"))
        bot_app.add_error_handler(error_handler)
        port = int(os.getenv("PORT", 8000))
        def run_fastapi():
            logger.info(f"Instance {INSTANCE_ID}: Starting FastAPI on port {port}")
            uvicorn.run(app, host="0.0.0.0", port=port)
        threading.Thread(target=run_fastapi, daemon=True).start()
        await bot_app.initialize()
        await bot_app.start()
        webhook_info = await bot_app.bot.get_webhook_info()
        if webhook_info.url:
            logger.info(f"Instance {INSTANCE_ID}: Removing webhook {webhook_info.url}")
            await bot_app.bot.delete_webhook(drop_pending_updates=True)
        logger.info(f"Instance {INSTANCE_ID}: Application started")
        await bot_app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            timeout=20,
            poll_interval=2.0
        )
        logger.info(f"Instance {INSTANCE_ID}: Polling started")
        while True:
            await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"Instance {INSTANCE_ID}: Error in main: {e}")
        raise
    finally:
        logger.info(f"Instance {INSTANCE_ID}: Shutting down...")
        if "bot_app" in locals():
            await bot_app.stop()
            await bot_app.shutdown()
        if "scheduler" in locals():
            scheduler.shutdown()
            logger.info(f"Instance {INSTANCE_ID}: Scheduler shutdown")
        db.close_db_pool()
        logger.info(f"Instance {INSTANCE_ID}: Shutdown complete")

if __name__ == "__main__":
    logger.info(f"Instance {INSTANCE_ID}: Starting bot...")
    asyncio.run(main())