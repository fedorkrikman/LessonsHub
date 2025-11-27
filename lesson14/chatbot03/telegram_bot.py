"""Telegram bot interface for WikiAmpBot."""

from __future__ import annotations

import asyncio
from typing import Dict, Iterable, Optional

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from .ask_service import AskService


class TelegramBot:
    """Aiogram-based bot that handles topic selection and answers."""

    def __init__(
        self,
        token: str,
        ask_service: AskService,
        *,
        available_topics: Iterable[str],
        default_topic: str,
    ) -> None:
        if not token:
            raise ValueError("Telegram token is required.")

        self.ask_service = ask_service
        self.bot = Bot(token=token)
        self.dispatcher = Dispatcher()
        self.user_topics: Dict[int, str] = {}
        self.available_topics = sorted(set(topic.lower() for topic in available_topics))
        self.default_topic = default_topic.lower()

        self._register_handlers()

    async def run(self) -> None:
        """Start polling Telegram updates."""

        await self.dispatcher.start_polling(self.bot)

    def _register_handlers(self) -> None:
        dp = self.dispatcher
        dp.message.register(self.cmd_start, Command(commands=["start"]))
        dp.message.register(self.cmd_help, Command(commands=["help"]))
        dp.message.register(self.cmd_topics, Command(commands=["topics"]))
        dp.message.register(self.cmd_reset, Command(commands=["reset"]))

        for topic in self.available_topics:
            dp.message.register(self._topic_handler_factory(topic), Command(commands=[f"set_{topic}"]))

        dp.message.register(self.handle_message)

    async def cmd_start(self, message: Message) -> None:
        user_id = self._user_id(message)
        if user_id is None:
            return
        self.user_topics[user_id] = self.default_topic
        await message.answer(
            "Привет! Я WikiAmpBot. Выберите тему командой /topics или сразу задайте вопрос."
        )

    async def cmd_help(self, message: Message) -> None:
        await message.answer(
            "Команды:\n"
            "/start — начать заново и выбрать тему по умолчанию.\n"
            "/topics — список доступных тем и команды для переключения.\n"
            "/reset — забыть текущую тему и вернуться к стандартной.\n"
            "Любой текст без команды будет передан в тему, выбранную для вашего чата."
        )

    async def cmd_topics(self, message: Message) -> None:
        topic_commands = "\n".join(f"/set_{topic} — тема {topic}" for topic in self.available_topics)
        await message.answer(
            "Доступные темы:\n"
            f"{topic_commands}\n"
            "После выбора тема сохранится для вашего чата."
        )

    async def cmd_reset(self, message: Message) -> None:
        user_id = self._user_id(message)
        if user_id is None:
            return
        self.user_topics[user_id] = self.default_topic
        await message.answer("Тема сброшена к значению по умолчанию.")

    def _topic_handler_factory(self, topic: str):
        async def handler(message: Message) -> None:
            user_id = self._user_id(message)
            if user_id is None:
                return
            self.user_topics[user_id] = topic
            await message.answer(f"Тема переключена на {topic}. Задайте вопрос.")

        return handler

    async def handle_message(self, message: Message) -> None:
        if not message.text:
            await message.answer("Отправьте, пожалуйста, текстовый вопрос.")
            return
        user_id = self._user_id(message)
        if user_id is None:
            return
        topic = self.user_topics.get(user_id, self.default_topic)
        try:
            answer = await asyncio.to_thread(self.ask_service.answer, message.text, topic)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - surface unexpected failures
            await message.answer(f"Не удалось получить ответ: {exc}")
            return
        await message.answer(answer)

    @staticmethod
    def _user_id(message: Message) -> Optional[int]:
        if not message.from_user:
            return None
        return message.from_user.id
