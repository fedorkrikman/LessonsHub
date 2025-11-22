"""
Слой доступа к данным квиза для YDB, эквивалентный app/db/quiz.py из Project12.
"""

from typing import Any, Dict, Optional

from database import execute_select_query, execute_update_query, pool


def _normalize_state(row: Any) -> Dict[str, Any]:
    """Преобразует строку ответа YDB в словарь, совместимый с предыдущей логикой."""

    def _get_value(key: str, default: Any = None) -> Any:
        try:
            value = row[key]
        except KeyError:
            return default
        return default if value is None else value

    return {
        "user_id": int(_get_value("user_id", 0)),
        "username": _get_value("username"),
        "question_index": int(_get_value("question_index", 0)),
        "correct_answers": int(_get_value("correct_answers", 0)),
        "incorrect_answers": int(_get_value("incorrect_answers", 0)),
        "is_active": bool(_get_value("is_active", False)),
    }


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
    execute_update_query(
        pool,
        query,
        user_id=user_id,
        username=username,
    )


async def set_question_index(user_id: int, index: int) -> None:
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
        question_index=index,
    )


async def record_answer(user_id: int, is_correct: bool) -> None:
    column = "correct_answers" if is_correct else "incorrect_answers"
    query = f"""
        DECLARE $user_id AS Uint64;

        UPDATE `quiz_state`
        SET {column} = COALESCE({column}, 0u) + 1u
        WHERE user_id == $user_id;
    """
    execute_update_query(
        pool,
        query,
        user_id=user_id,
    )


async def get_quiz_state(user_id: int) -> Optional[Dict[str, Any]]:
    query = """
        DECLARE $user_id AS Uint64;

        SELECT
            user_id,
            username,
            question_index,
            correct_answers,
            incorrect_answers,
            is_active
        FROM `quiz_state`
        WHERE user_id == $user_id;
    """
    rows = execute_select_query(pool, query, user_id=user_id)
    if not rows:
        return None
    return _normalize_state(rows[0])


async def finish_quiz_session(user_id: int) -> Optional[Dict[str, Any]]:
    state = await get_quiz_state(user_id)
    if not state:
        return None

    query = """
        DECLARE $user_id AS Uint64;

        UPDATE `quiz_state`
        SET is_active = false, question_index = 0u
        WHERE user_id == $user_id;
    """
    execute_update_query(pool, query, user_id=user_id)
    return state
