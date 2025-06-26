import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from db import init_db, get_user_id, add_topic, get_progress

from dotenv import load_dotenv
import os

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Добавить тему")],
    [KeyboardButton(text="Удалить тему")],
    [KeyboardButton(text="Мой прогресс")],
], resize_keyboard=True)

user_states = {}  # для временного хранения состояний

@dp.message(CommandStart())
async def start_handler(msg: types.Message):
    await msg.answer("Привет! Введи свой часовой пояс (например, +3 или -5):")
    user_states[msg.from_user.id] = "awaiting_timezone"

@dp.message(F.text.regexp(r'^[-+]?\d+$'))
async def timezone_setter(msg: types.Message):
    if user_states.get(msg.from_user.id) == "awaiting_timezone":
        offset = int(msg.text)
        uid = await get_user_id(msg.from_user.id, offset)
        await msg.answer("Отлично! Теперь можешь добавлять темы.", reply_markup=keyboard)
        user_states.pop(msg.from_user.id, None)

@dp.message(F.text == "Добавить тему")
async def ask_topic(msg: types.Message):
    user_states[msg.from_user.id] = "awaiting_topic"
    await msg.answer("Напиши тему, которую хочешь выучить:")

@dp.message()
async def any_text(msg: types.Message):
    if user_states.get(msg.from_user.id) == "awaiting_topic":
        uid = await get_user_id(msg.from_user.id, 0)  # уже должен быть в базе
        await add_topic(uid, msg.text.strip())
        await msg.answer(f"Тема \"{msg.text.strip()}\" добавлена! Я буду напоминать тебе по кривой забывания 🧠")
        user_states.pop(msg.from_user.id)
    elif msg.text == "Мой прогресс":
        uid = await get_user_id(msg.from_user.id, 0)
        total, pending = await get_progress(uid)
        await msg.answer(f"📚 Тем выучено: {total}\n⏰ Ожидает повторов: {pending}")
    else:
        await msg.answer("Выбери действие на клавиатуре ниже ⬇️", reply_markup=keyboard)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
