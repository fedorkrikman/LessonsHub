from aiogram import F, Router, types
from aiogram.filters import Command

from service import (
    START_BUTTON_TEXT,
    STOP_BUTTON_TEXT,
    build_quiz_keyboard,
    finish_quiz_session,
    format_results,
    get_session_question,
    get_session_question_count,
    get_quiz_state,
    new_quiz,
    record_answer,
    start_quiz_session,
)

# Перенесено из Project12:
# - app/logic.py (quiz_data, new_quiz): последовательность вопросов и inline-кнопки.
# - app/handlers/common.py (кнопки START/STOP): тексты клавиатуры и её построение.
# - app/handlers/start.py (cmd_start): приветствие и показ клавиатуры.
# - app/handlers/quiz.py (cmd_quiz/cmd_stop/process_quiz_answer/_show_results_and_finish):
#   сценарий диалога, обработка ответов и вывод статистики.
# - app/db/quiz.py (start_quiz_session, set_question_index, record_answer, finish_quiz_session, get_quiz_state):
#   операции сохранения состояния в базе.

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    state = await get_quiz_state(message.from_user.id)
    is_active = bool(state and state.get("is_active"))
    await message.answer(
        "Добро пожаловать в квиз!",
        reply_markup=build_quiz_keyboard(is_active),
    )


@router.message(F.text == START_BUTTON_TEXT)
@router.message(Command("quiz"))
async def cmd_quiz(message: types.Message) -> None:
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
    try:
        has_question = await new_quiz(message, user.id, 0)
    except Exception:
        await finish_quiz_session(user.id)
        await message.answer(
            "Не удалось отправить первый вопрос. Попробуйте начать игру позднее.",
            reply_markup=build_quiz_keyboard(False),
        )
        return

    if not has_question:
        await finish_quiz_session(user.id)
        await message.answer(
            "Не удалось найти вопросы для квиза. Попробуйте начать игру позднее.",
            reply_markup=build_quiz_keyboard(False),
        )
        return


@router.message(F.text == STOP_BUTTON_TEXT)
async def cmd_stop(message: types.Message) -> None:
    user_id = message.from_user.id
    state = await get_quiz_state(user_id)
    if not state or not state.get("is_active"):
        await message.answer(
            "Сейчас нет активного квиза.",
            reply_markup=build_quiz_keyboard(False),
        )
        return
    await _show_results_and_finish(message, user_id)


@router.callback_query(F.data.startswith("quiz_answer_"))
async def process_quiz_answer(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    _, _, question_index_str, answer_index_str = callback.data.split("_")
    question_index = int(question_index_str)
    answer_index = int(answer_index_str)

    question = get_session_question(user_id, question_index)
    total_questions = get_session_question_count(user_id)
    if not question or total_questions == 0:
        await callback.message.answer(
            "Не удалось найти вопрос. Запустите квиз заново командой /quiz."
        )
        await callback.answer()
        return

    is_correct = answer_index == question["correct_option"]
    selected_answer = question["options"][answer_index]
    question_header = (
        f"Вопрос {question_index + 1}/{total_questions}:\n{question['question']}"
    )

    await callback.message.edit_text(
        f"{question_header}\n\nВаш ответ: {selected_answer}"
    )

    if is_correct:
        await callback.message.answer("✅ Правильно!")
    else:
        correct_answer = question["options"][question["correct_option"]]
        await callback.message.answer(
            f"❌ Неправильно. Правильный ответ: {correct_answer}"
        )

    await record_answer(user_id, is_correct)
    await callback.answer()

    next_index = question_index + 1
    has_next = await new_quiz(callback.message, user_id, next_index)
    if not has_next:
        await _show_results_and_finish(callback.message, user_id)


async def _show_results_and_finish(message: types.Message, user_id: int) -> None:
    state = await finish_quiz_session(user_id)
    if not state:
        await message.answer(
            "Статистика не найдена.",
            reply_markup=build_quiz_keyboard(False),
        )
        return

    summary = format_results(
        state.get("username") or "Неизвестный пользователь",
        state.get("correct_answers", 0),
        state.get("incorrect_answers", 0),
    )
    await message.answer(summary, reply_markup=build_quiz_keyboard(False))
