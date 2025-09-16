import logging
import os
import re
import signal
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
from aiohttp.web import get, head
from dotenv import load_dotenv
import tenacity
import aiohttp

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
                schedule_daily_check(user_id, timezone)
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
            schedule_daily_check(user_id, text)
            context.user_data["state"] = None
            return
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
    text = "Выбери категорию для просмотра прогресса:"
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup
        )
    context.user_data["state"] = "awaiting_category_progress"
    logger.debug(f"User {user_id} requested progress, showing category selection")


async def show_category_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: Optional[int],
                                 timezone: str):
    user_id = update.effective_user.id
    logger.debug(f"User {user_id} requested progress for category {category_id}")
    topics = db.get_active_topics(user_id, timezone, category_id=category_id)
    total_repetitions = 7
    category_name = db.get_category(category_id, user_id).category_name if category_id else "📁 Без категории"

    if not topics:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_progress")]])
        text = f"В категории '{category_name}' пока нет тем! 😿"
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup
            )
            await update.callback_query.answer()
        else:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup
            )
        return

    tz = pytz.timezone(timezone)
    now_utc = datetime.utcnow()
    now_local = pytz.utc.localize(now_utc).astimezone(tz)
    message = f"📚 {category_name} ({timezone}) 😺\n\n"
    for topic in topics:
        next_review_local = db._from_utc_naive(topic.next_review, timezone) if topic.next_review else None
        progress_percentage = (topic.completed_repetitions / total_repetitions) * 100
        progress_bar = "█" * int(topic.completed_repetitions) + "░" * (total_repetitions - topic.completed_repetitions)
        if topic.is_completed:
            status = "Завершено"
        elif next_review_local:
            status = next_review_local.strftime('%d.%m.%Y %H:%M') if next_review_local > now_local else "Просрочено"
        else:
            status = "Завершено"
        message += (
            f"📖 {topic.topic_name}\n"
            f"⏰ Следующее: {status}\n"
            f"✅ Прогресс: {progress_bar} {topic.completed_repetitions}/{total_repetitions} ({progress_percentage:.1f}%)\n"
            f"──────────\n"
        )

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_progress")]])
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
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
            await update.callback_query.edit_message_text(
                error_message,
                reply_markup=reply_markup
            )
            await update.callback_query.answer()
        else:
            await update.message.reply_text(
                error_message,
                reply_markup=reply_markup
            )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await query.answer()
        return

    if data.startswith("tz:"):
        timezone = data.split(":", 1)[1]
        if timezone == "manual":
            await query.message.edit_text(
                "Введи часовой пояс вручную (например, 'Europe/Moscow' или 'UTC+8'):",
            )
            context.user_data["state"] = "awaiting_manual_timezone"
        else:
            db.save_user(user_id, update.effective_user.username or "", timezone)
            schedule_daily_check(user_id, timezone)
            await query.message.edit_text(
                f"Часовой пояс {timezone} сохранен! 😺",
                reply_markup=MAIN_KEYBOARD
            )
        await query.answer()
        context.user_data["state"] = None
        return

    if data.startswith("category_progress:"):
        category_id_str = data.split(":", 1)[1]
        category_id = int(category_id_str) if category_id_str != "none" else None
        await show_category_progress(update, context, category_id, user.timezone)
        return

    if data == "back_to_progress":
        await show_progress(update, context)
        await query.answer()
        return

    if data.startswith("add_topic_category:"):
        category_id_str = data.split(":", 1)[1]
        category_id = int(category_id_str) if category_id_str != "none" else None
        topic_name = context.user_data.get("new_topic_name")
        if topic_name:
            try:
                topic_id, reminder_id = db.add_topic(user_id, topic_name, user.timezone, category_id)
                tz = pytz.timezone(user.timezone)
                scheduler.add_job(
                    send_reminder,
                    "date",
                    run_date=db._from_utc_naive(db.get_reminder(reminder_id).scheduled_time, user.timezone),
                    args=[app.bot, user_id, topic_name, reminder_id],
                    id=f"reminder_{reminder_id}_{user_id}",
                    timezone=tz,
                    misfire_grace_time=None
                )
                await query.message.delete()
                await query.message.reply_text(
                    f"Тема '{topic_name}' добавлена! 😺 Первое повторение через 1 час.",
                    reply_markup=MAIN_KEYBOARD
                )
                logger.debug(f"User {user_id} added topic '{topic_name}' with reminder {reminder_id}")
            except Exception as e:
                logger.error(f"Error adding topic '{topic_name}' for user {user_id}: {str(e)}")
                await query.message.delete()
                await query.message.reply_text(
                    "Ой, что-то пошло не так при добавлении темы. 😔 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
        context.user_data["state"] = None
        context.user_data.pop("new_topic_name", None)
        await query.answer()
        return

    if data.startswith("delete:"):
        topic_id = int(data.split(":", 1)[1])
        if db.delete_topic(topic_id, user_id):
            await query.message.delete()
            await query.message.reply_text(
                "Тема удалена навсегда! 😿",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} deleted topic {topic_id}")
        else:
            await query.message.delete()
            await query.message.reply_text(
                "Тема не найдена. 😿",
                reply_markup=MAIN_KEYBOARD
            )
        context.user_data["state"] = None
        await query.answer()
        return

    if data.startswith("restore:"):
        completed_topic_id = int(data.split(":", 1)[1])
        result = db.restore_topic(completed_topic_id, user_id, user.timezone)
        if result:
            topic_id, topic_name = result
            reminder_id = db.get_reminder_by_topic(topic_id).reminder_id
            tz = pytz.timezone(user.timezone)
            scheduler.add_job(
                send_reminder,
                "date",
                run_date=db._from_utc_naive(db.get_reminder(reminder_id).scheduled_time, user.timezone),
                args=[app.bot, user_id, topic_name, reminder_id],
                id=f"reminder_{reminder_id}_{user_id}",
                timezone=tz,
                misfire_grace_time=None
            )
            await query.message.delete()
            await query.message.reply_text(
                f"Тема '{topic_name}' восстановлена! 😺 Первое повторение через 1 час.",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} restored topic {topic_name}")
        else:
            await query.message.delete()
            await query.message.reply_text(
                "Тема не найдена. 😿",
                reply_markup=MAIN_KEYBOARD
            )
        context.user_data["state"] = None
        await query.answer()
        return

    if data.startswith("category_action:"):
        action = data.split(":", 1)[1]
        if action == "create":
            context.user_data["state"] = "awaiting_category_name"
            await query.message.reply_text(
                "Напиши название новой категории! 😊",
                reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
            )
        elif action == "rename":
            categories = db.get_categories(user_id)
            if not categories:
                await query.message.reply_text(
                    "У тебя нет категорий для переименования! 😿",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                await query.answer()
                return
            keyboard = [
                [InlineKeyboardButton(category.category_name, callback_data=f"rename_category:{category.category_id}")]
                for category in categories
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Выбери категорию для переименования:", reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_category_rename"
        elif action == "delete":
            categories = db.get_categories(user_id)
            if not categories:
                await query.message.reply_text(
                    "У тебя нет категорий для удаления! 😿",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                await query.answer()
                return
            keyboard = [
                [InlineKeyboardButton(category.category_name, callback_data=f"delete_category:{category.category_id}")]
                for category in categories
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Выбери категорию для удаления (темы перейдут в 'Без категории'):", reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_category_deletion"
        elif action == "move":
            topics = db.get_active_topics(user_id, user.timezone, category_id='all')
            if not topics:
                await query.message.reply_text(
                    "У тебя нет тем для перемещения! 😿",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                await query.answer()
                return
            keyboard = [
                [InlineKeyboardButton(topic.topic_name, callback_data=f"move_topic:{topic.topic_id}")]
                for topic in topics
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Выбери тему для перемещения:", reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_topic_selection_move"
        await query.answer()
        return

    if data.startswith("rename_category:"):
        category_id = int(data.split(":", 1)[1])
        context.user_data["rename_category_id"] = category_id
        context.user_data["state"] = "awaiting_new_category_name"
        await query.message.reply_text(
            "Напиши новое название категории! 😊",
            reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
        )
        await query.answer()
        return

    if data.startswith("delete_category:"):
        category_id = int(data.split(":", 1)[1])
        if db.delete_category(category_id, user_id):
            await query.message.reply_text(
                "Категория удалена! Темы перемещены в 'Без категории'. 😺",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} deleted category {category_id}")
        else:
            await query.message.reply_text(
                "Категория не найдена. 😿",
                reply_markup=MAIN_KEYBOARD
            )
        context.user_data["state"] = None
        await query.answer()
        return

    if data.startswith("move_topic:"):
        topic_id = int(data.split(":", 1)[1])
        context.user_data["move_topic_id"] = topic_id
        categories = db.get_categories(user_id)
        keyboard = [
            [InlineKeyboardButton(category.category_name, callback_data=f"move_to_category:{category.category_id}")]
            for category in categories
        ]
        keyboard.append([InlineKeyboardButton("Без категории", callback_data="move_to_category:none")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Выбери новую категорию для темы:", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_category_selection"
        await query.answer()
        return

    if data.startswith("move_to_category:"):
        category_id_str = data.split(":", 1)[1]
        category_id = int(category_id_str) if category_id_str != "none" else None
        topic_id = context.user_data.get("move_topic_id")
        if db.move_topic_to_category(topic_id, user_id, category_id):
            category_name = db.get_category(category_id, user_id).category_name if category_id else "Без категории"
            await query.message.reply_text(
                f"Тема перемещена в категорию '{category_name}'! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} moved topic {topic_id} to category {category_id}")
        else:
            await query.message.reply_text(
                "Тема или категория не найдена. 😿",
                reply_markup=MAIN_KEYBOARD
            )
        context.user_data["state"] = None
        context.user_data.pop("move_topic_id", None)
        await query.answer()
        return

    if data.startswith("add_to_new_category:"):
        parts = data.split(":")
        if parts[-1] == "no":
            await query.message.reply_text(
                "Категория создана без добавления тем! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data.pop("new_category_id", None)
            context.user_data["state"] = None
            await query.answer()
            return
        elif parts[-1] == "yes":
            category_id = int(parts[1])
            topics = db.get_active_topics(user_id, user.timezone, category_id='all')
            if not topics:
                await query.message.reply_text(
                    "У тебя нет тем для добавления! 😿",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                await query.answer()
                return
            keyboard = [
                [InlineKeyboardButton(topic.topic_name, callback_data=f"add_to_category_topic:{topic.topic_id}")]
                for topic in topics
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Выбери тему для добавления в новую категорию:", reply_markup=reply_markup
            )
            context.user_data["move_to_category_id"] = category_id
            context.user_data["state"] = "awaiting_topic_add_to_category"
            await query.answer()
            return

    if data.startswith("add_to_category_topic:"):
        topic_id = int(data.split(":", 1)[1])
        category_id = context.user_data.get("move_to_category_id")
        if db.move_topic_to_category(topic_id, user_id, category_id):
            category_name = db.get_category(category_id, user_id).category_name
            await query.message.reply_text(
                f"Тема добавлена в категорию '{category_name}'! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} added topic {topic_id} to category {category_id}")
        else:
            await query.message.reply_text(
                "Ошибка добавления темы. 😿",
                reply_markup=MAIN_KEYBOARD
            )
        context.user_data["state"] = None
        context.user_data.pop("move_to_category_id", None)
        await query.answer()
        return

    if data.startswith("repeated:"):
        reminder_id = int(data.split(":", 1)[1])
        topic = db.get_topic_by_reminder_id(reminder_id, user_id, user.timezone)
        if not topic:
            await query.answer("Тема не найдена. 😿")
            return
        topic_name = topic.topic_name
        result = db.mark_topic_repeated_by_reminder(reminder_id, user_id, user.timezone)
        if not result:
            await query.answer("Ошибка при отметке повторения. 😔")
            return
        completed_repetitions, next_reminder_time, new_reminder_id = result
        total_repetitions = 7
        progress_percentage = (completed_repetitions / total_repetitions) * 100
        progress_bar = "█" * int(completed_repetitions) + "░" * (total_repetitions - completed_repetitions)
        tz = pytz.timezone(user.timezone)
        message = ""
        if completed_repetitions < total_repetitions:
            next_reminder_str = db._from_utc_naive(next_reminder_time, user.timezone).strftime("%d.%m.%Y %H:%M")
            if new_reminder_id:
                scheduler.add_job(
                    send_reminder,
                    "date",
                    run_date=db._from_utc_naive(next_reminder_time, user.timezone),
                    args=[app.bot, user_id, topic_name, new_reminder_id],
                    id=f"reminder_{new_reminder_id}_{user_id}",
                    timezone=tz,
                    misfire_grace_time=None
                )
            message = (
                f"Тема '{topic_name}' отмечена как повторённая! 😺\n"
                f"Завершено: {completed_repetitions}/{total_repetitions} повторений\n"
                f"Следующее повторение: {next_reminder_str}\n"
                f"Прогресс: {progress_bar} {progress_percentage:.1f}%"
            )
        else:
            message = (
                f"🎉 Поздравляю, ты полностью освоил тему '{topic_name}'! 🏆\n"
                f"Завершено: {completed_repetitions}/{total_repetitions} повторений\n"
                f"Прогресс: {progress_bar} {progress_percentage:.1f}%\n"
                f"Если захочешь повторить её заново, используй 'Восстановить тему'. 😺"
            )
        await query.message.delete()
        await query.message.reply_text(
            message,
            reply_markup=MAIN_KEYBOARD
        )
        await query.answer()
        logger.debug(f"User {user_id} marked topic '{topic_name}' as repeated via button")
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user = db.get_user(user_id)
    if not user and not text.startswith("/tz"):
        await update.message.reply_text(
            "Пожалуйста, сначала выбери часовой пояс с помощью /tz.",
            reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
        )
        return

    state = context.user_data.get("state")

    if state == "awaiting_timezone" or state == "awaiting_manual_timezone":
        timezone = parse_utc_offset(text)
        if timezone:
            try:
                pytz.timezone(timezone)
                db.save_user(user_id, update.effective_user.username or "", timezone)
                schedule_daily_check(user_id, timezone)
                await update.message.reply_text(
                    f"Часовой пояс {timezone} сохранен! 😺",
                    reply_markup=MAIN_KEYBOARD
                )
                context.user_data["state"] = None
                return
            except Exception as e:
                logger.error(f"Error validating timezone {timezone}: {str(e)}")
        try:
            pytz.timezone(text)
            db.save_user(user_id, update.effective_user.username or "", text)
            schedule_daily_check(user_id, text)
            await update.message.reply_text(
                f"Часовой пояс {text} сохранен! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
            return
        except Exception as e:
            logger.error(f"Error validating timezone {text}: {str(e)}")
            await update.message.reply_text(
                "Ой, что-то не так с часовым поясом. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
        return

    if state == "awaiting_category_name":
        if text == "Отмена":
            context.user_data["state"] = None
            await update.message.reply_text(
                "Создание категории отменено! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            return
        try:
            category_id = db.add_category(user_id, text)
            keyboard = [
                [InlineKeyboardButton("Да", callback_data=f"add_to_new_category:{category_id}:yes")],
                [InlineKeyboardButton("Нет", callback_data="add_to_new_category:no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"Категория '{text}' создана! 😺 Добавить в неё темы?",
                reply_markup=reply_markup
            )
            context.user_data["new_category_id"] = category_id
            context.user_data["state"] = "awaiting_add_to_category"
        except Exception as e:
            logger.error(f"Error creating category '{text}' for user {user_id}: {e}")
            await update.message.reply_text(
                "Ой, что-то пошло не так при создании категории. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
        return

    if state == "awaiting_new_category_name":
        if text == "Отмена":
            context.user_data["state"] = None
            await update.message.reply_text(
                "Переименование категории отменено! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            return
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

    if state in ["awaiting_category_action", "awaiting_topic_selection_move", "awaiting_category_selection", "awaiting_add_to_category", "awaiting_topic_add_to_category"]:
        context.user_data["state"] = None
        context.user_data.clear()
        await update.message.reply_text(
            "Действие отменено! 😺",
            reply_markup=MAIN_KEYBOARD
        )
        logger.debug(f"User {user_id} exited state {state} due to new command")
        return

    if text.startswith("Повторил "):
        topic_name = text[len("Повторил "):].strip()
        try:
            result = db.mark_topic_repeated(user_id, topic_name, user.timezone)
            if not result:
                await update.message.reply_text(
                    f"Тема '{topic_name}' не найдена или уже завершена. 😿 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
                return
            topic_id, completed_repetitions, next_reminder_time, reminder_id = result
            topic = db.get_topic(topic_id, user_id, user.timezone)
            total_repetitions = 7
            progress_percentage = (completed_repetitions / total_repetitions) * 100
            progress_bar = "█" * int(completed_repetitions) + "░" * (total_repetitions - completed_repetitions)
            tz = pytz.timezone(user.timezone)
            if completed_repetitions < total_repetitions:
                next_reminder_str = db._from_utc_naive(next_reminder_time, user.timezone).strftime("%d.%m.%Y %H:%M")
                if reminder_id:
                    scheduler.add_job(
                        send_reminder,
                        "date",
                        run_date=db._from_utc_naive(next_reminder_time, user.timezone),
                        args=[app.bot, user_id, topic_name, reminder_id],
                        id=f"reminder_{reminder_id}_{user_id}",
                        timezone=tz,
                        misfire_grace_time=None
                    )
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
        except Exception as e:
            logger.error(f"Error marking topic '{topic_name}' as repeated for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Ой, что-то пошло не так при отметке повторения. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
        return

    if text == "Мой прогресс":
        await show_progress(update, context)
        return

    if text == "Добавить тему":
        context.user_data["state"] = "awaiting_topic_name"
        await update.message.reply_text(
            "Напиши название темы, которую хочешь добавить! 😊",
            reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
        )
        return

    if text == "Удалить тему":
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
        return

    if text == "Восстановить тему":
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
        return

    if text == "Категории":
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
        return

    if text == "Отмена":
        context.user_data["state"] = None
        context.user_data.clear()
        await update.message.reply_text(
            "Действие отменено! 😺",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if state == "awaiting_topic_name":
        if text == "Отмена":
            context.user_data["state"] = None
            context.user_data.clear()
            await update.message.reply_text(
                "Действие отменено! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            return
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
        return

    await update.message.reply_text(
        "Неизвестная команда. 😿",
        reply_markup=MAIN_KEYBOARD
    )

async def send_reminder(bot, user_id: int, topic_name: str, reminder_id: int):
    try:
        keyboard = [[InlineKeyboardButton("Повторил!", callback_data=f"repeated:{reminder_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            chat_id=user_id,
            text=f"⏰ Пора повторить тему '{topic_name}'! 😺",
            reply_markup=reply_markup
        )
        logger.debug(f"Sent reminder {reminder_id} for topic '{topic_name}' to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending reminder {reminder_id} to user {user_id}: {str(e)}")

async def check_overdue_for_user(app: Application, user_id: int):
    user = db.get_user(user_id)
    if not user:
        return
    tz = pytz.timezone(user.timezone)
    now_utc = datetime.utcnow()
    now_local = pytz.utc.localize(now_utc).astimezone(tz)
    topics = db.get_active_topics(user_id, user.timezone, 'all')
    for topic in topics:
        if topic.next_review is None or topic.is_completed:
            continue
        next_review_utc = topic.next_review  # utc naive
        next_review_local = db._from_utc_naive(next_review_utc, user.timezone)
        if next_review_local < now_local:
            # Create temporary reminder for button
            reminder_id = db.add_reminder(user_id, topic.topic_id, now_utc)
            keyboard = [[InlineKeyboardButton("Повторил!", callback_data=f"repeated:{reminder_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await app.bot.send_message(
                chat_id=user_id,
                text=f"⏰ Просроченное напоминание! Пора повторить тему '{topic.topic_name}'! 😺",
                reply_markup=reply_markup
            )
            logger.debug(f"Sent overdue reminder for topic '{topic.topic_name}' to user {user_id}")

def schedule_daily_check(user_id: int, timezone: str):
    job_id = f"daily_check_{user_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        check_overdue_for_user,
        'cron',
        hour=9,
        minute=0,
        timezone=timezone,
        args=[app, user_id],  # app will be defined in main
        id=job_id
    )
    logger.debug(f"Scheduled daily check for user {user_id} at 9:00 {timezone}")

async def init_scheduler(app: Application):
    users = db.get_all_users()
    for user in users:
        reminders = db.get_reminders(user.user_id)
        tz = pytz.timezone(user.timezone)
        for reminder in reminders:
            topic = db.get_topic_by_reminder_id(reminder.reminder_id, user.user_id, user.timezone)
            if topic:
                run_date = db._from_utc_naive(reminder.scheduled_time, user.timezone)
                if run_date > datetime.now(tz):
                    scheduler.add_job(
                        send_reminder,
                        "date",
                        run_date=run_date,
                        args=[app.bot, user.user_id, topic.topic_name, reminder.reminder_id],
                        id=f"reminder_{reminder.reminder_id}_{user.user_id}",
                        timezone=tz,
                        misfire_grace_time=None
                    )
                    logger.debug(
                        f"Scheduled reminder {reminder.reminder_id} for topic '{topic.topic_name}' "
                        f"for user {user.user_id} at {run_date.isoformat()}"
                    )
        schedule_daily_check(user.user_id, user.timezone)
        await check_overdue_for_user(app, user.user_id)  # Check overdue at startup

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    text = "Ой, что-то пошло не так! 😿 Попробуй снова или используй /reset."
    if update and update.effective_message:
        await update.effective_message.reply_text(
            text,
            reply_markup=MAIN_KEYBOARD
        )


async def keep_awake():
    domain = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not domain:
        logger.warning("RENDER_EXTERNAL_HOSTNAME not set, keep-awake disabled")
        return

    url = f"https://{domain}/health"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url, timeout=10) as resp:
                    logger.debug(f"Keep-awake ping: {resp.status}")
            except Exception as e:
                logger.error(f"Keep-awake error: {e}")
            await asyncio.sleep(300)  # 5 минут вместо 10


async def main():
    global app

    # Уменьшаем логирование для некоторых библиотек
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    logger.info("Starting bot initialization...")

    try:
        app = Application.builder().token(BOT_TOKEN).build()
        logger.info("Bot application created successfully")
    except InvalidToken:
        logger.error("Invalid bot token provided")
        raise
    except Exception as e:
        logger.error(f"Failed to create bot application: {e}")
        raise

    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tz", handle_timezone))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    # Запускаем планировщик
    try:
        scheduler.start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise

    # Инициализируем планировщик с существующими напоминаниями
    try:
        await init_scheduler(app)
        logger.info("Scheduler initialized with existing reminders")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")
        # Не прерываем выполнение, продолжаем без напоминаний

    # Настраиваем web server для health checks
    try:
        web_app = web.Application()
        web_app.add_routes([web.get('/health', health_check)])
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
        await site.start()
        logger.info(f"Web server started on port {os.getenv('PORT', 8080)}")
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")
        # Не прерываем выполнение, бот может работать без web сервера

    # Запускаем keep-awake задачу (только если есть домен)
    keep_awake_task = None
    if os.getenv("RENDER_EXTERNAL_HOSTNAME"):
        keep_awake_task = asyncio.create_task(keep_awake())
        logger.info("Keep-awake task started")
    else:
        logger.warning("RENDER_EXTERNAL_HOSTNAME not set, keep-awake disabled")

    # Graceful shutdown handlers
    shutdown_event = asyncio.Event()

    async def shutdown():
        logger.info("Starting graceful shutdown...")

        # Отменяем keep-awake задачу
        if keep_awake_task and not keep_awake_task.done():
            keep_awake_task.cancel()
            try:
                await keep_awake_task
            except asyncio.CancelledError:
                logger.info("Keep-awake task cancelled")

        # Останавливаем бота
        try:
            await app.updater.stop()
            await app.stop()
            logger.info("Bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

        # Останавливаем планировщик
        try:
            scheduler.shutdown()
            logger.info("Scheduler shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")

        # Останавливаем web server
        try:
            await runner.cleanup()
            logger.info("Web server stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping web server: {e}")

        logger.info("Shutdown complete")
        shutdown_event.set()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(shutdown())

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Инициализируем и запускаем бота
    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        logger.info("Bot polling started successfully")

        # Основной цикл - просто ждем события завершения
        logger.info("Bot is now running and waiting for messages...")
        await shutdown_event.wait()

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        await shutdown()
        raise

    finally:
        # Гарантируем cleanup даже при ошибках
        if not shutdown_event.is_set():
            await shutdown()


if __name__ == "__main__":
    # Устанавливаем обработчик для asyncio исключений
    def handle_exception(loop, context):
        logger.error(f"AsyncIO exception: {context}")


    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(handle_exception)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Main loop error: {e}")
    finally:
        loop.close()
        logger.info("Event loop closed")