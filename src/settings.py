from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


def _env_str(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _env_int(name: str, default: int = 0) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw)
    except Exception:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw in ("1", "true", "yes", "y", "on"):
        return True
    if raw in ("0", "false", "no", "n", "off"):
        return False
    return default


class Settings(BaseModel):
    # Required
    MONGO_URI: str = Field(default_factory=lambda: _env_str("MONGO_URI", ""))
    DB_NAME: str = Field(default_factory=lambda: _env_str("DB_NAME", "ElectronDB"))
    COLLECTION: str = Field(default_factory=lambda: _env_str("COLLECTION", "MachineryTrader"))

    # Optional
    START_URL: str = Field(default_factory=lambda: _env_str("START_URL", "https://www.machinerytrader.com/"))
    HEADLESS: bool = Field(default_factory=lambda: _env_bool("HEADLESS", False))
    PAGE_TIMEOUT_SEC: int = Field(default_factory=lambda: _env_int("PAGE_TIMEOUT_SEC", 60))
    DETAIL_TIMEOUT_SEC: int = Field(default_factory=lambda: _env_int("DETAIL_TIMEOUT_SEC", 60))
    SLEEP_AFTER_FULL_RUN_SEC: int = Field(default_factory=lambda: _env_int("SLEEP_AFTER_FULL_RUN_SEC", 86400))
    MAX_PAGES_PER_CATEGORY: int = Field(default_factory=lambda: _env_int("MAX_PAGES_PER_CATEGORY", 0))

    # Concurrency (still used if you ever scrape all categories)
    CATEGORY_CONCURRENCY: int = Field(default_factory=lambda: _env_int("CATEGORY_CONCURRENCY", 2))

    # ✅ New: single-category selection
    CATEGORY_PICK: Optional[int] = Field(default_factory=lambda: (_env_int("CATEGORY_PICK", 0) or None))
    CATEGORY_ID: Optional[str] = Field(default_factory=lambda: (_env_str("CATEGORY_ID", "") or None))
    CATEGORY_LABEL: Optional[str] = Field(default_factory=lambda: (_env_str("CATEGORY_LABEL", "") or None))

    def model_post_init(self, __context) -> None:
        if not self.MONGO_URI:
            raise ValueError("MONGO_URI is required in .env")

        # Normalize empty strings to None (extra safety)
        if self.CATEGORY_ID is not None and not self.CATEGORY_ID.strip():
            
            self.CATEGORY_ID = None
        if self.CATEGORY_LABEL is not None and not self.CATEGORY_LABEL.strip():
            self.CATEGORY_LABEL = None


        # If CATEGORY_PICK <= 0 treat as not set
        if self.CATEGORY_PICK is not None and self.CATEGORY_PICK <= 0:
            self.CATEGORY_PICK = None