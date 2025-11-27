"""Entry point for ChatBot-03."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))

from .ask_service import AskService
from .config import Config
from .gpt_client import GPTClient
from .knowledge_base import KnowledgeBase
from .telegram_bot import TelegramBot


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def main() -> None:
    config = Config.load()
    gpt_client = GPTClient(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        embedding_model=config.embedding_model,
        chat_model=config.chat_model,
    )

    knowledge_bases: Dict[str, KnowledgeBase] = {}
    for topic, url in config.csv_urls.items():
        kb = KnowledgeBase(name=topic, csv_url=url, gpt_client=gpt_client)
        kb.load()
        knowledge_bases[topic] = kb

    ask_service = AskService(
        gpt_client=gpt_client,
        bases=knowledge_bases,
        top_n=config.top_n,
        system_prompt=config.system_prompt,
        default_topic=config.default_topic,
    )

    telegram_bot = TelegramBot(
        token=config.telegram_token,
        ask_service=ask_service,
        available_topics=ask_service.available_topics(),
        default_topic=ask_service.default_topic,
    )
    await telegram_bot.run()


if __name__ == "__main__":
    asyncio.run(main())
