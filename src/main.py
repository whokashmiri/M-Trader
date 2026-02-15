from __future__ import annotations

import asyncio

from .settings import Settings
from .log import log
from .core.browser import start_browser
from .machinerytrader.flow import run_forever


async def main() -> None:
    s = Settings()
    log(f"[boot] START_URL={s.START_URL}")
    log(f"[boot] HEADLESS={s.HEADLESS} DB={s.DB_NAME}.{s.COLLECTION}")

    browser = await start_browser(headless=s.HEADLESS)
    try:
        await run_forever(browser, s)
    finally:
        try:
            await browser.stop()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
