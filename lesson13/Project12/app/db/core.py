import aiosqlite
import os
from pathlib import Path
from typing import Dict
from app.config import DATABASE_URL


async def init_db():
    """Инициализирует базу данных и создает необходимые таблицы"""
    # Извлекаем путь к БД из DATABASE_URL (формат: sqlite:///./db/quiz_bot.db)
    db_path = DATABASE_URL.replace("sqlite:///", "")
    
    # Делаем путь абсолютным относительно корня проекта
    if db_path.startswith("./"):
        project_root = Path(__file__).parent.parent.parent
        db_path = str(project_root / db_path[2:])
    
    # Создаем директорию для БД, если её нет
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    # Создаем соединение с базой данных (если она не существует, то она будет создана)
    async with aiosqlite.connect(db_path) as db:
        # Выполняем SQL-запрос к базе данных
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS quiz_state (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                question_index INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                incorrect_answers INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 0
            )
            '''
        )
        await db.commit()
        await _ensure_quiz_state_columns(db)


async def _ensure_quiz_state_columns(db: aiosqlite.Connection) -> None:
    """Добавляет недостающие колонки в таблицу quiz_state (для обратной совместимости)."""
    required_columns: Dict[str, str] = {
        "username": "TEXT",
        "question_index": "INTEGER DEFAULT 0",
        "correct_answers": "INTEGER DEFAULT 0",
        "incorrect_answers": "INTEGER DEFAULT 0",
        "is_active": "INTEGER DEFAULT 0",
    }
    cursor = await db.execute("PRAGMA table_info(quiz_state)")
    rows = await cursor.fetchall()
    await cursor.close()
    existing_columns = {row[1] for row in rows}
    for column, definition in required_columns.items():
        if column not in existing_columns:
            await db.execute(f"ALTER TABLE quiz_state ADD COLUMN {column} {definition}")
    await db.commit()
