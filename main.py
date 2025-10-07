import logging.handlers
import os
import re
import signal
import time
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
from dotenv import load_dotenv


def setup_logging():
    """Настройка логирования с фильтрацией лишних сообщений"""

    log_dir = '/var/log/infinite_memory_bot'
    os.makedirs(log_dir, exist_ok=True)

    # Файл с сегодняшней датой
    today = datetime.now().strftime("%d.%m.%Y")
    log_file = os.path.join(log_dir, f'bot_{today}.log')

    # Формат логов
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Файловый обработчик с ротацией
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        encoding='utf-8',
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    file_handler.setLevel(logging.DEBUG)  # Временно для отладки
    console_handler.setLevel(logging.DEBUG)  # Временно для отладки
    root_logger.setLevel(logging.DEBUG)  # Временно для отладки

    # Полная очистка всех существующих обработчиков
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Очистка обработчиков у наших логгеров
    for logger_name in ['__main__', 'sqlalchemy', 'telegram', 'apscheduler', 'aiohttp', 'httpx', 'httpcore']:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    # Добавление наших обработчиков
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Жесткое ограничение уровня для шумных библиотек
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)

    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
    logging.getLogger("telegram.bot").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.updater").setLevel(logging.WARNING)

    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # НАСТРАИВАЕМ HTTPX НА ЛОГИРОВАНИЕ ТОЛЬКО КАЖДЫЕ 60 СЕКУНД
    class ThrottledFilter(logging.Filter):
        def __init__(self):
            super().__init__()
            self.last_log_time = 0
            self.throttle_interval = 60  # 60 секунд

        def filter(self, record):
            current_time = time.time()
            if current_time - self.last_log_time >= self.throttle_interval:
                self.last_log_time = current_time
                return True
            return False

    # Применяем фильтр к httpx и httpcore
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.INFO)  # Включаем обратно
    httpx_logger.addFilter(ThrottledFilter())

    httpcore_logger = logging.getLogger("httpcore")
    httpcore_logger.setLevel(logging.INFO)  # Включаем обратно
    httpcore_logger.addFilter(ThrottledFilter())

    # Наш основной логгер
    logger = logging.getLogger(__name__)

    # Убедимся, что у нашего логгера нет лишних обработчиков
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("=" * 50)
    logger.info(f"Логирование запущено в файл: {log_file}")
    logger.info("SQLAlchemy echo: DISABLED")
    logger.info("httpx/httpcore logging: THROTTLED (60s)")
    logger.info("=" * 50)

    return logger


# Инициализируем логирование
logger = setup_logging()

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

# Лимиты для пользователей
MAX_ACTIVE_TOPICS = 60
MAX_CATEGORIES = 10


