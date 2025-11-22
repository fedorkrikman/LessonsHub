from aiogram import Bot, Dispatcher
from app.config import API_TOKEN


def make_bot_and_dp():
    """Создает и возвращает экземпляры бота и диспетчера"""
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    return bot, dp

