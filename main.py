import logging.handlers
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


def setup_logging():
    """Настройка логирования с автоматическим переключением файлов по дням"""

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

    # Файловый обработчик
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Очистка старых обработчиков
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Добавление новых обработчиков
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Тихие библиотеки
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info(f"Логирование запущено в файл: {log_file}")
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
        # Убрал parse_mode чтобы избежать ошибок форматирования
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

    if data.startswith("delete_category_select:"):
        category_id_str = data.split(":", 1)[1]
        category_id = int(category_id_str) if category_id_str != "none" else None

        # Получаем темы для выбранной категории
        topics = db.get_active_topics(user_id, user.timezone, category_id=category_id)

        if not topics:
            await query.answer("В этой категории нет тем для удаления! 😿")
            return

        # Создаем клавиатуру с темами выбранной категории
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

        # Добавляем кнопку "Назад к категориям"
        keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_delete_categories")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        category_name = db.get_category(category_id, user_id).category_name if category_id else "📁 Без категории"
        await query.message.edit_text(
            f"Выбери тему для удаления из категории '{category_name}':",
            reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_topic_deletion"
        await query.answer()
        return

    if data == "delete_all_topics":
        # Оставляем старый функционал для тех, кто хочет видеть все темы сразу
        topics = db.get_active_topics(user_id, user.timezone, category_id='all')
        if not topics:
            await query.answer("У тебя нет тем для удаления! 😿")
            return

        # Ограничиваем количество выводимых тем (например, первые 20)
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

        # Если тем больше 20, показываем сообщение
        if len(topics) > 20:
            keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_delete_categories")])
            await query.message.edit_text(
                f"Слишком много тем для отображения ({len(topics)}). Показаны первые 20. Лучше используй выбор по категориям.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_delete_categories")])
            await query.message.edit_text(
                "Выбери тему для удаления (восстановить будет нельзя):",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        context.user_data["state"] = "awaiting_topic_deletion"
        await query.answer()
        return

    if data == "back_to_delete_categories":
        # Возвращаемся к выбору категорий
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
                    f"📁 Без категории ({len(topics_no_category)})",
                    callback_data="delete_category_select:none"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("🔍 Все темы сразу", callback_data="delete_all_topics")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "Выбери категорию для удаления тем:",
            reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_delete_category"
        await query.answer()
        return

    if data.startswith("delete:"):
        topic_id = int(data.split(":", 1)[1])

        # Сначала получаем все напоминания ДО удаления темы
        reminders = db.get_reminders_by_topic(topic_id)

        if db.delete_topic(topic_id, user_id):
            # Удаляем все напоминания этой темы из планировщика
            for reminder in reminders:
                job_id = f"reminder_{reminder.reminder_id}_{user_id}"
                job = scheduler.get_job(job_id)
                if job:
                    job.remove()  # Исправлено: используем job.remove() вместо scheduler.remove_job()
                    logger.debug(f"Removed scheduled job {job_id} for deleted topic")
                else:
                    logger.debug(f"Job {job_id} not found in scheduler (maybe already executed)")

            await query.message.delete()
            await query.message.reply_text(
                "Тема и все связанные напоминания удалены! 😿",
                reply_markup=MAIN_KEYBOARD
            )
            logger.debug(f"User {user_id} deleted topic {topic_id} with all reminders")
        else:
            await query.message.delete()
            await query.message.reply_text(
                "Тема не найдена. 😿",
                reply_markup=MAIN_KEYBOARD
            )
        context.user_data["state"] = None
        await query.answer()
        return

    if data.startswith("restore_category_select:"):
        category_id_str = data.split(":", 1)[1]
        category_id = int(category_id_str) if category_id_str != "none" else None

        # Получаем все завершенные темы
        completed_topics = db.get_completed_topics(user_id)

        # Фильтруем темы по выбранной категории
        if category_id is not None:
            filtered_topics = [t for t in completed_topics if t.category_id == category_id]
        else:
            filtered_topics = [t for t in completed_topics if t.category_id is None]

        if not filtered_topics:
            await query.answer("В этой категории нет завершённых тем! 😿")
            return

        # Создаем клавиатуру с темами выбранной категории
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
        await query.answer()
        return

    if data == "restore_all_topics":
        completed_topics = db.get_completed_topics(user_id)
        if not completed_topics:
            await query.answer("У тебя нет завершённых тем для восстановления! 😿")
            return

        # Ограничиваем количество выводимых тем
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
            keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_restore_categories")])
            await query.message.edit_text(
                f"Слишком много тем для отображения ({len(completed_topics)}). Показаны первые 20. Лучше используй выбор по категориям.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_restore_categories")])
            await query.message.edit_text(
                "Выбери завершённую тему для восстановления:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        context.user_data["state"] = "awaiting_topic_restoration"
        await query.answer()
        return

    if data == "back_to_restore_categories":
        # Возвращаемся к выбору категорий для восстановления
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
        await query.message.edit_text(
            "Выбери категорию для восстановления тем:",
            reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_restore_category"
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

        # Сначала проверяем, существует ли вообще такое напоминание
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
        categories = db.get_categories(user_id)
        if not categories and not db.get_active_topics(user_id, user.timezone, category_id=None):
            await update.message.reply_text(
                "У тебя нет тем для удаления! 😿",
                reply_markup=MAIN_KEYBOARD
            )
            return

        keyboard = []
        # Добавляем кнопки для категорий
        for category in categories:
            # Получаем количество тем в категории для отображения
            topics_in_category = db.get_active_topics(user_id, user.timezone, category.category_id)
            if topics_in_category:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{category.category_name} ({len(topics_in_category)})",
                        callback_data=f"delete_category_select:{category.category_id}"
                    )
                ])

        # Добавляем кнопку для тем без категории
        topics_no_category = db.get_active_topics(user_id, user.timezone, category_id=None)
        if topics_no_category:
            keyboard.append([
                InlineKeyboardButton(
                    f"📁 Без категории ({len(topics_no_category)})",
                    callback_data="delete_category_select:none"
                )
            ])

        # Добавляем кнопку "Все темы" (опционально, если нужно)
        keyboard.append([
            InlineKeyboardButton("🔍 Все темы сразу", callback_data="delete_all_topics")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выбери категорию для удаления тем:",
            reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_delete_category"
        return

    if text == "Восстановить тему":
        completed_topics = db.get_completed_topics(user_id)
        if not completed_topics:
            await update.message.reply_text(
                "У тебя нет завершённых тем для восстановления! 😺",
                reply_markup=MAIN_KEYBOARD
            )
            return

        # Группируем завершенные темы по категориям
        categories_dict = {}
        no_category_topics = []

        for topic in completed_topics:
            if topic.category_id:
                if topic.category_id not in categories_dict:
                    # Получаем название категории
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

        # Добавляем кнопки для категорий
        for category_id, category_data in categories_dict.items():
            if category_data['topics']:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{category_data['name']} ({len(category_data['topics'])})",
                        callback_data=f"restore_category_select:{category_id}"
                    )
                ])

        # Добавляем кнопку для тем без категории
        if no_category_topics:
            keyboard.append([
                InlineKeyboardButton(
                    f"📁 Без категории ({len(no_category_topics)})",
                    callback_data="restore_category_select:none"
                )
            ])

        # Добавляем кнопку "Все темы"
        keyboard.append([
            InlineKeyboardButton("🔍 Все темы сразу", callback_data="restore_all_topics")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выбери категорию для восстановления тем:",
            reply_markup=reply_markup
        )
        context.user_data["state"] = "awaiting_restore_category"
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