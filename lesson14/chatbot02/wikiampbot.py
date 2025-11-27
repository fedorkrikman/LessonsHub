import asyncio
import os
from pathlib import Path
from typing import Dict, Optional

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / "local.env")

TELEGRAM_TOKEN = os.getenv("BOT_API_KEY")
LLM_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_BASE_URL = os.getenv("base_url", "https://api.vsegpt.ru/v1")
COVER_IMAGE_URL = os.getenv(
    "COVER_IMAGE_URL", "https://storage.yandexcloud.net/vedro-c-gvozdyami/wikiampbot-olympic.png"
)


bot: Optional[Bot] = None
dispatcher: Optional[Dispatcher] = None

user_mode: Dict[int, str] = {}
user_topic: Dict[int, Optional[str]] = {}


async def call_llm(prompt: str) -> str:
    """
    Получает строку prompt, отправляет её в LLM и возвращает текст ответа.
    """
    if not LLM_API_KEY:
        raise RuntimeError("Не задан ключ LLM. Проверьте переменную OPENAI_API_KEY.")

    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "Ты - большая языковая модель. Отвечай на вопросы пользователя.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                if response.status != 200:
                    detail = await response.text()
                    raise RuntimeError(
                        f"LLM ответил со статусом {response.status}: {detail.strip() or 'нет подробностей'}"
                    )
                data = await response.json()
    except aiohttp.ClientError as exc:
        raise RuntimeError("Ошибка сети при обращении к LLM. Попробуйте позже.") from exc

    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LLM вернул неожиданный формат ответа.") from exc

    return answer.strip()


async def cmd_start(message: Message) -> None:
    user = message.from_user
    if not user:
        await message.answer("Не удалось определить пользователя.")
        return
    user_mode.pop(user.id, None)
    user_topic.pop(user.id, None)
    start_text = (
        "Привет! Я @wikiampbot. Пока доступен простой режим /talk для диалога с GPT. "
        "Используйте /help, чтобы узнать о командах."
    )
    if COVER_IMAGE_URL:
        try:
            await message.answer_photo(
                photo=COVER_IMAGE_URL,
                caption=start_text,
            )
            return
        except Exception:
            pass
    await message.answer(start_text)


async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/talk — прямой диалог с GPT (активный режим).\n"
        "/start — перезапуск и выбор темы.\n"
        "/help — подсказка по командам.\n"
        "/topics — список тематических баз (в разработке).\n"
        "/settopic — выбор темы (в разработке).\n"
        "/info — информация о текущей теме (в разработке).\n"
        "/random — случайный факт (в разработке).\n"
        "/ask — вопрос с Wiki-усилением (в разработке).\n"
        "/reset — сброс режима и темы.\n"
        "/about — информация о @wikiampbot.\n"
        "Полноценно работают только /talk и /reset, остальные команды пока в разработке."
    )


async def cmd_talk(message: Message) -> None:
    user = message.from_user
    if not user:
        await message.answer("Не удалось определить пользователя.")
        return
    user_mode[user.id] = "talk"
    await message.answer(
        "Режим прямого разговора включен. Отправьте текстовый запрос, и я передам его GPT."
    )


async def cmd_reset(message: Message) -> None:
    user = message.from_user
    if not user:
        await message.answer("Не удалось определить пользователя.")
        return
    user_mode.pop(user.id, None)
    user_topic.pop(user.id, None)
    await message.answer("Режим и тема сброшены. Можно начать заново с /talk или /start.")


async def cmd_about(message: Message) -> None:
    await message.answer(
        "@wikiampbot — учебный бот, который обращается к внешней LLM через API VseGPT. "
        "Сейчас полностью работает базовый режим /talk."
    )


async def cmd_topics(message: Message) -> None:
    await message.answer("Функция выбора тематических баз пока не реализована. Следите за обновлениями.")


async def cmd_settopic(message: Message) -> None:
    await message.answer("Выбор темы будет добавлен позже. Пока используйте режим /talk.")


async def cmd_info(message: Message) -> None:
    await message.answer("Информация о теме появится после реализации тематических модулей.")


async def cmd_random(message: Message) -> None:
    await message.answer("Случайные факты будут доступны позже, как только появятся базы знаний.")


async def cmd_ask(message: Message) -> None:
    await message.answer("Режим Wiki-усиления ещё в разработке. Используйте /talk для вопросов.")


async def handle_text_in_talk_mode(message: Message) -> None:
    user = message.from_user
    if not user:
        await message.answer("Не удалось определить пользователя.")
        return
    if user_mode.get(user.id) != "talk":
        await message.answer("Режим прямого диалога с GPT сейчас не активен. Используйте /talk для запуска.")
        return

    user_text = message.text or ""
    if not user_text.strip():
        await message.answer("Пожалуйста, отправьте текстовый запрос.")
        return

    try:
        reply_text = await call_llm(user_text)
    except RuntimeError as exc:
        await message.answer(f"Не удалось получить ответ от LLM: {exc}")
        return

    await message.answer(reply_text)


def register_handlers(dp: Dispatcher) -> None:
    dp.message.register(cmd_start, Command(commands=["start"]))
    dp.message.register(cmd_help, Command(commands=["help"]))
    dp.message.register(cmd_talk, Command(commands=["talk"]))
    dp.message.register(cmd_topics, Command(commands=["topics"]))
    dp.message.register(cmd_settopic, Command(commands=["settopic"]))
    dp.message.register(cmd_info, Command(commands=["info"]))
    dp.message.register(cmd_random, Command(commands=["random"]))
    dp.message.register(cmd_ask, Command(commands=["ask"]))
    dp.message.register(cmd_reset, Command(commands=["reset"]))
    dp.message.register(cmd_about, Command(commands=["about"]))
    dp.message.register(handle_text_in_talk_mode)


async def main() -> None:
    global bot, dispatcher

    if not TELEGRAM_TOKEN:
        raise RuntimeError("Не задан токен Telegram. Установите BOT_API_KEY в local.env.")
    if not LLM_API_KEY:
        raise RuntimeError("Не задан ключ LLM. Установите OPENAI_API_KEY в local.env.")

    bot = Bot(token=TELEGRAM_TOKEN)
    dispatcher = Dispatcher()
    register_handlers(dispatcher)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
