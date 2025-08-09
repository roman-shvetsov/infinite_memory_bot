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
import tenacity

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
            f"🎉 Привет, {update.effective_user.first_name}! 😺\n"
            f"Твой текущий часовой пояс: {user.timezone}\n"
            "Хочешь изменить его? \nИспользуй команду /tz или напиши название часового пояса (например, 'Europe/Moscow') или смещение (например, 'UTC+8').\nЧтобы узнать подробнее о боте, используйте команду /help",
            reply_markup=MAIN_KEYBOARD
        )
    else:
        await update.message.reply_text(
            "🎉 Добро пожаловать в бот для повторения тем! 📚\n\n"
            "Я создан, чтобы помочь тебе эффективно запоминать информацию с помощью метода интервального повторения (кривой забывания). 😺 "
            "Добавляй темы, которые хочешь изучить, и я напомню тебе о них в нужное время, чтобы знания закрепились надолго! 🚀\n\n"
            "Для начала выбери свой часовой пояс. Это важно, чтобы напоминания приходили вовремя! ⏰\n"
            "📍 Отправь название часового пояса (например, 'Europe/Moscow' для Москвы, UTC+3).\n"
            "📍 Или укажи смещение от UTC (например, 'UTC+8' или '+8').\n"
            "📍 Хочешь выбрать из списка? Используй команду /tz.\n\n"
            "Давай начнем! 😊 Какой у тебя часовой пояс?",
            reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
        )
    logger.debug(f"Sent start response to user {update.effective_user.id}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет подробное описание бота и его функционала."""
    user_id = update.effective_user.id
    logger.debug(f"Received /help command from user {user_id}")

    help_text = (
        "🎉 **Добро пожаловать в бот для повторения тем!** 📚\n\n"
        "Я создан, чтобы помочь тебе эффективно запоминать информацию с помощью **метода интервального повторения** (кривой забывания). 😺 "
        "Добавляй темы, которые хочешь изучить, а я напомню о них в нужное время, чтобы знания закрепились надолго! 🚀\n\n"
        "📖 **Что я умею?**\n"
        "✅ **Добавлять темы**: Создавай темы для изучения и распределяй их по категориям.\n"
        "✅ **Напоминать о повторении**: Я отправлю напоминания в твоём часовом поясе, чтобы ты повторял темы по оптимальному графику (6 повторений для закрепления).\n"
        "✅ **Показывать прогресс**: Отслеживай, сколько повторений завершено для каждой темы, включая завершённые, с удобной прогресс-баром!\n"
        "✅ **Управлять категориями**: Создавай, переименовывай, удаляй категории или перемещай темы между ними.\n"
        "✅ **Удалять темы**: Удалённые темы исчезают навсегда, так что будь осторожен!\n"
        "✅ **Восстанавливать завершённые темы**: Завершил все 6 повторений? Поздравляю! Ты можешь восстановить тему через 'Восстановить тему', чтобы начать заново.\n"
        "✅ **Настраивать часовой пояс**: Укажи свой часовой пояс, чтобы напоминания приходили вовремя.\n\n"
        "🛠 **Как пользоваться?**\n"
        "🔹 **/start** — Начать работу с ботом и установить часовой пояс.\n"
        "🔹 **/tz** — Изменить часовой пояс (например, 'Europe/Moscow' или 'UTC+8').\n"
        "🔹 **/help** — Показать это сообщение.\n"
        "🔹 **/reset** — Сбросить текущее состояние (если что-то пошло не так).\n"
        "🔹 **Кнопки главного меню**:\n"
        "   - *Мой прогресс*: Посмотреть прогресс по темам и категориям, включая завершённые темы.\n"
        "   - *Добавить тему*: Создать новую тему и выбрать для неё категорию.\n"
        "   - *Удалить тему*: Удалить тему навсегда (восстановить нельзя).\n"
        "   - *Восстановить тему*: Восстановить завершённую тему для повторного изучения.\n"
        "   - *Категории*: Создать, переименовать, удалить категории или перенести темы.\n"
        "🔹 Напиши **'Повторил <название темы>'**, чтобы отметить повторение вручную.\n\n"
        "⏰ **Часовой пояс**\n"
        "Чтобы напоминания приходили вовремя, убедись, что твой часовой пояс настроен правильно. "
        "Используй /tz для изменения (например, '/tz Europe/Moscow' или '/tz UTC+8').\n\n"
        "Готов начать? 😊 Попробуй добавить первую тему через кнопку 'Добавить тему' или настрой часовой пояс с помощью /tz!"
    )

    await update.message.reply_text(
        help_text,
        reply_markup=MAIN_KEYBOARD,
        parse_mode="Markdown"
    )
    logger.debug(f"Sent help response to user {user_id}")

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

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text(
            "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
            reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
        )
        return
    categories = db.get_categories(user_id)
    keyboard = [
        [InlineKeyboardButton(category.category_name, callback_data=f"category_progress:{category.category_id}")]
        for category in categories
    ]
    keyboard.append([InlineKeyboardButton("📁 Без категории", callback_data="category_progress:none")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выбери категорию для просмотра прогресса:",
        reply_markup=reply_markup
    )
    context.user_data["state"] = "awaiting_category_progress"
    logger.debug(f"User {user_id} requested progress, showing category selection")


async def show_category_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: Optional[int],
                                 timezone: str):
    user_id = update.effective_user.id
    logger.debug(f"User {user_id} requested progress for category {category_id}")
    topics = db.get_active_topics(user_id, timezone, category_id=category_id)
    total_repetitions = 6
    category_name = db.get_category(category_id, user_id).category_name if category_id else "📁 Без категории"

    if not topics:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_progress")]])
        if update.callback_query:
            await update.callback_query.message.reply_text(
                f"В категории '{category_name}' пока нет тем! 😿",
                reply_markup=reply_markup
            )
            await update.callback_query.answer()
        else:
            await update.message.reply_text(
                f"В категории '{category_name}' пока нет тем! 😿",
                reply_markup=reply_markup
            )
        return

    tz = pytz.timezone(timezone)
    message = f"📚 {category_name} ({timezone}) 😺\n\n"
    for topic in topics:
        progress_percentage = (topic.completed_repetitions / total_repetitions) * 100
        progress_bar = "█" * int(topic.completed_repetitions) + "░" * (total_repetitions - topic.completed_repetitions)
        status = "Завершено" if topic.is_completed else f"{topic.next_review.astimezone(tz).strftime('%d.%m.%Y %H:%M')}" if topic.next_review else "Завершено"
        message += (
            f"📖 {topic.topic_name}\n"
            f"⏰ Следующее: {status}\n"
            f"✅ Прогресс: {progress_bar} {topic.completed_repetitions}/{total_repetitions} ({progress_percentage:.1f}%)\n"
            f"──────────\n"
        )

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_progress")]])
    try:
        if update.callback_query:
            await update.callback_query.message.reply_text(
                message,
                reply_markup=reply_markup
            )
            await update.callback_query.answer()
        else:
            await update.message.reply_text(
                message,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error sending category progress for user {user_id}, category {category_id}: {str(e)}")
        error_message = "Ой, что-то пошло не так при отображении прогресса! 😿 Попробуй снова или используй /reset."
        if update.callback_query:
            await update.callback_query.message.reply_text(
                error_message,
                reply_markup=MAIN_KEYBOARD
            )
            await update.callback_query.answer()
        else:
            await update.message.reply_text(
                error_message,
                reply_markup=MAIN_KEYBOARD
            )

async def send_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int, topic_name: str, reminder_id: int):
    user = db.get_user(user_id)
    if not user:
        logger.warning(f"User {user_id} not found for reminder {reminder_id}")
        return
    try:
        topic = db.get_topic_by_reminder_id(reminder_id, user_id, user.timezone)
        if not topic:
            logger.warning(f"Topic for reminder {reminder_id} not found for user {user_id}")
            return
        keyboard = [[InlineKeyboardButton("Повторил!", callback_data=f"repeated:{reminder_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ Пора повторить тему '{topic_name}'! 😺",
            reply_markup=reply_markup
        )
        logger.debug(f"Sent reminder {reminder_id} for topic '{topic_name}' to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending reminder {reminder_id} to user {user_id}: {str(e)}")

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
        user = db.get_user(user_id)
        if not user:
            await query.message.reply_text(
                "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
                reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
            )
            await query.answer()
            return
        topic = db.get_topic(topic_id, user_id, user.timezone)
        if topic:
            try:
                reminders = db.get_reminders(user_id, user.timezone)
                for reminder in reminders:
                    if reminder.topic_id == topic_id:
                        try:
                            scheduler.remove_job(f"reminder_{reminder.reminder_id}_{user_id}")
                            logger.debug(
                                f"Removed scheduled job reminder_{reminder.reminder_id}_{user_id} for topic {topic_id}"
                            )
                        except Exception as e:
                            logger.warning(f"Could not remove job reminder_{reminder.reminder_id}_{user_id}: {e}")
                db.delete_topic(topic_id, user_id)
                await query.message.reply_text(
                    f"Тема '{topic.topic_name}' удалена навсегда! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                await query.message.edit_reply_markup(reply_markup=None)
                context.user_data["state"] = None
                logger.debug(f"User {user_id} permanently deleted topic {topic_id}, keyboard removed")
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
        completed_topic_id = int(data.split("restore:")[1])
        user = db.get_user(user_id)
        if not user:
            await query.message.reply_text(
                "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
                reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
            )
            await query.answer()
            return
        try:
            result = db.restore_topic(completed_topic_id, user_id, user.timezone)
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
                completed_topics = db.get_completed_topics(user_id)
                if completed_topics:
                    keyboard = [
                        [InlineKeyboardButton(topic.topic_name, callback_data=f"restore:{topic.completed_topic_id}")]
                        for topic in completed_topics
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.message.edit_reply_markup(reply_markup=reply_markup)
                    logger.debug(f"Updated keyboard for user {user_id} after restoring topic {topic_id}")
                else:
                    await query.message.edit_reply_markup(reply_markup=None)
                    await query.message.reply_text(
                        "У тебя больше нет завершённых тем для восстановления! 😺",
                        reply_markup=MAIN_KEYBOARD
                    )
                    logger.debug(f"No completed topics left for user {user_id}, removed keyboard")
                context.user_data["state"] = None
            else:
                await query.message.reply_text(
                    "Тема не найдена. 😿 Попробуй снова с помощью 'Восстановить тему'.",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
        except Exception as e:
            logger.error(f"Error restoring completed topic {completed_topic_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при восстановлении темы. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    elif data.startswith("category_progress:"):
        category_id = data.split("category_progress:")[1]
        user = db.get_user(user_id)
        if not user:
            await query.message.reply_text(
                "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
                reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
            )
            await query.answer()
            return
        category_id = None if category_id == "none" else int(category_id)
        await show_category_progress(update, context, category_id, user.timezone)
        await query.answer()
    elif data == "back_to_progress":
        user_id = update.effective_user.id
        categories = db.get_categories(user_id)
        keyboard = [
            [InlineKeyboardButton(category.category_name, callback_data=f"category_progress:{category.category_id}")]
            for category in categories
        ]
        keyboard.append([InlineKeyboardButton("📁 Без категории", callback_data="category_progress:none")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "Выбери категорию для просмотра прогресса:",
            reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_category_progress"
        logger.debug(f"User {user_id} returned to category selection")
        await query.answer()
    elif data.startswith("category_action:"):
        action = data.split("category_action:")[1]
        if action == "create":
            await query.message.reply_text(
                "Напиши название новой категории:",
                reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
            )
            context.user_data["state"] = "awaiting_category_name"
        elif action == "rename":
            categories = db.get_categories(user_id)
            if not categories:
                await query.message.reply_text(
                    "У тебя нет категорий для переименования! 😿 Создай новую с помощью 'Создать категорию'.",
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
            context.user_data["state"] = "awaiting_category_selection"
        elif action == "move":
            user = db.get_user(user_id)
            if not user:
                await query.message.reply_text(
                    "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
                    reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
                )
                await query.answer()
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
                [InlineKeyboardButton(
                    f"{topic.topic_name} ({db.get_category(topic.category_id, user_id).category_name if topic.category_id else 'Без категории'})",
                    callback_data=f"move_topic:{topic.topic_id}"
                )] for topic in topics
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Выбери тему для переноса:", reply_markup=reply_markup
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
            context.user_data["state"] = "awaiting_category_deletion"
    elif data.startswith("rename_category:"):
        category_id = int(data.split("rename_category:")[1])
        context.user_data["rename_category_id"] = category_id
        await query.message.reply_text(
            "Напиши новое название категории:",
            reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
        )
        context.user_data["state"] = "awaiting_category_rename"
    elif data.startswith("delete_category:"):
        category_id = int(data.split("delete_category:")[1])
        user = db.get_user(user_id)
        if not user:
            await query.message.reply_text(
                "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
                reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
            )
            await query.answer()
            return
        try:
            category = db.get_category(category_id, user_id)
            if category:
                topics = db.get_active_topics(user_id, user.timezone, category_id=category_id)
                moved_topics = []
                if topics:
                    for topic in topics:
                        db.move_topic_to_category(topic.topic_id, user_id, None)
                        moved_topics.append(topic.topic_name)
                        logger.debug(f"Moved topic '{topic.topic_name}' to 'Без категории' for user {user_id}")
                db.delete_category(category_id, user_id)
                if moved_topics:
                    topics_list = ", ".join(f"'{topic}'" for topic in moved_topics)
                    await query.message.reply_text(
                        f"Категория '{category.category_name}' удалена! 😺\n"
                        f"Темы {topics_list} перенесены в 'Без категории'.",
                        reply_markup=MAIN_KEYBOARD
                    )
                else:
                    await query.message.reply_text(
                        f"Категория '{category.category_name}' удалена! 😺",
                        reply_markup=MAIN_KEYBOARD
                    )
                context.user_data["state"] = None
            else:
                await query.message.reply_text(
                    "Категория не найдена. 😿 Попробуй снова!", reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
        except Exception as e:
            logger.error(f"Error deleting category {category_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при удалении категории. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    elif data.startswith("create_category_add:"):
        decision = data.split("create_category_add:")[1]
        if decision == "yes":
            user = db.get_user(user_id)
            if not user:
                await query.message.reply_text(
                    "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
                    reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
                )
                await query.answer()
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
                [InlineKeyboardButton(
                    f"{topic.topic_name} ({db.get_category(topic.category_id, user_id).category_name if topic.category_id else 'Без категории'})",
                    callback_data=f"move_topic:{topic.topic_id}"
                )] for topic in topics
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Выбери тему для переноса в новую категорию:", reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_topic_selection_move"
        else:
            await query.message.reply_text(
                "Хорошо, категория создана без тем! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
    elif data.startswith("move_topic:"):
        topic_id = int(data.split("move_topic:")[1])
        context.user_data["move_topic_id"] = topic_id
        categories = db.get_categories(user_id)
        if not categories:
            await query.message.reply_text(
                "У тебя нет категорий для переноса! 😿 Создай новую категорию сначала.",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
            return
        keyboard = [
            [InlineKeyboardButton(category.category_name, callback_data=f"move_to_category:{category.category_id}")]
            for category in categories
        ]
        keyboard.append([InlineKeyboardButton("Без категории", callback_data="move_to_category:none")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Выбери категорию для переноса темы:", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_category_selection_move"
    elif data.startswith("move_to_category:"):
        category_id = data.split("move_to_category:")[1]
        topic_id = context.user_data.get("move_topic_id")
        if not topic_id:
            await query.message.reply_text(
                "Ой, что-то пошло не так. 😔 Попробуй снова с помощью 'Категории' -> 'Перенести тему'.",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
            return
        try:
            user = db.get_user(user_id)
            if not user:
                await query.message.reply_text(
                    "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
                    reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
                )
                await query.answer()
                return
            topic = db.get_topic(topic_id, user_id, user.timezone)
            if topic:
                category_id = None if category_id == "none" else int(category_id)
                db.move_topic_to_category(topic_id, user_id, category_id)
                category_name = db.get_category(category_id, user_id).category_name if category_id else "Без категории"
                await query.message.reply_text(
                    f"Тема '{topic.topic_name}' перенесена в категорию '{category_name}'! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                context.user_data.pop("move_topic_id", None)
            else:
                await query.message.reply_text(
                    "Тема не найдена. 😿 Попробуй снова!", reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
        except Exception as e:
            logger.error(f"Error moving topic {topic_id} to category {category_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при переносе темы. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    elif data.startswith("add_topic_category:"):
        category_id = data.split("add_topic_category:")[1]
        topic_name = context.user_data.get("new_topic_name")
        if not topic_name:
            await query.message.reply_text(
                "Ой, что-то пошло не так. 😔 Попробуй добавить тему заново с помощью 'Добавить тему'.",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
            return
        try:
            user = db.get_user(user_id)
            if not user:
                await query.message.reply_text(
                    "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
                    reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
                )
                await query.answer()
                return
            category_id = None if category_id == "none" else int(category_id)
            topic_id, reminder_id = db.add_topic(user_id, topic_name, user.timezone, category_id=category_id)
            tz = pytz.timezone(user.timezone)
            reminder_time = datetime.now(tz) + timedelta(hours=1)
            scheduler.add_job(
                send_reminder,
                "date",
                run_date=reminder_time,
                args=[context, user_id, topic_name, reminder_id],
                id=f"reminder_{reminder_id}_{user_id}",
                timezone=tz
            )
            logger.debug(f"Scheduled reminder {reminder_id} for topic '{topic_name}' at {reminder_time.isoformat()}")
            category_name = db.get_category(category_id, user_id).category_name if category_id else "Без категории"
            await query.message.reply_text(
                f"Тема '{topic_name}' добавлена в категорию '{category_name}'! 😺 Первое повторение через 1 час.",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
            context.user_data.pop("new_topic_name", None)
            logger.debug(f"User {user_id} added topic '{topic_name}' with reminder {reminder_id}")
        except Exception as e:
            logger.error(f"Error adding topic '{topic_name}' for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при добавлении темы. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
    elif data.startswith("repeated:"):
        reminder_id = int(data.split("repeated:")[1])
        user = db.get_user(user_id)
        if not user:
            await query.message.reply_text(
                "Пожалуйста, сначала выбери часовой пояс с помощью /start или /tz.",
                reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
            )
            await query.answer()
            return
        try:
            topic = db.get_topic_by_reminder_id(reminder_id, user_id, user.timezone)
            if not topic:
                await query.message.reply_text(
                    f"Тема для напоминания не найдена. 😿 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
                await query.answer()
                return
            result = db.mark_topic_repeated(user_id, topic.topic_name, user.timezone)
            if not result:
                logger.error(f"Topic '{topic.topic_name}' not found for user {user_id}")
                await query.message.reply_text(
                    f"Тема '{topic.topic_name}' не найдена. 😿 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
                await query.answer()
                return
            topic_id, completed_repetitions, next_reminder_time, new_reminder_id = result
            topic = db.get_topic(topic_id, user_id, user.timezone)
            if not topic:
                logger.error(f"Topic {topic_id} not found after marking repeated for user {user_id}")
                await query.message.reply_text(
                    f"Тема '{topic.topic_name}' не найдена после обновления. 😿 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
                await query.answer()
                return
            total_repetitions = 6
            progress_percentage = (completed_repetitions / total_repetitions) * 100
            progress_bar = "█" * int(completed_repetitions) + "░" * (total_repetitions - completed_repetitions)
            tz = pytz.timezone(user.timezone)
            if completed_repetitions < total_repetitions:
                next_reminder_str = next_reminder_time.astimezone(tz).strftime("%d.%m.%Y %H:%M")
                if new_reminder_id:
                    scheduler.add_job(
                        send_reminder,
                        "date",
                        run_date=next_reminder_time,
                        args=[context, user_id, topic.topic_name, new_reminder_id],
                        id=f"reminder_{new_reminder_id}_{user_id}",
                        timezone=tz
                    )
                    logger.debug(f"Scheduled new reminder {new_reminder_id} for topic '{topic.topic_name}' at {next_reminder_time.isoformat()}")
                await query.message.reply_text(
                    f"Тема '{topic.topic_name}' отмечена как повторённая! 😺\n"
                    f"Завершено: {completed_repetitions}/{total_repetitions} повторений\n"
                    f"Следующее повторение: {next_reminder_str}\n"
                    f"Прогресс: {progress_bar} {progress_percentage:.1f}%",
                    reply_markup=MAIN_KEYBOARD
                )
            else:
                await query.message.reply_text(
                    f"🎉 Поздравляю, ты полностью освоил тему '{topic.topic_name}'! 🏆\n"
                    f"Завершено: {completed_repetitions}/{total_repetitions} повторений\n"
                    f"Прогресс: {progress_bar} {progress_percentage:.1f}%\n"
                    f"Если захочешь повторить её заново, используй 'Восстановить тему'. 😺",
                    reply_markup=MAIN_KEYBOARD
                )
            await query.message.edit_reply_markup(reply_markup=None)
            await query.answer()
            logger.debug(f"User {user_id} marked topic '{topic.topic_name}' as repeated")
        except Exception as e:
            logger.error(f"Error processing repeated callback for reminder {reminder_id} for user {user_id}: {e}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при отметке повторения. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
            await query.answer()
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

    if context.user_data.get("state") in ["awaiting_category_action", "awaiting_topic_selection_move", "awaiting_category_selection"]:
        context.user_data["state"] = None
        context.user_data.clear()
        logger.debug(f"User {user_id} exited state {context.user_data.get('state')} due to new command")

    if text.startswith("Повторил "):
        logger.debug(f"User {user_id} sent repeat command: {text}")
        topic_name = text[len("Повторил "):].strip()
        try:
            result = db.mark_topic_repeated(user_id, topic_name, user.timezone)
            if not result:
                logger.error(f"Topic '{topic_name}' not found for user {user_id}")
                await update.message.reply_text(
                    f"Тема '{topic_name}' не найдена или уже завершена. 😿 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
                return
            topic_id, completed_repetitions, next_reminder_time, reminder_id = result
            topic = db.get_topic(topic_id, user_id, user.timezone)
            if not topic:
                logger.error(f"Topic {topic_id} not found after marking repeated for user {user_id}")
                await update.message.reply_text(
                    f"Тема '{topic_name}' не найдена после обновления. 😿 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
                return
            total_repetitions = 6
            progress_percentage = (completed_repetitions / total_repetitions) * 100
            progress_bar = "█" * int(completed_repetitions) + "░" * (total_repetitions - completed_repetitions)
            tz = pytz.timezone(user.timezone)
            if completed_repetitions < total_repetitions:
                next_reminder_str = next_reminder_time.strftime("%d.%m.%Y %H:%M")
                if reminder_id:
                    scheduler.add_job(
                        send_reminder,
                        "date",
                        run_date=next_reminder_time,
                        args=[context, user_id, topic_name, reminder_id],
                        id=f"reminder_{reminder_id}_{user_id}",
                        timezone=tz
                    )
                    logger.debug(f"Scheduled new reminder {reminder_id} for topic '{topic_name}' at {next_reminder_time.isoformat()}")
                await update.message.reply_text(
                    f"Тема '{topic_name}' отмечена как повторённая! 😺\n"
                    f"Завершено: {completed_repetitions}/{total_repetitions} повторений\n"
                    f"Следующее повторение: {next_reminder_str}\n"
                    f"Прогресс: {progress_bar} {progress_percentage:.1f}%",
                    reply_markup=MAIN_KEYBOARD
                )
            else:
                await update.message.reply_text(
                    f"🎉 Поздравляю, ты полностью освоил тему '{topic_name}'! 🏆\n"
                    f"Завершено: {completed_repetitions}/{total_repetitions} повторений\n"
                    f"Прогресс: {progress_bar} {progress_percentage:.1f}%\n"
                    f"Если захочешь повторить её заново, используй 'Восстановить тему'. 😺",
                    reply_markup=MAIN_KEYBOARD
                )
            logger.debug(f"User {user_id} marked topic '{topic_name}' as repeated")
        except Exception as e:
            logger.error(f"Error marking topic '{topic_name}' as repeated for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Ой, что-то пошло не так при отметке повторения. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
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
        topics = db.get_active_topics(user_id, user.timezone, category_id='all')
        if not topics:
            await update.message.reply_text(
                "У тебя нет тем для удаления! 😿",
                reply_markup=MAIN_KEYBOARD
            )
            return
        keyboard = [
            [InlineKeyboardButton(
                f"{topic.topic_name} ({db.get_category(topic.category_id, user_id).category_name if topic.category_id else '📁 Без категории'})",
                callback_data=f"delete:{topic.topic_id}"
            )] for topic in topics
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выбери тему для удаления (восстановить будет нельзя):", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_topic_deletion"
        logger.debug(f"User {user_id} prompted to select topic for deletion")
    elif text == "Восстановить тему":
        logger.debug(f"User {user_id} requested to restore topic")
        completed_topics = db.get_completed_topics(user_id)
        if not completed_topics:
            await update.message.reply_text(
                "У тебя нет завершённых тем для восстановления! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            return
        keyboard = [
            [InlineKeyboardButton(topic.topic_name, callback_data=f"restore:{topic.completed_topic_id}")]
            for topic in completed_topics
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выбери завершённую тему для восстановления:", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_topic_restoration"
        logger.debug(f"User {user_id} prompted to select completed topic for restoration")
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

async def send_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int, topic_name: str, reminder_id: int):
    user = db.get_user(user_id)
    if not user:
        logger.warning(f"User {user_id} not found for reminder {reminder_id}")
        return
    try:
        topic = db.get_topic_by_reminder_id(reminder_id, user_id, user.timezone)
        if not topic:
            logger.warning(f"Topic for reminder {reminder_id} not found for user {user_id}")
            return
        keyboard = [[InlineKeyboardButton("Повторил!", callback_data=f"repeated:{reminder_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ Пора повторить тему '{topic_name}'! 😺",
            reply_markup=reply_markup
        )
        logger.debug(f"Sent reminder {reminder_id} for topic '{topic_name}' to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending reminder {reminder_id} to user {user_id}: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_user:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="Ой, что-то пошло не так! 😿 Попробуй снова или используй /reset.",
            reply_markup=MAIN_KEYBOARD
        )

async def init_scheduler(context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    for user in users:
        reminders = db.get_reminders(user.user_id, user.timezone)
        tz = pytz.timezone(user.timezone)
        for reminder in reminders:
            topic = db.get_topic_by_reminder_id(reminder.reminder_id, user.user_id, user.timezone)
            if topic and reminder.scheduled_time > datetime.now(tz):
                scheduler.add_job(
                    send_reminder,
                    "date",
                    run_date=reminder.scheduled_time.astimezone(tz),
                    args=[context, user.user_id, topic.topic_name, reminder.reminder_id],
                    id=f"reminder_{reminder.reminder_id}_{user.user_id}",
                    timezone=tz
                )
                logger.debug(
                    f"Scheduled reminder {reminder.reminder_id} for topic '{topic.topic_name}' "
                    f"for user {user.user_id} at {reminder.scheduled_time.isoformat()}"
                )

async def main():
    try:
        app = Application.builder().token(BOT_TOKEN).build()
    except InvalidToken:
        logger.error("Invalid bot token provided")
        raise

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tz", handle_timezone))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    scheduler.start()
    logger.debug("Scheduler started")

    await init_scheduler(app)
    logger.debug("Initialized scheduler with existing reminders")

    app_runner = web.AppRunner(web.Application())
    await app_runner.setup()
    site = web.TCPSite(app_runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()
    logger.debug(f"Web server started on port {os.getenv('PORT', 8080)}")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.debug("Bot polling started")

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down bot...")
        await app.updater.stop()
        await app.stop()
        await app_runner.cleanup()
        scheduler.shutdown()
        logger.debug("Bot and web server stopped")

if __name__ == "__main__":
    asyncio.run(main())