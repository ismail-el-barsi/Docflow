"""Point d'entrée FastAPI — DocFlow Backend."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from datetime import datetime, timezone

from app.api import alerts, auth, business, documents
from app.database import close_connection, get_db

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def _seed_admin(db) -> None:
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@docflow.fr")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin2026!")
    if await db.users.find_one({"email": admin_email}):
        return
    await db.users.insert_one({
        "email": admin_email,
        "full_name": "Administrateur",
        "hashed_password": pwd.hash(admin_password),
        "role": "admin",
        "created_at": datetime.now(timezone.utc),
    })
    logger.info("Admin par défaut créé : %s", admin_email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Créer les dossiers Data Lake au démarrage
    base = Path(os.getenv("STORAGE_BASE_PATH", "./storage"))
    for zone in ["bronze", "silver", "gold"]:
        (base / zone).mkdir(parents=True, exist_ok=True)
    logger.info("Data Lake initialisé : %s", base.resolve())

    # Index MongoDB + seed admin
    db = get_db()
    await db.users.create_index("email", unique=True)
    await _seed_admin(db)
    logger.info("MongoDB connecté et index users créé")

    # Logger le provider LLM
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    logger.info(f"LLM Provider configuré : {provider}")
    yield
    await close_connection()
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

app.include_router(auth.router)
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
