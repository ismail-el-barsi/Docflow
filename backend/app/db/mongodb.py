"""MongoDB connection management for DocFlow ."""

import logging
import os
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

_client: MongoClient | None = None
_database: Database | None = None


def get_mongodb_uri() -> str:
    return os.getenv("MONGODB_URI", "mongodb://localhost:27017")


def get_mongodb_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "docflow")


def connect_to_mongo() -> Database:
    global _client, _database

    if _database is not None:
        return _database

    uri = get_mongodb_uri()
    db_name = get_mongodb_db_name()

    _client = MongoClient(uri, serverSelectionTimeoutMS=3000, uuidRepresentation="standard")
    _database = _client[db_name]
    _client.admin.command("ping")

    logger.info("MongoDB connecte : %s/%s", uri, db_name)
    _ensure_indexes(_database)
    return _database


def disconnect_from_mongo() -> None:
    global _client, _database

    if _client is not None:
        _client.close()
        logger.info("Connexion MongoDB fermee")

    _client = None
    _database = None


def get_database() -> Database:
    if _database is None:
        return connect_to_mongo()
    return _database


def get_collection(name: str) -> Collection:
    return get_database()[name]


def mongo_health() -> dict[str, Any]:
    try:
        db = get_database()
        db.command("ping")
        return {
            "status": "ok",
            "uri": get_mongodb_uri(),
            "database": db.name,
        }
    except PyMongoError as exc:
        logger.warning("MongoDB indisponible : %s", exc)
        return {
            "status": "error",
            "uri": get_mongodb_uri(),
            "database": get_mongodb_db_name(),
            "error": str(exc),
        }


def _ensure_indexes(database: Database) -> None:
    database["bronze"].create_index("document.id", unique=True)
    database["silver"].create_index("document_id", unique=True)
    database["gold"].create_index("document_id", unique=True)
    database["gold"].create_index("extraction.siren")
    database["gold"].create_index("extraction.emetteur_nom")
    database["gold"].create_index("alerts.id")
