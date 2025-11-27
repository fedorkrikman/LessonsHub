"""Knowledge base handling for CSV-stored embeddings."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd

from .gpt_client import GPTClient


logger = logging.getLogger(__name__)


@dataclass
class KnowledgeBase:
    """Stores embeddings loaded from a CSV and performs similarity search."""

    name: str
    csv_url: str
    gpt_client: GPTClient
    _df: pd.DataFrame | None = None
    _embedding_matrix: np.ndarray | None = None

    def load(self) -> None:
        """Load CSV into memory and pre-compute normalized embeddings."""

        logger.info("Loading knowledge base '%s' from %s", self.name, self.csv_url)
        df = pd.read_csv(self.csv_url)
        if "embedding" not in df.columns or "text" not in df.columns:
            raise ValueError("Knowledge base CSV must include 'text' and 'embedding' columns.")

        df["embedding"] = df["embedding"].apply(self._parse_embedding)
        embeddings = np.vstack(df["embedding"].to_numpy())
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1e-9
        self._embedding_matrix = embeddings / norms
        self._df = df
        logger.info("Loaded %d fragments for topic '%s'.", len(df), self.name)

    def search(self, query: str, top_n: int) -> Tuple[List[str], List[float]]:
        """Return top_n fragments ordered by cosine similarity to the query."""

        if not query.strip():
            return [], []
        if self._df is None or self._embedding_matrix is None:
            raise RuntimeError("Knowledge base must be loaded before calling search().")

        query_vector = np.array(self.gpt_client.get_embedding(query), dtype="float32")
        norm = np.linalg.norm(query_vector)
        if norm == 0:
            return [], []

        normalized_query = query_vector / norm
        similarities = self._embedding_matrix @ normalized_query
        top_n = min(top_n, len(similarities))
        top_indices = np.argsort(similarities)[-top_n:][::-1]

        fragments: List[str] = []
        scores: List[float] = []
        for idx in top_indices:
            row = self._df.iloc[int(idx)]
            fragment = (
                f"{row['page_title']} — {row['section']} (chunk {row['chunk_id']}):\n"
                f"{row['text']}"
            )
            fragments.append(fragment)
            scores.append(float(similarities[idx]))
        return fragments, scores

    @staticmethod
    def _parse_embedding(raw: str) -> List[float]:
        """Parse serialized embeddings stored as JSON arrays in CSV."""

        if isinstance(raw, list):
            return raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            import ast

            return list(ast.literal_eval(raw))
