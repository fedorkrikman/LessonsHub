"""Service layer that connects knowledge bases with GPT."""

from __future__ import annotations

from typing import Dict, Iterable, List

from .gpt_client import GPTClient
from .knowledge_base import KnowledgeBase


class AskService:
    """Builds context-aware answers using knowledge bases and GPT."""

    def __init__(
        self,
        gpt_client: GPTClient,
        bases: Dict[str, KnowledgeBase],
        *,
        top_n: int,
        system_prompt: str,
        default_topic: str,
    ) -> None:
        if not bases:
            raise ValueError("AskService requires at least one knowledge base.")
        self.gpt_client = gpt_client
        self.bases = {topic.lower(): kb for topic, kb in bases.items()}
        self.top_n = top_n
        self.system_prompt = system_prompt
        self.default_topic = default_topic.lower()
        if self.default_topic not in self.bases:
            raise ValueError(f"Default topic '{self.default_topic}' is not in provided bases.")

    def available_topics(self) -> List[str]:
        return sorted(self.bases.keys())

    def answer(self, question: str, topic: str | None = None) -> str:
        """Return GPT answer for the given question and topic."""

        topic_key = (topic or self.default_topic).lower()
        knowledge_base = self.bases.get(topic_key)
        if knowledge_base is None:
            raise ValueError(f"Unknown topic '{topic}'. Available topics: {', '.join(self.available_topics())}")

        fragments, scores = knowledge_base.search(question, top_n=self.top_n)
        context_block = self._build_context_block(fragments, scores)

        prompt = (
            "Use the numbered context snippets below to answer the user's question. "
            "If the answer is not contained in the context, reply that you don't know.\n\n"
            f"{context_block}\n\nQuestion: {question}"
        ).strip()

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        return self.gpt_client.chat(messages)

    @staticmethod
    def _build_context_block(fragments: Iterable[str], scores: Iterable[float]) -> str:
        lines = []
        for idx, (fragment, score) in enumerate(zip(fragments, scores), start=1):
            lines.append(f"{idx}. (score={score:.3f}) {fragment}")
        if not lines:
            return "No relevant context found."
        return "Context:\n" + "\n".join(lines)
