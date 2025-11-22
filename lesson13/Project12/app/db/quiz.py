import aiosqlite
from pathlib import Path
from typing import Optional, Dict, Any
from app.config import DATABASE_URL

# Извлекаем путь к БД и делаем его абсолютным
_db_path = DATABASE_URL.replace("sqlite:///", "")
if _db_path.startswith("./"):
    project_root = Path(__file__).parent.parent.parent
    DB_NAME = str(project_root / _db_path[2:])
else:
    DB_NAME = _db_path


async def start_quiz_session(user_id: int, username: str) -> None:
    """Запускает (или перезапускает) квиз для пользователя."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            '''
            INSERT INTO quiz_state (user_id, username, question_index, correct_answers, incorrect_answers, is_active)
            VALUES (?, ?, 0, 0, 0, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                question_index = 0,
                correct_answers = 0,
                incorrect_answers = 0,
                is_active = 1
            ''',
            (user_id, username),
        )
        await db.commit()


async def set_question_index(user_id: int, index: int) -> None:
    """Сохраняет текущий индекс вопроса для пользователя."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'UPDATE quiz_state SET question_index = ? WHERE user_id = ?',
            (index, user_id)
        )
        await db.commit()


async def record_answer(user_id: int, is_correct: bool) -> None:
    """Обновляет статистику ответов пользователя."""
    column = "correct_answers" if is_correct else "incorrect_answers"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            f'UPDATE quiz_state SET {column} = {column} + 1 WHERE user_id = ?',
            (user_id,)
        )
        await db.commit()


async def finish_quiz_session(user_id: int) -> Optional[Dict[str, Any]]:
    """Помечает квиз как завершенный и возвращает статистику пользователя."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''
            SELECT user_id, username, question_index, correct_answers, incorrect_answers, is_active
            FROM quiz_state WHERE user_id = ?
            ''',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        await db.execute(
            'UPDATE quiz_state SET is_active = 0, question_index = 0 WHERE user_id = ?',
            (user_id,)
        )
        await db.commit()
        return dict(row)


async def get_quiz_state(user_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает текущее состояние квиза пользователя."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''
            SELECT user_id, username, question_index, correct_answers, incorrect_answers, is_active
            FROM quiz_state WHERE user_id = ?
            ''',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return dict(row)
