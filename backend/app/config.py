"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for ArthaLens backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://arthalens:arthalens_dev_password@localhost:5432/arthalens"
    )
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    jwt_secret_key: str = "dev-only-change-in-production-arthalens-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    upload_storage_dir: str = "./storage/uploads"
    max_upload_size_mb: int = 20

    chunk_size_tokens: int = 900
    chunk_overlap_tokens: int = 125
    retrieval_top_k: int = 6
    similarity_threshold: float = 0.15

    arthalens_reference_date: Optional[str] = "2026-05-15"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def storage_path(self) -> Path:
        p = Path(self.upload_storage_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
