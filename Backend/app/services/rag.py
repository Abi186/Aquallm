"""
AquaLLM - local RAG (Retrieval-Augmented Generation)

Reads the aquaculture knowledge documents (Documents/knowledge/*.md),
splits them into chunks, embeds them with a local Ollama embedding
model, and finds the chunks most relevant to a user question.

No extra Python package is needed (only numpy + requests).

How it works
------------
1. First question  -> index is built automatically (takes a few seconds)
2. Index is saved in Backend/rag_index/
3. If you edit / add a .md file, the index is rebuilt automatically
4. Each question  -> embed question -> cosine similarity -> top chunks

Useful commands (run inside the Backend folder, venv active)
------------------------------------------------------------
    python -m app.services.rag --status
    python -m app.services.rag --rebuild
    python -m app.services.rag --ask "what is FCR"
"""

import argparse
import hashlib
import json
import logging
import re
import threading
from pathlib import Path
from typing import List, Optional

import numpy as np
import requests

from app.config import (
    KNOWLEDGE_DIR,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_EMBED_TIMEOUT,
    RAG_CHUNK_CHARS,
    RAG_ENABLED,
    RAG_INDEX_DIR,
    RAG_MIN_SCORE,
    RAG_TOP_K,
)

logger = logging.getLogger("aquallm.rag")


# ============================================================
# ERRORS
# ============================================================

class RAGUnavailable(Exception):
    """Knowledge base could not be used (Ollama down, model missing...)."""


# ============================================================
# CHUNKING
# ============================================================

def _split_long_text(text: str, limit: int) -> List[str]:
    """Split a long section on paragraph / line boundaries."""

    parts = []
    current = ""

    for block in re.split(r"\n\s*\n", text.strip()):

        block = block.strip()

        if not block:
            continue

        if current and len(current) + len(block) + 2 > limit:
            parts.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block

    if current:
        parts.append(current)

    # A single huge block (no blank lines) - split by lines
    final = []

    for part in parts:

        if len(part) <= limit * 1.5:
            final.append(part)
            continue

        buffer = ""

        for line in part.split("\n"):

            if buffer and len(buffer) + len(line) + 1 > limit:
                final.append(buffer)
                buffer = line
            else:
                buffer = f"{buffer}\n{line}" if buffer else line

        if buffer:
            final.append(buffer)

    return final


def chunk_markdown(path: Path, limit: int) -> List[dict]:
    """Split one markdown file into chunks, one per heading section."""

    raw = path.read_text(encoding="utf-8", errors="ignore")

    raw = raw.replace("\r\n", "\n")

    title = path.stem.replace("_", " ").replace("-", " ").strip()
    heading_path = []
    buffer = []
    sections = []

    def flush():
        body = "\n".join(buffer).strip()
        if body:
            sections.append((" > ".join(heading_path), body))
        buffer.clear()

    for line in raw.split("\n"):

        match = re.match(r"^(#{1,4})\s+(.*)$", line)

        if match:

            flush()

            level = len(match.group(1))
            heading = match.group(2).strip()

            if level == 1:
                title = heading
                heading_path = []
            else:
                heading_path = heading_path[: level - 2] + [heading]

        else:
            buffer.append(line)

    flush()

    chunks = []

    for heading, body in sections:

        for piece in _split_long_text(body, limit):

            chunks.append({
                "source": path.name,
                "title": title,
                "heading": heading,
                "text": piece,
            })

    return chunks


def load_chunks() -> List[dict]:

    if not KNOWLEDGE_DIR.exists():
        raise RAGUnavailable(
            f"Knowledge folder not found: {KNOWLEDGE_DIR}"
        )

    files = sorted(KNOWLEDGE_DIR.glob("*.md"))

    if not files:
        raise RAGUnavailable(
            f"No .md files in knowledge folder: {KNOWLEDGE_DIR}"
        )

    chunks = []

    for file in files:
        chunks.extend(chunk_markdown(file, RAG_CHUNK_CHARS))

    return chunks


def _docs_hash() -> str:

    digest = hashlib.sha256()

    digest.update(OLLAMA_EMBED_MODEL.encode())
    digest.update(str(RAG_CHUNK_CHARS).encode())

    if KNOWLEDGE_DIR.exists():
        for file in sorted(KNOWLEDGE_DIR.glob("*.md")):
            digest.update(file.name.encode())
            digest.update(file.read_bytes())

    return digest.hexdigest()


