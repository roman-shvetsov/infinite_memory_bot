import logging.handlers
import os
import re
import signal
import time
from typing import Optional
from translations import get_text, get_main_keyboard, get_kex_message, TRANSLATIONS, get_streak_emoji
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from telegram.error import TimedOut, NetworkError
import random
from telegram.error import InvalidToken
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import Database, UserReactivation
import asyncio
from dotenv import load_dotenv


def get_day_word(days: int, language: str = 'ru') -> str:
    """Возвращает правильно склоненное слово 'день/дня/дней' или эквивалент на других языках"""
    if language == 'ru':
        if days % 10 == 1 and days % 100 != 11:
            return "день"
        elif 2 <= days % 10 <= 4 and not (12 <= days % 100 <= 14):
            return "дня"
        else:
            return "дней"
    elif language == 'en':
        return "day" if days == 1 else "days"
    elif language == 'es':
        return "día" if days == 1 else "días"
    elif language == 'de':
        return "Tag" if days == 1 else "Tage"
    elif language == 'fr':
        return "jour" if days == 1 else "jours"
    elif language == 'zh':
        return "天"  # В китайском не склоняется
    else:
        return "days"  # fallback


def setup_logging():
    """Настройка логирования с автоматической ротацией по дням в МОСКОВСКОМ времени"""

    log_dir = '/var/log/infinite_memory_bot'
    os.makedirs(log_dir, exist_ok=True)

    # Базовое имя файла (без даты)
    log_file = os.path.join(log_dir, 'bot.log')

    # Формат логов
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Таймированная ротация - каждый день в полночь ПО МОСКОВСКОМУ ВРЕМЕНИ
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',  # Ротация в полночь
        interval=1,  # Каждый день
        backupCount=7,  # Хранить 7 дней логов
        encoding='utf-8',
        utc=False  # НЕ использовать UTC - использовать системное время
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    file_handler.suffix = "%d.%m.%Y.log"  # Формат суффикса для backup файлов

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    file_handler.setLevel(logging.DEBUG)
    console_handler.setLevel(logging.DEBUG)
    root_logger.setLevel(logging.DEBUG)

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
    httpx_logger.setLevel(logging.INFO)
    httpx_logger.addFilter(ThrottledFilter())

    httpcore_logger = logging.getLogger("httpcore")
    httpcore_logger.setLevel(logging.INFO)
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
    logger.info("Автоматическая ротация: каждый день в полночь по МОСКОВСКОМУ времени")
    logger.info("Храним логи за 7 дней")
    logger.info("SQLAlchemy echo: DISABLED")
    logger.info("httpx/httpcore logging: THROTTLED (60s)")
    logger.info("Кодировка: UTF-8")
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

# Создаем папку для изображений если ее нет
os.makedirs("images", exist_ok=True)
logger.info(f"Images directory: {os.path.abspath('images')}")

# Лимиты для пользователей
MAX_ACTIVE_TOPICS = 100
MAX_CATEGORIES = 10


# ВРЕМЕННО ДЛЯ ТЕСТИРОВАНИЯ - уменьшаем сроки реактивации
REACTIVATION_STAGES_TEST = [
    (0.02, 1),   # через ~30 минут
    (0.04, 2),   # через ~1 час
    (0.06, 3),   # через ~1.5 часа
    (0.08, 4)    # через ~2 часа
]

REACTIVATION_STAGES_PROD = [
    (3, 1),   # через 3 дня - friendly
    (7, 2),   # через 7 дней - sad
    (14, 3),  # через 14 дней - angry
    (30, 4)   # через 30 дней - final
]

