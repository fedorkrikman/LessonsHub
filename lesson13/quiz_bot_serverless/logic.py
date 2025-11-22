"""
Логика квиза и структура вопросов, перенесенная из lesson13/Project12/app/logic.py.
"""

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from quiz_state import set_question_index

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


async def new_quiz(message: types.Message, user_id: int, question_index: int = 0) -> bool:
    """Отправляет очередной вопрос пользователю и обновляет состояние."""
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

    question_header = f"Вопрос {question_index + 1}/{len(quiz_data)}:\n{question['question']}"
    await message.answer(question_header, reply_markup=builder.as_markup())
    await set_question_index(user_id, question_index)
    return True
