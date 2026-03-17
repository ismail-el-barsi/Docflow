"""Point d'entree FastAPI - DocFlow Backend."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, business, documents
from app.db.mongodb import connect_to_mongo, disconnect_from_mongo, mongo_health

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create Data Lake folders before serving requests.
    base = Path(os.getenv("STORAGE_BASE_PATH", "./storage"))
    for zone in ["bronze", "silver", "gold"]:
        (base / zone).mkdir(parents=True, exist_ok=True)
    logger.info("Data Lake initialise : %s", base.resolve())

    try:
        connect_to_mongo()
    except Exception as exc:
        logger.warning("Connexion MongoDB echouee au demarrage : %s", exc)

    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    logger.info("LLM Provider configure : %s", provider)
    yield
    disconnect_from_mongo()
    logger.info("Arret de DocFlow Backend")


app = FastAPI(
    title="DocFlow API",
    description="Plateforme de traitement automatique de documents administratifs",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(alerts.router)
app.include_router(business.router)


@app.get("/api/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
        "storage": os.getenv("STORAGE_BASE_PATH", "./storage"),
        "mongodb": mongo_health(),
    }