def parse_utc_offset(text: str) -> tuple:
    """Преобразует UTC-смещение и возвращает (timezone, display_name)."""
    if not text:
        return None, None

    text = text.strip().replace(" ", "").upper()

    # Убираем 'UTC' если есть
    text = text.replace("UTC", "")

    # Добавляем '+' если его нет и текст состоит из цифр
    if text and text[0] not in ['+', '-'] and text.lstrip('+-').isdigit():
        text = '+' + text

    # Проверяем формат: [+-]число
    match = re.match(r'^([+-])?(\d{1,2})$', text)
    if not match:
        return None, None

    sign, offset_str = match.groups()
    sign = sign or '+'

    try:
        offset = int(sign + offset_str)

        # Проверяем диапазон
        if not -12 <= offset <= 14:
            return None, None

        # Правильная логика для Etc/GMT
        gmt_sign = '-' if offset > 0 else '+'
        gmt_offset = abs(offset)
        timezone = f"Etc/GMT{gmt_sign}{gmt_offset}"

        # Понятное название для пользователя
        display_name = f"UTC{sign}{offset_str}" if offset != 0 else "UTC"

        return timezone, display_name

    except ValueError:
        return None, None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Received /start command from user {update.effective_user.id}")
    user = db.get_user(update.effective_user.id)
    if user:
        await update.message.reply_text(
            f"С возвращением, {update.effective_user.first_name}! 😺\n"
            f"Твой текущий часовой пояс: {user.timezone}\n"
            "Хочешь изменить? Используй /tz\n"
            "Помощь: /help\n\n"
            "Помни: регулярные повторения = знания навсегда! 🚀",
            reply_markup=MAIN_KEYBOARD
        )
    else:
        await update.message.reply_text(
            "🚀 *Добро пожаловать в твоего персонального тренера памяти!*\n\n"

            "💡 *Знаешь ли ты что?*\n"
            "• 90% информации мы забываем за первые 24 часа\n"
            "• Без повторений знания просто \"испаряются\"\n"
            "• Можно учить часами и не запомнить ничего\n\n"

            "🎯 *А теперь хорошие новости:*\n"
            "Есть научный способ запоминать информацию *навсегда*!\n\n"

            "🔬 *Метод интервального повторения:*\n"
            "Я напоминаю повторить в идеальные моменты:\n"
            "• Когда ты вот-вот забудешь\n"
            "• Чтобы закрепить в долговременной памяти\n"
            "• Без лишних усилий с твоей стороны\n\n"

            "📊 *Всего 7 повторений = знание на годы:*\n"
            "1 час → 1 день → 3 дня → 1 неделя → 2 недели → 1 месяц → 3 месяца\n\n"

            "✨ *Что это тебе даёт:*\n"
            "• Запоминаешь в 3 раза эффективнее\n"
            "• Тратишь всего 5-15 минут в день\n"
            "• Знания остаются с тобой навсегда\n"
            "• Учишься без стресса и напряжения\n\n"

            "🎯 *Начни прямо сейчас:*\n"
            "1. Выбери часовой пояс (чтобы напоминания приходили вовремя)\n"
            "2. Добавь первую тему\n"
            "3. Отмечай повторения когда я напоминаю\n"
            "4. Следи как растёт твоя эрудиция!\n\n"

            "⏰ *Выбери свой часовой пояс:*\n"
            "Напиши название (например, 'Europe/Moscow') или смещение (например, 'UTC+3')\n"
            "Или используй /tz для выбора из списка",
            reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True),
            parse_mode="Markdown"
        )
    logger.debug(f"Sent start response to user {update.effective_user.id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"Received /help command from user {user_id}")

    help_text = (
        "🚀 Твой персональный тренер памяти - запоминай навсегда!\n\n"

        "💡 Научный подход к запоминанию:\n"
        "Наш мозг забывает информацию по определённой кривой (кривая Эббингауза). "
        "90% информации забывается за первые 24 часа, если её не повторить!\n\n"

        "🎯 Почему именно такая последовательность?\n"
        "1 час - фиксируем в кратковременной памяти\n"
        "1 день - переносим в среднесрочную память  \n"
        "3 дня - усиливаем нейронные связи\n"
        "1-2 недели - закрепляем в долговременной памяти\n"
        "1-3 месяца - окончательно фиксируем\n\n"

        "📊 Результат: После 7 повторений информация переходит в долговременную память "
        "и остаётся с тобой на годы!\n\n"

        "🔬 Это не просто цифры:\n"
        "Метод интервального повторения научно доказан и используется:\n"
        "• В обучении врачей и пилотов\n"
        "• При изучении иностранных языков\n"
        "• В подготовке к серьёзным экзаменам\n"
        "• Спортсменами для запоминания тактик\n\n"

        "🎯 Что можно учить:\n"
        "• Иностранные слова и фразы\n"
        "• Научные термины и формулы\n"
        "• Исторические даты и факты\n"
        "• Код и алгоритмы\n"
        "• Подготовка к экзаменам\n"
        "• И всё что угодно!\n\n"

        "🛠 Быстрый старт:\n"
        "1. Добавь тему - начни с 2-3 тем\n"
        "2. Отмечай «Повторил!» по напоминаниям\n"
        "3. Следи за прогрессом - смотри как знания закрепляются\n"
        "4. Достигай 100% - получай знания навсегда!\n\n"

        "📋 Основные команды:\n"
        "• Добавить тему - создать новую тему\n"
        "• Мой прогресс - увидеть прогресс\n"
        "• Категории - организовать темы\n"
        "• Восстановить тему - повторить завершённое\n\n"

        "💫 Попробуй всего 1 тему и увидишь как это работает!\n"
        "Через неделю ты удивишься сколько запомнил без усилий.\n\n"

        "🎉 Готов начать? Нажми «Добавить тему» и убедись сам!\n\n"
        "❓ Есть вопросы? Пиши: @garage_pineapple"
    )

    await update.message.reply_text(
        help_text,
        reply_markup=MAIN_KEYBOARD
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

    # Получаем общее количество активных тем для информации о лимите
    all_active_topics = db.get_active_topics(user_id, user.timezone, category_id='all')

    categories = db.get_categories(user_id)
    keyboard = [
        [InlineKeyboardButton(category.category_name, callback_data=f"category_progress:{category.category_id}")]
        for category in categories
    ]
    keyboard.append([InlineKeyboardButton("📁 Без категории", callback_data="category_progress:none")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"📊 Активных тем: {len(all_active_topics)}/{MAX_ACTIVE_TOPICS}\n"
    text += "Выбери категорию для просмотра прогресса:"

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


async def handle_timezone_callback(query, context, parts, user_id):
    timezone = parts[1] if len(parts) > 1 else None
    if timezone == "manual":
        # Устанавливаем состояние ДО отправки сообщения
        context.user_data["state"] = "awaiting_manual_timezone"
        await query.message.reply_text(
            "⌨️ Введи часовой пояс вручную:\n\n"
            "• Название: Europe/Moscow, Asia/Tokyo, America/New_York\n"
            "• Смещение: +3, UTC+3, -5, UTC-5\n"
            "• Или используй /tz list для полного списка"
        )
        logger.debug(f"User {user_id} set state to: awaiting_manual_timezone")
    else:
        try:
            db.save_user(user_id, query.from_user.username or "", timezone)
            schedule_daily_check(user_id, timezone)

            # ВАЖНО: Сбрасываем состояние после успешного сохранения
            context.user_data["state"] = None
            context.user_data.clear()

            await query.message.reply_text(
                f"Часовой пояс {timezone} сохранен! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            logger.info(f"User {user_id} set timezone to {timezone}")
        except Exception as e:
            logger.error(f"Error saving timezone for user {user_id}: {str(e)}")
            await query.message.reply_text(
                "Ой, что-то пошло не так при сохранении часового пояса. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )

    await query.answer()


async def handle_repeated_callback(query, context, parts, user_id, user):
    reminder_id = int(parts[1]) if len(parts) > 1 else None
    if not reminder_id:
        await query.answer("Ошибка: неверный формат команды")
        return

    # Единая проверка существования напоминания и темы
    reminder = db.get_reminder(reminder_id)
    if not reminder:
        await query.answer("Напоминание не найдено. Возможно, тема была удалена. 😿")
        await query.message.delete()
        return

    topic = db.get_topic_by_reminder_id(reminder_id, user_id, user.timezone)
    if not topic:
        await query.answer("Тема не найдена. Возможно, она была удалена. 😿")
        await query.message.delete()
        return

    topic_name = topic.topic_name
    logger.info(f"USER_ACTION: User {user_id} marked topic '{topic_name}' as repeated (reminder_id: {reminder_id})")
    result = db.mark_topic_repeated_by_reminder(reminder_id, user_id, user.timezone)

    if not result:
        await query.answer("Ошибка при отметке повторения. 😔")
        return

    completed_repetitions, next_reminder_time, new_reminder_id = result
    total_repetitions = 7
    progress_percentage = (completed_repetitions / total_repetitions) * 100
    progress_bar = "█" * completed_repetitions + "░" * (total_repetitions - completed_repetitions)

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
    logger.debug(f"User {user_id} marked topic '{topic_name}' as repeated via button")


async def handle_add_topic_category(query, context, parts, user_id, user):
    category_id_str = parts[1] if len(parts) > 1 else None
    category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None
    topic_name = context.user_data.get("new_topic_name")

    if topic_name:
        try:
            topic_id, reminder_id = db.add_topic(user_id, topic_name, user.timezone, category_id)
            tz = pytz.timezone(user.timezone)

            # Логирование успешного добавления темы
            category_name = db.get_category(category_id, user_id).category_name if category_id else "Без категории"
            logger.info(
                f"USER_ACTION: User {user_id} added topic '{topic_name}' to category '{category_name}' (topic_id: {topic_id})")

            # Получаем время напоминания для логирования
            reminder_time = db._from_utc_naive(db.get_reminder(reminder_id).scheduled_time, user.timezone)
            logger.info(
                f"REMINDER_SCHEDULED: Topic '{topic_name}' reminder scheduled for {reminder_time.strftime('%Y-%m-%d %H:%M')} (reminder_id: {reminder_id})")

            scheduler.add_job(
                send_reminder,
                "date",
                run_date=reminder_time,
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
        except Exception as e:
            logger.error(f"Error adding topic '{topic_name}' for user {user_id}: {str(e)}")
            await query.message.delete()
            await query.message.reply_text(
                "Ой, что-то пошло не так при добавлении темы. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )

    context.user_data["state"] = None
    context.user_data.pop("new_topic_name", None)


async def handle_delete_topic(query, context, parts, user_id):
    topic_id = int(parts[1]) if len(parts) > 1 else None

    # Сначала получаем тему для логирования
    user = db.get_user(user_id)
    topic = db.get_topic(topic_id, user_id, user.timezone if user else "UTC")
    topic_name = topic.topic_name if topic else "Unknown"

    # Сначала получаем все напоминания ДО удаления темы
    reminders = db.get_reminders_by_topic(topic_id)

    # Логирование попытки удаления
    logger.info(f"USER_ACTION: User {user_id} attempting to delete topic '{topic_name}' (topic_id: {topic_id})")

    if db.delete_topic(topic_id, user_id):
        # Логирование успешного удаления темы
        logger.info(f"TOPIC_DELETED: User {user_id} successfully deleted topic '{topic_name}' (topic_id: {topic_id})")
        logger.info(f"REMINDER_CLEANUP: Removing {len(reminders)} reminders for deleted topic '{topic_name}'")

        # Удаляем все напоминания этой темы из планировщика
        removed_jobs_count = 0
        for reminder in reminders:
            job_id = f"reminder_{reminder.reminder_id}_{user_id}"
            job = scheduler.get_job(job_id)
            if job:
                job.remove()
                removed_jobs_count += 1
                logger.info(f"REMINDER_REMOVED: Removed scheduled job {job_id} for topic '{topic_name}'")
            else:
                logger.debug(f"REMINDER_NOT_FOUND: Job {job_id} not found in scheduler (maybe already executed)")

        logger.info(f"REMINDER_CLEANUP_COMPLETE: Removed {removed_jobs_count} scheduled jobs for topic '{topic_name}'")

        await query.message.delete()
        await query.message.reply_text(
            "Тема и все связанные напоминания удалены! 😿",
            reply_markup=MAIN_KEYBOARD
        )
        logger.debug(f"User {user_id} deleted topic {topic_id} with all reminders")
    else:
        # Логирование неудачной попытки удаления
        logger.warning(f"TOPIC_DELETE_FAILED: Topic {topic_id} not found for user {user_id}")
        await query.message.delete()
        await query.message.reply_text(
            "Тема не найдена. 😿",
            reply_markup=MAIN_KEYBOARD
        )
    context.user_data["state"] = None


async def handle_restore_topic(query, context, parts, user_id, user):
    completed_topic_id = int(parts[1]) if len(parts) > 1 else None
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


async def handle_category_action(query, context, parts, user_id):
    action = parts[1] if len(parts) > 1 else None

    if action == "create":
        # ПРОВЕРКА ЛИМИТА СРАЗУ ПРИ ВЫБОРЕ "СОЗДАТЬ КАТЕГОРИЮ"
        categories = db.get_categories(user_id)
        if len(categories) >= MAX_CATEGORIES:
            await query.message.reply_text(
                f"❌ Достигнут лимит категорий ({MAX_CATEGORIES})! 😿\n\n"
                f"Чтобы создать новую категорию, сначала удали одну из существующих.\n"
                f"Сейчас у тебя {len(categories)} категорий.",
                reply_markup=MAIN_KEYBOARD
            )
            logger.info(f"LIMIT_REACHED: User {user_id} reached category limit ({len(categories)}/{MAX_CATEGORIES})")
            context.user_data["state"] = None
            return

        context.user_data["state"] = "awaiting_category_name"
        await query.message.reply_text(
            "Напиши название новой категории! 😊",
            reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
        )

        # Логирование начала создания категории
        logger.info(f"USER_ACTION: User {user_id} starting to create new category ({len(categories)}/{MAX_CATEGORIES})")
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
        context.user_data["state"] = "awaiting_category_rename"

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
            "Выбери категорию для удаления (темы перейдут в 'Без категории'):", reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_category_deletion"

    elif action == "move":
        # Получаем пользователя
        user = db.get_user(user_id)
        if not user:
            await query.answer("Пользователь не найден")
            return

        topics = db.get_active_topics(user_id, user.timezone, category_id='all')  # Теперь user доступен
        if not topics:
            await query.message.reply_text(
                "У тебя нет тем для перемещения! 😿",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
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


async def handle_rename_category(query, context, parts, user_id):
    category_id = int(parts[1]) if len(parts) > 1 else None
    context.user_data["rename_category_id"] = category_id
    context.user_data["state"] = "awaiting_new_category_name"
    await query.message.reply_text(
        "Напиши новое название категории! 😊",
        reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
    )


async def handle_delete_category(query, context, parts, user_id):
    category_id = int(parts[1]) if len(parts) > 1 else None

    # Получаем информацию о категории для логирования
    category = db.get_category(category_id, user_id)
    category_name = category.category_name if category else "Unknown"

    # Логирование попытки удаления категории
    logger.info(
        f"USER_ACTION: User {user_id} attempting to delete category '{category_name}' (category_id: {category_id})")

    if db.delete_category(category_id, user_id):
        # Логирование успешного удаления категории
        logger.info(f"CATEGORY_DELETED: User {user_id} successfully deleted category '{category_name}'")
        logger.info(f"CATEGORY_CLEANUP: All topics from category '{category_name}' moved to 'No category'")

        await query.message.reply_text(
            "Категория удалена! Темы перемещены в 'Без категории'. 😺",
            reply_markup=MAIN_KEYBOARD
        )
        logger.debug(f"User {user_id} deleted category {category_id}")
    else:
        # Логирование неудачной попытки
        logger.warning(f"CATEGORY_DELETE_FAILED: Category {category_id} not found for user {user_id}")
        await query.message.reply_text(
            "Категория не найдена. 😿",
            reply_markup=MAIN_KEYBOARD
        )
    context.user_data["state"] = None


async def handle_move_topic(query, context, parts, user_id):
    topic_id = int(parts[1]) if len(parts) > 1 else None
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


async def handle_move_to_category(query, context, parts, user_id):
    category_id_str = parts[1] if len(parts) > 1 else None
    category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None
    topic_id = context.user_data.get("move_topic_id")

    # Получаем информацию для логирования
    user = db.get_user(user_id)
    topic = db.get_topic(topic_id, user_id, user.timezone if user else "UTC")
    topic_name = topic.topic_name if topic else "Unknown"

    old_category_name = db.get_category(topic.category_id,
                                        user_id).category_name if topic and topic.category_id else "Без категории"
    new_category_name = db.get_category(category_id, user_id).category_name if category_id else "Без категории"

    if db.move_topic_to_category(topic_id, user_id, category_id):
        # Логирование перемещения темы
        logger.info(
            f"TOPIC_MOVED: User {user_id} moved topic '{topic_name}' from '{old_category_name}' to '{new_category_name}'")

        await query.message.reply_text(
            f"Тема перемещена в категорию '{new_category_name}'! 😺",
            reply_markup=MAIN_KEYBOARD
        )
        logger.debug(f"User {user_id} moved topic {topic_id} to category {category_id}")
    else:
        logger.warning(f"TOPIC_MOVE_FAILED: Failed to move topic {topic_id} for user {user_id}")
        await query.message.reply_text(
            "Тема или категория не найдена. 😿",
            reply_markup=MAIN_KEYBOARD
        )
    context.user_data["state"] = None
    context.user_data.pop("move_topic_id", None)


async def handle_add_to_new_category(query, context, parts, user_id, user):  # Добавил user
    if len(parts) > 1 and parts[-1] == "no":
        await query.message.reply_text(
            "Категория создана без добавления тем! 😺",
            reply_markup=MAIN_KEYBOARD
        )
        context.user_data.pop("new_category_id", None)
        context.user_data["state"] = None
    elif len(parts) > 2 and parts[-1] == "yes":
        category_id = int(parts[1])
        topics = db.get_active_topics(user_id, user.timezone, category_id='all')
        if not topics:
            await query.message.reply_text(
                "У тебя нет тем для добавления! 😿",
                reply_markup=MAIN_KEYBOARD
            )
            context.user_data["state"] = None
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


async def handle_add_to_category_topic(query, context, parts, user_id):
    topic_id = int(parts[1]) if len(parts) > 1 else None
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


async def show_delete_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    # Получаем пользователя внутри функции
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Пользователь не найден")
        return

    categories = db.get_categories(user_id)
    keyboard = []

    for category in categories:
        topics_in_category = db.get_active_topics(user_id, user.timezone, category.category_id)  # Теперь user доступен
        if topics_in_category:
            keyboard.append([
                InlineKeyboardButton(
                    f"{category.category_name} ({len(topics_in_category)})",
                    callback_data=f"delete_category_select:{category.category_id}"
                )
            ])

    topics_no_category = db.get_active_topics(user_id, user.timezone, category_id=None)  # Теперь user доступен
    if topics_no_category:
        keyboard.append([
            InlineKeyboardButton(
                f"📁 Без категории ({len(topics_no_category)})",
                callback_data="delete_category_select:none"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🔍 Все темы сразу", callback_data="delete_all_topics")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Выбери категорию для удаления тем:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Выбери категорию для удаления тем:",
            reply_markup=reply_markup
        )
    context.user_data["state"] = "awaiting_delete_category"


async def show_restore_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    # Получаем пользователя внутри функции (хотя для completed_topics timezone может и не нужен)
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Пользователь не найден")
        return

    completed_topics = db.get_completed_topics(user_id)

    categories_dict = {}
    no_category_topics = []

    for topic in completed_topics:
        if topic.category_id:
            if topic.category_id not in categories_dict:
                category = db.get_category(topic.category_id, user_id)
                if category:
                    categories_dict[topic.category_id] = {
                        'name': category.category_name,
                        'topics': []
                    }
            categories_dict[topic.category_id]['topics'].append(topic)
        else:
            no_category_topics.append(topic)

    keyboard = []

    for category_id, category_data in categories_dict.items():
        if category_data['topics']:
            keyboard.append([
                InlineKeyboardButton(
                    f"{category_data['name']} ({len(category_data['topics'])})",
                    callback_data=f"restore_category_select:{category_id}"
                )
            ])

    if no_category_topics:
        keyboard.append([
            InlineKeyboardButton(
                f"📁 Без категории ({len(no_category_topics)})",
                callback_data="restore_category_select:none"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🔍 Все темы сразу", callback_data="restore_all_topics")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Выбери категорию для восстановления тем:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Выбери категорию для восстановления тем:",
            reply_markup=reply_markup
        )
    context.user_data["state"] = "awaiting_restore_category"


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await query.answer()
        return

    # Разбиваем data на части для удобства
    parts = data.split(':')
    action = parts[0]

    try:
        if action == "tz":
            await handle_timezone_callback(query, context, parts, user_id)

        elif action == "category_progress":
            category_id_str = parts[1] if len(parts) > 1 else None
            category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None
            await show_category_progress(update, context, category_id, user.timezone)

        elif action == "add_topic_category":
            await handle_add_topic_category(query, context, parts, user_id, user)

        elif action == "delete_category_select":
            category_id_str = parts[1] if len(parts) > 1 else None
            category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None

            topics = db.get_active_topics(user_id, user.timezone, category_id=category_id)
            if not topics:
                await query.answer("В этой категории нет тем для удаления! 😿")
                return

            keyboard = []
            for topic in topics:
                category_name = db.get_category(topic.category_id,
                                                user_id).category_name if topic.category_id else "📁 Без категории"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{topic.topic_name} ({category_name})",
                        callback_data=f"delete:{topic.topic_id}"
                    )
                ])

            keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_delete_categories")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            category_name = db.get_category(category_id, user_id).category_name if category_id else "📁 Без категории"
            await query.message.edit_text(
                f"Выбери тему для удаления из категории '{category_name}':",
                reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_topic_deletion"

        elif action == "delete":
            await handle_delete_topic(query, context, parts, user_id)

        elif action == "restore_category_select":
            category_id_str = parts[1] if len(parts) > 1 else None
            category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None

            completed_topics = db.get_completed_topics(user_id)
            if category_id is not None:
                filtered_topics = [t for t in completed_topics if t.category_id == category_id]
            else:
                filtered_topics = [t for t in completed_topics if t.category_id is None]

            if not filtered_topics:
                await query.answer("В этой категории нет завершённых тем! 😿")
                return

            keyboard = []
            for topic in filtered_topics:
                category_name = db.get_category(topic.category_id,
                                                user_id).category_name if topic.category_id else "📁 Без категории"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{topic.topic_name} ({category_name})",
                        callback_data=f"restore:{topic.completed_topic_id}"
                    )
                ])

            keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_restore_categories")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            category_name = db.get_category(category_id, user_id).category_name if category_id else "📁 Без категории"
            await query.message.edit_text(
                f"Выбери тему для восстановления из категории '{category_name}':",
                reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_topic_restoration"

        elif action == "restore":
            await handle_restore_topic(query, context, parts, user_id, user)

        elif action == "category_action":
            await handle_category_action(query, context, parts, user_id)

        elif action == "rename_category":
            await handle_rename_category(query, context, parts, user_id)

        elif action == "delete_category":
            await handle_delete_category(query, context, parts, user_id)

        elif action == "move_topic":
            await handle_move_topic(query, context, parts, user_id)

        elif action == "move_to_category":
            await handle_move_to_category(query, context, parts, user_id)

        elif action == "add_to_new_category":
            await handle_add_to_new_category(query, context, parts, user_id, user)

        elif action == "add_to_category_topic":
            await handle_add_to_category_topic(query, context, parts, user_id)

        elif action == "repeated":
            await handle_repeated_callback(query, context, parts, user_id, user)

        elif data == "back_to_progress":
            await show_progress(update, context)

        elif data == "back_to_delete_categories":
            await show_delete_categories(update, context, user_id)

        elif data == "back_to_restore_categories":
            await show_restore_categories(update, context, user_id)

        elif data == "delete_all_topics":
            topics = db.get_active_topics(user_id, user.timezone, category_id='all')
            if not topics:
                await query.answer("У тебя нет тем для удаления! 😿")
                return

            limited_topics = topics[:20]
            keyboard = []
            for topic in limited_topics:
                category_name = db.get_category(topic.category_id,
                                                user_id).category_name if topic.category_id else "📁 Без категории"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{topic.topic_name} ({category_name})",
                        callback_data=f"delete:{topic.topic_id}"
                    )
                ])

            if len(topics) > 20:
                keyboard.append(
                    [InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_delete_categories")])
                await query.message.edit_text(
                    f"Слишком много тем для отображения ({len(topics)}). Показаны первые 20. Лучше используй выбор по категориям.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                keyboard.append(
                    [InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_delete_categories")])
                await query.message.edit_text(
                    "Выбери тему для удаления (восстановить будет нельзя):",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            context.user_data["state"] = "awaiting_topic_deletion"

        elif data == "restore_all_topics":
            completed_topics = db.get_completed_topics(user_id)
            if not completed_topics:
                await query.answer("У тебя нет завершённых тем для восстановления! 😿")
                return

            limited_topics = completed_topics[:20]
            keyboard = []
            for topic in limited_topics:
                category_name = db.get_category(topic.category_id,
                                                user_id).category_name if topic.category_id else "📁 Без категории"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{topic.topic_name} ({category_name})",
                        callback_data=f"restore:{topic.completed_topic_id}"
                    )
                ])

            if len(completed_topics) > 20:
                keyboard.append(
                    [InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_restore_categories")])
                await query.message.edit_text(
                    f"Слишком много тем для отображения ({len(completed_topics)}). Показаны первые 20. Лучше используй выбор по категориям.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                keyboard.append(
                    [InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_restore_categories")])
                await query.message.edit_text(
                    "Выбери завершённую тему для восстановления:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            context.user_data["state"] = "awaiting_topic_restoration"

        else:
            logger.warning(f"Unknown callback data: {data} from user {user_id}")
            await query.answer("Неизвестная команда")

    except Exception as e:
        logger.error(f"Error handling callback {data} for user {user_id}: {str(e)}")
        await query.answer("Произошла ошибка. Попробуйте снова.")
        await query.message.reply_text(
            "Ой, что-то пошло не так! 😿 Попробуй снова или используй /reset.",
            reply_markup=MAIN_KEYBOARD
        )

    await query.answer()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user = db.get_user(user_id)

    # ДОБАВЬ ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
    logger.debug(
        f"User {user_id} sent: '{text}', state: {context.user_data.get('state')}, user exists: {user is not None}")

    # ВАЖНОЕ ИСПРАВЛЕНИЕ: Если пользователь уже существует и пытается использовать основное меню,
    # но состояние застряло - принудительно сбрасываем состояние для основных команд
    if user and text in ["Мой прогресс", "Добавить тему", "Удалить тему", "Восстановить тему", "Категории"]:
        if context.user_data.get("state") in ["awaiting_timezone", "awaiting_manual_timezone"]:
            logger.warning(f"Force resetting stuck timezone state for user {user_id}")
            context.user_data["state"] = None
            context.user_data.clear()

    if not user and not text.startswith("/tz"):
        await update.message.reply_text(
            "Пожалуйста, сначала выбери часовой пояс с помощью /tz.",
            reply_markup=ReplyKeyboardMarkup([["/tz"]], resize_keyboard=True)
        )
        return

    state = context.user_data.get("state")

    if state == "awaiting_timezone" or state == "awaiting_manual_timezone":
        logger.debug(f"Processing timezone input: '{text}' for user {user_id}")

        # Пробуем разные варианты парсинга
        timezone_candidate = None
        display_name = None

        # Вариант 1: Пробуем как UTC смещение
        timezone_candidate, display_name = parse_utc_offset(text)
        logger.debug(f"UTC offset parse result: {timezone_candidate}, display: {display_name}")

        # Вариант 2: Если не получилось, пробуем как есть
        if not timezone_candidate:
            timezone_candidate = text
            display_name = text
            logger.debug(f"Trying as direct timezone: {timezone_candidate}")

        # Проверяем валидность часового пояса
        try:
            pytz.timezone(timezone_candidate)

            # Сохраняем часовой пояс
            db.save_user(user_id, update.effective_user.username or "", timezone_candidate)
            schedule_daily_check(user_id, timezone_candidate)

            # ВАЖНО: Сбрасываем состояние после успешного сохранения
            context.user_data["state"] = None
            context.user_data.clear()

            await update.message.reply_text(
                f"✅ Часовой пояс {display_name} сохранен! 😺\n\n"
                f"Теперь можно добавлять темы!",
                reply_markup=MAIN_KEYBOARD
            )

            logger.info(f"User {user_id} successfully set timezone to: {timezone_candidate} (display: {display_name})")

        except pytz.UnknownTimeZoneError:
            logger.warning(f"User {user_id} entered unknown timezone: {text}")
            await update.message.reply_text(
                f"❌ Неизвестный часовой пояс: {text}\n\n"
                "Доступные форматы:\n"
                "• `Europe/Moscow`, `Asia/Tokyo`\n"
                "• `+3`, `UTC+3`, `-5`, `UTC-5`\n"
                "• Используй /tz для выбора из списка",
                reply_markup=MAIN_KEYBOARD
            )
            # Не сбрасываем состояние здесь - даем пользователю попробовать снова

        except Exception as e:
            logger.error(f"Error setting timezone for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "❌ Ошибка при сохранении часового пояса. Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
            # Сбрасываем состояние при других ошибках
            context.user_data["state"] = None

        return

    if state == "awaiting_category_name":
        if text == "Отмена":
            context.user_data["state"] = None
            await update.message.reply_text(
                "Создание категории отменено! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            return

        # Лимит уже проверен при нажатии кнопки "Создать категорию", так что здесь просто создаем
        try:
            category_id = db.add_category(user_id, text)
            keyboard = [
                [InlineKeyboardButton("Да", callback_data=f"add_to_new_category:{category_id}:yes")],
                [InlineKeyboardButton("Нет", callback_data="add_to_new_category:no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Логирование создания категории
            categories = db.get_categories(user_id)
            logger.info(f"USER_ACTION: User {user_id} created category '{text}' ({len(categories)}/{MAX_CATEGORIES})")

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

    if state in ["awaiting_category_action", "awaiting_topic_selection_move", "awaiting_category_selection",
                 "awaiting_add_to_category", "awaiting_topic_add_to_category"]:
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
        logger.info(f"USER_ACTION: User {user_id} attempting to mark topic '{topic_name}' as repeated via text command")
        try:
            result = db.mark_topic_repeated(user_id, topic_name, user.timezone)
            if not result:
                logger.warning(f"TOPIC_NOT_FOUND: User {user_id} tried to mark unknown topic '{topic_name}' as repeated")
                await update.message.reply_text(
                    f"Тема '{topic_name}' не найдена или уже завершена. 😿 Попробуй снова!",
                    reply_markup=MAIN_KEYBOARD
                )
                return
            topic_id, completed_repetitions, next_reminder_time, reminder_id = result
            topic = db.get_topic(topic_id, user_id, user.timezone)
            total_repetitions = 7

            logger.info(f"TOPIC_REPEATED: User {user_id} marked topic '{topic_name}' as repeated via text command")
            logger.info(
                f"TOPIC_PROGRESS: Topic '{topic_name}' - {completed_repetitions}/{total_repetitions} repetitions completed")

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
                    logger.info(
                        f"REMINDER_SCHEDULED: Next reminder for '{topic_name}' scheduled for {next_reminder_str} (reminder_id: {reminder_id})")
                await update.message.reply_text(
                    f"Тема '{topic_name}' отмечена как повторённая! 😺\n"
                    f"Завершено: {completed_repetitions}/{total_repetitions} повторений\n"
                    f"Следующее повторение: {next_reminder_str}\n"
                    f"Прогресс: {progress_bar} {progress_percentage:.1f}%",
                    reply_markup=MAIN_KEYBOARD
                )
            else:
                logger.info(f"TOPIC_COMPLETED: User {user_id} completed topic '{topic_name}' via text command!")
                await update.message.reply_text(
                    f"🎉 Поздравляю, ты полностью освоил тему '{topic_name}'! 🏆\n"
                    f"Завершено: {completed_repetitions}/{total_repetitions} повторений\n"
                    f"Прогресс: {progress_bar} {progress_percentage:.1f}%\n"
                    f"Если захочешь повторить её заново, используй 'Восстановить тему'. 😺",
                    reply_markup=MAIN_KEYBOARD
                )
        except Exception as e:
            logger.error(f"ERROR: Failed to mark topic '{topic_name}' as repeated for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Ой, что-то пошло не так при отметке повторения. 😔 Попробуй снова!",
                reply_markup=MAIN_KEYBOARD
            )
        return

    if text == "Мой прогресс":
        await show_progress(update, context)
        return

    if text == "Добавить тему":
        # ПРОВЕРКА ЛИМИТА СРАЗУ ПРИ НАЖАТИИ КНОПКИ
        active_topics = db.get_active_topics(user_id, user.timezone, category_id='all')
        if len(active_topics) >= MAX_ACTIVE_TOPICS:
            await update.message.reply_text(
                f"❌ Достигнут лимит активных тем ({MAX_ACTIVE_TOPICS})! 😿\n\n"
                f"Чтобы добавить новую тему, сначала заверши или удали одну из существующих.\n"
                f"Сейчас у тебя {len(active_topics)} активных тем.\n\n"
                f"💡 *Совет:* Лучше сосредоточься на качестве, а не количестве!",
                reply_markup=MAIN_KEYBOARD,
                parse_mode="Markdown"
            )
            logger.info(
                f"LIMIT_REACHED: User {user_id} reached topic limit ({len(active_topics)}/{MAX_ACTIVE_TOPICS}) when trying to add topic")
            return

        # Если лимит не достигнут, переходим к вводу названия темы
        context.user_data["state"] = "awaiting_topic_name"
        await update.message.reply_text(
            "Напиши название темы, которую хочешь добавить! 😊",
            reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
        )

        # Логирование начала создания темы
        logger.info(f"USER_ACTION: User {user_id} starting to add new topic ({len(active_topics)}/{MAX_ACTIVE_TOPICS})")
        return

    if text == "Удалить тему":
        await show_delete_categories(update, context, user_id)
        return

    if text == "Восстановить тему":
        await show_restore_categories(update, context, user_id)
        return

    if text == "Категории":
        # ПРОВЕРКА ЛИМИТА ПРИ СОЗДАНИИ КАТЕГОРИИ (если пользователь выберет создание)
        categories = db.get_categories(user_id)

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

        # Добавляем информацию о лимите в сообщение
        limit_info = f"\n\n📁 Категорий: {len(categories)}/{MAX_CATEGORIES}"

        await update.message.reply_text(
            f"Выбери действие с категориями:{limit_info}",
            reply_markup=reply_markup
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

        # Логирование создания темы
        logger.info(f"USER_ACTION: User {user_id} creating topic '{text}'")

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

        # Логирование отправки напоминания
        logger.info(f"REMINDER_SENT: Sending reminder {reminder_id} for topic '{topic_name}' to user {user_id}")

        await bot.send_message(
            chat_id=user_id,
            text=f"⏰ Пора повторить тему '{topic_name}'! 😺",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"REMINDER_ERROR: Failed to send reminder {reminder_id} to user {user_id}: {str(e)}")


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
    logger.info(f"Initializing scheduler for {len(users)} users")

    for i, user in enumerate(users, 1):
        logger.info(f"Processing user {i}/{len(users)}: {user.user_id}")

        reminders = db.get_reminders(user.user_id)
        logger.info(f"User {user.user_id} has {len(reminders)} reminders in database")

        tz = pytz.timezone(user.timezone)
        scheduled_count = 0
        skipped_count = 0

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
                    scheduled_count += 1
                    logger.debug(f"Scheduled reminder {reminder.reminder_id} for topic '{topic.topic_name}'")
                else:
                    skipped_count += 1
                    logger.info(f"REMINDER_SKIPPED: Reminder {reminder.reminder_id} for topic '{topic.topic_name}' is in the past (was: {run_date})")
            else:
                logger.warning(f"ORPHANED_REMINDER: Reminder {reminder.reminder_id} has no associated topic")

        schedule_daily_check(user.user_id, user.timezone)
        await check_overdue_for_user(app, user.user_id)

        logger.info(f"SCHEDULER_STATS: User {user.user_id} - {scheduled_count} reminders scheduled, {skipped_count} skipped (past due)")

    total_jobs = len(scheduler.get_jobs())
    logger.info(f"Scheduler initialization complete. Total jobs: {total_jobs}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    text = "Ой, что-то пошло не так! 😿 Попробуй снова или используй /reset."
    if update and update.effective_message:
        await update.effective_message.reply_text(
            text,
            reply_markup=MAIN_KEYBOARD
        )


async def main():
    global app

    # Прежде всего отключаем дублирование логов
    logging.getLogger('sqlalchemy.engine').propagate = False

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

    logger.info("Keep-awake disabled - running on dedicated server")

    # Graceful shutdown handlers
    shutdown_event = asyncio.Event()

    async def shutdown():
        logger.info("Starting graceful shutdown...")

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