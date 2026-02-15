from __future__ import annotations

import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    # Required
    MONGO_URI: str = Field(default_factory=lambda: os.getenv("MONGO_URI", "").strip())
    DB_NAME: str = Field(default_factory=lambda: os.getenv("DB_NAME", "ElectronDB").strip())
    COLLECTION: str = Field(default_factory=lambda: os.getenv("COLLECTION", "MachineryTrader").strip())

    # Optional
    START_URL: str = Field(default_factory=lambda: os.getenv("START_URL", "https://www.machinerytrader.com/").strip())
    HEADLESS: bool = Field(default_factory=lambda: os.getenv("HEADLESS", "false").strip().lower() == "true")
    PAGE_TIMEOUT_SEC: int = Field(default_factory=lambda: int(os.getenv("PAGE_TIMEOUT_SEC", "60")))
    DETAIL_TIMEOUT_SEC: int = Field(default_factory=lambda: int(os.getenv("DETAIL_TIMEOUT_SEC", "60")))
    SLEEP_AFTER_FULL_RUN_SEC: int = Field(default_factory=lambda: int(os.getenv("SLEEP_AFTER_FULL_RUN_SEC", "86400")))
    MAX_PAGES_PER_CATEGORY: int = Field(default_factory=lambda: int(os.getenv("MAX_PAGES_PER_CATEGORY", "0")))
    CATEGORY_CONCURRENCY: int = int(os.getenv("CATEGORY_CONCURRENCY", "2"))


    def model_post_init(self, __context) -> None:
        if not self.MONGO_URI:
            raise ValueError("MONGO_URI is required in .env")
