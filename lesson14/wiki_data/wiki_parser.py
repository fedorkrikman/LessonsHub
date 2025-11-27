"""
Utility script that fetches Wikipedia articles for a target category, cleans and chunks
their text, builds embeddings, and saves the result to a CSV file.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Sequence

import mwclient
from mwclient import errors as mw_errors
import mwparserfromhell
import pandas as pd
from openai import OpenAI


def load_local_env(path: Path) -> None:
    """Load key=value pairs from a simple .env file into os.environ."""

    if not path.exists():
        return

    with path.open(encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# --------------------------------------------------------------------------------------
# Configuration block
# --------------------------------------------------------------------------------------
load_local_env(Path(__file__).resolve().parent / "local.env")
#CATEGORY_TITLE = os.getenv("WIKI_CATEGORY", "Category:2022 Winter Olympics")
CATEGORY_TITLE = os.getenv("WIKI_CATEGORY", "Category:1980 Summer Olympics")
WIKI_SITE = os.getenv("WIKI_SITE", "en.wikipedia.org")
MAX_PAGES = int(os.getenv("MAX_PAGES", "10"))
USE_PAGE_LIMIT = os.getenv("USE_PAGE_LIMIT", "true").lower() == "true"
MAX_CHARS_PER_CHUNK = int(os.getenv("MAX_CHARS_PER_CHUNK", "1000"))
MAX_EMBEDDING_CHARS = int(os.getenv("MAX_EMBEDDING_CHARS", str(MAX_CHARS_PER_CHUNK)))
PAUSE_SECONDS = float(os.getenv("WIKI_REQUEST_PAUSE", "0.1"))
OUTPUT_CSV = Path(
    os.getenv(
        "WIKI_OUTPUT_CSV",
        Path(__file__).resolve().parent / "wiki_chunks.csv",
    )
)
OVERWRITE_OUTPUT = os.getenv("OVERWRITE_OUTPUT", "true").lower() == "true"

SECTIONS_TO_IGNORE = {
    "References",
    "See also",
    "External links",
    "Further reading",
    "Sources",
    "Notes",
    "Footnotes",
    "Bibliography",
}

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.vsegpt.ru/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USER_AGENT = os.getenv("USER_AGENT", "LessonsHubWikiParser/0.1 (your-email-or-url)")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "8"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def fetch_category_titles(site: mwclient.Site) -> list[str]:
    """Return up to MAX_PAGES article titles that belong to CATEGORY_TITLE."""

    logging.info("Fetching titles for category '%s'", CATEGORY_TITLE)
    try:
        category_page = site.pages[CATEGORY_TITLE]
    except mw_errors.InvalidPageTitle as exc:
        logging.error("Category title is invalid: %s", exc)
        return []

    titles: list[str] = []
    target_count = MAX_PAGES if USE_PAGE_LIMIT else None

    try:
        for member in category_page.members():
            time.sleep(PAUSE_SECONDS)
            if isinstance(member, mwclient.page.Page):
                titles.append(member.name)
                if target_count and len(titles) >= target_count:
                    break
    except mw_errors.APIError as exc:
        logging.error("Failed to iterate category members: %s", exc)
        return []

    logging.info("Collected %d titles from category '%s'", len(titles), CATEGORY_TITLE)
    return titles


def fetch_page_content(site: mwclient.Site, title: str) -> str:
    """Load page text for the given title, returning an empty string on failure."""

    try:
        time.sleep(PAUSE_SECONDS)
        page = site.pages[title]
        text = page.text()
        logging.debug("Fetched %s (%d chars)", title, len(text))
        return text or ""
    except (mw_errors.APIError, mw_errors.InvalidPageTitle) as exc:
        logging.warning("Skipping '%s' due to fetch error: %s", title, exc)
        return ""
    except mw_errors.InsufficientPermission as exc:
        logging.warning("No permission to fetch '%s': %s", title, exc)
        return ""


def extract_sections(page_title: str, raw_text: str) -> list[tuple[str, str]]:
    """
    Split page text into logical sections and remove ignored service sections.
    Returns list of (section_name, section_text).
    """

    if not raw_text:
        return []

    parsed = mwparserfromhell.parse(raw_text)
    sections: list[tuple[str, str]] = []

    for section in parsed.get_sections(include_lead=True, levels=[2, 3, 4]):
        headings = section.filter_headings()
        if headings:
            heading_text = re.sub(r"=+", "", str(headings[0])).strip()
        else:
            heading_text = "Lead"

        if heading_text in SECTIONS_TO_IGNORE:
            continue

        section_body = section.strip_code().strip()
        cleaned = clean_text(section_body)
        if cleaned:
            sections.append((heading_text, cleaned))

    logging.debug("Extracted %d sections from page '%s'", len(sections), page_title)
    return sections


def clean_text(text: str) -> str:
    """Remove templates, references, navigation blocks, and redundant whitespace."""

    code = mwparserfromhell.parse(text)
    for template in list(code.filter_templates(recursive=True)):
        code.remove(template)

    plain = code.strip_code().strip()
    plain = re.sub(r"<ref[^>]*>.*?</ref>", " ", plain, flags=re.DOTALL)
    plain = re.sub(r"\{\{.*?\}\}", " ", plain, flags=re.DOTALL)
    plain = re.sub(r"\[\[(?:File|Image):.*?\]\]", " ", plain, flags=re.IGNORECASE)
    plain = re.sub(r"\[\[Category:.*?\]\]", " ", plain, flags=re.IGNORECASE)
    plain = re.sub(r"http[s]?://\S+", " ", plain)
    plain = re.sub(r"\s+", " ", plain)

    return plain.strip()


def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """Slice text into fixed-size chunks, preserving order."""

    chunks: list[str] = []
    for idx in range(0, len(text), max_chars):
        chunk = text[idx : idx + max_chars].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def build_dataframe(records: Sequence[dict]) -> pd.DataFrame:
    """Convert chunk records into a pandas DataFrame."""

    df = pd.DataFrame.from_records(records)
    if df.empty:
        logging.warning("No data available to save.")
    return df


def filter_chunks_for_embedding(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with empty or overly long text prior to embedding."""

    if df.empty:
        return df
    stripped_lengths = df["text"].str.strip().str.len()
    mask = stripped_lengths > 0
    if MAX_EMBEDDING_CHARS:
        mask &= df["text"].str.len() <= MAX_EMBEDDING_CHARS

    dropped = len(df) - mask.sum()
    if dropped:
        logging.info("Filtered out %d chunks prior to embedding.", dropped)

    return df.loc[mask].copy()


