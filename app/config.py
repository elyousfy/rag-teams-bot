"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent

# Azure Bot Configuration
AZURE_APP_ID = os.getenv("AZURE_APP_ID", "")
AZURE_APP_SECRET = os.getenv("AZURE_APP_SECRET", "")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")  # Required for client credentials
ALLOWED_AD_GROUP_ID = os.getenv("ALLOWED_AD_GROUP_ID", "")

# Ollama Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:14b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Paths
DOCUMENTS_PATH = Path(os.getenv("DOCUMENTS_PATH", BASE_DIR / "data" / "documents"))
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", BASE_DIR / "data" / "chroma"))

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# RAG Configuration
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
TOP_K = 5
CONVERSATION_MEMORY_SIZE = 5

# Embedding dimensions for nomic-embed-text
EMBED_DIM = 768
