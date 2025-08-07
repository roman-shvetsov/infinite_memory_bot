import logging
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import InvalidToken
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import Database
import asyncio
from aiohttp import web
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Проверка токена
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable is not set")
    raise ValueError("BOT_TOKEN environment variable is not set")

# Инициализация базы данных и планировщика
db = Database()
scheduler = AsyncIOScheduler(timezone="UTC")

# Основная клавиатура
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["Мой прогресс", "Добавить тему"], ["Удалить тему", "Восстановить тему"]],
    resize_keyboard=True
)

def parse_utc_offset(text: str) -> str:
    """
    Преобразует UTC-смещение (например, 'UTC+8', '+8', '-6') в формат часового пояса (например, 'Etc/GMT-8').
    Возвращает None, если формат неверный или смещение вне диапазона [-12, +14].
    """
    text = text.strip().replace(" ", "").upper()
    text = text.replace("UTC", "")
    match = re.match(r'^([+-]?)(\d{1,2})$', text)
    if not match:
        return None
    sign, offset = match.groups()
    try:
        offset = int(sign + offset)
        if not -12 <= offset <= 14:
            return None
        return f"Etc/GMT{'+' if offset < 0 else '-'}{abs(offset)}"
    except ValueError:
        return None

async def health_check(request):
    """
    Обработка GET и HEAD запросов для /health.
    Возвращает JSON {"status": "ok"} для GET и пустой ответ для HEAD.
    """
    logger.debug(f"Received {request.method} request to /health")
    if request.method == "HEAD":
        return web.Response(status=200)
    return web.json_response({"status": "ok"})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Received /start command from user {update.effective_user.id}")
    user = db.get_user(update.effective_user.id)
    if user:
        await update.message.reply_text(
            f"Твой текущий часовой пояс: {user.timezone}\n"
            "Хочешь изменить его? Выбери новый часовой пояс с помощью /tz или напиши его (например, 'Europe/Moscow' или 'UTC+8').",
            reply_markup=MAIN_KEYBOARD
        )
    else:
        await update.message.reply_text(
            "Привет! 😊 Я помогу тебе повторять темы по кривой забывания. "
            "Выбери свой часовой пояс, отправив его название (например, 'Europe/Moscow' для МСК (+3)) "
            "или смещение (например, 'UTC+8'), или напиши /tz для выбора.",
            reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
        )
    logger.debug(f"Sent start response to user {update.effective_user.id}")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data["state"] = None
    await update.message.reply_text(
        "Состояние сброшено! 😺",
        reply_markup=MAIN_KEYBOARD
    )
    logger.debug(f"User {user_id} reset state")

