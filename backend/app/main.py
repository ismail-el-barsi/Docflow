"""Point d'entree FastAPI - DocFlow Backend."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, auth, business, documents
from app.database import close_connection, get_db
from app.db.mongodb import connect_to_mongo, disconnect_from_mongo, mongo_health

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
    # Create Data Lake folders before serving requests.
    base = Path(os.getenv("STORAGE_BASE_PATH", "./storage"))
    for zone in ["bronze", "silver", "gold"]:
        (base / zone).mkdir(parents=True, exist_ok=True)
    logger.info("Data Lake initialise : %s", base.resolve())

    # Connexion MongoDB synchrone (datalake)
    try:
        connect_to_mongo()
    except Exception as exc:
        logger.warning("Connexion MongoDB sync echouee : %s", exc)

    # Connexion MongoDB async (auth) + seed admin
    db = get_db()
    await db.users.create_index("email", unique=True)
    await _seed_admin(db)
    logger.info("MongoDB async connecte et index users cree")

    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    logger.info("LLM Provider configure : %s", provider)
    yield

    disconnect_from_mongo()
    await close_connection()
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

app.include_router(auth.router)
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
