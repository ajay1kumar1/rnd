"""
Centralised configuration loaded from .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/stocks.db")
    DATA_PROVIDER: str = os.getenv("DATA_PROVIDER", "yfinance")
    ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")

    RSI_PERIOD: int = int(os.getenv("RSI_PERIOD", "14"))
    RSI_BUY_THRESHOLD: float = float(os.getenv("RSI_BUY_THRESHOLD", "40"))

    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    AUTO_REFRESH_INTERVAL_SECONDS: int = int(os.getenv("AUTO_REFRESH_INTERVAL_SECONDS", "300"))

    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")

    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    @property
    def database_url(self) -> str:
        db_path = (BASE_DIR / self.DATABASE_PATH).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"

    @property
    def chroma_path(self) -> str:
        path = (BASE_DIR / "data" / "chroma_store").resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)


settings = Settings()
