"""Логика квиза и данные вопросов"""

# Структура квиза
quiz_data = [
    {
        'question': 'Что такое Python?',
        'options': ['Язык программирования', 'Тип данных', 'Музыкальный инструмент', 'Змея на английском'],
        'correct_option': 0
    },
    {
        'question': 'Какой тип данных используется для хранения целых чисел?',
        'options': ['int', 'float', 'str', 'natural'],
        'correct_option': 0
    },
    # Добавьте другие вопросы
    {
        'question': 'Какой тип данных используется для хранения вещественных чисел?',
        'options': ['float', 'int', 'complex', 'double'],
        'correct_option': 0
    },
    {
        'question': 'Какой оператор используется для возведения в степень?',
        'options': ['**', '^', 'exp()', '//'],
        'correct_option': 0
    },
    {
        'question': 'Как называется структура данных, изменяемая и индексируемая, позволяющая хранить последовательности?',
        'options': ['list', 'tuple', 'set', 'dict'],
        'correct_option': 0
    },
    {
        'question': 'Какой тип данных представляет неизменяемую последовательность?',
        'options': ['tuple', 'list', 'set', 'dict'],
        'correct_option': 0
    },
    {
        'question': 'Какой метод строки позволяет перевести её в нижний регистр?',
        'options': ['lower()', 'down()', 'to_lower()', 'small()'],
        'correct_option': 0
    },
    {
        'question': 'Какой оператор сравнения проверяет равенство значений?',
        'options': ['==', '=', '!=', '==='],
        'correct_option': 0
    },
    {
        'question': 'Какой цикл используется для перебора элементов последовательности?',
        'options': ['for', 'while', 'loop', 'repeat'],
        'correct_option': 0
    },
    {
        'question': 'Как называется структура данных, использующая пары «ключ–значение»?',
        'options': ['dict', 'list', 'tuple', 'array'],
        'correct_option': 0
    },
    {
        'question': 'Какой встроенный тип данных представляет множество уникальных элементов?',
        'options': ['set', 'list', 'dict', 'array'],
        'correct_option': 0
    },
    {
        'question': 'Какой оператор используется для целочисленного деления?',
        'options': ['//', '/', '%', 'div'],
        'correct_option': 0
    },
]


async def new_quiz(message, user_id: int, question_index: int = 0):
    """Запускает новый квиз или продолжает существующий. Возвращает True, если вопрос отправлен."""
    from app.db.quiz import set_question_index
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram import types
    
    if question_index >= len(quiz_data):
        return False
    
    question = quiz_data[question_index]
    
    # Создаем инлайн-клавиатуру с вариантами ответов
    builder = InlineKeyboardBuilder()
    for i, option in enumerate(question['options']):
        builder.add(types.InlineKeyboardButton(
            text=option,
            callback_data=f"quiz_answer_{question_index}_{i}"
        ))
    builder.adjust(1)  # По одной кнопке в ряд
    
    await message.answer(
        f"Вопрос {question_index + 1}/{len(quiz_data)}:\n{question['question']}",
        reply_markup=builder.as_markup()
    )
    
    await set_question_index(user_id, question_index)
    return True
