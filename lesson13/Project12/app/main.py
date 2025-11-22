import asyncio
import sys
from pathlib import Path

# Позволяем запускать файл напрямую (python app/main.py) без ModuleNotFoundError
if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from app.bot import make_bot_and_dp
from app.handlers.start import register_start
from app.handlers.quiz import register_quiz
from app.db.core import init_db

async def main():
    await init_db()
    bot, dp = make_bot_and_dp()
    register_start(dp)
    register_quiz(dp)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
