"""ArthaLens FastAPI application entrypoint."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, automation, chat, documents, intelligence
from app.config import get_settings
from app.database import init_db

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    cfg = get_settings()
    if not cfg.is_groq_configured():
        logger.warning(
            "GROQ_API_KEY is not configured. Set GROQ_API_KEY in backend/.env to enable Ask ArthaLens AI."
        )
    else:
        logger.info(
            "Groq OpenAI-compatible API configured (base_url=%s, model=%s).",
            cfg.groq_base_url,
            cfg.groq_model,
        )
    yield


settings = get_settings()

app = FastAPI(
    title="ArthaLens Financial Intelligence API",
    description="RAG + Hybrid SQL Financial Document Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(intelligence.router)
app.include_router(automation.router)
app.include_router(chat.router)


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": "arthalens-backend"}
