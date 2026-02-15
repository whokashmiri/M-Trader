from __future__ import annotations

from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient

_client: Optional[AsyncIOMotorClient] = None


def get_client(mongo_uri: str) -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(mongo_uri)
    return _client


def get_collection(mongo_uri: str, db_name: str, collection: str):
    client = get_client(mongo_uri)
    return client[db_name][collection]


async def already_have(col, listing_id: str) -> bool:
    if not listing_id:
        return False
    doc = await col.find_one({"_id": listing_id}, {"_id": 1})
    return doc is not None


async def upsert_listing(col, listing: Dict[str, Any]) -> None:
    listing_id = str(listing.get("_id") or "").strip()
    if not listing_id:
        return
    await col.update_one({"_id": listing_id}, {"$set": listing}, upsert=True)
