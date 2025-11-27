"""Telegram bot interface for WikiAmpBot."""

from __future__ import annotations

import asyncio
from typing import Dict, Iterable, Optional

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from .ask_service import AskService


class TelegramBot:
    """Aiogram-based bot that handles mode switching and answers."""

    TALK_MODE = "talk"
    ALLOWED_COMMANDS = {"talk", "1980", "2022", "help", "info", "about"}
    MODE_INDICATORS = {
        TALK_MODE: "[GPT]",
        "1980": "[1980]",
        "2022": "[2022]",
    }
    MODE_RESPONSES = {
        TALK_MODE: "Режим установлен: прямой диалог с GPT без тематического усиления.",
        "1980": "Режим установлен: Олимпиада-1980 (усиление ответов по базе Wiki).",
        "2022": "Режим установлен: Олимпиада-2022 (усиление ответов по базе Wiki).",
    }
    MIN_QUESTION_LEN = 16
    COVER_IMAGE_URL = "https://storage.yandexcloud.net/vedro-c-gvozdyami/wikiampbot-olympic02s.jpg"

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
        self.user_modes: Dict[int, str] = {}
        self.available_topics = {topic.lower() for topic in available_topics}
        self._topic_labels = self._build_topic_labels()
        self.default_mode = self.TALK_MODE
        if default_topic.lower() in self.available_topics:
            self.default_mode = default_topic.lower()

        self._register_handlers()

    async def run(self) -> None:
        """Start polling Telegram updates."""

        await self.dispatcher.start_polling(self.bot)

    def _register_handlers(self) -> None:
        dp = self.dispatcher
        dp.message.register(self.cmd_talk, Command(commands=["talk"]))
        dp.message.register(self.cmd_1980, Command(commands=["1980"]))
        dp.message.register(self.cmd_2022, Command(commands=["2022"]))
        dp.message.register(self.cmd_help, Command(commands=["help"]))
        dp.message.register(self.cmd_info, Command(commands=["info"]))
        dp.message.register(self.cmd_about, Command(commands=["about"]))
        dp.message.register(self.handle_message)

    async def cmd_talk(self, message: Message) -> None:
        await self._set_mode(message, self.TALK_MODE)
        await self._send_cover(message, caption=self.MODE_RESPONSES[self.TALK_MODE])

    async def cmd_1980(self, message: Message) -> None:
        await self._set_mode(message, "1980")

    async def cmd_2022(self, message: Message) -> None:
        await self._set_mode(message, "2022")

    async def cmd_help(self, message: Message) -> None:
        await message.answer(
            "Доступные команды:\n"
            "/talk — прямой диалог без базы.\n"
            "/1980 — режим Олимпиада-1980.\n"
            "/2022 — режим Олимпиада-2022.\n"
            "/help — краткая справка.\n"
            "/info — информация о режимах и текущем состоянии.\n"
            "/about — сведения о проекте."
        )

    async def cmd_info(self, message: Message) -> None:
        user_id = self._user_id(message)
        if user_id is None:
            return
        mode = self.user_modes.get(user_id, self.default_mode)
        info_text = self._build_info_text(mode)
        await message.answer(info_text)

    async def cmd_about(self, message: Message) -> None:
        await self._send_cover(message, caption=(
            "WikiAmpBot — учебный проект по работе с базами Wiki и GPT. "
            "Бот умеет вести обычный диалог (/talk) и отвечать на вопросы по темам Олимпиады 1980 и 2022."
        ))

    async def handle_message(self, message: Message) -> None:
        text = (message.text or "").strip()
        if not text:
            await message.answer("Отправьте, пожалуйста, текстовый вопрос.")
            return
        if text.startswith("/"):
            command = text.split()[0][1:].lower() if len(text) > 1 else ""
            if command not in self.ALLOWED_COMMANDS:
                await message.answer("Неизвестная команда. Используйте /help для списка доступных команд.")
            return

        if len(text) < self.MIN_QUESTION_LEN:
            await message.answer("Пожалуйста, задайте более внятный вопрос (не короче 16 символов).")
            return

        user_id = self._user_id(message)
        if user_id is None:
            return
        mode = self.user_modes.get(user_id, self.default_mode)
        await self._answer_with_mode(message, text, mode)

    async def _answer_with_mode(self, message: Message, text: str, mode: str) -> None:
        try:
            if mode == self.TALK_MODE:
                answer = await asyncio.to_thread(self._ask_direct_gpt, text)
            elif mode in self.available_topics:
                answer = await asyncio.to_thread(self.ask_service.answer, text, mode)
            else:
                await message.answer("Выбранный режим недоступен. Используйте /info для проверки.")
                return
        except ValueError as exc:
            await message.answer(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            await message.answer(f"Не удалось получить ответ: {exc}")
            return

        prefix = self.MODE_INDICATORS.get(mode, "[GPT]")
        await message.answer(f"{prefix} {answer}")

    def _ask_direct_gpt(self, text: str) -> str:
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant. Answer the user's question without extra context.",
            },
            {"role": "user", "content": text},
        ]
        return self.ask_service.gpt_client.chat(messages)

    async def _set_mode(self, message: Message, mode: str) -> None:
        user_id = self._user_id(message)
        if user_id is None:
            return
        if mode != self.TALK_MODE and mode not in self.available_topics:
            await message.answer("Этот режим недоступен в текущей конфигурации.")
            return
        self.user_modes[user_id] = mode
        await message.answer(self.MODE_RESPONSES.get(mode, "Режим установлен."))

    def _mode_label(self, mode: str) -> str:
        return {
            self.TALK_MODE: "GPT",
            "1980": "Олимпиада-1980",
            "2022": "Олимпиада-2022",
        }.get(mode, "неизвестно")

    def _build_topic_labels(self) -> Dict[str, str]:
        labels = {self.TALK_MODE: "GPT"}
        if "1980" in self.available_topics:
            labels["1980"] = "Олимпиада-1980"
        if "2022" in self.available_topics:
            labels["2022"] = "Олимпиада-2022"
        return labels

    def _build_info_text(self, current_mode: str) -> str:
        kb_1980 = self.ask_service.bases.get("1980")
        kb_2022 = self.ask_service.bases.get("2022")
        len_1980 = len(kb_1980._df) if kb_1980 and kb_1980._df is not None else 0
        len_2022 = len(kb_2022._df) if kb_2022 and kb_2022._df is not None else 0

        parts = [
            f"Текущий режим: {self._mode_label(current_mode)}.",
            "",
            "База 1: Олимпиада-1980",
            f"всего записей: {len_1980}",
            "",
            "База 2: Олимпиада-2022",
            f"всего записей: {len_2022}",
            "",
            "Пример запроса: Сколько медалей всего разыграно?",
        ]
        return "\n".join(parts)

    async def _send_cover(self, message: Message, caption: str) -> None:
        try:
            await message.answer_photo(photo=self.COVER_IMAGE_URL, caption=caption)
        except Exception:
            await message.answer(caption)

    @staticmethod
    def _user_id(message: Message) -> Optional[int]:
        if not message.from_user:
            return None
        return message.from_user.id
