import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


APP_NAME = os.getenv("APP_NAME", "AquaLLM")
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "aquallm")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


# Safely encode username/password for PostgreSQL URL
DB_USER_ENCODED = quote_plus(DB_USER)
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)


DATABASE_URL = (
    f"postgresql://{DB_USER_ENCODED}:{DB_PASSWORD_ENCODED}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173"
)

LLM_PROVIDER = os.getenv(
    "LLM_PROVIDER",
    "huggingface"
)


# ============================================================
# OLLAMA (LOCAL LLM)
# ============================================================
#
# Change these in .env - no code change needed.
#
#   OLLAMA_MODEL=qwen2.5:7b      (better answers, needs ~8 GB free RAM)
#   OLLAMA_MODEL=qwen2.5:3b      (lighter, for low-RAM laptops)
#
# ============================================================

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434"
).rstrip("/")

OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:7b"
)

OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

# Context window. Ollama's default is small; DB context +
# knowledge chunks need more room or the prompt gets cut.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

# Keep the model loaded in memory (avoids slow reload).
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")


# ============================================================
# RAG - AQUACULTURE KNOWLEDGE BASE
# ============================================================

OLLAMA_EMBED_MODEL = os.getenv(
    "OLLAMA_EMBED_MODEL",
    "nomic-embed-text"
)

OLLAMA_EMBED_TIMEOUT = int(os.getenv("OLLAMA_EMBED_TIMEOUT", "120"))

RAG_ENABLED = os.getenv("RAG_ENABLED", "True").lower() == "true"

# Folder with the .md knowledge documents
KNOWLEDGE_DIR = Path(
    os.getenv(
        "KNOWLEDGE_DIR",
        str(BASE_DIR / "Documents" / "knowledge")
    )
)

# Where the embedding index is cached (auto-created)
RAG_INDEX_DIR = Path(
    os.getenv(
        "RAG_INDEX_DIR",
        str(BASE_DIR / "Backend" / "rag_index")
    )
)

RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# Minimum similarity (0-1) for a chunk to be used.
# Check scores with:  python -m app.services.rag --ask "what is FCR"
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.45"))

RAG_CHUNK_CHARS = int(os.getenv("RAG_CHUNK_CHARS", "900"))
