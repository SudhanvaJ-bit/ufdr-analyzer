from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "UFDR Forensic Analysis Tool"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/sqlite_db/ufdr_forensics.db"
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    SAMPLE_DATA_DIR: Path = BASE_DIR / "data" / "sample_ufdr"
    CHROMA_DB_DIR: str = str(BASE_DIR / "vector_db")
    CHROMA_COLLECTION_NAME: str = "forensic_evidence"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    GEMINI_MODEL: str = "gemini-1.5-flash"
    RAG_TOP_K: int = 15
    MAX_RESPONSE_TOKENS: int = 2048
    SUSPICIOUS_KEYWORDS: list = [
        "bitcoin", "crypto", "wallet", "btc", "eth", "usdt",
        "drugs", "cocaine", "heroin", "meth", "weed", "ganja",
        "gun", "weapon", "bomb", "explosive", "arms",
        "money laundering", "hawala", "transfer", "cash",
        "fake", "fraud", "scam", "phishing",
        "kill", "threat", "eliminate", "target",
        "dark web", "tor", "vpn", "anonymous",
        "meet", "delivery", "package", "shipment",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
