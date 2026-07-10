"""
Central project configuration.

Loads .env once, exposes paths and pipeline constants everything else uses.
Import this from anywhere to get configured paths and settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.resolve()

# Load .env from project root (override=True so .env wins over inherited shell vars)
load_dotenv(PROJECT_ROOT / ".env", override=True)

# --- Project paths ---
DATA_DIR = PROJECT_ROOT / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"      # raw documents to ingest
CHROMA_DIR = DATA_DIR / "chroma"            # vector store on disk
STATE_DIR = DATA_DIR / "state"              # walker state, indexes, metadata
LOGS_DIR = PROJECT_ROOT / "logs"

for d in (DATA_DIR, DOCUMENTS_DIR, CHROMA_DIR, STATE_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- Ingestion pipeline ---
CHUNK_SIZE_TOKENS = int(os.getenv("CHUNK_SIZE_TOKENS", "500"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "50"))
VECTOR_DB_PROVIDER = os.getenv("VECTOR_DB_PROVIDER", "chromadb").lower()
VESSEL_NAMESPACE = os.getenv("VESSEL_NAMESPACE", "gelliceaux_001")

# --- Retrieval ---
_threshold = os.getenv("RETRIEVAL_DISTANCE_THRESHOLD")
RETRIEVAL_DISTANCE_THRESHOLD: float | None = float(_threshold) if _threshold else None

# --- Sensors (Exocet read-only data tap; architecture rule 2: never write to vessel systems) ---
EXOCET_URL = os.getenv("EXOCET_URL", "http://192.168.1.101/data")
EXOCET_POLL_INTERVAL_SECONDS = int(os.getenv("EXOCET_POLL_INTERVAL_SECONDS", "60"))
