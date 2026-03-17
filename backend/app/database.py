"""MongoDB connection — DocFlow."""
from __future__ import annotations

import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        url = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        _client = AsyncIOMotorClient(url)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    db_name = os.getenv("MONGODB_DB_NAME", "docflow")
    return get_client()[db_name]


async def close_connection() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
