"""SQLAlchemy engine, session factory, and pgvector initialization."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ArthaLens ORM models."""


def _create_engine_from_url(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    elif database_url.startswith("postgresql"):
        connect_args = {"connect_timeout": 5}
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


settings = get_settings()
engine = _create_engine_from_url(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def init_db(target_engine=None) -> None:
    """Ensure pgvector extension (on PostgreSQL) and all tables/indexes exist."""
    eng = target_engine or engine
    # Import models so metadata is populated
    import app.models  # noqa: F401

    if eng.dialect.name == "postgresql":
        with eng.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=eng)

    if eng.dialect.name == "postgresql":
        with eng.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
                    "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_chunks_text_gin "
                    "ON document_chunks USING gin (to_tsvector('english', chunk_text))"
                )
            )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
