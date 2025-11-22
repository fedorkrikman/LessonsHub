from aiogram import types
from aiogram.utils.keyboard import ReplyKeyboardBuilder

START_BUTTON_TEXT = "Начать игру"
STOP_BUTTON_TEXT = "Прервать и показать результаты"


def build_quiz_keyboard(is_active: bool) -> types.ReplyKeyboardMarkup:
    """Создает клавиатуру с кнопкой запуска или прерывания игры."""
    builder = ReplyKeyboardBuilder()
    text = STOP_BUTTON_TEXT if is_active else START_BUTTON_TEXT
    builder.add(types.KeyboardButton(text=text))
    return builder.as_markup(resize_keyboard=True)
