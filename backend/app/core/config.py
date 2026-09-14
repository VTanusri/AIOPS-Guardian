from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AIOps Guardian"
    api_prefix: str = "/api"
    debug: bool = True

    # SQLite for local demo without Docker; override with Postgres in compose
    database_url: str = ""

    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    llm_provider: str = "auto"  # auto | ollama | mock
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    embedding_model: str = "all-MiniLM-L6-v2"
    chroma_persist_dir: str = str(ROOT_DIR / "knowledge_base" / "chroma_db")
    knowledge_runbooks_dir: str = str(ROOT_DIR / "knowledge_base" / "runbooks")
    knowledge_uploads_dir: str = str(ROOT_DIR / "knowledge_base" / "uploads")

    telemetry_interval_seconds: float = 3.0
    anomaly_window_size: int = 30
    correlation_window_seconds: int = 120

    # Optional — enables private repos + higher rate limits + Actions details
    github_token: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url.strip():
            return self.database_url
        return f"sqlite:///{BACKEND_DIR / 'aiops_guardian.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