# Переменная для переключения между тестовым и продакшен режимом
TEST_MODE = False  # Поставьте False когда закончите тестирование

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
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if user:
        language_name = get_text('russian', user.language) if user.language == 'ru' else get_text('english', user.language)
        await update.message.reply_text(
            get_text('welcome_back_extended', user.language,
                     name=update.effective_user.first_name,
                     timezone=user.timezone,
                     language=language_name),
            reply_markup=get_main_keyboard(user.language)
        )
    else:
        # Новый пользователь - предлагаем выбрать язык
        keyboard = [
            [
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
                InlineKeyboardButton("🇪🇸 Español", callback_data="lang:es"),
            ],
            [
                InlineKeyboardButton("🇨🇳 中文", callback_data="lang:zh"),
                InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang:de"),
                InlineKeyboardButton("🇫🇷 Français", callback_data="lang:fr"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            get_text('welcome_new', 'ru'),  # По умолчанию на русском для выбора языка
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        # Сохраняем пользователя с временными значениями
        db.save_user(user_id, update.effective_user.username or "", "UTC", "ru")
        context.user_data["state"] = "awaiting_language"

    logger.debug(f"Sent start response to user {update.effective_user.id}")


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    current_lang = user.language if user else 'ru'

    # ОБНОВЛЕННАЯ КЛАВИАТУРА СО ВСЕМИ ЯЗЫКАМИ
    keyboard = [
        [
            InlineKeyboardButton(f"🇷🇺 Русский {'✅' if current_lang == 'ru' else ''}", callback_data="change_lang:ru"),
            InlineKeyboardButton(f"🇬🇧 English {'✅' if current_lang == 'en' else ''}", callback_data="change_lang:en"),
            InlineKeyboardButton(f"🇪🇸 Español {'✅' if current_lang == 'es' else ''}", callback_data="change_lang:es"),
        ],
        [
            InlineKeyboardButton(f"🇨🇳 中文 {'✅' if current_lang == 'zh' else ''}", callback_data="change_lang:zh"),
            InlineKeyboardButton(f"🇩🇪 Deutsch {'✅' if current_lang == 'de' else ''}", callback_data="change_lang:de"),
            InlineKeyboardButton(f"🇫🇷 Français {'✅' if current_lang == 'fr' else ''}", callback_data="change_lang:fr"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        get_text('choose_language', current_lang),
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"Received /help command from user {user_id}")

    # Получаем язык пользователя
    user = db.get_user(user_id)
    language = user.language if user else 'ru'

    # Используем get_text для получения текста помощи
    help_text = get_text('help_text', language)

    await update.message.reply_text(
        help_text,
        reply_markup=get_main_keyboard(language)  # Используем правильную клавиатуру
    )
    logger.debug(f"Sent help response to user {user_id}")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data["state"] = None
    context.user_data.clear()

    # ПОЛУЧАЕМ ПОЛЬЗОВАТЕЛЯ ИЗ БАЗЫ
    user = db.get_user(user_id)
    language = user.language if user else 'ru'

    await update.message.reply_text(
        get_text('reset_state', language),
        reply_markup=get_main_keyboard(language)  # Используем правильную клавиатуру
    )
    logger.debug(f"User {user_id} reset state")


async def perf_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тест производительности инициализации"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested performance test")

    try:
        message = await update.message.reply_text("🔄 Запускаю тест производительности...")

        # ЗАПОМИНАЕМ текущие задания
        jobs_before = len(scheduler.get_jobs())

        # Замеряем время
        start_time = time.time()

        # УДАЛЯЕМ все существующие задания перед тестом
        for job in scheduler.get_jobs():
            job.remove()
        logger.info(f"Removed {jobs_before} existing jobs before test")

        # Тестируем оптимизированную инициализацию
        scheduled, overdue = await init_scheduler_optimized(app)

        elapsed_time = time.time() - start_time

        # Получаем статистику
        total_users = len(db.get_all_users())

        # Считаем темы более эффективно
        total_topics = 0
        users = db.get_all_users()
        for user in users:
            topics = db.get_active_topics(user.user_id, user.timezone, category_id='all')
            total_topics += len(topics)

        total_jobs = len(scheduler.get_jobs())

        result_text = (
            f"✅ Тест производительности завершен!\n\n"
            f"📊 **Статистика:**\n"
            f"• Пользователей: {total_users}\n"
            f"• Активных тем: {total_topics}\n"
            f"• Запланировано: {scheduled}\n"
            f"• Просрочено: {overdue}\n"
            f"• Всего заданий: {total_jobs}\n\n"
            f"⏱ **Время выполнения:** {elapsed_time:.2f} секунд\n\n"
        )

        # Оценка производительности
        if elapsed_time < 1:
            result_text += "⚡ **Быстрее молнии!** Идеальная производительность!"
        elif elapsed_time < 3:
            result_text += "⚡ **Отлично!** Система готова к масштабированию."
        elif elapsed_time < 10:
            result_text += "👍 **Хорошо!** Производительность приемлемая."
        else:
            result_text += "⚠️ **Требует оптимизации!** При увеличении пользователей будут проблемы."

        await message.edit_text(result_text)

    except Exception as e:
        logger.error(f"Error in perf_test: {str(e)}")
        try:
            await update.message.reply_text(f"❌ Ошибка при тестировании: {str(e)}")
        except:
            pass


async def handle_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.split(maxsplit=1)[1] if len(update.message.text.split()) > 1 else None
    logger.debug(f"User {user_id} sent timezone command: {text}")

    # ПОЛУЧАЕМ ПОЛЬЗОВАТЕЛЯ СРАЗУ
    user = db.get_user(user_id)
    language = user.language if user else 'ru'  # Язык по умолчанию

    if text == "list":
        await update.message.reply_text(
            get_text('timezone_list_info', language),
            reply_markup=get_main_keyboard(language)  # Используем правильную клавиатуру
        )
        return

    if text:
        timezone = parse_utc_offset(text)
        if timezone:
            try:
                pytz.timezone(timezone)
                db.save_user(user_id, update.effective_user.username or "", timezone, language)
                logger.debug(f"User {user_id} saved with timezone {timezone} (from UTC offset {text})")
                await update.message.reply_text(
                    get_text('timezone_saved_with_offset', language, timezone=timezone, offset=text),
                    reply_markup=get_main_keyboard(language)
                )
                schedule_daily_check(user_id, timezone)
                context.user_data["state"] = None
                return
            except Exception as e:
                logger.error(f"Error validating UTC timezone {timezone}: {str(e)}")
        try:
            pytz.timezone(text)
            db.save_user(user_id, update.effective_user.username or "", text, language)
            logger.debug(f"User {user_id} saved with timezone {text}")
            await update.message.reply_text(
                get_text('timezone_saved_simple', language, timezone=text),
                reply_markup=get_main_keyboard(language)
            )
            schedule_daily_check(user_id, text)
            context.user_data["state"] = None
            return
        except Exception as e:
            logger.error(f"Error saving user timezone: {str(e)}")
            await update.message.reply_text(
                get_text('timezone_error', language),
                reply_markup=get_main_keyboard(language)
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
        [InlineKeyboardButton(get_text('other_manual_button', language), callback_data="tz:manual")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        get_text('choose_timezone', language),
        reply_markup=reply_markup
    )
    context.user_data["state"] = "awaiting_timezone"
    logger.debug(f"User {user_id} prompted to select timezone")


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, language: str = 'ru'):
    user_id = update.effective_user.id
    db.update_user_activity(user_id)
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text(
            get_text('need_timezone', language),
            reply_markup=ReplyKeyboardMarkup([[get_text('tz_button', language)]], resize_keyboard=True)
        )
        return

    # Получаем стрик пользователя
    current_streak, longest_streak = db.get_streak(user_id)

    # Получаем смайлик для стрика
    streak_emoji = get_streak_emoji(current_streak)

    # Получаем правильно склоненные слова для дней
    current_days_word = get_day_word(current_streak, language)
    longest_days_word = get_day_word(longest_streak, language)

    # Получаем общее количество активных тем
    all_active_topics = db.get_active_topics(user_id, user.timezone, category_id='all')

    categories = db.get_categories(user_id)
    keyboard = [
        [InlineKeyboardButton(category.category_name, callback_data=f"category_progress:{category.category_id}")]
        for category in categories
    ]
    keyboard.append([InlineKeyboardButton(get_text('no_category', language), callback_data="category_progress:none")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Собираем текст с информацией о стрике
    streak_text = get_text('streak_info', language,
                           days=current_streak,
                           days_word=current_days_word,
                           emoji=streak_emoji,
                           longest=longest_streak,
                           longest_word=longest_days_word)

    if not streak_text:
        # Fallback если перевод не найден
        streak_text = f"🔥 Ударный режим: {current_streak} {current_days_word} {streak_emoji}\n"
        if longest_streak > current_streak:
            streak_text += f"🏆 Лучший результат: {longest_streak} {longest_days_word}\n"

    # Текст с активными темами
    topics_text = get_text('active_topics_count', language,
                           current=len(all_active_topics),
                           max=MAX_ACTIVE_TOPICS)

    if not topics_text:
        topics_text = f"📊 Активных тем: {len(all_active_topics)}/{MAX_ACTIVE_TOPICS}\n"

    select_text = get_text('select_category_for_progress', language)
    if not select_text:
        select_text = "Выбери категорию для просмотра прогресса:"

    text = f"{streak_text}\n{topics_text}\n{select_text}"

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
    logger.debug(f"User {user_id} requested progress, streak: {current_streak} {current_days_word}")


async def show_category_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: Optional[int],
                                 timezone: str, language: str = 'ru'):

    user_id = update.effective_user.id
    logger.debug(f"User {user_id} requested progress for category {category_id}")
    topics = db.get_active_topics(user_id, timezone, category_id=category_id)
    total_repetitions = 7
    category_name = db.get_category(category_id, user_id).category_name if category_id else get_text('no_category_with_icon', language)

    if not topics:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_progress")]])
        text = get_text('no_topics_in_category_msg', language, category_name=category_name)

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
    message = get_text('progress_header', language, category_name=category_name, timezone=timezone)

    for topic in topics:
        next_review_local = db._from_utc_naive(topic.next_review, timezone) if topic.next_review else None
        progress_percentage = (topic.completed_repetitions / total_repetitions) * 100
        progress_bar = "█" * int(topic.completed_repetitions) + "░" * (total_repetitions - topic.completed_repetitions)
        if topic.is_completed:
            status = get_text('status_completed', language)
        elif next_review_local:
            status = next_review_local.strftime('%d.%m.%Y %H:%M') if next_review_local > now_local else get_text(
                'status_overdue', language)
        else:
            status = get_text('status_completed', language)
        message += (
            f"📖 {topic.topic_name}\n"
            f"⏰ Следующее: {status}\n"
            f"✅ Прогресс: {progress_bar} {topic.completed_repetitions}/{total_repetitions} ({progress_percentage:.1f}%)\n"
            f"──────────\n"
        )

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back', language), callback_data="back_to_progress")]])
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
        error_message = get_text('progress_error', language)
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
    user = db.get_user(user_id)
    language = user.language if user else 'ru'

    if timezone == "manual":
        context.user_data["state"] = "awaiting_manual_timezone"
        await query.message.reply_text(
            get_text('enter_timezone_manual', language)
        )
    else:
        try:
            db.save_user(user_id, query.from_user.username or "", timezone, language)
            schedule_daily_check(user_id, timezone)
            db.update_user_activity(user_id)
            context.user_data["state"] = None
            context.user_data.clear()

            await query.message.reply_text(
                get_text('timezone_set', language, timezone=timezone),
                reply_markup=get_main_keyboard(language)
            )
        except Exception as e:
            logger.error(f"Error saving timezone for user {user_id}: {str(e)}")
            await query.message.reply_text(
                get_text('timezone_error', language),
                reply_markup=get_main_keyboard(language)
            )

    await query.answer()


async def handle_repeated_callback(query, context, parts, user_id, user, language: str = 'ru'):
    reminder_id = int(parts[1]) if len(parts) > 1 else None
    if not reminder_id:
        await query.answer("Ошибка: неверный формат команды")
        return

    # Если language не передан, берем из пользователя
    if not language:
        language = user.language if user else 'ru'

    # ДОБАВЛЯЕМ ПРОВЕРКУ НА ДУБЛИРОВАНИЕ ОБРАБОТКИ
    processing_key = f"processing_reminder_{reminder_id}"
    if context.user_data.get(processing_key):
        logger.warning(f"DUPLICATE_PROCESSING: Reminder {reminder_id} is already being processed for user {user_id}")
        await query.answer("Повторение уже обрабатывается...")
        return

    context.user_data[processing_key] = True

    try:
        # Логируем попытку
        logger.info(f"USER_ACTION: User {user_id} clicking 'Repeated' for reminder {reminder_id}")

        # Единая проверка существования напоминания и темы
        reminder = db.get_reminder(reminder_id)
        if not reminder:
            logger.warning(f"REMINDER_NOT_FOUND: Reminder {reminder_id} not found")
            await query.answer(get_text('reminder_not_found', language))
            await query.message.delete()
            return

        topic = db.get_topic_by_reminder_id(reminder_id, user_id, user.timezone)
        if not topic:
            logger.error(
                f"TOPIC_NOT_FOUND_BY_REMINDER: Reminder {reminder_id} exists but topic not found (topic_id: {reminder.topic_id})")
            await query.answer(get_text('topic_not_found_by_reminder', language))
            await query.message.delete()
            return

        # ПРОВЕРЯЕМ, ЧТО ТЕМА ЕЩЕ НЕ ЗАВЕРШЕНА
        if topic.is_completed:
            logger.warning(
                f"TOPIC_ALREADY_COMPLETED: User {user_id} tried to mark completed topic {topic.topic_id} as repeated")
            await query.answer(get_text('topic_already_completed', language))
            await query.message.delete()
            return

        topic_name = topic.topic_name
        logger.info(
            f"TOPIC_REPEATED: User {user_id} marked topic {topic.topic_id} as repeated via button (reminder_id: {reminder_id})")

        # ОТВЕЧАЕМ СРАЗУ, ЧТОБЫ ПОЛЬЗОВАТЕЛЬ ВИДЕЛ РЕАКЦИЮ
        await query.answer(get_text('processing_repetition', language))

        result = db.mark_topic_repeated_by_reminder(reminder_id, user_id, user.timezone)

        if not result:
            logger.error(f"DB_ERROR: Failed to mark topic {topic.topic_id} as repeated for user {user_id}")
            await query.answer("Ошибка при отметке повторения. 😔")
            return

        completed_repetitions, next_reminder_time, new_reminder_id = result
        db.update_user_activity(user_id)
        total_repetitions = 7
        logger.info(
            f"TOPIC_PROGRESS: Topic {topic.topic_id} - {completed_repetitions}/{total_repetitions} repetitions completed")
        progress_percentage = (completed_repetitions / total_repetitions) * 100
        progress_bar = "█" * completed_repetitions + "░" * (total_repetitions - completed_repetitions)

        tz = pytz.timezone(user.timezone)
        message = ""

        if completed_repetitions < total_repetitions:
            next_reminder_str = db._from_utc_naive(next_reminder_time, user.timezone).strftime("%d.%m.%Y %H:%M")
            if new_reminder_id:
                # УДАЛЯЕМ СТАРОЕ ЗАДАНИЕ ПЕРЕД СОЗДАНИЕМ НОВОГО
                old_job_id = f"reminder_{reminder_id}_{user_id}"
                if scheduler.get_job(old_job_id):
                    scheduler.remove_job(old_job_id)
                    logger.info(f"REMINDER_CLEANUP: Removed old job {old_job_id}")

                # СОЗДАЕМ НОВОЕ ЗАДАНИЕ С КОРРЕКТНЫМ ID
                new_job_id = f"reminder_{new_reminder_id}_{user_id}"
                scheduler.add_job(
                    send_reminder,
                    "date",
                    run_date=db._from_utc_naive(next_reminder_time, user.timezone),
                    args=[app.bot, user_id, topic_name, new_reminder_id],
                    id=new_job_id,
                    timezone=tz,
                    misfire_grace_time=None
                )
                logger.info(f"REMINDER_SCHEDULED: New reminder {new_reminder_id} scheduled for {next_reminder_str}")

            message = get_text('topic_repeated_with_next', language,
                               topic_name=topic_name,
                               completed=completed_repetitions,
                               total=total_repetitions,
                               next_time=next_reminder_str,
                               progress_bar=progress_bar,
                               percentage=progress_percentage)
            if not message:
                message = f"Тема '{topic_name}' отмечена как повторённая! 😺\nЗавершено: {completed_repetitions}/{total_repetitions} повторений\nСледующее повторение: {next_reminder_str}\nПрогресс: {progress_bar} {progress_percentage:.1f}%"
        else:
            # УДАЛЯЕМ СТАРОЕ ЗАДАНИЕ ПРИ ЗАВЕРШЕНИИ ТЕМЫ
            old_job_id = f"reminder_{reminder_id}_{user_id}"
            if scheduler.get_job(old_job_id):
                scheduler.remove_job(old_job_id)
                logger.info(f"REMINDER_CLEANUP: Removed completed topic job {old_job_id}")

            message = get_text('topic_completed', language,
                               topic_name=topic_name,
                               completed=completed_repetitions,
                               total=total_repetitions,
                               progress_bar=progress_bar,
                               percentage=progress_percentage)
            if not message:
                message = f"🎉 Поздравляю, ты полностью освоил тему '{topic_name}'! 🏆\nЗавершено: {completed_repetitions}/{total_repetitions} повторений\nПрогресс: {progress_bar} {progress_percentage:.1f}%\nЕсли захочешь повторить её заново, используй 'Восстановить тему'. 😺"

        await query.message.delete()
        await query.message.reply_text(
            message,
            reply_markup=get_main_keyboard(language)  # Используем правильную клавиатуру
        )
        logger.debug(f"User {user_id} marked topic '{topic_name}' as repeated via button")

    except Exception as e:
        logger.error(f"Error in handle_repeated_callback for reminder {reminder_id}: {str(e)}")
        await query.answer("Произошла ошибка при обработке. Попробуйте снова.")
    finally:
        # ОЧИЩАЕМ ФЛАГ ОБРАБОТКИ
        context.user_data.pop(processing_key, None)


async def handle_add_topic_category(query, context, parts, user_id, user):
    category_id_str = parts[1] if len(parts) > 1 else None
    category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None
    topic_name = context.user_data.get("new_topic_name")

    if topic_name:
        try:
            # ВАЖНО: Должен возвращать (topic_id, reminder_id)
            topic_id, reminder_id = db.add_topic(user_id, topic_name, user.timezone, category_id)
            tz = pytz.timezone(user.timezone)

            # Логирование успешного добавления темы
            category_name = db.get_category(category_id, user_id).category_name if category_id else "Без категории"
            logger.info(
                f"USER_ACTION: User {user_id} added topic '{topic_name}' to category '{category_name}' (topic_id: {topic_id}, reminder_id: {reminder_id})")

            # Получаем время напоминания для логирования
            reminder_time = db._from_utc_naive(db.get_reminder(reminder_id).scheduled_time, user.timezone)
            logger.info(
                f"REMINDER_SCHEDULED: Topic '{topic_name}' reminder scheduled for {reminder_time.strftime('%Y-%m-%d %H:%M')} (reminder_id: {reminder_id})")

            # Добавляем в планировщик
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


async def show_delete_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, language: str = 'ru'):
    # Получаем пользователя внутри функции
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text(get_text('user_not_found', language))
        return

    categories = db.get_categories(user_id)
    keyboard = []

    for category in categories:
        topics_in_category = db.get_active_topics(user_id, user.timezone, category.category_id)
        if topics_in_category:
            keyboard.append([
                InlineKeyboardButton(
                    f"{category.category_name} ({len(topics_in_category)})",
                    callback_data=f"delete_category_select:{category.category_id}"
                )
            ])

    topics_no_category = db.get_active_topics(user_id, user.timezone, category_id=None)
    if topics_no_category:
        keyboard.append([
            InlineKeyboardButton(
                f"{get_text('no_category_icon', language, default='📁')} {get_text('no_category', language)} ({len(topics_no_category)})",
                callback_data="delete_category_select:none"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(get_text('all_topics_at_once', language, default="🔍 Все темы сразу"),
                             callback_data="delete_all_topics")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Используем get_text для получения переведенного текста
    message_text = get_text('select_category_to_delete', language)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )
    context.user_data["state"] = "awaiting_delete_category"


async def show_restore_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, language: str = 'ru'):
    # Получаем пользователя внутри функции
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text(get_text('user_not_found', language))
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
                f"{get_text('no_category_icon', language)} {get_text('no_category', language)} ({len(no_category_topics)})",
                callback_data="restore_category_select:none"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(get_text('all_topics_at_once', language), callback_data="restore_all_topics")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Используем get_text
    message_text = get_text('select_category_to_restore', language)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )
    context.user_data["state"] = "awaiting_restore_category"


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    username = update.effective_user.username
    username_display = f"@{username}" if username else f"user_{user_id}"
    db.update_user_activity(user_id)
    user = db.get_user(user_id)

    logger.debug(f"User {user_id} ({username_display}) clicked: {data}")

    if not user:
        await query.answer()
        return

    # Получаем язык пользователя
    language = user.language if user else 'ru'

    # Разбиваем data на части для удобства
    parts = data.split(':')
    action = parts[0]

    try:
        # ОБРАБОТКА ВЫБОРА ЯЗЫКА
        if action == "lang":
            language = parts[1] if len(parts) > 1 else 'ru'

            # Обновляем язык пользователя
            user = db.get_user(user_id)
            if user:
                db.save_user(user_id, user.username or "", user.timezone or "UTC", language)
                language = language  # Обновляем локальную переменную

            # Переходим к выбору часового пояса
            keyboard = [
                [
                    InlineKeyboardButton("Europe/Moscow (MSK, UTC+3)", callback_data="tz:Europe/Moscow"),
                    InlineKeyboardButton("America/New_York (EST, UTC-5)", callback_data="tz:America/New_York"),
                ],
                [
                    InlineKeyboardButton("Europe/London (GMT, UTC+0)", callback_data="tz:Europe/London"),
                    InlineKeyboardButton("Asia/Tokyo (JST, UTC+9)", callback_data="tz:Asia/Tokyo"),
                ],
                [InlineKeyboardButton(
                    get_text('other_manual', language) if 'other_manual' in TRANSLATIONS.get(language, {})
                    else ("Другой (введи вручную)" if language == 'ru' else "Other (enter manually)"),
                    callback_data="tz:manual")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(
                get_text('choose_timezone', language),
                reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_timezone"
            await query.answer()
            return

        # ОБРАБОТКА СМЕНЫ ЯЗЫКА (команда /language)
        if action == "change_lang":
            language = parts[1] if len(parts) > 1 else 'ru'

            if user:
                db.save_user(user_id, user.username or "", user.timezone, language)
                await query.message.edit_text(
                    get_text('language_set', language)
                )
                await query.message.reply_text(
                    get_text('welcome_back', language,
                             name=query.from_user.first_name,
                             timezone=user.timezone),
                    reply_markup=get_main_keyboard(language)
                )
            await query.answer()
            return

        # ОБРАБОТКА ЧАСОВОГО ПОЯСА
        if action == "tz":
            timezone = parts[1] if len(parts) > 1 else None

            if timezone == "manual":
                context.user_data["state"] = "awaiting_manual_timezone"
                await query.message.reply_text(
                    "⌨️ " + get_text('enter_timezone_manual', language) if 'enter_timezone_manual' in TRANSLATIONS.get(
                        language, {})
                    else "Введи часовой пояс вручную:\n\n• Название: Europe/Moscow, Asia/Tokyo, America/New_York\n• Смещение: +3, UTC+3, -5, UTC-5"
                )
                logger.debug(f"User {user_id} set state to: awaiting_manual_timezone")
            else:
                try:
                    # ОБНОВЛЯЕМ часовой пояс пользователя
                    db.save_user(user_id, query.from_user.username or "", timezone, language)
                    schedule_daily_check(user_id, timezone)

                    # Обновляем активность
                    db.update_user_activity(user_id)

                    # Сбрасываем состояние
                    context.user_data["state"] = None
                    context.user_data.clear()

                    await query.message.reply_text(
                        get_text('timezone_set', language, timezone=timezone),
                        reply_markup=get_main_keyboard(language)
                    )
                    logger.info(f"User {user_id} updated timezone to {timezone}")
                except Exception as e:
                    logger.error(f"Error saving timezone for user {user_id}: {str(e)}")
                    await query.message.reply_text(
                        get_text('timezone_error', language),
                        reply_markup=get_main_keyboard(language)
                    )

            await query.answer()
            return

        elif action == "category_progress":
            category_id_str = parts[1] if len(parts) > 1 else None
            category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None
            await show_category_progress(update, context, category_id, user.timezone, language)

        elif action == "add_topic_category":
            category_id_str = parts[1] if len(parts) > 1 else None
            category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None
            topic_name = context.user_data.get("new_topic_name")

            if topic_name:
                try:
                    topic_id, reminder_id = db.add_topic(user_id, topic_name, user.timezone, category_id)
                    tz = pytz.timezone(user.timezone)

                    # Логирование успешного добавления темы
                    category_name = db.get_category(category_id, user_id).category_name if category_id else get_text(
                        'no_category', language, default="Без категории")
                    logger.info(
                        f"USER_ACTION: User {user_id} added topic '{topic_name}' to category '{category_name}' (topic_id: {topic_id}, reminder_id: {reminder_id})")

                    # Получаем время напоминания для логирования
                    reminder_time = db._from_utc_naive(db.get_reminder(reminder_id).scheduled_time, user.timezone)
                    logger.info(
                        f"REMINDER_SCHEDULED: Topic '{topic_name}' reminder scheduled for {reminder_time.strftime('%Y-%m-%d %H:%M')} (reminder_id: {reminder_id})")

                    # Добавляем в планировщик
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
                        f"✅ {get_text('topic_added', language, topic_name=topic_name) if 'topic_added' in TRANSLATIONS.get(language, {}) else f'Тема {topic_name} добавлена!'} 😺",
                        reply_markup=get_main_keyboard(language)
                    )
                except Exception as e:
                    logger.error(f"Error adding topic '{topic_name}' for user {user_id}: {str(e)}")
                    await query.message.delete()
                    await query.message.reply_text(
                        get_text('error_occurred', language),
                        reply_markup=get_main_keyboard(language)
                    )

            context.user_data["state"] = None
            context.user_data.pop("new_topic_name", None)

        elif action == "delete_category_select":
            category_id_str = parts[1] if len(parts) > 1 else None
            category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None

            topics = db.get_active_topics(user_id, user.timezone, category_id=category_id)
            if not topics:
                await query.answer(
                    get_text('no_topics_in_category', language, default="В этой категории нет тем для удаления! 😿"))
                return

            keyboard = []
            for topic in topics:
                category_name = db.get_category(topic.category_id,
                                                user_id).category_name if topic.category_id else get_text('no_category',
                                                                                                          language,
                                                                                                          default="📁 Без категории")
                keyboard.append([
                    InlineKeyboardButton(
                        f"{topic.topic_name} ({category_name})",
                        callback_data=f"delete:{topic.topic_id}"
                    )
                ])

            keyboard.append(
                [InlineKeyboardButton(get_text('back', language), callback_data="back_to_delete_categories")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            category_name = db.get_category(category_id, user_id).category_name if category_id else get_text(
                'no_category', language, default="📁 Без категории")
            await query.message.edit_text(
                get_text('select_topic_to_delete', language,
                         category_name=category_name) if 'select_topic_to_delete' in TRANSLATIONS.get(language, {})
                else f"Выбери тему для удаления из категории '{category_name}':",
                reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_topic_deletion"

        elif action == "delete":
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
                logger.info(
                    f"TOPIC_DELETED: User {user_id} successfully deleted topic '{topic_name}' (topic_id: {topic_id})")
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
                        logger.debug(
                            f"REMINDER_NOT_FOUND: Job {job_id} not found in scheduler (maybe already executed)")

                logger.info(
                    f"REMINDER_CLEANUP_COMPLETE: Removed {removed_jobs_count} scheduled jobs for topic '{topic_name}'")

                await query.message.delete()
                await query.message.reply_text(
                    get_text('topic_deleted', language) if 'topic_deleted' in TRANSLATIONS.get(language, {})
                    else "Тема и все связанные напоминания удалены! 😿",
                    reply_markup=get_main_keyboard(language)
                )
                logger.debug(f"User {user_id} deleted topic {topic_id} with all reminders")
            else:
                # Логирование неудачной попытки удаления
                logger.warning(f"TOPIC_DELETE_FAILED: Topic {topic_id} not found for user {user_id}")
                await query.message.delete()
                await query.message.reply_text(
                    get_text('topic_not_found', language) if 'topic_not_found' in TRANSLATIONS.get(language, {})
                    else "Тема не найдена. 😿",
                    reply_markup=get_main_keyboard(language)
                )
            context.user_data["state"] = None

        elif action == "restore_category_select":
            category_id_str = parts[1] if len(parts) > 1 else None
            category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None

            completed_topics = db.get_completed_topics(user_id)
            if category_id is not None:
                filtered_topics = [t for t in completed_topics if t.category_id == category_id]
            else:
                filtered_topics = [t for t in completed_topics if t.category_id is None]

            if not filtered_topics:
                await query.answer(
                    get_text('no_completed_topics', language, default="В этой категории нет завершённых тем! 😿"))
                return

            keyboard = []
            for topic in filtered_topics:
                category_name = db.get_category(topic.category_id,
                                                user_id).category_name if topic.category_id else get_text('no_category',
                                                                                                          language,
                                                                                                          default="📁 Без категории")
                keyboard.append([
                    InlineKeyboardButton(
                        f"{topic.topic_name} ({category_name})",
                        callback_data=f"restore:{topic.completed_topic_id}"
                    )
                ])

            keyboard.append(
                [InlineKeyboardButton(get_text('back', language), callback_data="back_to_restore_categories")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            category_name = db.get_category(category_id, user_id).category_name if category_id else get_text(
                'no_category', language, default="📁 Без категории")
            await query.message.edit_text(
                get_text('select_topic_to_restore', language,
                         category_name=category_name) if 'select_topic_to_restore' in TRANSLATIONS.get(language, {})
                else f"Выбери тему для восстановления из категории '{category_name}':",
                reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_topic_restoration"

        elif action == "restore":
            completed_topic_id = int(parts[1]) if len(parts) > 1 else None
            result = db.restore_topic(completed_topic_id, user_id, user.timezone)

            if result:
                topic_id, topic_name = result
                reminder = db.get_reminder_by_topic(topic_id)
                if reminder:
                    reminder_id = reminder.reminder_id
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
                    f"✅ {get_text('topic_restored', language, topic_name=topic_name) if 'topic_restored' in TRANSLATIONS.get(language, {}) else f'Тема {topic_name} восстановлена!'} 😺",
                    reply_markup=get_main_keyboard(language)
                )
                logger.debug(f"User {user_id} restored topic {topic_name}")
            else:
                await query.message.delete()
                await query.message.reply_text(
                    get_text('topic_not_found', language) if 'topic_not_found' in TRANSLATIONS.get(language, {})
                    else "Тема не найдена. 😿",
                    reply_markup=get_main_keyboard(language)
                )
            context.user_data["state"] = None

        elif action == "category_action":
            action_type = parts[1] if len(parts) > 1 else None

            if action_type == "create":
                # ПРОВЕРКА ЛИМИТА СРАЗУ ПРИ ВЫБОРЕ "СОЗДАТЬ КАТЕГОРИЮ"
                categories = db.get_categories(user_id)
                if len(categories) >= MAX_CATEGORIES:
                    await query.message.reply_text(
                        get_text('category_limit_reached', language, max_categories=MAX_CATEGORIES,
                                 current_count=len(categories))
                        if 'category_limit_reached' in TRANSLATIONS.get(language, {})
                        else f"❌ Достигнут лимит категорий ({MAX_CATEGORIES})! 😿\n\nЧтобы создать новую категорию, сначала удали одну из существующих.\nСейчас у тебя {len(categories)} категорий.",
                        reply_markup=get_main_keyboard(language)
                    )
                    logger.info(
                        f"LIMIT_REACHED: User {user_id} reached category limit ({len(categories)}/{MAX_CATEGORIES})")
                    context.user_data["state"] = None
                    return

                context.user_data["state"] = "awaiting_category_name"
                await query.message.reply_text(
                    get_text('enter_category_name', language) if 'enter_category_name' in TRANSLATIONS.get(language, {})
                    else "Напиши название новой категории! 😊",
                    reply_markup=ReplyKeyboardMarkup([[get_text('cancel', language)]], resize_keyboard=True)
                )

                logger.info(
                    f"USER_ACTION: User {user_id} starting to create new category ({len(categories)}/{MAX_CATEGORIES})")
            elif action_type == "rename":
                categories = db.get_categories(user_id)
                if not categories:
                    await query.message.reply_text(
                        get_text('no_categories_to_rename', language) if 'no_categories_to_rename' in TRANSLATIONS.get(
                            language, {})
                        else "У тебя нет категорий для переименования! 😿",
                        reply_markup=get_main_keyboard(language)
                    )
                    context.user_data["state"] = None
                    return

                keyboard = [
                    [InlineKeyboardButton(category.category_name,
                                          callback_data=f"rename_category:{category.category_id}")]
                    for category in categories
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    get_text('select_category_to_rename', language) if 'select_category_to_rename' in TRANSLATIONS.get(
                        language, {})
                    else "Выбери категорию для переименования:",
                    reply_markup=reply_markup
                )
                context.user_data["state"] = "awaiting_category_rename"

            elif action_type == "delete":
                categories = db.get_categories(user_id)
                if not categories:
                    await query.message.reply_text(
                        get_text('no_categories_to_delete', language) if 'no_categories_to_delete' in TRANSLATIONS.get(
                            language, {})
                        else "У тебя нет категорий для удаления! 😿",
                        reply_markup=get_main_keyboard(language)
                    )
                    context.user_data["state"] = None
                    return

                keyboard = [
                    [InlineKeyboardButton(category.category_name,
                                          callback_data=f"delete_category:{category.category_id}")]
                    for category in categories
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    get_text('select_category_to_delete', language) if 'select_category_to_delete' in TRANSLATIONS.get(
                        language, {})
                    else "Выбери категорию для удаления (темы перейдут в 'Без категории'):",
                    reply_markup=reply_markup
                )
                context.user_data["state"] = "awaiting_category_deletion"

            elif action_type == "move":
                topics = db.get_active_topics(user_id, user.timezone, category_id='all')
                if not topics:
                    await query.message.reply_text(
                        get_text('no_topics_to_move', language) if 'no_topics_to_move' in TRANSLATIONS.get(language, {})
                        else "У тебя нет тем для перемещения! 😿",
                        reply_markup=get_main_keyboard(language)
                    )
                    context.user_data["state"] = None
                    return

                keyboard = [
                    [InlineKeyboardButton(topic.topic_name, callback_data=f"move_topic:{topic.topic_id}")]
                    for topic in topics
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    get_text('select_topic_to_move', language) if 'select_topic_to_move' in TRANSLATIONS.get(language,
                                                                                                             {})
                    else "Выбери тему для перемещения:",
                    reply_markup=reply_markup
                )
                context.user_data["state"] = "awaiting_topic_selection_move"

        elif action == "rename_category":
            category_id = int(parts[1]) if len(parts) > 1 else None
            context.user_data["rename_category_id"] = category_id
            context.user_data["state"] = "awaiting_new_category_name"
            await query.message.reply_text(
                get_text('enter_new_category_name', language) if 'enter_new_category_name' in TRANSLATIONS.get(language,
                                                                                                               {})
                else "Напиши новое название категории! 😊",
                reply_markup=ReplyKeyboardMarkup([[get_text('cancel', language)]], resize_keyboard=True)
            )

        elif action == "delete_category":
            category_id = int(parts[1]) if len(parts) > 1 else None

            category = db.get_category(category_id, user_id)
            category_name = category.category_name if category else "Unknown"

            logger.info(
                f"USER_ACTION: User {user_id} attempting to delete category '{category_name}' (category_id: {category_id})")

            if db.delete_category(category_id, user_id):
                logger.info(f"CATEGORY_DELETED: User {user_id} successfully deleted category '{category_name}'")
                logger.info(f"CATEGORY_CLEANUP: All topics from category '{category_name}' moved to 'No category'")

                await query.message.reply_text(
                    get_text('category_deleted', language) if 'category_deleted' in TRANSLATIONS.get(language, {})
                    else "Категория удалена! Темы перемещены в 'Без категории'. 😺",
                    reply_markup=get_main_keyboard(language)
                )
                logger.debug(f"User {user_id} deleted category {category_id}")
            else:
                logger.warning(f"CATEGORY_DELETE_FAILED: Category {category_id} not found for user {user_id}")
                await query.message.reply_text(
                    get_text('category_not_found', language) if 'category_not_found' in TRANSLATIONS.get(language, {})
                    else "Категория не найдена. 😿",
                    reply_markup=get_main_keyboard(language)
                )
            context.user_data["state"] = None

        elif action == "move_topic":
            topic_id = int(parts[1]) if len(parts) > 1 else None
            context.user_data["move_topic_id"] = topic_id
            categories = db.get_categories(user_id)
            keyboard = [
                [InlineKeyboardButton(category.category_name, callback_data=f"move_to_category:{category.category_id}")]
                for category in categories
            ]
            keyboard.append([InlineKeyboardButton(get_text('no_category', language, default="Без категории"),
                                                  callback_data="move_to_category:none")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                get_text('select_new_category', language) if 'select_new_category' in TRANSLATIONS.get(language, {})
                else "Выбери новую категорию для темы:",
                reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_category_selection"

        elif action == "move_to_category":
            category_id_str = parts[1] if len(parts) > 1 else None
            category_id = int(category_id_str) if category_id_str and category_id_str != "none" else None
            topic_id = context.user_data.get("move_topic_id")

            user = db.get_user(user_id)
            topic = db.get_topic(topic_id, user_id, user.timezone if user else "UTC")
            topic_name = topic.topic_name if topic else "Unknown"

            old_category_name = db.get_category(topic.category_id,
                                                user_id).category_name if topic and topic.category_id else get_text(
                'no_category', language, default="Без категории")
            new_category_name = db.get_category(category_id, user_id).category_name if category_id else get_text(
                'no_category', language, default="Без категории")

            if db.move_topic_to_category(topic_id, user_id, category_id):
                logger.info(
                    f"TOPIC_MOVED: User {user_id} moved topic '{topic_name}' from '{old_category_name}' to '{new_category_name}'")

                await query.message.reply_text(
                    get_text('topic_moved', language,
                             new_category_name=new_category_name) if 'topic_moved' in TRANSLATIONS.get(language, {})
                    else f"Тема перемещена в категорию '{new_category_name}'! 😺",
                    reply_markup=get_main_keyboard(language)
                )
                logger.debug(f"User {user_id} moved topic {topic_id} to category {category_id}")
            else:
                logger.warning(f"TOPIC_MOVE_FAILED: Failed to move topic {topic_id} for user {user_id}")
                await query.message.reply_text(
                    get_text('topic_or_category_not_found',
                             language) if 'topic_or_category_not_found' in TRANSLATIONS.get(language, {})
                    else "Тема или категория не найдена. 😿",
                    reply_markup=get_main_keyboard(language)
                )
            context.user_data["state"] = None
            context.user_data.pop("move_topic_id", None)

        elif action == "add_to_new_category":
            if len(parts) > 1 and parts[-1] == "no":
                await query.message.reply_text(
                    get_text('category_created_no_topics',
                             language) if 'category_created_no_topics' in TRANSLATIONS.get(language, {})
                    else "Категория создана без добавления тем! 😺",
                    reply_markup=get_main_keyboard(language)
                )
                context.user_data.pop("new_category_id", None)
                context.user_data["state"] = None
            elif len(parts) > 2 and parts[-1] == "yes":
                category_id = int(parts[1])
                topics = db.get_active_topics(user_id, user.timezone, category_id='all')
                if not topics:
                    await query.message.reply_text(
                        get_text('no_topics_to_add', language) if 'no_topics_to_add' in TRANSLATIONS.get(language, {})
                        else "У тебя нет тем для добавления! 😿",
                        reply_markup=get_main_keyboard(language)
                    )
                    context.user_data["state"] = None
                    return

                keyboard = [
                    [InlineKeyboardButton(topic.topic_name, callback_data=f"add_to_category_topic:{topic.topic_id}")]
                    for topic in topics
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    get_text('select_topic_for_new_category',
                             language) if 'select_topic_for_new_category' in TRANSLATIONS.get(language, {})
                    else "Выбери тему для добавления в новую категорию:",
                    reply_markup=reply_markup
                )
                context.user_data["move_to_category_id"] = category_id
                context.user_data["state"] = "awaiting_topic_add_to_category"

        elif action == "add_to_category_topic":
            topic_id = int(parts[1]) if len(parts) > 1 else None
            category_id = context.user_data.get("move_to_category_id")

            if db.move_topic_to_category(topic_id, user_id, category_id):
                category_name = db.get_category(category_id, user_id).category_name
                await query.message.reply_text(
                    get_text('topic_added_to_category', language,
                             category_name=category_name) if 'topic_added_to_category' in TRANSLATIONS.get(language, {})
                    else f"Тема добавлена в категорию '{category_name}'! 😺",
                    reply_markup=get_main_keyboard(language)
                )
                logger.debug(f"User {user_id} added topic {topic_id} to category {category_id}")
            else:
                await query.message.reply_text(
                    get_text('error_adding_topic', language) if 'error_adding_topic' in TRANSLATIONS.get(language, {})
                    else "Ошибка добавления темы. 😿",
                    reply_markup=get_main_keyboard(language)
                )
            context.user_data["state"] = None
            context.user_data.pop("move_to_category_id", None)

        elif action == "repeated":
            await handle_repeated_callback(query, context, parts, user_id, user, language)

        elif data == "back_to_progress":
            await show_progress(update, context, language)

        elif data == "back_to_delete_categories":
            await show_delete_categories(update, context, user_id, language)

        elif data == "back_to_restore_categories":
            await show_restore_categories(update, context, user_id, language)

        elif data == "delete_all_topics":
            topics = db.get_active_topics(user_id, user.timezone, category_id='all')
            if not topics:
                await query.answer(get_text('no_topics_to_delete', language, default="У тебя нет тем для удаления! 😿"))
                return

            limited_topics = topics[:20]
            keyboard = []
            for topic in limited_topics:
                category_name = db.get_category(topic.category_id,
                                                user_id).category_name if topic.category_id else get_text('no_category',
                                                                                                          language,
                                                                                                          default="📁 Без категории")
                keyboard.append([
                    InlineKeyboardButton(
                        f"{topic.topic_name} ({category_name})",
                        callback_data=f"delete:{topic.topic_id}"
                    )
                ])

            if len(topics) > 20:
                keyboard.append(
                    [InlineKeyboardButton(get_text('back', language), callback_data="back_to_delete_categories")])
                await query.message.edit_text(
                    get_text('too_many_topics', language, count=len(topics)) if 'too_many_topics' in TRANSLATIONS.get(
                        language, {})
                    else f"Слишком много тем для отображения ({len(topics)}). Показаны первые 20. Лучше используй выбор по категориям.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                keyboard.append(
                    [InlineKeyboardButton(get_text('back', language), callback_data="back_to_delete_categories")])
                await query.message.edit_text(
                    get_text('select_topic_to_delete_all',
                             language) if 'select_topic_to_delete_all' in TRANSLATIONS.get(language, {})
                    else "Выбери тему для удаления (восстановить будет нельзя):",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            context.user_data["state"] = "awaiting_topic_deletion"

        elif data == "restore_all_topics":
            completed_topics = db.get_completed_topics(user_id)
            if not completed_topics:
                await query.answer(get_text('no_completed_topics_all', language,
                                            default="У тебя нет завершённых тем для восстановления! 😿"))
                return

            limited_topics = completed_topics[:20]
            keyboard = []
            for topic in limited_topics:
                category_name = db.get_category(topic.category_id,
                                                user_id).category_name if topic.category_id else get_text('no_category',
                                                                                                          language,
                                                                                                          default="📁 Без категории")
                keyboard.append([
                    InlineKeyboardButton(
                        f"{topic.topic_name} ({category_name})",
                        callback_data=f"restore:{topic.completed_topic_id}"
                    )
                ])

            if len(completed_topics) > 20:
                keyboard.append(
                    [InlineKeyboardButton(get_text('back', language), callback_data="back_to_restore_categories")])
                await query.message.edit_text(
                    get_text('too_many_completed_topics', language,
                             count=len(completed_topics)) if 'too_many_completed_topics' in TRANSLATIONS.get(language,
                                                                                                             {})
                    else f"Слишком много тем для отображения ({len(completed_topics)}). Показаны первые 20. Лучше используй выбор по категориям.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                keyboard.append(
                    [InlineKeyboardButton(get_text('back', language), callback_data="back_to_restore_categories")])
                await query.message.edit_text(
                    get_text('select_completed_topic_to_restore',
                             language) if 'select_completed_topic_to_restore' in TRANSLATIONS.get(language, {})
                    else "Выбери завершённую тему для восстановления:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            context.user_data["state"] = "awaiting_topic_restoration"

        else:
            logger.warning(f"Unknown callback data: {data} from user {user_id}")
            await query.answer(get_text('unknown_command', language))

    except Exception as e:
        logger.error(f"Error handling callback {data} for user {user_id}: {str(e)}")
        await query.answer(get_text('error_occurred', language))
        await query.message.reply_text(
            get_text('error_occurred', language),
            reply_markup=get_main_keyboard(language)
        )

    await query.answer()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    username_display = f"@{username}" if username else f"user_{user_id}"
    text = update.message.text.strip()
    user = db.get_user(user_id)
    db.update_user_activity(user_id)

    # Получаем язык пользователя или используем русский по умолчанию
    language = user.language if user else 'ru'

    logger.debug(
        f"User {user_id} ({username_display}) sent: '{text}', state: {context.user_data.get('state')}, language: {language}")

    # ========== ОБРАБОТКА ВЫБОРА ЯЗЫКА ЧЕРЕЗ ТЕКСТ ==========
    if not user and not text.startswith("/"):
        # Новый пользователь выбирает язык через текст
        if text.lower() in ["русский", "russian", "ru", "🇷🇺 русский"]:
            language = 'ru'
        elif text.lower() in ["английский", "english", "en", "🇬🇧 english"]:
            language = 'en'
        else:
            # Показываем меню выбора языка
            keyboard = [
                [
                    InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
                    InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                get_text('choose_language', 'ru'),
                reply_markup=reply_markup
            )
            return

        # Сохраняем пользователя с выбранным языком
        db.save_user(user_id, update.effective_user.username or "", "UTC", language)
        user = db.get_user(user_id)  # Обновляем объект пользователя

        # Показываем выбор часового пояса
        keyboard = [
            [
                InlineKeyboardButton("Europe/Moscow (MSK, UTC+3)", callback_data="tz:Europe/Moscow"),
                InlineKeyboardButton("America/New_York (EST, UTC-5)", callback_data="tz:America/New_York"),
            ],
            [
                InlineKeyboardButton("Europe/London (GMT, UTC+0)", callback_data="tz:Europe/London"),
                InlineKeyboardButton("Asia/Tokyo (JST, UTC+9)", callback_data="tz:Asia/Tokyo"),
            ],
            [InlineKeyboardButton(
                get_text('other_manual', language) if 'other_manual' in TRANSLATIONS.get(language, {})
                else ("Другой (введи вручную)" if language == 'ru' else "Other (enter manually)"),
                callback_data="tz:manual")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            get_text('choose_timezone', language),
            reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_timezone"
        return

    # ВАЖНОЕ ИСПРАВЛЕНИЕ: Если пользователь уже существует и пытается использовать основное меню,
    # но состояние застряло - принудительно сбрасываем состояние для основных команд
    main_commands = get_text('main_keyboard', language)
    if user and text in main_commands:
        if context.user_data.get("state") in ["awaiting_timezone", "awaiting_manual_timezone", "awaiting_language"]:
            logger.warning(f"Force resetting stuck state for user {user_id}")
            context.user_data["state"] = None
            context.user_data.clear()

    if not user and not text.startswith("/tz"):
        await update.message.reply_text(
            get_text('need_timezone', language),
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
            db.save_user(user_id, update.effective_user.username or "", timezone_candidate, language)
            schedule_daily_check(user_id, timezone_candidate)

            # ВАЖНО: Сбрасываем состояние после успешного сохранения
            context.user_data["state"] = None
            context.user_data.clear()

            await update.message.reply_text(
                get_text('timezone_set', language, timezone=display_name),
                reply_markup=get_main_keyboard(language)
            )

            logger.info(f"User {user_id} successfully set timezone to: {timezone_candidate} (display: {display_name})")

        except pytz.UnknownTimeZoneError:
            logger.warning(f"User {user_id} entered unknown timezone: {text}")
            await update.message.reply_text(
                get_text('timezone_error', language),
                reply_markup=get_main_keyboard(language)
            )
            # Не сбрасываем состояние здесь - даем пользователю попробовать снова

        except Exception as e:
            logger.error(f"Error setting timezone for user {user_id}: {str(e)}")
            await update.message.reply_text(
                get_text('error_occurred', language),
                reply_markup=get_main_keyboard(language)
            )
            # Сбрасываем состояние при других ошибках
            context.user_data["state"] = None

        return

    if state == "awaiting_category_name":
        if text == get_text('cancel', language):
            context.user_data["state"] = None
            await update.message.reply_text(
                get_text('action_canceled', language),
                reply_markup=get_main_keyboard(language)
            )
            return

        # Лимит уже проверен при нажатии кнопки "Создать категорию", так что здесь просто создаем
        try:
            category_id = db.add_category(user_id, text)
            keyboard = [
                [InlineKeyboardButton(get_text('yes', language, default="Да"),
                                      callback_data=f"add_to_new_category:{category_id}:yes")],
                [InlineKeyboardButton(get_text('no', language, default="Нет"), callback_data="add_to_new_category:no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Логирование создания категории
            categories = db.get_categories(user_id)
            logger.info(f"USER_ACTION: User {user_id} created category '{text}' ({len(categories)}/{MAX_CATEGORIES})")

            await update.message.reply_text(
                get_text('category_created_ask_add_topics', language, category_name=text)
                if 'category_created_ask_add_topics' in TRANSLATIONS.get(language, {})
                else f"Категория '{text}' создана! 😺 Добавить в неё темы?",
                reply_markup=reply_markup
            )
            context.user_data["new_category_id"] = category_id
            context.user_data["state"] = "awaiting_add_to_category"
        except Exception as e:
            logger.error(f"Error creating category '{text}' for user {user_id}: {e}")
            await update.message.reply_text(
                get_text('error_occurred', language),
                reply_markup=get_main_keyboard(language)
            )
        return

    if state == "awaiting_new_category_name":
        if text == get_text('cancel', language):
            context.user_data["state"] = None
            await update.message.reply_text(
                get_text('action_canceled', language),
                reply_markup=get_main_keyboard(language)
            )
            return
        category_id = context.user_data.get("rename_category_id")
        try:
            category = db.get_category(category_id, user_id)
            if category and db.rename_category(category_id, user_id, text):
                await update.message.reply_text(
                    get_text('category_renamed', language, old_name=category.category_name, new_name=text)
                    if 'category_renamed' in TRANSLATIONS.get(language, {})
                    else f"Категория '{category.category_name}' переименована в '{text}'! 😺",
                    reply_markup=get_main_keyboard(language)
                )
                context.user_data["state"] = None
                context.user_data.pop("rename_category_id", None)
            else:
                await update.message.reply_text(
                    get_text('category_not_found', language),
                    reply_markup=get_main_keyboard(language)
                )
        except Exception as e:
            logger.error(f"Error renaming category {category_id} for user {user_id}: {e}")
            await update.message.reply_text(
                get_text('error_occurred', language),
                reply_markup=get_main_keyboard(language)
            )
        context.user_data["state"] = None
        return

    if state in ["awaiting_category_action", "awaiting_topic_selection_move", "awaiting_category_selection",
                 "awaiting_add_to_category", "awaiting_topic_add_to_category"]:
        context.user_data["state"] = None
        context.user_data.clear()
        await update.message.reply_text(
            get_text('action_canceled', language),
            reply_markup=get_main_keyboard(language)
        )
        logger.debug(f"User {user_id} exited state {state} due to new command")
        return

    # ОБРАБОТКА КОМАНДЫ "ПОВТОРИЛ"
    if text.lower().startswith(get_text('repeated_prefix', language, default="повторил").lower()):
        topic_name = text[len(get_text('repeated_prefix', language, default="повторил")):].strip()
        logger.info(f"USER_ACTION: User {user_id} attempting to mark topic '{topic_name}' as repeated via text command")
        try:
            result = db.mark_topic_repeated(user_id, topic_name, user.timezone)
            if not result:
                logger.warning(
                    f"TOPIC_NOT_FOUND: User {user_id} tried to mark unknown topic '{topic_name}' as repeated")
                await update.message.reply_text(
                    get_text('topic_not_found_or_completed', language, topic_name=topic_name)
                    if 'topic_not_found_or_completed' in TRANSLATIONS.get(language, {})
                    else f"Тема '{topic_name}' не найдена или уже завершена. 😿 Попробуй снова!",
                    reply_markup=get_main_keyboard(language)
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

                message = get_text('topic_repeated_with_next', language,
                                   topic_name=topic_name,
                                   completed=completed_repetitions,
                                   total=total_repetitions,
                                   next_time=next_reminder_str,
                                   progress_bar=progress_bar,
                                   percentage=progress_percentage)
                if not message:
                    message = f"Тема '{topic_name}' отмечена как повторённая! 😺\nЗавершено: {completed_repetitions}/{total_repetitions} повторений\nСледующее повторение: {next_reminder_str}\nПрогресс: {progress_bar} {progress_percentage:.1f}%"

                await update.message.reply_text(
                    message,
                    reply_markup=get_main_keyboard(language)
                )
            else:
                logger.info(f"TOPIC_COMPLETED: User {user_id} completed topic '{topic_name}' via text command!")

                message = get_text('topic_completed', language,
                                   topic_name=topic_name,
                                   completed=completed_repetitions,
                                   total=total_repetitions,
                                   progress_bar=progress_bar,
                                   percentage=progress_percentage)
                if not message:
                    message = f"🎉 Поздравляю, ты полностью освоил тему '{topic_name}'! 🏆\nЗавершено: {completed_repetitions}/{total_repetitions} повторений\nПрогресс: {progress_bar} {progress_percentage:.1f}%\nЕсли захочешь повторить её заново, используй 'Восстановить тему'. 😺"

                await update.message.reply_text(
                    message,
                    reply_markup=get_main_keyboard(language)
                )
        except Exception as e:
            logger.error(f"ERROR: Failed to mark topic '{topic_name}' as repeated for user {user_id}: {str(e)}")
            await update.message.reply_text(
                get_text('error_occurred', language),
                reply_markup=get_main_keyboard(language)
            )
        return

    # ОБРАБОТКА ОСНОВНЫХ КОМАНД МЕНЮ
    main_commands_list = get_text('main_keyboard', language)

    if text == main_commands_list[0]:  # Мой прогресс / My Progress
        await show_progress(update, context, language)
        return

    if text == main_commands_list[1]:  # Добавить тему / Add Topic
        # ПРОВЕРКА ЛИМИТА СРАЗУ ПРИ НАЖАТИИ КНОПКИ
        active_topics = db.get_active_topics(user_id, user.timezone, category_id='all')
        if len(active_topics) >= MAX_ACTIVE_TOPICS:
            await update.message.reply_text(
                get_text('topic_limit_reached', language, max_topics=MAX_ACTIVE_TOPICS,
                         current_count=len(active_topics)),
                reply_markup=get_main_keyboard(language),
                parse_mode="Markdown"
            )
            logger.info(
                f"LIMIT_REACHED: User {user_id} reached topic limit ({len(active_topics)}/{MAX_ACTIVE_TOPICS}) when trying to add topic")
            return

        # Если лимит не достигнут, переходим к вводу названия темы
        context.user_data["state"] = "awaiting_topic_name"
        await update.message.reply_text(
            get_text('enter_topic_name', language),
            reply_markup=ReplyKeyboardMarkup([[get_text('cancel', language)]], resize_keyboard=True)
        )

        logger.info(f"USER_ACTION: User {user_id} starting to add new topic ({len(active_topics)}/{MAX_ACTIVE_TOPICS})")
        return

    if text == main_commands_list[2]:  # Удалить тему / Delete Topic
        await show_delete_categories(update, context, user_id, language)
        return

    if text == main_commands_list[3]:  # Восстановить тему / Restore Topic
        await show_restore_categories(update, context, user_id, language)
        return

    if text == main_commands_list[4]:  # Категории / Categories
        # ПРОВЕРКА ЛИМИТА ПРИ СОЗДАНИИ КАТЕГОРИИ
        categories = db.get_categories(user_id)

        keyboard = [
            [
                InlineKeyboardButton(get_text('create_category', language), callback_data="category_action:create"),
                InlineKeyboardButton(get_text('rename_category', language), callback_data="category_action:rename"),
            ],
            [
                InlineKeyboardButton(get_text('move_topic', language), callback_data="category_action:move"),
                InlineKeyboardButton(get_text('delete_category', language), callback_data="category_action:delete"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Используем get_text для limit_info
        limit_info = get_text('categories_limit_info', language, current=len(categories), max=MAX_CATEGORIES)

        message_text = get_text('select_category_action', language)
        if limit_info:
            message_text += limit_info

        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_category_action"
        return

    if text == get_text('cancel', language):
        context.user_data["state"] = None
        context.user_data.clear()
        await update.message.reply_text(
            get_text('action_canceled', language),
            reply_markup=get_main_keyboard(language)
        )
        return

    if state == "awaiting_topic_name":
        if text == get_text('cancel', language):
            context.user_data["state"] = None
            context.user_data.clear()
            await update.message.reply_text(
                get_text('action_canceled', language),
                reply_markup=get_main_keyboard(language)
            )
            return

        context.user_data["new_topic_name"] = text
        categories = db.get_categories(user_id)
        keyboard = [
            [InlineKeyboardButton(category.category_name, callback_data=f"add_topic_category:{category.category_id}")]
            for category in categories
        ]
        keyboard.append([InlineKeyboardButton(get_text('no_category', language, default="Без категории"),
                                              callback_data="add_topic_category:none")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Логирование создания темы
        logger.info(f"USER_ACTION: User {user_id} creating topic '{text}'")

        await update.message.reply_text(
            get_text('select_category_for_topic', language) if 'select_category_for_topic' in TRANSLATIONS.get(language,
                                                                                                               {})
            else "Выбери категорию для темы:",
            reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_topic_category"
        return

    # Если команда не распознана
    await update.message.reply_text(
        get_text('unknown_command', language),
        reply_markup=get_main_keyboard(language)
    )


async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для очистки дубликатов напоминаний"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested cleanup of duplicate reminders")

    # Проверяем, что это администратор (добавьте свою логику проверки)
    # Пока разрешаем всем для тестирования

    try:
        removed_count = db.cleanup_duplicate_reminders()

        if removed_count > 0:
            await update.message.reply_text(
                f"✅ Очистка завершена! Удалено {removed_count} дубликатов напоминаний."
            )
        else:
            await update.message.reply_text(
                "✅ Дубликатов не найдено. База данных в порядке!"
            )

    except Exception as e:
        logger.error(f"Error in cleanup_command: {str(e)}")
        await update.message.reply_text(
            f"❌ Ошибка при очистке: {str(e)}"
        )

@retry(
    stop=stop_after_attempt(3),  # 3 попытки
    wait=wait_exponential(multiplier=1, min=2, max=10),  # экспоненциальная задержка
    retry=retry_if_exception_type((TimedOut, NetworkError)),  # повторяем только при таймаутах и сетевых ошибках
    reraise=True
)
async def send_reminder_with_retry(bot, user_id: int, topic_name: str, reminder_id: int):
    """Отправляет напоминание с повторными попытками при таймаутах"""
    try:
        user = db.get_user(user_id)
        username_display = f"@{user.username}" if user and user.username else f"user_{user_id}"

        if not user:
            logger.error(f"REMINDER_ERROR: User {user_id} not found for reminder {reminder_id}")
            return

        # Получаем язык пользователя
        language = user.language if user else 'ru'

        topic = db.get_topic_by_reminder_id(reminder_id, user_id, user.timezone)
        if not topic:
            logger.error(f"REMINDER_ERROR: Topic not found for reminder {reminder_id}")
            return

        button_text = get_text('repeated_button', language)
        keyboard = [[InlineKeyboardButton(button_text, callback_data=f"repeated:{reminder_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        logger.info(
            f"REMINDER_ATTEMPT: Attempting to send reminder {reminder_id} for topic '{topic_name}' to user {user_id} ({username_display})")

        await bot.send_message(
            chat_id=user_id,
            text=get_text('reminder_time', language, topic_name=topic_name),
            reply_markup=reply_markup
        )

        logger.info(
            f"REMINDER_SUCCESS: Successfully sent reminder {reminder_id} for topic '{topic_name}' to user {user_id} ({username_display})")

    except Exception as e:
        logger.error(f"REMINDER_ERROR: Failed to send reminder {reminder_id} to user {user_id}: {str(e)}")
        raise  # Пробрасываем исключение для tenacity


async def send_reminder(bot, user_id: int, topic_name: str, reminder_id: int):
    """Основная функция отправки напоминания с обработкой ошибок и резервным планированием"""
    try:
        await send_reminder_with_retry(bot, user_id, topic_name, reminder_id)
    except Exception as e:
        logger.error(f"REMINDER_FINAL_ERROR: All retries failed for reminder {reminder_id} to user {user_id}: {str(e)}")

        # Пытаемся перепланировать через 5 минут
        try:
            await reschedule_failed_reminder(bot, user_id, topic_name, reminder_id)
        except Exception as reschedule_error:
            logger.error(
                f"REMINDER_RESCHEDULE_CRITICAL: Cannot reschedule reminder {reminder_id}: {str(reschedule_error)}")


async def reschedule_failed_reminder(bot, user_id: int, topic_name: str, reminder_id: int):
    """Перепланирует неудачное напоминание через 5 минут"""
    try:
        user = db.get_user(user_id)
        if not user:
            return

        tz = pytz.timezone(user.timezone)
        retry_time = datetime.now(tz) + timedelta(minutes=5)

        scheduler.add_job(
            send_reminder,
            "date",
            run_date=retry_time,
            args=[bot, user_id, topic_name, reminder_id],
            id=f"reminder_retry_{reminder_id}_{user_id}",
            timezone=tz,
            misfire_grace_time=None
        )

        logger.info(
            f"REMINDER_RESCHEDULED: Rescheduled reminder {reminder_id} for topic '{topic_name}' to {retry_time}")

    except Exception as e:
        logger.error(f"REMINDER_RESCHEDULE_ERROR: Failed to reschedule reminder {reminder_id}: {str(e)}")


async def send_reactivation_message(bot, user_id: int, stage: int):
    """Отправляет реактивационное сообщение пользователю"""
    try:
        user = db.get_user(user_id)
        if not user:
            logger.warning(f"REACTIVATION: User {user_id} not found in database")
            return

        # Определяем тип сообщения по стадии
        if stage == 1:
            mood = "friendly"
        elif stage == 2:
            mood = "sad"
        elif stage == 3:
            mood = "angry"
        elif stage == 4:
            mood = "final_warning"
        else:
            logger.warning(f"REACTIVATION: Unknown stage {stage} for user {user_id}")
            return

        # Используем get_kex_message вместо REACTIVATION_MESSAGES
        message_data = get_kex_message(mood, user.language)
        if not message_data:
            logger.error(f"REACTIVATION: No messages found for mood {mood} and language {user.language}")
            return

        text = message_data["text"]
        image_filename = message_data["image"]

        logger.info(f"REACTIVATION: Sending {mood} message to user {user_id}: '{text}' with image: {image_filename}")

        # Пробуем отправить с изображением
        try:
            # Сначала проверяем существует ли файл
            image_path = f"images/{image_filename}"
            logger.info(f"REACTIVATION: Looking for image at: {image_path}")

            if os.path.exists(image_path):
                logger.info(f"REACTIVATION: Image found, sending with photo...")
                with open(image_path, 'rb') as photo:
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=photo,
                        caption=text
                    )
                logger.info(f"REACTIVATION: Photo sent successfully to user {user_id}")
            else:
                logger.warning(f"REACTIVATION: Image not found at {image_path}, sending text only")
                await bot.send_message(
                    chat_id=user_id,
                    text=text
                )

        except Exception as photo_error:
            logger.error(f"REACTIVATION: Failed to send photo to user {user_id}: {str(photo_error)}")
            # Fallback - отправляем только текст
            logger.info(f"REACTIVATION: Falling back to text message for user {user_id}")
            await bot.send_message(
                chat_id=user_id,
                text=text
            )

        # Обновляем стадию в БД
        db.update_reactivation_stage(user_id, stage)

        logger.info(f"REACTIVATION: Successfully sent {mood} message to user {user_id} (stage {stage})")

    except Exception as e:
        logger.error(f"REACTIVATION_ERROR: Failed to send reactivation to user {user_id}: {str(e)}")


async def check_inactive_users(app: Application):
    """Проверяет неактивных пользователей и отправляет реактивационные сообщения"""
    try:
        logger.info("REACTIVATION: Checking inactive users...")

        # Выбираем stages в зависимости от режима
        if TEST_MODE:
            stages = REACTIVATION_STAGES_TEST
            logger.info("REACTIVATION: Using TEST mode with reduced timings")
        else:
            stages = REACTIVATION_STAGES_PROD
            logger.info("REACTIVATION: Using PRODUCTION mode")

        for days, stage in stages:
            inactive_users = db.get_inactive_users(days)

            # ДОБАВЛЯЕМ ИНФОРМАЦИЮ О USERNAME В ЛОГ
            user_info = []
            for user_reactivation in inactive_users:
                user = db.get_user(user_reactivation.user_id)
                username_display = f"@{user.username}" if user and user.username else f"user_{user_reactivation.user_id}"
                user_info.append(f"{user_reactivation.user_id} ({username_display})")

            logger.info(
                f"REACTIVATION: Found {len(inactive_users)} users inactive for {days} days (stage {stage}): {', '.join(user_info)}")

            for user_reactivation in inactive_users:
                # Получаем username для логирования
                user = db.get_user(user_reactivation.user_id)
                username_display = f"@{user.username}" if user and user.username else f"user_{user_reactivation.user_id}"

                # Проверяем, не отправляли ли уже сообщение этой стадии
                if user_reactivation.reactivation_stage < stage:
                    logger.info(
                        f"REACTIVATION: Sending stage {stage} message to user {user_reactivation.user_id} ({username_display})")
                    await send_reactivation_message(app.bot, user_reactivation.user_id, stage)
                    # Делаем небольшую паузу между сообщениями
                    await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"REACTIVATION_ERROR: Failed to check inactive users: {str(e)}")


async def check_overdue_for_user(app: Application, user_id: int):
    """Проверяет и отправляет просроченные напоминания для пользователя"""
    try:
        user = db.get_user(user_id)
        if not user:
            logger.warning(f"OVERDUE_CHECK: User {user_id} not found")
            return

        # Получаем язык пользователя
        language = user.language if user else 'ru'

        tz = pytz.timezone(user.timezone)
        now_utc = datetime.utcnow()
        now_local = pytz.utc.localize(now_utc).astimezone(tz)

        topics = db.get_active_topics(user_id, user.timezone, 'all')
        overdue_count = 0

        for topic in topics:
            if topic.next_review is None or topic.is_completed:
                continue

            next_review_utc = topic.next_review  # utc naive
            next_review_local = db._from_utc_naive(next_review_utc, user.timezone)

            if next_review_local < now_local:
                # Создаем временное напоминание для кнопки
                reminder_id = db.add_reminder(user_id, topic.topic_id, now_utc)
                button_text = get_text('repeated_button', language)
                keyboard = [[InlineKeyboardButton(button_text, callback_data=f"repeated:{reminder_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await app.bot.send_message(
                    chat_id=user_id,
                    text=get_text('overdue_reminder', language, topic_name=topic.topic_name),
                    reply_markup=reply_markup
                )
                overdue_count += 1
                logger.info(f"OVERDUE_SENT: Sent overdue reminder for topic '{topic.topic_name}' to user {user_id}")

        if overdue_count > 0:
            logger.info(f"OVERDUE_SUMMARY: Sent {overdue_count} overdue reminders to user {user_id}")

    except Exception as e:
        logger.error(f"OVERDUE_ERROR: Failed to check overdue for user {user_id}: {str(e)}")


def schedule_daily_check(user_id: int, timezone: str):
    job_id = f"daily_check_{user_id}"
    reactivation_job_id = f"reactivation_{user_id}"

    # Удаляем старые задания если есть
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    if scheduler.get_job(reactivation_job_id):
        scheduler.remove_job(reactivation_job_id)

    # Задание для проверки просроченных тем
    scheduler.add_job(
        check_overdue_for_user,
        'cron',
        hour=9,
        minute=0,
        timezone=timezone,
        args=[app, user_id],
        id=job_id
    )

    # Задание для реактивации
    scheduler.add_job(
        check_inactive_users,
        'cron',
        hour=22,
        minute=10,
        timezone=timezone,
        args=[app],
        id=reactivation_job_id
    )

    logger.debug(f"Scheduled daily checks for user {user_id} at 9:00 and reactivation at 19:00 {timezone}")


async def init_scheduler_optimized(app: Application):
    """Оптимизированная инициализация планировщика с пагинацией"""
    logger.info("🚀 Starting OPTIMIZED scheduler initialization")

    batch_size = 100  # Обрабатываем по 100 пользователей за раз
    offset = 0
    total_scheduled = 0
    total_overdue = 0
    total_users_processed = 0

    start_time = time.time()

    while True:
        # Получаем пачку пользователей
        users = db.get_users_batch(offset, batch_size)
        if not users:
            break

        user_count = len(users)
        total_users_processed += user_count
        logger.info(
            f"📦 Processing batch {offset // batch_size + 1}: {user_count} users (total: {total_users_processed})")

        # Получаем ID пользователей
        user_ids = [user.user_id for user in users]

        # ОДИН запрос для всех активных тем этих пользователей
        all_topics = db.get_active_topics_batch(user_ids)

        # Группируем темы по пользователям
        topics_by_user = {}
        for topic in all_topics:
            if topic.user_id not in topics_by_user:
                topics_by_user[topic.user_id] = []
            topics_by_user[topic.user_id].append(topic)

        # Получаем ID всех тем
        topic_ids = [topic.topic_id for topic in all_topics]

        # ОДИН запрос для всех напоминаний этих тем
        reminders_dict = db.get_reminders_batch(topic_ids)

        # Обрабатываем каждого пользователя в пачке
        batch_scheduled = 0
        batch_overdue = 0

        for user in users:
            user_topics = topics_by_user.get(user.user_id, [])
            user_scheduled = 0
            user_overdue = 0

            tz = pytz.timezone(user.timezone)
            now_local = datetime.now(tz)

            for topic in user_topics:
                # Берем напоминание из словаря (быстрый доступ)
                reminder = reminders_dict.get(topic.topic_id)

                if topic.next_review is None or topic.is_completed:
                    continue

                next_review_local = db._from_utc_naive(topic.next_review, user.timezone)

                if next_review_local < now_local:
                    # Просроченная тема
                    if reminder:
                        reminder_id = reminder.reminder_id
                    else:
                        reminder_id = db.add_reminder(user.user_id, topic.topic_id, datetime.utcnow())

                    # Отправляем напоминание сразу
                    button_text = get_text('repeated_button', user.language)
                    keyboard = [[InlineKeyboardButton(button_text, callback_data=f"repeated:{reminder_id}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    try:
                        await app.bot.send_message(
                            chat_id=user.user_id,
                            text=get_text('overdue_reminder', user.language, topic_name=topic.topic_name),
                            reply_markup=reply_markup
                        )
                        user_overdue += 1
                        logger.debug(f"Sent overdue reminder for topic '{topic.topic_name}' to user {user.user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send overdue reminder to user {user.user_id}: {str(e)}")

                else:
                    # Планируем напоминание
                    if reminder:
                        reminder_id = reminder.reminder_id
                    else:
                        reminder_id = db.add_reminder(user.user_id, topic.topic_id, topic.next_review)

                    # Добавляем в планировщик
                    scheduler.add_job(
                        send_reminder,
                        "date",
                        run_date=next_review_local,
                        args=[app.bot, user.user_id, topic.topic_name, reminder_id],
                        id=f"reminder_{reminder_id}_{user.user_id}",
                        timezone=tz,
                        misfire_grace_time=None
                    )
                    user_scheduled += 1

            # Планируем ежедневные проверки для пользователя
            schedule_daily_check(user.user_id, user.timezone)

            batch_scheduled += user_scheduled
            batch_overdue += user_overdue

            # Логируем каждые 10 пользователей или последнего
            if user_scheduled > 0 or user_overdue > 0:
                logger.debug(f"User {user.user_id}: {user_scheduled} scheduled, {user_overdue} overdue")

        total_scheduled += batch_scheduled
        total_overdue += batch_overdue

        offset += batch_size

        # Делаем небольшую паузу между пачками, чтобы не перегружать БД
        if len(users) == batch_size:  # Если есть еще пользователи
            await asyncio.sleep(0.1)  # 100ms пауза

    elapsed_time = time.time() - start_time
    total_jobs = len(scheduler.get_jobs())

    logger.info(f"✅ OPTIMIZED initialization COMPLETE in {elapsed_time:.2f} seconds")
    logger.info(
        f"📊 STATS: Users: {total_users_processed}, Scheduled: {total_scheduled}, Overdue: {total_overdue}, Total jobs: {total_jobs}")

    # Глобальное задание для реактивации
    if not scheduler.get_job("global_reactivation_check"):
        scheduler.add_job(
            check_inactive_users,
            'cron',
            hour=19,
            minute=0,
            timezone="UTC",
            args=[app],
            id="global_reactivation_check"
        )

    return total_scheduled, total_overdue


async def init_scheduler(app: Application):
    users = db.get_all_users()
    logger.info(f"Initializing scheduler for {len(users)} users")

    total_scheduled = 0
    total_overdue = 0

    for i, user in enumerate(users, 1):
        # ДОБАВЛЯЕМ USERNAME В ЛОГ
        username_display = f"@{user.username}" if user.username else f"user_{user.user_id}"
        logger.info(f"Processing user {i}/{len(users)}: {user.user_id} ({username_display})")

        try:
            # Получаем язык пользователя
            language = user.language if user else 'ru'

            active_topics = db.get_active_topics(user.user_id, user.timezone, category_id='all')
            logger.info(f"User {user.user_id} ({username_display}) has {len(active_topics)} active topics")

            tz = pytz.timezone(user.timezone)
            scheduled_count = 0
            overdue_count = 0

            for topic in active_topics:
                if topic.next_review is None or topic.is_completed:
                    continue

                next_review_local = db._from_utc_naive(topic.next_review, user.timezone)
                now_local = datetime.now(tz)

                # Ищем существующее напоминание для этой темы
                existing_reminder = db.get_reminder_by_topic(topic.topic_id)

                if next_review_local < now_local:
                    # Тема просрочена
                    if existing_reminder:
                        reminder_id = existing_reminder.reminder_id
                    else:
                        reminder_id = db.add_reminder(user.user_id, topic.topic_id, datetime.utcnow())

                    button_text = get_text('repeated_button', language)
                    keyboard = [[InlineKeyboardButton(button_text, callback_data=f"repeated:{reminder_id}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await app.bot.send_message(
                        chat_id=user.user_id,
                        text=get_text('overdue_reminder', language, topic_name=topic.topic_name),
                        reply_markup=reply_markup
                    )
                    overdue_count += 1
                    logger.info(
                        f"OVERDUE_SENT: Sent overdue reminder for topic '{topic.topic_name}' to user {user.user_id} ({username_display})")

                else:
                    # Тема не просрочена - планируем напоминание
                    if existing_reminder:
                        reminder_id = existing_reminder.reminder_id
                    else:
                        reminder_id = db.add_reminder(user.user_id, topic.topic_id, topic.next_review)

                    scheduler.add_job(
                        send_reminder,
                        "date",
                        run_date=next_review_local,
                        args=[app.bot, user.user_id, topic.topic_name, reminder_id],
                        id=f"reminder_{reminder_id}_{user.user_id}",
                        timezone=tz,
                        misfire_grace_time=None
                    )
                    scheduled_count += 1
                    logger.debug(
                        f"Scheduled reminder {reminder_id} for topic '{topic.topic_name}' to user {user.user_id} ({username_display}) at {next_review_local}")

            schedule_daily_check(user.user_id, user.timezone)

            total_scheduled += scheduled_count
            total_overdue += overdue_count

            logger.info(
                f"SCHEDULER_STATS: User {user.user_id} ({username_display}) - {scheduled_count} reminders scheduled, {overdue_count} overdue sent")

        except Exception as e:
            logger.error(f"Error processing user {user.user_id} ({username_display}): {str(e)}")
            continue

    # Глобальное задание для реактивации
    if not scheduler.get_job("global_reactivation_check"):
        scheduler.add_job(
            check_inactive_users,
            'cron',
            hour=19,
            minute=0,
            timezone="UTC",
            args=[app],
            id="global_reactivation_check"
        )

    total_jobs = len(scheduler.get_jobs())
    logger.info(
        f"Scheduler initialization complete. Total jobs: {total_jobs}, Total scheduled: {total_scheduled}, Total overdue: {total_overdue}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    text = "Ой, что-то пошло не так! 😿 Попробуй снова или используй /reset."
    if update and update.effective_message:
        await update.effective_message.reply_text(
            text,
            reply_markup=MAIN_KEYBOARD
        )


# Временный скрипт для исправления
def fix_missing_reminders():
    users = db.get_all_users()
    for user in users:
        topics = db.get_active_topics(user.user_id, user.timezone, category_id='all')
        for topic in topics:
            existing_reminder = db.get_reminder_by_topic(topic.topic_id)
            if not existing_reminder:
                # Создаем недостающее напоминание
                reminder_id = db.add_reminder(user.user_id, topic.topic_id, topic.next_review)
                logger.info(f"Created missing reminder {reminder_id} for topic {topic.topic_id}")


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

    # ВАЖНО: Очищаем дубликаты при запуске
    try:
        logger.info("Checking for duplicate reminders...")
        removed = db.cleanup_duplicate_reminders()
        if removed > 0:
            logger.info(f"Removed {removed} duplicate reminders on startup")
    except Exception as e:
        logger.error(f"Failed to cleanup duplicates on startup: {e}")
        # Не прерываем запуск, продолжаем

    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tz", handle_timezone))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("cleanup", cleanup_command))
    app.add_handler(CommandHandler("perf", perf_test))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("lang", language_command))

    # Запускаем планировщик
    try:
        scheduler.start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise

    # Инициализируем планировщик с ОПТИМИЗИРОВАННОЙ версией
    try:
        await init_scheduler_optimized(app)
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