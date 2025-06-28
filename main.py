import os
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from datetime import datetime
import pytz
from db import Database

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db = Database()

# List of common timezones for selection
TIMEZONES = [
    ("UTC-5 (New York)", "America/New_York"),
    ("UTC+0 (London)", "Europe/London"),
    ("UTC+3 (Moscow)", "Europe/Moscow"),
    ("UTC+5 (Yekaterinburg)", "Asia/Yekaterinburg"),
    ("UTC+7 (Bangkok)", "Asia/Bangkok"),
    ("UTC+9 (Tokyo)", "Asia/Tokyo"),
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command and prompt for timezone selection."""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if user and user.timezone:
        await show_main_menu(update, context)
        return

    keyboard = [
        [InlineKeyboardButton(tz[0], callback_data=f"tz_{tz[1]}")] for tz in TIMEZONES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! 😊 Я помогу тебе повторять темы по кривой забывания. "
        "Для начала выбери свой часовой пояс:",
        reply_markup=reply_markup,
    )


async def timezone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle timezone selection."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    timezone = query.data.replace("tz_", "")

    try:
        pytz.timezone(timezone)  # Validate timezone
        db.save_user(user_id, update.effective_user.username, timezone)
        await query.message.reply_text(
            f"Часовой пояс {timezone} сохранен! 😊 Теперь ты можешь добавлять темы и следить за прогрессом."
        )
        await show_main_menu(query, context)
    except pytz.exceptions.UnknownTimeZoneError:
        await query.message.reply_text(
            "Ой, что-то пошло не так с часовым поясом. 😔 Попробуй еще раз с командой /start."
        )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show main menu with buttons."""
    keyboard = [
        ["Добавить тему", "Удалить тему"],
        ["Мой прогресс"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await (update.message or update.callback_query.message).reply_text(
        "Выбери, что хочешь сделать! 😺", reply_markup=reply_markup
    )


def main() -> None:
    """Run the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
        return

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(timezone_callback, pattern="^tz_"))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()