async def handle_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.split(maxsplit=1)[1] if len(update.message.text.split()) > 1 else None
    logger.debug(f"User {user_id} sent timezone command: {text}")

    if text == "list":
        await update.message.reply_text(
            "Полный список часовых поясов: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\n"
            "Отправь название (например, 'Europe/Moscow') или смещение (например, 'UTC+8' или '+8').",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if text:
        timezone = parse_utc_offset(text)
        if timezone:
            try:
                pytz.timezone(timezone)
                db.save_user(user_id, update.effective_user.username or "", timezone)
                logger.debug(f"User {user_id} saved with timezone {timezone} (from UTC offset {text})")
                await update.message.reply_text(
                    f"Часовой пояс {timezone} (UTC{text}) сохранен! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                return
            except Exception as e:
                logger.error(f"Error validating UTC timezone {timezone}: {str(e)}")
        try:
            pytz.timezone(text)
            db.save_user(user_id, update.effective_user.username or "", text)
            logger.debug(f"User {user_id} saved with timezone {text}")
            await update.message.reply_text(
                f"Часовой пояс {text} сохранен! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
        except Exception as e:
            logger.error(f"Error saving user timezone: {str(e)}")
            await update.message.reply_text(
                "Ой, что-то не так с часовым поясом. 😔 Попробуй название (например, 'Europe/Moscow') или смещение (например, 'UTC+8' или '+8').",
                reply_markup=MAIN_KEYBOARD
            )
        return

    keyboard = [
        [
            InlineKeyboardButton("Europe/Moscow (MSK, UTC+3)", callback_data="tz:Europe/Moscow"),
            InlineKeyboardButton("America/New_York (EST, UTC-5)", callback_data="tz:America/New_York"),
        ],
        [
            InlineKeyboardButton("Europe/London (GMT, UTC+0)", callback_data="tz:Europe/London"),
            InlineKeyboardButton("Asia/Tokyo (JST, UTC+9)", callback_data="tz:Asia/Tokyo"),
        ],
        [InlineKeyboardButton("Другой (введи вручную)", callback_data="tz:manual")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выбери часовой пояс или введи его вручную (например, 'Europe/Moscow' или 'UTC+8'):",
        reply_markup=reply_markup
    )
    context.user_data["state"] = "awaiting_timezone"
    logger.debug(f"User {user_id} prompted to select timezone")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.debug(f"User {user_id} selected callback: {data}")

    if data.startswith("tz:"):
        timezone = data.split("tz:")[1]
        if timezone == "manual":
            await query.message.reply_text(
                "Отправь название часового пояса (например, 'Europe/Moscow') или смещение (например, 'UTC+8' или '+8'):",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = "awaiting_timezone"
        else:
            try:
                pytz.timezone(timezone)
                db.save_user(user_id, update.effective_user.username or "", timezone)
                logger.debug(f"User {user_id} saved with timezone {timezone}")
                await query.message.reply_text(
                    f"Часовой пояс {timezone} сохранен! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
            except Exception as e:
                logger.error(f"Error saving user timezone: {str(e)}")
                await query.message.reply_text(
                    "Ой, что-то не так с часовым поясом. 😔 Попробуй другой с помощью /tz.",
                    reply_markup=MAIN_KEYBOARD
                )
    elif data.startswith("delete:"):
        topic_id = int(data.split("delete:")[1])
        topic = db.get_topic(topic_id, user_id, db.get_user(user_id).timezone)
        if topic:
            try:
                reminders = db.get_reminders(user_id, db.get_user(user_id).timezone)
                for reminder in reminders:
                    if reminder.topic_id == topic_id:
                        try:
                            scheduler.remove_job(f"reminder_{reminder.reminder_id}_{user_id}")
                            logger.debug(f"Removed scheduled job reminder_{reminder.reminder_id}_{user_id} for topic {topic_id}")
                        except Exception as e:
                            logger.warning(f"Could not remove job reminder_{reminder.reminder_id}_{user_id}: {e}")
                db.delete_topic(topic_id, user_id, topic.topic_name)
                await query.message.reply_text(
                    f"Тема '{topic.topic_name}' перенесена в удалённые! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                topics = db.get_active_topics(user_id, db.get_user(user_id).timezone)
                if topics:
                    keyboard = [
                        [InlineKeyboardButton(topic.topic_name, callback_data=f"delete:{topic.topic_id}")]
                        for topic in topics
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.message.edit_reply_markup(reply_markup=reply_markup)
                    logger.debug(f"Updated keyboard for user {user_id} after deleting topic {topic_id}")
                else:
                    await query.message.edit_reply_markup(reply_markup=None)
                    await query.message.reply_text(
                        "У тебя больше нет активных тем! 😿",
                        reply_markup=MAIN_KEYBOARD
                    )
                    logger.debug(f"No active topics left for user {user_id}, removed keyboard")
                context.user_data["state"] = None
            except Exception as e:
                logger.error(f"Error deleting topic {topic_id} for user {user_id}: {e}")
                await query.message.reply_text(
                    "Ой, что-то пошло не так при удалении темы. 😔 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
        else:
            await query.message.reply_text(
                "Тема не найдена. 😿 Попробуй снова с помощью 'Удалить тему'.",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
    elif data.startswith("restore:"):
        deleted_topic_id = int(data.split("restore:")[1])
        user = db.get_user(user_id)
        try:
            # Восстанавливаем тему
            result = db.restore_topic(deleted_topic_id, user_id, user.timezone)
            if result:
                topic_id, topic_name = result
                # Планируем новое напоминание
                tz = pytz.timezone(user.timezone)
                now = datetime.now(tz).astimezone(tz)
                reminders = db.get_reminders(user_id, user.timezone)
                reminder = next((r for r in reminders if r.topic_id == topic_id), None)
                if reminder:
                    scheduler.add_job(
                        send_reminder,
                        "date",
                        run_date=reminder.scheduled_time.astimezone(tz),
                        args=[context, user_id, topic_name, reminder.reminder_id],
                        id=f"reminder_{reminder.reminder_id}_{user_id}",
                        timezone=tz
                    )
                    logger.debug(
                        f"Scheduled reminder {reminder.reminder_id} for restored topic '{topic_name}' at {reminder.scheduled_time.isoformat()}"
                    )
                await query.message.reply_text(
                    f"Тема '{topic_name}' восстановлена! 😺 Первое повторение через 1 час.",
                    reply_markup=MAIN_KEYBOARD
                )
                # Обновляем список удалённых тем
                deleted_topics = db.get_deleted_topics(user_id)
                if deleted_topics:
                    keyboard = [
                        [InlineKeyboardButton(topic.topic_name, callback_data=f"restore:{topic.deleted_topic_id}")]
                        for topic in deleted_topics
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.message.edit_reply_markup(reply_markup=reply_markup)
                    logger.debug(f"Updated keyboard for user {user_id} after restoring topic {topic_id}")
                else:
                    await query.message.edit_reply_markup(reply_markup=None)
                    await query.message.reply_text(
                        "У тебя больше нет удалённых тем! 😺",
                        reply_markup=MAIN_KEYBOARD
                    )
                    logger.debug(f"No deleted topics left for user {user_id}, removed keyboard")
                context.user_data["state"] = None
            else:
                await query.message.reply_text(
                    "Тема не найдена. 😿 Попробуй снова с помощью 'Восстановить тему'.",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
        except Exception as e:
            logger.error(f"Error restoring topic {deleted_topic_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при восстановлении темы. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    elif data.startswith("repeated:"):
        reminder_id = int(data.split("repeated:")[1])
        try:
            user = db.get_user(user_id)
            if not user:
                logger.error(f"User {user_id} not found for reminder {reminder_id}")
                await query.message.reply_text(
                    "Ой, что-то пошло не так. 😔 Пользователь не найден.",
                    reply_markup=MAIN_KEYBOARD
                )
                return
            reminder = db.get_reminder(reminder_id, user_id, user.timezone)
            if not reminder:
                logger.warning(f"Reminder {reminder_id} not found for user {user_id}, checking topic progress")
                topic = db.get_topic_by_reminder_id(reminder_id, user_id, user.timezone)
                if topic and topic.completed_repetitions > 0:
                    await query.message.reply_text(
                        f"Повторение для темы '{topic.topic_name}' уже засчитано! 😺",
                        reply_markup=MAIN_KEYBOARD
                    )
                else:
                    await query.message.reply_text(
                        "Ой, напоминание или тема не найдены. 😿 Попробуй снова!",
                        reply_markup=MAIN_KEYBOARD
                    )
                return
            result = db.complete_reminder(reminder_id, user_id, user.timezone)
            if result:
                topic, new_reminder_id = result
                if new_reminder_id:
                    tz = pytz.timezone(user.timezone)
                    scheduler.add_job(
                        send_reminder,
                        "date",
                        run_date=topic.next_review.astimezone(tz),
                        args=[context, user_id, topic.topic_name, new_reminder_id],
                        id=f"reminder_{new_reminder_id}_{user_id}",
                        timezone=tz
                    )
                    logger.debug(
                        f"Scheduled new reminder {new_reminder_id} for topic '{topic.topic_name}' at {topic.next_review.isoformat()}"
                    )
                next_review = topic.next_review.astimezone(pytz.timezone(user.timezone)) if topic.next_review else None
                if topic.is_completed:
                    await query.message.reply_text(
                        f"Молодец! 😺 Тема '{topic.topic_name}' завершена!",
                        reply_markup=MAIN_KEYBOARD
                    )
                else:
                    await query.message.reply_text(
                        f"Молодец! 😺 Следующее повторение темы '{topic.topic_name}' {next_review.strftime('%d.%m.%Y %H:%M')}.",
                        reply_markup=MAIN_KEYBOARD
                    )
                logger.debug(f"User {user_id} confirmed repetition for reminder {reminder_id}, topic '{topic.topic_name}'")
            else:
                await query.message.reply_text(
                    "Ой, напоминание или тема не найдены. 😿 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
        except Exception as e:
            logger.error(f"Error processing repeated reminder {reminder_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при обработке повторения. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text(
            "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
            reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
        )
        return

    if context.user_data.get("state") == "awaiting_timezone":
        logger.debug(f"User {user_id} sent timezone: {text}")
        timezone = parse_utc_offset(text)
        if timezone:
            try:
                pytz.timezone(timezone)
                db.save_user(user_id, update.effective_user.username or "", timezone)
                logger.debug(f"User {user_id} saved with timezone {timezone} (from UTC offset {text})")
                await update.message.reply_text(
                    f"Часовой пояс {timezone} (UTC{text}) сохранен! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                return
            except Exception as e:
                logger.error(f"Error validating UTC timezone {timezone}: {str(e)}")
        try:
            pytz.timezone(text)
            db.save_user(user_id, update.effective_user.username or "", text)
            logger.debug(f"User {user_id} saved with timezone {text}")
            await update.message.reply_text(
                f"Часовой пояс {text} сохранен! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
        except Exception as e:
            logger.error(f"Error saving user timezone: {str(e)}")
            await update.message.reply_text(
                "Ой, что-то не так с часовым поясом. 😔 Попробуй название (например, 'Europe/Moscow') или смещение (например, 'UTC+8' или '+8').",
                reply_markup=MAIN_KEYBOARD
            )
        return

    if text.startswith("Повторил "):
        logger.debug(f"User {user_id} sent repeat command: {text}")
        topic_name = text[len("Повторил "):].strip()
        await mark_repeated(update, context, topic_name)
    elif text == "Мой прогресс":
        logger.debug(f"User {user_id} requested progress")
        await show_progress(update, context)
    elif text == "Добавить тему":
        logger.debug(f"User {user_id} requested to add topic")
        context.user_data["state"] = "awaiting_topic_name"
        await update.message.reply_text(
            "Напиши название темы, которую хочешь добавить! 😊",
            reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
        )
        logger.debug(f"User {user_id} prompted to enter topic name")
    elif text == "Удалить тему":
        logger.debug(f"User {user_id} requested to delete topic")
        topics = db.get_active_topics(user_id, user.timezone)
        if not topics:
            await update.message.reply_text(
                "У тебя нет активных тем для удаления! 😿",
                reply_markup=MAIN_KEYBOARD
            )
            return
        keyboard = [
            [InlineKeyboardButton(topic.topic_name, callback_data=f"delete:{topic.topic_id}")]
            for topic in topics
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выбери тему для удаления:", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_topic_deletion"
        logger.debug(f"User {user_id} prompted to select topic for deletion")
    elif text == "Восстановить тему":
        logger.debug(f"User {user_id} requested to restore topic")
        deleted_topics = db.get_deleted_topics(user_id)
        if not deleted_topics:
            await update.message.reply_text(
                "У тебя нет удалённых тем для восстановления! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            return
        keyboard = [
            [InlineKeyboardButton(topic.topic_name, callback_data=f"restore:{topic.deleted_topic_id}")]
            for topic in deleted_topics
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выбери тему для восстановления:", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_topic_restoration"
        logger.debug(f"User {user_id} prompted to select topic for restoration")
    elif text == "Отмена":
        context.user_data["state"] = None
        await update.message.reply_text(
            "Действие отменено! 😺",
            reply_markup=MAIN_KEYBOARD
        )
        logger.debug(f"User {user_id} cancelled action")
    elif context.user_data.get("state") == "awaiting_topic_name":
        logger.debug(f"User {user_id} sent text: {text}, state: awaiting_topic_name")
        await add_new_topic(update, context, text)
    else:
        await update.message.reply_text(
            "Неизвестная команда. 😿",
            reply_markup=MAIN_KEYBOARD
        )

async def mark_repeated(update: Update, context: ContextTypes.DEFAULT_TYPE, topic_name: str):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    tz = pytz.timezone(user.timezone)

    topic = db.get_topic_by_name(user_id, topic_name, user.timezone)
    if not topic:
        await update.message.reply_text(
            f"Тема '{topic_name}' не найдена. 😿 Проверь название или выбери 'Мой прогресс'.",
            reply_markup=MAIN_KEYBOARD
        )
        return

    try:
        reminders = db.get_reminders(user_id, user.timezone)
        reminder = next((r for r in reminders if r.topic_id == topic.topic_id), None)
        if not reminder:
            await update.message.reply_text(
                f"Для темы '{topic_name}' нет активных напоминаний. 😿",
                reply_markup=MAIN_KEYBOARD
            )
            return

        result = db.complete_reminder(reminder.reminder_id, user_id, user.timezone)
        if result:
            topic, new_reminder_id = result
            if new_reminder_id:
                scheduler.add_job(
                    send_reminder,
                    "date",
                    run_date=topic.next_review.astimezone(tz),
                    args=[context, user_id, topic.topic_name, new_reminder_id],
                    id=f"reminder_{new_reminder_id}_{user_id}",
                    timezone=tz
                )
                logger.debug(
                    f"Scheduled new reminder {new_reminder_id} for topic '{topic.topic_name}' at {topic.next_review.isoformat()}"
                )
            next_review = topic.next_review.astimezone(tz) if topic.next_review else None
            await update.message.reply_text(
                f"Тема '{topic_name}' отмечена как повторённая! 😺\n"
                f"Завершено: {topic.completed_repetitions}/6 повторений\n"
                f"Следующее повторение: {next_review.strftime('%d.%m.%Y %H:%M') if next_review else 'нет'}",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} marked topic '{topic_name}' as repeated")
        else:
            await update.message.reply_text(
                f"Ой, что-то пошло не так при отметке повторения темы '{topic_name}'. 😿 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    except Exception as e:
        logger.error(f"Error marking topic '{topic_name}' as repeated for user {user_id}: {str(e)}")
        await update.message.reply_text(
            "Ой, что-то пошло не так при отметке повторения. 😔 Попробуй снова!",
            reply_markup=MAIN_KEYBOARD
        )

async def send_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int, topic_name: str, reminder_id: int):
    try:
        user = db.get_user(user_id)
        if not user:
            logger.error(f"User {user_id} not found for reminder {reminder_id}")
            return
        logger.debug(f"Sending reminder {reminder_id} for topic '{topic_name}' to user {user_id}")
        keyboard = [[InlineKeyboardButton("Повторил", callback_data=f"repeated:{reminder_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            user_id,
            f"Пора повторить тему '{topic_name}'! 😺",
            reply_markup=reply_markup
        )
        logger.debug(f"Reminder {reminder_id} sent for topic '{topic_name}' to user {user_id}")
    except InvalidToken:
        logger.error(f"Invalid token when sending reminder {reminder_id} to user {user_id} for topic '{topic_name}'")
    except Exception as e:
        logger.error(f"Error sending reminder {reminder_id} to user {user_id} for topic '{topic_name}': {str(e)}")

async def check_missed_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        users = db.get_all_users()
        current_time = datetime.now(pytz.UTC)
        for user in users:
            tz = pytz.timezone(user.timezone)
            reminders = db.get_reminders(user.user_id, user.timezone)
            for reminder in reminders:
                topic = db.get_topic(reminder.topic_id, user.user_id, user.timezone)
                if topic and not topic.is_completed and reminder.scheduled_time <= current_time:
                    logger.debug(f"Missed reminder {reminder.reminder_id} for topic '{topic.topic_name}' for user {user.user_id}, sending now")
                    await send_reminder(context, user.user_id, topic.topic_name, reminder.reminder_id)
    except Exception as e:
        logger.error(f"Error checking missed reminders: {str(e)}")

async def add_new_topic(update: Update, context: ContextTypes.DEFAULT_TYPE, topic_name: str):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    timezone = user.timezone

    try:
        topic_id = db.add_topic(user_id, topic_name, timezone)
        topic = db.get_topic(topic_id, user_id, timezone)
        logger.debug(f"Topic '{topic_name}' added for user {user_id}")

        tz = pytz.timezone(timezone)
        reminders = db.get_reminders(user_id, timezone)
        reminder = next((r for r in reminders if r.topic_id == topic_id), None)
        if reminder:
            scheduler.add_job(
                send_reminder,
                "date",
                run_date=reminder.scheduled_time.astimezone(tz),
                args=[context, user_id, topic_name, reminder.reminder_id],
                id=f"reminder_{reminder.reminder_id}_{user_id}",
                timezone=tz
            )
            logger.debug(
                f"Scheduled reminder {reminder.reminder_id} for topic '{topic_name}' at {reminder.scheduled_time.isoformat()}"
            )

        await update.message.reply_text(
            f"Тема '{topic_name}' добавлена! 😺 Первое повторение через 1 час.",
            reply_markup=MAIN_KEYBOARD
        )
        context.user_data["state"] = None
    except Exception as e:
        logger.error(f"Error adding topic for user {user_id}: {str(e)}")
        await update.message.reply_text(
            "Ой, что-то пошло не так с базой данных. 😔 Попробуй позже!",
            reply_markup=MAIN_KEYBOARD
        )

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    tz = pytz.timezone(user.timezone)
    topics = db.get_active_topics(user_id, user.timezone)

    topics = sorted(topics, key=lambda topic: topic.created_at)

    if not topics:
        await update.message.reply_text(
            "У тебя пока нет активных тем! 😿",
            reply_markup=MAIN_KEYBOARD
        )
        logger.debug(f"No active topics found for user {user_id}")
        return

    progress_text = f"📚 Твой прогресс: 😺 (Часовой пояс: {user.timezone})\n\n"
    for topic in topics:
        logger.debug(
            f"Topic {topic.topic_name}: next_review={topic.next_review.isoformat() if topic.next_review else 'None'}"
        )
        next_review = topic.next_review.astimezone(tz) if topic.next_review else None
        last_reviewed = topic.last_reviewed.astimezone(tz) if topic.last_reviewed else None
        progress_text += (
            f"📖 Тема: {topic.topic_name}\n"
            f"⏰ Последнее повторение: {'нет' if not last_reviewed else last_reviewed.strftime('%d.%m.%Y %H:%M')}\n"
            f"⏰ Следующее повторение: {next_review.strftime('%d.%m.%Y %H:%M') if next_review else 'нет'}\n"
            f"✅ Завершено: {topic.completed_repetitions}/6 повторений\n\n"
            f"---\n"
        )

    await update.message.reply_text(progress_text.strip(), reply_markup=MAIN_KEYBOARD)
    logger.debug(f"Progress sent to user {user_id}")

async def schedule_existing_reminders(application):
    try:
        users = db.get_all_users()
        current_time = datetime.now(pytz.UTC)
        for user in users:
            tz = pytz.timezone(user.timezone)
            reminders = db.get_reminders(user.user_id, user.timezone)
            for reminder in reminders:
                topic = db.get_topic(reminder.topic_id, user.user_id, user.timezone)
                if topic and not topic.is_completed:
                    if reminder.scheduled_time <= current_time:
                        logger.debug(f"Missed reminder {reminder.reminder_id} for topic '{topic.topic_name}' for user {user.user_id}, sending now")
                        await send_reminder(application, user.user_id, topic.topic_name, reminder.reminder_id)
                    else:
                        scheduler.add_job(
                            send_reminder,
                            "date",
                            run_date=reminder.scheduled_time.astimezone(tz),
                            args=[application, user.user_id, topic.topic_name, reminder.reminder_id],
                            id=f"reminder_{reminder.reminder_id}_{user.user_id}",
                            timezone=tz
                        )
                        logger.debug(
                            f"Scheduled reminder {reminder.reminder_id} for topic {topic.topic_name} at {reminder.scheduled_time.isoformat()}"
                        )
            scheduler.add_job(
                check_missed_reminders,
                "cron",
                hour=10,
                minute=0,
                timezone=tz,
                args=[application],
                id=f"daily_check_missed_reminders_{user.user_id}"
            )
            logger.debug(f"Scheduled daily missed reminder check for user {user.user_id} at 10:00 {user.timezone}")
    except Exception as e:
        logger.error(f"Error scheduling existing reminders: {str(e)}")

async def main():
    runner = None
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("tz", handle_timezone))
        application.add_handler(CommandHandler("reset", reset))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_callback_query))

        app = web.Application()
        app.router.add_route('GET', '/health', health_check)
        app.router.add_route('HEAD', '/health', health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        logger.debug("Health check server started on port 8080")

        scheduler.start()
        logger.debug("Scheduler started")

        await schedule_existing_reminders(application)

        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.debug("Received cancellation, stopping bot")
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            await runner.cleanup()
            scheduler.shutdown(wait=False)
            logger.debug("Scheduler, application, and health check server shut down successfully")

    except InvalidToken as e:
        logger.error(f"Invalid token error: {str(e)}")
        if runner:
            await runner.cleanup()
        if scheduler.running:
            scheduler.shutdown(wait=False)
        raise
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        if runner:
            await runner.cleanup()
        if scheduler.running:
            scheduler.shutdown(wait=False)
        raise

if __name__ == "__main__":
    asyncio.run(main())