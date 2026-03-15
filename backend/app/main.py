"""Point d'entrée FastAPI — DocFlow Backend."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, business, documents

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Créer les dossiers Data Lake au démarrage
    base = Path(os.getenv("STORAGE_BASE_PATH", "./storage"))
    for zone in ["bronze", "silver", "gold"]:
        (base / zone).mkdir(parents=True, exist_ok=True)
    logger.info("Data Lake initialisé : %s", base.resolve())
    
    # Logger le provider LLM
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    logger.info(f"LLM Provider configuré : {provider}")
    yield
    logger.info("Arrêt de DocFlow Backend")


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
        "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
        "storage": os.getenv("STORAGE_BASE_PATH", "./storage"),
    }
