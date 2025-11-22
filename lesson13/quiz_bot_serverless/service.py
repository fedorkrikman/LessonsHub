"""
Общие сервисные функции для клавиатур и форматирования сообщений.
"""

from aiogram import types
from aiogram.utils.keyboard import ReplyKeyboardBuilder

START_BUTTON_TEXT = "Начать игру"
STOP_BUTTON_TEXT = "Прервать и показать результаты"


def build_quiz_keyboard(is_active: bool) -> types.ReplyKeyboardMarkup:
    """Создает клавиатуру с кнопками запуска или остановки квиза."""
    builder = ReplyKeyboardBuilder()
    button_text = STOP_BUTTON_TEXT if is_active else START_BUTTON_TEXT
    builder.add(types.KeyboardButton(text=button_text))
    return builder.as_markup(resize_keyboard=True)


def format_results(username: str, correct: int, incorrect: int) -> str:
    """Формирует текст итоговой статистики."""
    return "\n".join(
        [
            "--------------",
            '"КВИЗ про python"',
            f"Пользователь [{username}]:",
            f"Правильных ответов: {correct}",
            f"Неправильных ответов: {incorrect}",
            "-------------------",
        ]
    )