# ============================================================
# EMBEDDINGS (OLLAMA)
# ============================================================

def _with_prefix(text: str, kind: str) -> str:
    """nomic-embed-text works best with task prefixes."""

    if "nomic" in OLLAMA_EMBED_MODEL.lower():
        prefix = "search_document: " if kind == "doc" else "search_query: "
        return prefix + text

    return text


def _embed(texts: List[str], kind: str) -> np.ndarray:

    prepared = [_with_prefix(t, kind) for t in texts]

    try:

        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": OLLAMA_EMBED_MODEL, "input": prepared},
            timeout=OLLAMA_EMBED_TIMEOUT,
        )

        # Older Ollama versions have no /api/embed
        if response.status_code == 404 and "not found" not in response.text.lower():
            vectors = []
            for text in prepared:
                old = requests.post(
                    f"{OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
                    timeout=OLLAMA_EMBED_TIMEOUT,
                )
                old.raise_for_status()
                vectors.append(old.json()["embedding"])
            matrix = np.array(vectors, dtype=np.float32)

        elif response.status_code == 404:
            raise RAGUnavailable(
                f"Embedding model '{OLLAMA_EMBED_MODEL}' is not installed. "
                f"Run: ollama pull {OLLAMA_EMBED_MODEL}"
            )

        else:
            response.raise_for_status()
            matrix = np.array(
                response.json()["embeddings"], dtype=np.float32
            )

    except requests.exceptions.ConnectionError:
        raise RAGUnavailable("Cannot connect to Ollama (is it running?).")

    except requests.exceptions.Timeout:
        raise RAGUnavailable("Ollama embedding request timed out.")

    except RAGUnavailable:
        raise

    except Exception as exc:
        raise RAGUnavailable(f"Embedding failed: {exc}")

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0

    return matrix / norms


# ============================================================
# INDEX (BUILD / LOAD / CACHE)
# ============================================================

_INDEX_FILE = RAG_INDEX_DIR / "index.npz"
_META_FILE = RAG_INDEX_DIR / "meta.json"

_lock = threading.Lock()
_cache = {"hash": None, "vectors": None, "chunks": None}