def generate_embeddings(texts: Sequence[str]) -> list[list[float]]:
    """Request embeddings for the provided texts."""

    if not texts:
        return []
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=EMBEDDING_BASE_URL)

    embeddings: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = list(texts[start : start + EMBEDDING_BATCH_SIZE])
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
                encoding_format="float",
            )
        except Exception as exc:  # noqa: BLE001 - want to catch client errors
            logging.error("Embedding request failed: %s", exc)
            raise

        batch_embeddings = [item.embedding for item in response.data]
        embeddings.extend(batch_embeddings)

    logging.info("Generated %d embeddings.", len(embeddings))
    return embeddings


def serialize_embeddings(df: pd.DataFrame, embeddings: Sequence[Sequence[float]]) -> pd.DataFrame:
    """Attach embeddings to the DataFrame and serialize them for CSV persistence."""

    if len(df) != len(embeddings):
        raise ValueError(
            f"Row/embedding mismatch: {len(df)} rows vs {len(embeddings)} embeddings."
        )

    serialized = [json.dumps(vec) for vec in embeddings]
    df = df.copy()
    df["embedding"] = serialized
    return df


def save_dataframe(df: pd.DataFrame, path: Path, overwrite: bool = True) -> None:
    """Persist dataframe to CSV respecting overwrite flag, and validate serialization."""

    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists and OVERWRITE_OUTPUT is False.")

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logging.info("Saved %d rows to %s", len(df), path)
    _validate_serialization(path)


def _validate_serialization(path: Path) -> None:
    """Ensure embeddings round-trip from CSV."""

    loaded = pd.read_csv(path)
    try:
        _ = loaded["embedding"].apply(json.loads)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to deserialize embeddings from {path}: {exc}") from exc


def run_pipeline() -> None:
    """Execute the full workflow from fetching pages to saving CSV."""

    logging.info("Starting pipeline for site '%s' and category '%s'", WIKI_SITE, CATEGORY_TITLE)
    site = mwclient.Site(host=WIKI_SITE, clients_useragent=USER_AGENT)

    titles = fetch_category_titles(site)
    if not titles:
        logging.error("No titles retrieved; aborting.")
        return

    records: list[dict] = []
    for title in titles:
        logging.info("Processing page '%s'", title)
        text = fetch_page_content(site, title)
        if not text:
            continue

        try:
            sections = extract_sections(title, text)
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to parse '%s': %s", title, exc)
            continue

        for section_name, section_text in sections:
            for idx, chunk in enumerate(chunk_text(section_text)):
                records.append(
                    {
                        "page_title": title,
                        "section": section_name,
                        "chunk_id": idx,
                        "text": chunk,
                    }
                )

    df = build_dataframe(records)
    if df.empty:
        logging.error("No records to process; exiting.")
        return

    df_for_embedding = filter_chunks_for_embedding(df)
    embeddings = generate_embeddings(df_for_embedding["text"].tolist())
    df_with_embeddings = serialize_embeddings(df_for_embedding, embeddings)
    save_dataframe(df_with_embeddings, OUTPUT_CSV, overwrite=OVERWRITE_OUTPUT)


if __name__ == "__main__":
    run_pipeline()
