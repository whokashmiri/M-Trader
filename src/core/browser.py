from __future__ import annotations

import nodriver as uc

from ..log import log


async def start_browser(headless: bool = False):
    log(f"[boot] Starting browser headless={headless}")
    browser = await uc.start(headless=headless)
    log("[boot] Browser started")
    return browser
