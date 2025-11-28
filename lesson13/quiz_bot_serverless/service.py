import random
from typing import Any, Dict, List, Optional

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from database import execute_select_query, execute_update_query, pool

START_BUTTON_TEXT = "Начать игру"
STOP_BUTTON_TEXT = "Прервать и показать результаты"
QUIZ_COVER_IMAGE_URL = "https://storage.yandexcloud.net/vedro-c-gvozdyami/pythonquizcover.png"

QUESTIONS_PER_SESSION = 5

_OPTION_LETTER_TO_INDEX = {"a": 0, "b": 1, "c": 2, "d": 3}
_QUIZ_SELECT_QUERY = """
    SELECT id, text, option_a, option_b, option_c, option_d, correct_option, points
    FROM `quiz_questions`
    ORDER BY id;
"""
_quiz_data_cache: Optional[List[Dict[str, Any]]] = None
_active_user_questions: Dict[int, List[Dict[str, Any]]] = {}


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def load_quiz_data() -> List[Dict[str, Any]]:
    rows = execute_select_query(pool, _QUIZ_SELECT_QUERY) or []
    loaded_data: List[Dict[str, Any]] = []

    for row in rows:
        correct_letter = str(_row_value(row, "correct_option", "")).lower()
        if correct_letter not in _OPTION_LETTER_TO_INDEX:
            raise ValueError(f"Unexpected correct option value: {correct_letter!r}")

        loaded_data.append(
            {
                "id": _row_value(row, "id"),
                "question": _row_value(row, "text", ""),
                "options": [
                    _row_value(row, "option_a", ""),
                    _row_value(row, "option_b", ""),
                    _row_value(row, "option_c", ""),
                    _row_value(row, "option_d", ""),
                ],
                "correct_option": _OPTION_LETTER_TO_INDEX[correct_letter],
            }
        )
    return loaded_data


def get_quiz_data() -> List[Dict[str, Any]]:
    global _quiz_data_cache
    if _quiz_data_cache is None:
        _quiz_data_cache = load_quiz_data()
    return _quiz_data_cache


quiz_data = get_quiz_data()


def _prepare_question_for_session(question_template: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of question data with shuffled answer options."""
    question_copy = dict(question_template)
    options = list(question_template.get("options", []))
    indexed_options = list(enumerate(options))
    random.shuffle(indexed_options)

    question_copy["options"] = [option for _, option in indexed_options]
    correct_option = question_template.get("correct_option")
    for idx, (original_index, _) in enumerate(indexed_options):
        if original_index == correct_option:
            question_copy["correct_option"] = idx
            break
    else:
        question_copy["correct_option"] = 0
    return question_copy


def _assign_questions_for_user(user_id: int) -> List[Dict[str, Any]]:
    questions = get_quiz_data()
    if len(questions) < QUESTIONS_PER_SESSION:
        raise ValueError(
            f"Not enough quiz questions in DB: required {QUESTIONS_PER_SESSION}, got {len(questions)}"
        )
    selected_templates = random.sample(questions, QUESTIONS_PER_SESSION)
    selected = [_prepare_question_for_session(question) for question in selected_templates]
    _active_user_questions[user_id] = selected
    return selected


def ensure_session_questions(user_id: int) -> List[Dict[str, Any]]:
    questions = _active_user_questions.get(user_id)
    if questions is None:
        questions = _assign_questions_for_user(user_id)
    return questions


def reset_session_questions(user_id: int) -> None:
    _active_user_questions.pop(user_id, None)


def get_session_question(user_id: int, question_index: int) -> Optional[Dict[str, Any]]:
    questions = _active_user_questions.get(user_id)
    if not questions:
        return None
    if 0 <= question_index < len(questions):
        return questions[question_index]
    return None


def get_session_question_count(user_id: int) -> int:
    questions = _active_user_questions.get(user_id)
    return len(questions) if questions else 0


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
    session_questions = ensure_session_questions(user_id)
    total_questions = len(session_questions)
    if question_index >= total_questions:
        return False

    if question_index == 0 and QUIZ_COVER_IMAGE_URL:
        await message.answer_photo(photo=QUIZ_COVER_IMAGE_URL)

    question = session_questions[question_index]
    builder = InlineKeyboardBuilder()
    for option_index, option in enumerate(question["options"]):
        builder.add(
            types.InlineKeyboardButton(
                text=option,
                callback_data=f"quiz_answer_{question_index}_{option_index}",
            )
        )
    builder.adjust(1)

    header = f"Вопрос {question_index + 1}/{total_questions}:\n{question['question']}"
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
    reset_session_questions(user_id)
    ensure_session_questions(user_id)


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
    reset_session_questions(user_id)
    return state


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "user_id": _row_value(row, "user_id"),
        "username": _row_value(row, "username"),
        "question_index": _row_value(row, "question_index", 0),
        "correct_answers": _row_value(row, "correct_answers", 0),
        "incorrect_answers": _row_value(row, "incorrect_answers", 0),
        "is_active": bool(_row_value(row, "is_active", False)),
    }
