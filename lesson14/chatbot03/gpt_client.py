"""Client wrapper around the OpenAI/VseGPT API."""

from __future__ import annotations

from typing import List, Sequence

from openai import OpenAI


class GPTClient:
    """Thin wrapper for embedding and chat completions."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        embedding_model: str,
        chat_model: str,
    ) -> None:
        if not api_key:
            raise ValueError("API key is required for GPTClient.")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.embedding_model = embedding_model
        self.chat_model = chat_model

    def get_embedding(self, text: str) -> List[float]:
        """Return embedding vector for a given text."""

        response = self._client.embeddings.create(
            model=self.embedding_model,
            input=text,
            encoding_format="float",
        )
        return response.data[0].embedding

    def chat(self, messages: Sequence[dict]) -> str:
        """Send chat completion request and return model reply."""

        response = self._client.chat.completions.create(
            model=self.chat_model,
            messages=list(messages),
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
