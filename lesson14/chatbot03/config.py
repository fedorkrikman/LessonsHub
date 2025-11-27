"""Configuration helpers for ChatBot-03."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv


DEFAULT_SYSTEM_PROMPT = (
    "You are WikiAmpBot, a helpful assistant that answers only with the provided "
    "historical context about Olympic Games. If the context does not contain the "
    "answer, say you don't know."
)


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    telegram_token: str
    openai_api_key: str
    openai_base_url: str
    embedding_model: str
    chat_model: str
    csv_urls: Dict[str, str] = field(default_factory=dict)
    top_n: int = 4
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    default_topic: str = ""

    @classmethod
    def load(cls, env_path: Path | None = None) -> "Config":
        """Load configuration from a .env file and the current environment."""

        env_path = env_path or Path(__file__).resolve().parent / "local.env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()

        telegram_token = os.getenv("BOT_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.vsegpt.ru/v1")
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        chat_model = os.getenv("CHAT_MODEL", "gpt-5-nano")
        top_n = int(os.getenv("TOP_N", "4"))
        system_prompt = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

        csv_urls = _collect_csv_urls()
        if not csv_urls:
            raise ValueError("No knowledge base URLs found. Set KB_<topic>_URL values in local.env.")

        default_topic = os.getenv("DEFAULT_TOPIC") or next(iter(csv_urls))
        default_topic = default_topic.lower()
        if default_topic not in csv_urls:
            raise ValueError(f"DEFAULT_TOPIC '{default_topic}' is not present among KB URLs.")

        _ensure_required("BOT_API_KEY", telegram_token)
        _ensure_required("OPENAI_API_KEY", openai_api_key)

        return cls(
            telegram_token=telegram_token,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            embedding_model=embedding_model,
            chat_model=chat_model,
            csv_urls=csv_urls,
            top_n=top_n,
            system_prompt=system_prompt,
            default_topic=default_topic,
        )


def _collect_csv_urls() -> Dict[str, str]:
    """Collect KB URLs from environment variables with the KB_<TOPIC>_URL pattern."""

    urls: Dict[str, str] = {}
    for key, value in os.environ.items():
        if not key.startswith("KB_") or not key.endswith("_URL"):
            continue
        topic = key[3:-4].lower()
        if value:
            urls[topic] = value
    return urls


def _ensure_required(name: str, value: str | None) -> None:
    if not value:
        raise ValueError(f"Environment variable {name} is required but missing.")
