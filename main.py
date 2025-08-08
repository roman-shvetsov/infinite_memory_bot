import logging
import os
import re
from typing import Optional
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
    [["Мой прогресс", "Добавить тему"], ["Удалить тему", "Восстановить тему"], ["Категории"]],
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
    context.user_data.clear()
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
                            logger.debug(
                                f"Removed scheduled job reminder_{reminder.reminder_id}_{user_id} for topic {topic_id}")
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
            result = db.restore_topic(deleted_topic_id, user_id, user.timezone)
            if result:
                topic_id, topic_name = result
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
                logger.debug(
                    f"User {user_id} confirmed repetition for reminder {reminder_id}, topic '{topic.topic_name}'")
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
    elif data.startswith("category_progress:"):
        category_id = data.split("category_progress:")[1]
        category_id = int(category_id) if category_id != "none" else None
        user = db.get_user(user_id)
        if user:
            await show_category_progress(update, context, category_id, user.timezone)
        else:
            await query.message.edit_text("Пользователь не найден. Попробуйте /start.")
    elif data == "back_to_progress":
        user = db.get_user(user_id)
        if user:
            await show_progress(update, context)
            await query.answer()
        else:
            await query.message.edit_text("Пользователь не найден. Попробуйте /start.")
            await query.answer()
    elif data.startswith("create_category_add:"):
        response = data.split("create_category_add:")[1]
        category_id = context.user_data.get("new_category_id")
        if response == "yes":
            user = db.get_user(user_id)
            topics = db.get_active_topics(user_id, user.timezone, category_id=None)
            if not topics:
                await query.message.reply_text(
                    "У тебя нет тем без категории для добавления! 😿",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                context.user_data.pop("new_category_id", None)
                return
            keyboard = [
                [InlineKeyboardButton(topic.topic_name,
                                      callback_data=f"add_to_category:{topic.topic_id}:{category_id}")]
                for topic in topics
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Выбери тему для добавления в категорию:", reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_topic_to_category"
        else:
            await query.message.reply_text(
                "Хорошо, категория создана! 😺", reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
            context.user_data.pop("new_category_id", None)
    elif data.startswith("add_to_category:"):
        topic_id, category_id = map(int, data.split("add_to_category:")[1].split(":"))
        user = db.get_user(user_id)
        try:
            if db.move_topic_to_category(topic_id, user_id, category_id):
                topic = db.get_topic(topic_id, user_id, user.timezone)
                category = db.get_category(category_id, user_id)
                await query.message.reply_text(
                    f"Тема '{topic.topic_name}' добавлена в '{category.category_name}'! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                context.user_data.pop("new_category_id", None)
            else:
                await query.message.reply_text(
                    "Ой, что-то пошло не так. 😿 Попробуй снова!", reply_markup=MAIN_KEYBOARD
                )
        except Exception as e:
            logger.error(f"Error moving topic {topic_id} to category {category_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при добавлении темы в категорию. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    elif data.startswith("rename_category:"):
        category_id = int(data.split("rename_category:")[1])
        context.user_data["rename_category_id"] = category_id
        await query.message.reply_text(
            "Введи новое название категории:",
            reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
        )
        context.user_data["state"] = "awaiting_category_rename"
    elif data.startswith("delete_category:"):
        category_id = int(data.split("delete_category:")[1])
        user = db.get_user(user_id)
        try:
            category = db.get_category(category_id, user_id)
            if category and db.delete_category(category_id, user_id):
                await query.message.reply_text(
                    f"Категория '{category.category_name}' удалена, темы перемещены в 'Без категории'! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
            else:
                await query.message.reply_text(
                    "Категория не найдена. 😿 Попробуй снова!", reply_markup=MAIN_KEYBOARD
                )
        except Exception as e:
            logger.error(f"Error deleting category {category_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при удалении категории. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    elif data.startswith("move_topic:"):
        topic_id = int(data.split("move_topic:")[1])
        context.user_data["move_topic_id"] = topic_id
        user = db.get_user(user_id)
        categories = db.get_categories(user_id)
        logger.debug(f"User {user_id} selected topic {topic_id} for moving, categories available: {len(categories)}")
        if not categories:
            await query.message.reply_text(
                "У тебя нет категорий для переноса темы! 😿 Создай категорию с помощью 'Создать категорию'.",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
            return
        keyboard = [
            [InlineKeyboardButton(category.category_name,
                                  callback_data=f"move_to_category:{topic_id}:{category.category_id}")]
            for category in categories
        ]
        keyboard.append([InlineKeyboardButton("Без категории", callback_data=f"move_to_category:{topic_id}:none")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel_action")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Выбери категорию для переноса темы:", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_category_selection"
    elif data.startswith("move_to_category:"):
        topic_id, category_id = data.split("move_to_category:")[1].split(":")
        topic_id = int(topic_id)
        category_id = int(category_id) if category_id != "none" else None
        user = db.get_user(user_id)
        try:
            if db.move_topic_to_category(topic_id, user_id, category_id):
                topic = db.get_topic(topic_id, user_id, user.timezone)
                category_name = "Без категории" if category_id is None else db.get_category(category_id,
                                                                                            user_id).category_name
                await query.message.reply_text(
                    f"Тема '{topic.topic_name}' перенесена в '{category_name}'! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                context.user_data.pop("move_topic_id", None)
            else:
                await query.message.reply_text(
                    "Ой, что-то пошло не так. 😿 Попробуй снова!", reply_markup=MAIN_KEYBOARD
                )
        except Exception as e:
            logger.error(f"Error moving topic {topic_id} to category {category_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при переносе темы. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    elif data.startswith("add_topic_category:"):
        category_id = data.split("add_topic_category:")[1]
        category_id = int(category_id) if category_id != "none" else None
        user = db.get_user(user_id)
        topic_name = context.user_data.get("new_topic_name")
        try:
            topic_id = db.add_topic(user_id, topic_name, user.timezone, category_id)
            tz = pytz.timezone(user.timezone)
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
                    f"Scheduled reminder {reminder.reminder_id} for topic '{topic_name}' at {reminder.scheduled_time.isoformat()}"
                )
            category_name = "Без категории" if category_id is None else db.get_category(category_id,
                                                                                        user_id).category_name
            await query.message.reply_text(
                f"Тема '{topic_name}' добавлена в '{category_name}'! 😺 Первое повторение через 1 час.",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
            context.user_data.pop("new_topic_name", None)
        except Exception as e:
            logger.error(f"Error adding topic '{topic_name}' to category {category_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при добавлении темы. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    elif data == "back_to_categories":
        await show_progress(update, context)
    elif data == "cancel_action":
        context.user_data["state"] = None
        context.user_data.clear()
        await query.message.reply_text(
            "Действие отменено! 😺",
            reply_markup=MAIN_KEYBOARD
        )
        logger.debug(f"User {user_id} cancelled action")
    elif data.startswith("category_action:"):
        action = data.split("category_action:")[1]
        if action == "create":
            await query.message.reply_text(
                "Напиши название категории:",
                reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
            )
            context.user_data["state"] = "awaiting_category_name"
        elif action == "rename":
            categories = db.get_categories(user_id)
            if not categories:
                await query.message.reply_text(
                    "У тебя нет категорий для переименования! 😿",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                return
            keyboard = [
                [InlineKeyboardButton(category.category_name, callback_data=f"rename_category:{category.category_id}")]
                for category in categories
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Выбери категорию для переименования:", reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_category_selection_rename"
        elif action == "move":
            user = db.get_user(user_id)
            categories = db.get_categories(user_id)
            if not categories:
                await query.message.reply_text(
                    "У тебя нет категорий для переноса тем! 😿 Создай категорию с помощью 'Создать категорию'.",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                return
            topics = db.get_active_topics(user_id, user.timezone, category_id='all')
            if not topics:
                await query.message.reply_text(
                    "У тебя нет тем для переноса! 😿",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                return
            keyboard = [
                [InlineKeyboardButton(f"{topic.topic_name} ({db.get_category(topic.category_id, user_id).category_name if topic.category_id else 'Без категории'})", callback_data=f"move_topic:{topic.topic_id}")]
                for topic in topics
            ]
            keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel_action")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Сначала выбери тему, которую хочешь перенести:", reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_topic_selection_move"
        elif action == "delete":
            categories = db.get_categories(user_id)
            if not categories:
                await query.message.reply_text(
                    "У тебя нет категорий для удаления! 😿",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                return
            keyboard = [
                [InlineKeyboardButton(category.category_name, callback_data=f"delete_category:{category.category_id}")]
                for category in categories
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Выбери категорию для удаления:", reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_category_selection_delete"
    else:
        await query.answer()


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

    if context.user_data.get("state") == "awaiting_category_name":
        if text == "Отмена":
            context.user_data["state"] = None
            context.user_data.clear()
            await update.message.reply_text(
                "Действие отменено! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} cancelled category creation")
            return
        logger.debug(f"User {user_id} sent category name: {text}")
        try:
            category_id = db.add_category(user_id, text)
            context.user_data["new_category_id"] = category_id
            keyboard = [
                [InlineKeyboardButton("Да", callback_data=f"create_category_add:yes")],
                [InlineKeyboardButton("Нет", callback_data=f"create_category_add:no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"Категория '{text}' создана! Добавить в неё темы?", reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_category_add_decision"
        except Exception as e:
            logger.error(f"Error creating category '{text}' for user {user_id}: {e}")
            await update.message.reply_text(
                "Ой, что-то пошло не так при создании категории. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
        return

    if context.user_data.get("state") == "awaiting_category_rename":
        if text == "Отмена":
            context.user_data["state"] = None
            context.user_data.pop("rename_category_id", None)
            await update.message.reply_text(
                "Действие отменено! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} cancelled category rename")
            return
        logger.debug(f"User {user_id} sent new category name: {text}")
        category_id = context.user_data.get("rename_category_id")
        try:
            category = db.get_category(category_id, user_id)
            if category and db.rename_category(category_id, user_id, text):
                await update.message.reply_text(
                    f"Категория '{category.category_name}' переименована в '{text}'! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                context.user_data.pop("rename_category_id", None)
            else:
                await update.message.reply_text(
                    "Категория не найдена. 😿 Попробуй снова!", reply_markup=MAIN_KEYBOARD
                )
        except Exception as e:
            logger.error(f"Error renaming category {category_id} for user {user_id}: {e}")
            await update.message.reply_text(
                "Ой, что-то пошло не так при переименовании категории. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
        context.user_data["state"] = None
        return

    # Исправление: Сбрасываем состояние для любых команд, если пользователь в процессе переноса темы
    if context.user_data.get("state") in ["awaiting_category_action", "awaiting_topic_selection_move", "awaiting_category_selection"]:
        context.user_data["state"] = None
        context.user_data.clear()
        logger.debug(f"User {user_id} exited state {context.user_data.get('state')} due to new command")

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
    elif text == "Категории":
        logger.debug(f"User {user_id} requested categories menu")
        keyboard = [
            [
                InlineKeyboardButton("Создать категорию", callback_data="category_action:create"),
                InlineKeyboardButton("Переименовать категорию", callback_data="category_action:rename"),
            ],
            [
                InlineKeyboardButton("Перенести тему", callback_data="category_action:move"),
                InlineKeyboardButton("Удалить категорию", callback_data="category_action:delete"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выбери действие с категориями:", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_category_action"
        logger.debug(f"User {user_id} prompted to select category action")
    elif text == "Отмена":
        context.user_data["state"] = None
        context.user_data.clear()
        await update.message.reply_text(
            "Действие отменено! 😺",
            reply_markup=MAIN_KEYBOARD
        )
        logger.debug(f"User {user_id} cancelled action")
    elif context.user_data.get("state") == "awaiting_topic_name":
        if text == "Отмена":
            context.user_data["state"] = None
            context.user_data.clear()
            await update.message.reply_text(
                "Действие отменено! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} cancelled topic creation")
            return
        logger.debug(f"User {user_id} sent text: {text}, state: awaiting_topic_name")
        context.user_data["new_topic_name"] = text
        categories = db.get_categories(user_id)
        keyboard = [
            [InlineKeyboardButton(category.category_name, callback_data=f"add_topic_category:{category.category_id}")]
            for category in categories
        ]
        keyboard.append([InlineKeyboardButton("Без категории", callback_data="add_topic_category:none")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выбери категорию для темы:", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_topic_category"
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
                    logger.debug(
                        f"Missed reminder {reminder.reminder_id} for topic '{topic.topic_name}' for user {user.user_id}, sending now")
                    await send_reminder(context, user.user_id, topic.topic_name, reminder.reminder_id)
    except Exception as e:
        logger.error(f"Error checking missed reminders: {str(e)}")


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        if update.callback_query:
            await update.callback_query.message.edit_text(
                "Пользователь не найден. Попробуйте /start.",
                reply_markup=MAIN_KEYBOARD
            )
            await update.callback_query.answer()
        else:
            await update.effective_chat.send_message(
                "Пользователь не найден. Попробуйте /start.",
                reply_markup=MAIN_KEYBOARD
            )
        logger.debug(f"User {user_id} not found")
        return

    categories = db.get_categories(user_id)
    no_category_topics = db.get_active_topics(user_id, user.timezone, category_id=None)

    keyboard = [
        [InlineKeyboardButton(category.category_name, callback_data=f"category_progress:{category.category_id}")]
        for category in categories
    ]
    if no_category_topics:
        keyboard.append([InlineKeyboardButton("Без категории", callback_data="category_progress:none")])

    if not categories and not no_category_topics:
        if update.callback_query:
            await update.callback_query.message.edit_text(
                "У тебя пока нет активных тем или категорий! 😿",
                reply_markup=MAIN_KEYBOARD
            )
            await update.callback_query.answer()
        else:
            await update.effective_chat.send_message(
                "У тебя пока нет активных тем или категорий! 😿",
                reply_markup=MAIN_KEYBOARD
            )
        logger.debug(f"No categories or topics found for user {user_id}")
        context.user_data["state"] = None
        return

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if update.callback_query:
            await update.callback_query.message.edit_text(
                "Выбери категорию для просмотра прогресса:",
                reply_markup=reply_markup
            )
            await update.callback_query.answer()
        else:
            await update.effective_chat.send_message(
                "Выбери категорию для просмотра прогресса:",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error showing progress for user {user_id}: {str(e)}")
        if update.callback_query:
            await update.callback_query.answer("Произошла ошибка, попробуйте позже.")
        else:
            await update.effective_chat.send_message("Произошла ошибка, попробуйте позже.")

    context.user_data["state"] = "awaiting_category_progress"
    logger.debug(f"Progress categories sent to user {user_id}")


async def show_category_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: Optional[int], timezone: str):
    user_id = update.effective_user.id
    tz = pytz.timezone(timezone)
    topics = db.get_active_topics(user_id, timezone, category_id)
    category = db.get_category(category_id, user_id) if category_id else None
    category_name = category.category_name if category else "Без категории"

    if not topics:
        text = f"В категории '{category_name}' нет активных тем! 😿"
    else:
        topics = sorted(topics, key=lambda topic: topic.created_at)
        text = f"📚 Прогресс в категории '{category_name}' 😺 (Часовой пояс: {timezone})\n\n"
        for topic in topics:
            next_review = topic.next_review.astimezone(tz) if topic.next_review else None
            last_reviewed = topic.last_reviewed.astimezone(tz) if topic.last_reviewed else None
            text += (
                f"📖 Тема: {topic.topic_name}\n"
                f"⏰ Последнее повторение: {'нет' if not last_reviewed else last_reviewed.strftime('%d.%m.%Y %H:%M')}\n"
                f"⏰ Следующее повторение: {next_review.strftime('%d.%m.%Y %H:%M') if next_review else 'нет'}\n"
                f"✅ Завершено: {topic.completed_repetitions}/6 повторений\n\n"
                f"---\n"
            )

    keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_progress")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if update.callback_query:
            # Подтверждаем обработку callback-запроса
            await update.callback_query.answer()
            # Редактируем текущее сообщение
            await update.callback_query.message.edit_text(
                text.strip(),
                reply_markup=reply_markup
            )
        else:
            # Отправляем новое сообщение, если вызвано не через callback
            await update.effective_chat.send_message(
                text.strip(),
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error sending category progress for user {user_id} in category {category_name}: {str(e)}")
        if update.callback_query:
            await update.callback_query.answer("Произошла ошибка, попробуйте позже.")
        else:
            await update.effective_chat.send_message("Произошла ошибка, попробуйте позже.")

    context.user_data["state"] = None
    logger.debug(f"Category progress sent to user {user_id} for category {category_name}")


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
                        logger.debug(
                            f"Missed reminder {reminder.reminder_id} for topic '{topic.topic_name}' for user {user.user_id}, sending now")
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