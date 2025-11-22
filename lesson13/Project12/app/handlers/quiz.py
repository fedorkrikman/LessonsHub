from aiogram import types, F
from aiogram.filters.command import Command
from app.logic import new_quiz, quiz_data
from app.db.quiz import (
    start_quiz_session,
    record_answer,
    finish_quiz_session,
    get_quiz_state,
)
from app.handlers.common import (
    build_quiz_keyboard,
    START_BUTTON_TEXT,
    STOP_BUTTON_TEXT,
)


def register_quiz(dp):
    """Регистрирует обработчики квиза"""
    
    @dp.message(F.text == START_BUTTON_TEXT)
    @dp.message(Command("quiz"))
    async def cmd_quiz(message: types.Message):
        user = message.from_user
        state = await get_quiz_state(user.id)
        if state and state.get("is_active"):
            await message.answer(
                "Квиз уже запущен. Отвечайте на вопросы или завершите игру.",
                reply_markup=build_quiz_keyboard(True),
            )
            return
        
        username = user.username or user.full_name or str(user.id)
        await start_quiz_session(user.id, username)
        await message.answer(
            "Давайте начнем квиз!",
            reply_markup=build_quiz_keyboard(True),
        )
        await new_quiz(message, user.id, 0)
    
    @dp.message(F.text == STOP_BUTTON_TEXT)
    async def cmd_stop(message: types.Message):
        user = message.from_user
        state = await get_quiz_state(user.id)
        if not state or not state.get("is_active"):
            await message.answer(
                "Сейчас нет активного квиза.",
                reply_markup=build_quiz_keyboard(False),
            )
            return
        await _show_results_and_finish(message, user.id)
    
    @dp.callback_query(F.data.startswith("quiz_answer_"))
    async def process_quiz_answer(callback: types.CallbackQuery):
        """Обрабатывает ответ пользователя на вопрос квиза"""
        user_id = callback.from_user.id
        # Парсим данные из callback_data: quiz_answer_{question_index}_{answer_index}
        parts = callback.data.split("_")
        question_index = int(parts[2])
        answer_index = int(parts[3])
        
        question = quiz_data[question_index]
        is_correct = answer_index == question['correct_option']
        selected_answer = question['options'][answer_index]
        question_header = f"Вопрос {question_index + 1}/{len(quiz_data)}:\n{question['question']}"
        await callback.message.edit_text(
            f"{question_header}\n\nВаш ответ: {selected_answer}"
        )
        
        if is_correct:
            await callback.message.answer("✅ Правильно!")
        else:
            correct_answer = question['options'][question['correct_option']]
            await callback.message.answer(f"❌ Неправильно. Правильный ответ: {correct_answer}")
        
        await record_answer(user_id, is_correct)
        await callback.answer()
        
        # Переходим к следующему вопросу
        next_index = question_index + 1
        has_next = await new_quiz(callback.message, user_id, next_index)
        if not has_next:
            await _show_results_and_finish(callback.message, user_id)


async def _show_results_and_finish(message: types.Message, user_id: int) -> None:
    """Отправляет статистику пользователя и завершает сессию."""
    state = await finish_quiz_session(user_id)
    if not state:
        await message.answer(
            "Статистика не найдена.",
            reply_markup=build_quiz_keyboard(False),
        )
        return
    username = state.get("username") or "Неизвестный пользователь"
    correct = state.get("correct_answers", 0)
    incorrect = state.get("incorrect_answers", 0)
    summary = "\n".join([
        "--------------",
        "\"КВИЗ про python\"",
        f"Пользователь [{username}]:",
        f"Правильных ответов: {correct}",
        f"Неправильных ответов: {incorrect}",
        "-------------------",
    ])
    await message.answer(summary, reply_markup=build_quiz_keyboard(False))