def build_index() -> dict:
    """(Re)build the embedding index from the knowledge folder."""

    chunks = load_chunks()

    texts = [
        f"{c['title']} - {c['heading']}\n{c['text']}"
        if c["heading"] else f"{c['title']}\n{c['text']}"
        for c in chunks
    ]

    vectors = []

    # Embed in small batches (keeps Ollama responsive)
    for start in range(0, len(texts), 16):
        vectors.append(_embed(texts[start:start + 16], "doc"))

    matrix = np.vstack(vectors)

    docs_hash = _docs_hash()

    RAG_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(_INDEX_FILE, vectors=matrix)

    _META_FILE.write_text(
        json.dumps(
            {
                "hash": docs_hash,
                "embed_model": OLLAMA_EMBED_MODEL,
                "chunks": chunks,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _cache.update(hash=docs_hash, vectors=matrix, chunks=chunks)

    logger.info("RAG index built: %d chunks", len(chunks))

    return {"chunks": len(chunks), "files": len({c['source'] for c in chunks})}


def ensure_index():
    """Load the index (from memory, disk, or build it)."""

    current_hash = _docs_hash()

    with _lock:

        if _cache["hash"] == current_hash and _cache["vectors"] is not None:
            return _cache["vectors"], _cache["chunks"]

        if _INDEX_FILE.exists() and _META_FILE.exists():

            try:

                meta = json.loads(_META_FILE.read_text(encoding="utf-8"))

                if meta.get("hash") == current_hash:

                    vectors = np.load(_INDEX_FILE)["vectors"]

                    _cache.update(
                        hash=current_hash,
                        vectors=vectors,
                        chunks=meta["chunks"],
                    )

                    return vectors, meta["chunks"]

            except Exception as exc:
                logger.warning("RAG index unreadable, rebuilding: %s", exc)

        build_index()

        return _cache["vectors"], _cache["chunks"]


# ============================================================
# RETRIEVAL
# ============================================================

_STOPWORDS = {
    "what", "is", "are", "the", "of", "in", "on", "for", "to", "a", "an",
    "and", "or", "why", "how", "does", "do", "can", "my", "me", "it",
    "this", "that", "with", "about", "explain", "tell", "give", "show",
    "mean", "means", "meaning", "define", "when", "which", "should",
}


def _keyword_bonus(question: str, chunk: dict) -> float:
    """Small boost when a question word appears in the chunk heading.

    Short questions like "What is FCR?" give weak embeddings, so an
    exact term match in the title / heading helps a lot.
    """

    words = {
        w for w in re.findall(r"[a-z0-9]+", question.lower())
        if w not in _STOPWORDS and len(w) >= 2
    }

    label = f"{chunk['title']} {chunk['heading']}".lower()

    label_words = set(re.findall(r"[a-z0-9]+", label))

    return 0.10 if words & label_words else 0.0


def retrieve(
    question: str,
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
    debug: bool = False,
) -> List[dict]:
    """Return the best matching knowledge chunks (empty list on any problem).

    Never raises - the chatbot must keep working even if RAG does not.
    """

    if not RAG_ENABLED:
        return []

    top_k = top_k or RAG_TOP_K
    min_score = RAG_MIN_SCORE if min_score is None else min_score

    try:

        vectors, chunks = ensure_index()

        query = _embed([question], "query")[0]

        scores = vectors @ query

        results = []

        for index, base_score in enumerate(scores):

            score = float(base_score) + _keyword_bonus(question, chunks[index])

            results.append((score, index))

        results.sort(reverse=True)

        selected = []

        for score, index in results[: top_k * 2 if debug else top_k]:

            if score < min_score and not debug:
                continue

            chunk = dict(chunks[index])

            chunk["score"] = round(min(score, 1.0), 3)

            selected.append(chunk)

        return selected

    except RAGUnavailable as exc:
        logger.warning("RAG unavailable: %s", exc)
        return []

    except Exception as exc:
        logger.exception("RAG retrieval failed: %s", exc)
        return []


# ============================================================
# FORMAT FOR THE PROMPT / ANSWER
# ============================================================

def format_context(chunks: List[dict]) -> str:

    if not chunks:
        return ""

    parts = []

    for number, chunk in enumerate(chunks, start=1):

        label = chunk["title"]

        if chunk["heading"]:
            label += f" > {chunk['heading']}"

        parts.append(f"[{number}] {label}\n{chunk['text']}")

    return "\n\n".join(parts)


def format_sources(chunks: List[dict]) -> str:
    """One short line listing the documents that were used."""

    if not chunks:
        return ""

    seen = []

    for chunk in chunks:

        name = chunk["title"]

        if name not in seen:
            seen.append(name)

    return "Sources (general guideline): " + "; ".join(seen)


# ============================================================
# COMMAND LINE
# ============================================================

def _status():

    print(f"Knowledge folder : {KNOWLEDGE_DIR}")
    print(f"Embedding model  : {OLLAMA_EMBED_MODEL}")
    print(f"Index folder     : {RAG_INDEX_DIR}")

    try:
        chunks = load_chunks()
        files = sorted({c['source'] for c in chunks})
        print(f"Documents        : {len(files)} files, {len(chunks)} chunks")
        for name in files:
            print(f"   - {name}")
    except RAGUnavailable as exc:
        print(f"Documents        : {exc}")

    try:
        tags = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5).json()
        installed = [m["name"] for m in tags.get("models", [])]
        print(f"Ollama models    : {', '.join(installed) or '(none)'}")
        wanted = OLLAMA_EMBED_MODEL
        if not any(name.split(":")[0] == wanted.split(":")[0] for name in installed):
            print(f"   !! '{wanted}' not installed -> ollama pull {wanted}")
    except Exception:
        print("Ollama models    : cannot connect to Ollama")


def _main():

    parser = argparse.ArgumentParser(description="AquaLLM knowledge base")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--ask", type=str)
    args = parser.parse_args()

    if args.status:
        _status()

    if args.rebuild:
        print("Building index ...")
        print(build_index())

    if args.ask:

        results = retrieve(args.ask, debug=True)

        if not results:
            print("No result. Run --status to check Ollama and the model.")

        for chunk in results:

            used = "USED" if chunk["score"] >= RAG_MIN_SCORE else "below threshold"

            print(
                f"\n[{chunk['score']:.3f}] ({used}) "
                f"{chunk['title']} > {chunk['heading']}"
            )
            print(chunk["text"][:200].replace("\n", " ") + " ...")

    if not (args.status or args.rebuild or args.ask):
        parser.print_help()


if __name__ == "__main__":
    _main()
