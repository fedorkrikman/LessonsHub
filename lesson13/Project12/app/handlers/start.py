from aiogram import types
from aiogram.filters.command import Command
from app.db.quiz import get_quiz_state
from app.handlers.common import build_quiz_keyboard


def register_start(dp):
    """Регистрирует обработчики команды /start"""
    
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        state = await get_quiz_state(message.from_user.id)
        is_active = bool(state and state.get("is_active"))
        await message.answer(
            "Добро пожаловать в квиз!",
            reply_markup=build_quiz_keyboard(is_active),
        )
