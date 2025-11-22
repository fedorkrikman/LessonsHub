from typing import Any, Dict, Optional

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from database import execute_select_query, execute_update_query, pool

START_BUTTON_TEXT = "Начать игру"
STOP_BUTTON_TEXT = "Прервать и показать результаты"

quiz_data = [
    {
        "question": "Что такое Python?",
        "options": [
            "Язык программирования",
            "Тип данных",
            "Музыкальный инструмент",
            "Змея на английском",
        ],
        "correct_option": 0,
    },
    {
        "question": "Какой тип данных используется для хранения целых чисел?",
        "options": ["int", "float", "str", "natural"],
        "correct_option": 0,
    },
    {
        "question": "Какой тип данных используется для хранения вещественных чисел?",
        "options": ["float", "int", "complex", "double"],
        "correct_option": 0,
    },
    {
        "question": "Какой оператор используется для возведения в степень?",
        "options": ["**", "^", "exp()", "//"],
        "correct_option": 0,
    },
    {
        "question": "Как называется структура данных, изменяемая и индексируемая, позволяющая хранить последовательности?",
        "options": ["list", "tuple", "set", "dict"],
        "correct_option": 0,
    },
    {
        "question": "Какой тип данных представляет неизменяемую последовательность?",
        "options": ["tuple", "list", "set", "dict"],
        "correct_option": 0,
    },
    {
        "question": "Какой метод строки позволяет перевести её в нижний регистр?",
        "options": ["lower()", "down()", "to_lower()", "small()"],
        "correct_option": 0,
    },
    {
        "question": "Какой оператор сравнения проверяет равенство значений?",
        "options": ["==", "=", "!=", "==="],
        "correct_option": 0,
    },
    {
        "question": "Какой цикл используется для перебора элементов последовательности?",
        "options": ["for", "while", "loop", "repeat"],
        "correct_option": 0,
    },
    {
        "question": "Как называется структура данных, использующая пары «ключ–значение»?",
        "options": ["dict", "list", "tuple", "array"],
        "correct_option": 0,
    },
    {
        "question": "Какой встроенный тип данных представляет множество уникальных элементов?",
        "options": ["set", "list", "dict", "array"],
        "correct_option": 0,
    },
    {
        "question": "Какой оператор используется для целочисленного деления?",
        "options": ["//", "/", "%", "div"],
        "correct_option": 0,
    },
]


def build_quiz_keyboard(is_active: bool) -> types.ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    text = STOP_BUTTON_TEXT if is_active else START_BUTTON_TEXT
    builder.add(types.KeyboardButton(text=text))
    return builder.as_markup(resize_keyboard=True)


def format_results(username: str, correct: int, incorrect: int) -> str:
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


async def new_quiz(message: types.Message, user_id: int, question_index: int = 0) -> bool:
    if question_index >= len(quiz_data):
        return False

    question = quiz_data[question_index]
    builder = InlineKeyboardBuilder()
    for option_index, option in enumerate(question["options"]):
        builder.add(
            types.InlineKeyboardButton(
                text=option,
                callback_data=f"quiz_answer_{question_index}_{option_index}",
            )
        )
    builder.adjust(1)

    header = f"Вопрос {question_index + 1}/{len(quiz_data)}:\n{question['question']}"
    await message.answer(header, reply_markup=builder.as_markup())
    await set_question_index(user_id, question_index)
    return True


async def start_quiz_session(user_id: int, username: str) -> None:
    query = """
        DECLARE $user_id AS Uint64;
        DECLARE $username AS Utf8;

        UPSERT INTO `quiz_state` (
            `user_id`,
            `username`,
            `question_index`,
            `correct_answers`,
            `incorrect_answers`,
            `is_active`
        ) VALUES (
            $user_id,
            $username,
            0u,
            0u,
            0u,
            true
        );
    """
    execute_update_query(pool, query, user_id=user_id, username=username)


async def set_question_index(user_id: int, question_index: int) -> None:
    query = """
        DECLARE $user_id AS Uint64;
        DECLARE $question_index AS Uint64;

        UPDATE `quiz_state`
        SET question_index = $question_index
        WHERE user_id == $user_id;
    """
    execute_update_query(
        pool,
        query,
        user_id=user_id,
        question_index=question_index,
    )


async def record_answer(user_id: int, is_correct: bool) -> None:
    column = "correct_answers" if is_correct else "incorrect_answers"
    query = f"""
        DECLARE $user_id AS Uint64;

        UPDATE `quiz_state`
        SET {column} = COALESCE({column}, 0u) + 1u
        WHERE user_id == $user_id;
    """
    execute_update_query(pool, query, user_id=user_id)


async def get_quiz_state(user_id: int) -> Optional[Dict[str, Any]]:
    query = """
        DECLARE $user_id AS Uint64;

        SELECT user_id, username, question_index, correct_answers, incorrect_answers, is_active
        FROM `quiz_state`
        WHERE user_id == $user_id;
    """
    rows = execute_select_query(pool, query, user_id=user_id)
    if not rows:
        return None
    return _row_to_dict(rows[0])


async def finish_quiz_session(user_id: int) -> Optional[Dict[str, Any]]:
    state = await get_quiz_state(user_id)
    if not state:
        return None
    query = """
        DECLARE $user_id AS Uint64;

        UPDATE `quiz_state`
        SET is_active = false,
            question_index = 0u
        WHERE user_id == $user_id;
    """
    execute_update_query(pool, query, user_id=user_id)
    return state


def _row_to_dict(row: Any) -> Dict[str, Any]:
    def _value(key: str, default: Any = None) -> Any:
        try:
            value = row[key]
        except (KeyError, IndexError):
            return default
        return default if value is None else value

    return {
        "user_id": _value("user_id"),
        "username": _value("username"),
        "question_index": _value("question_index", 0),
        "correct_answers": _value("correct_answers", 0),
        "incorrect_answers": _value("incorrect_answers", 0),
        "is_active": bool(_value("is_active", False)),
    }
