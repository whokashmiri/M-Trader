# flow.py
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any, Dict, List

import nodriver as uc

from ..db.mongo import already_have, get_collection, upsert_listing
from ..log import log
from .selectors import SEL_BTN_FIRST, SEL_BTN_NEXT
from .js_snippets import JS_GET_CATEGORIES, JS_GET_DETAIL, JS_LIST_PAGE_CARDS
from .utils import abs_url, clean_space, listing_id_from_url


# ----------------------------
# Block detection (NO bypass)
# ----------------------------


JS_GET_CURRENT_PAGE = r"""
(() => {
  const cur = document.querySelector('nav[aria-label="pagination navigation"] button[aria-current="true"]');
  if (!cur) return "";
  return (cur.textContent || "").trim();
})()
""".strip()

JS_GET_PAGINATION_STATE = r"""
(() => {
  const nav = document.querySelector('nav[aria-label="pagination navigation"]');
  if (!nav) return { ok:false };

  const curBtn = nav.querySelector('button[aria-current="true"]');
  const cur = curBtn ? (curBtn.textContent || "").trim() : "";

  const nextBtn = nav.querySelector('button[aria-label="Next Page"]');
  const firstBtn = nav.querySelector('button[aria-label="First Page"]');

  const isDisabled = (el) => {
    if (!el) return true;
    const aria = (el.getAttribute("aria-disabled") || "").toLowerCase() === "true";
    const disAttr = el.hasAttribute("disabled");
    const prop = !!el.disabled;
    const cls = (el.className || "");
    const mui = cls.includes("Mui-disabled");
    return aria || disAttr || prop || mui;
  };

  return {
    ok: true,
    current: cur,
    nextDisabled: isDisabled(nextBtn),
    firstDisabled: isDisabled(firstBtn),
  };
})()
""".strip()

JS_CLICK_NEXT = r"""
(() => {
  const btn = document.querySelector('nav[aria-label="pagination navigation"] button[aria-label="Next Page"]');
  if (!btn) return false;
  try { btn.scrollIntoView({behavior:"instant", block:"center"}); } catch(e) {}
  try { btn.click(); return true; } catch(e) {}
  try {
    btn.dispatchEvent(new MouseEvent("click", {bubbles:true, cancelable:true, view:window}));
    return true;
  } catch(e) {}
  return false;
})()
""".strip()

JS_CLICK_FIRST = r"""
(() => {
  const btn = document.querySelector('nav[aria-label="pagination navigation"] button[aria-label="First Page"]');
  if (!btn) return false;
  try { btn.scrollIntoView({behavior:"instant", block:"center"}); } catch(e) {}
  try { btn.click(); return true; } catch(e) {}
  try {
    btn.dispatchEvent(new MouseEvent("click", {bubbles:true, cancelable:true, view:window}));
    return true;
  } catch(e) {}
  return false;
})()
""".strip()

# Optional: a small "signature" of the list that changes per page
JS_GET_LIST_SIGNATURE = r"""
(() => {
  const ids = Array.from(document.querySelectorAll('#listContainer .listing-card-grid[data-listing-id]'))
    .slice(0, 8)
    .map(el => el.getAttribute('data-listing-id') || "")
    .filter(Boolean);
  return ids.join(",");
})()
""".strip()

JS_IS_BLOCKED = r"""
(() => {
  const t = (document.title || "").toLowerCase();
  const b = (document.body?.innerText || "").toLowerCase();
  return (
    t.includes("pardon our interruption") ||
    b.includes("pardon our interruption") ||
    b.includes("made us think you were a bot") ||
    b.includes("enable cookies") ||
    b.includes("blocked")
  );
})()
""".strip()


def unwrap_remote(obj: Any) -> Any:
    """
    nodriver sometimes returns RemoteObject-like dicts:
      {"type":"object","value":...}
    or nested versions of that. This unwraps it recursively.
    """
    if isinstance(obj, dict) and "type" in obj and "value" in obj:
        return unwrap_remote(obj["value"])
    if isinstance(obj, list):
        return [unwrap_remote(x) for x in obj]
    if isinstance(obj, dict):
        return {k: unwrap_remote(v) for k, v in obj.items()}
    return obj


def as_dict(x: Any) -> Dict[str, Any]:
    """
    Convert:
      - dict -> dict
      - list of [key, value] pairs -> dict
    """
    if isinstance(x, dict):
        return x
    if isinstance(x, list):
        if all(isinstance(it, (list, tuple)) and len(it) == 2 for it in x):
            try:
                return {str(k): v for k, v in x}
            except Exception:
                return {}
    return {}


async def _sleep(seconds: int) -> None:
    for _ in range(int(seconds)):
        await asyncio.sleep(1)


async def _wait_for(page: Any, css: str, timeout: float = 60.0) -> bool:
    import time

    end = time.time() + timeout
    while time.time() < end:
        try:
            ok = await page.evaluate(f"document.querySelector({css!r}) !== null")
            if bool(ok):
                return True
        except Exception:
            pass
        await asyncio.sleep(0.25)
    return False


async def _assert_not_blocked(tab: Any, where: str = "") -> bool:
    try:
        blocked = await tab.evaluate(JS_IS_BLOCKED)
        blocked = unwrap_remote(blocked)
        if blocked:
            log(f"[block] Detected block page{(' @ ' + where) if where else ''}. Stopping this category browser.")
            return False
    except Exception:
        pass
    return True


async def _close_popups(page: Any) -> None:
    """
    Close cookie/consent/modals safely.
    - NEVER click normal links (<a href=...>) because that can navigate away.
    - Prefer explicit close / accept buttons.
    """
    js = r"""
(() => {
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim().toLowerCase();

  const explicit = [
    "button[aria-label*='close' i]",
    "button[title*='close' i]",
    "button[data-testid*='close' i]",
    "button[class*='close' i]",
    "[role='button'][aria-label*='close' i]",
  ];
  for (const sel of explicit) {
    const el = document.querySelector(sel);
    if (el) { try { el.click(); return {clicked: true, text: norm(el.textContent)}; } catch(e) {} }
  }

  const btns = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit'], [role='button']"))
    .filter(el => el && el.offsetParent !== null);

  const allow = ["accept","agree","i agree","allow","got it","ok","okay","dismiss","close","continue"];

  for (const b of btns) {
    const t = norm(b.textContent || b.value || "");
    if (!t) continue;
    if (t.length > 30) continue; // avoid clicking random ads
    if (allow.some(w => t === w || t.includes(w))) {
      try { b.click(); return {clicked: true, text: t}; } catch(e) {}
    }
  }

  return {clicked: false, text: ""};
})()
""".strip()

    try:
        res = await page.evaluate(js)
        res = unwrap_remote(res)
        if isinstance(res, list):
            res = as_dict(res)
        if isinstance(res, dict) and res.get("clicked"):
            log(f"[ui] closed popup via: {res.get('text')}")
    except Exception:
        pass


# ----------------------------
# Robust MUI pagination helpers
# ----------------------------
JS_BTN_IS_DISABLED = r"""
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return true;

  const aria = (el.getAttribute("aria-disabled") || "").toLowerCase() === "true";
  const disAttr = el.hasAttribute("disabled");
  const prop = !!el.disabled;
  const cls = (el.className || "");
  const mui = cls.includes("Mui-disabled");

  return aria || disAttr || prop || mui;
}
""".strip()

JS_BTN_CLICK = r"""
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return false;

  try { el.scrollIntoView({behavior:"instant", block:"center", inline:"center"}); } catch(e) {}

  try { el.click(); return true; } catch(e) {}

  try {
    const evt = new MouseEvent("click", {bubbles:true, cancelable:true, view:window});
    el.dispatchEvent(evt);
    return true;
  } catch(e) {}

  return false;
}
""".strip()


async def _get_first_listing_id(tab: Any) -> str:
    try:
        raw = await tab.evaluate(JS_LIST_PAGE_CARDS)
        raw = unwrap_remote(raw)
        if not isinstance(raw, list) or not raw:
            return ""
        first = as_dict(raw[0])
        return str(first.get("listingId") or "").strip()
    except Exception:
        return ""


async def _click_next_and_wait(tab: Any, settings) -> bool:
    if not await _assert_not_blocked(tab, "before-next"):
        return False

    # snapshot BEFORE
    before_state = unwrap_remote(await tab.evaluate(JS_GET_PAGINATION_STATE))
    if isinstance(before_state, list):
        before_state = as_dict(before_state)

    if not isinstance(before_state, dict) or not before_state.get("ok"):
        return False

    if before_state.get("nextDisabled"):
        return False

    before_page = str(before_state.get("current") or "").strip()
    before_sig = ""
    try:
        before_sig = unwrap_remote(await tab.evaluate(JS_GET_LIST_SIGNATURE)) or ""
    except Exception:
        pass

    clicked = unwrap_remote(await tab.evaluate(JS_CLICK_NEXT))
    if not clicked:
        return False

    # wait until pagination current page changes OR list signature changes
    for _ in range(160):  # ~40 seconds
        await asyncio.sleep(0.25)

        if not await _assert_not_blocked(tab, "after-next"):
            return False

        st = unwrap_remote(await tab.evaluate(JS_GET_PAGINATION_STATE))
        if isinstance(st, list):
            st = as_dict(st)
        if not isinstance(st, dict) or not st.get("ok"):
            continue

        after_page = str(st.get("current") or "").strip()

        # primary: MUI aria-current page number changes
        if after_page and before_page and after_page != before_page:
            # give list time to render
            await asyncio.sleep(0.8)
            return True

        # secondary: list content signature changes
        try:
            after_sig = unwrap_remote(await tab.evaluate(JS_GET_LIST_SIGNATURE)) or ""
            if after_sig and before_sig and after_sig != before_sig:
                await asyncio.sleep(0.8)
                return True
        except Exception:
            pass

    return False


async def _goto_first_page(tab: Any, settings) -> None:
    # click first page until it becomes disabled (meaning you're on page 1)
    for _ in range(5):
        st = unwrap_remote(await tab.evaluate(JS_GET_PAGINATION_STATE))
        if isinstance(st, list):
            st = as_dict(st)
        if not isinstance(st, dict) or not st.get("ok"):
            return
        if st.get("firstDisabled"):
            return  # already on first
        await tab.evaluate(JS_CLICK_FIRST)
        await asyncio.sleep(1.0 + random.random() * 3)


# ----------------------------
# Categories
# ----------------------------
async def _open_categories_only(start_tab: Any, start_url: str, timeout: int) -> List[Dict[str, Any]]:
    """
    Open homepage and read all categories.
    DO NOT open tabs here.
    """
    await start_tab.get(start_url)

    await _wait_for(start_tab, "body", timeout=timeout)
    await asyncio.sleep(1.0)
    await _close_popups(start_tab)

    await _wait_for(start_tab, "div.categories, div.category[category-id], a.category-content", timeout=timeout)

    # small scroll to trigger hydration
    try:
        await start_tab.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.6)")
        await asyncio.sleep(0.7)
        await start_tab.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.3)
    except Exception:
        pass

    try:
        c1 = await start_tab.evaluate("document.querySelectorAll('div.categories').length")
        c2 = await start_tab.evaluate("document.querySelectorAll('div.category[category-id]').length")
        c3 = await start_tab.evaluate("document.querySelectorAll('a.category-content[href]').length")
        log(f"[cats:dbg] div.categories={c1} category blocks={c2} anchors={c3}")
    except Exception:
        pass

    cats: List[Dict[str, Any]] = []
    for _ in range(1, 8):
        try:
            raw = await start_tab.evaluate(JS_GET_CATEGORIES)
            raw = unwrap_remote(raw)
            if isinstance(raw, list) and raw:
                tmp = [as_dict(x) for x in raw]
                tmp = [c for c in tmp if isinstance(c, dict) and c.get("href")]
                if tmp:
                    cats = tmp
                    break
        except Exception:
            pass
        await asyncio.sleep(0.6)

    out: List[Dict[str, Any]] = []
    for c in cats:
        href = abs_url(str(c.get("href") or "").strip())
        label = clean_space(str(c.get("label") or "").strip())
        cid = clean_space(str(c.get("categoryId") or "").strip())

        if not href or "/listings/for-sale/" not in href:
            continue

        out.append({"label": label, "categoryId": cid, "url": href})

    log(f"[cats] prepared {len(out)} categories")
    if out:
        log(f"[cats] sample={out[:3]}")
    return out


# ----------------------------
# Detail + Category scraping
# ----------------------------
async def _scrape_listing_detail(tab: Any, listing_url: str, category: Dict[str, Any], settings) -> Dict[str, Any]:
    await tab.get(listing_url)

    if not await _assert_not_blocked(tab, "detail"):
        return {}

    await _wait_for(
        tab,
        "div.detail__title-container, h1.detail__title, div.detail__breadcrumbs",
        timeout=settings.DETAIL_TIMEOUT_SEC,
    )
    await _close_popups(tab)

    detail = await tab.evaluate(JS_GET_DETAIL)
    detail = unwrap_remote(detail)
    if isinstance(detail, list):
        detail = as_dict(detail)
    if not isinstance(detail, dict):
        detail = {}

    listing_id = listing_id_from_url(listing_url)
    now = datetime.now(timezone.utc).isoformat()

    return {
        "_id": listing_id,
        "source": "machinerytrader",
        "url": listing_url,
        "category": {
            "label": category.get("label", ""),
            "categoryId": category.get("categoryId", ""),
            "url": category.get("url", ""),
        },
        "breadcrumbs": detail.get("breadcrumbs") or [],
        "title": detail.get("title") or "",
        "priceText": detail.get("priceText") or "",
        "city": detail.get("city") or "",
        "machineLocationText": detail.get("machineLocationText") or "",
        "seller": detail.get("seller") or {},
        "specs": detail.get("specs") or {},
        "updatedText": detail.get("updatedText") or "",
        "scrapedAt": now,
    }


async def _scrape_category(tab: Any, category: Dict[str, Any], col, settings) -> int:
    url = category["url"]
    log(f"[cat] {category.get('label') or url}")

    await tab.get(url)
    if not await _assert_not_blocked(tab, "category-load"):
        return 0

    await _wait_for(tab, "div#listContainer", timeout=settings.PAGE_TIMEOUT_SEC)
    await _wait_for(tab, 'nav[aria-label="pagination navigation"]', timeout=settings.PAGE_TIMEOUT_SEC)

    await _close_popups(tab)

    new_count = 0
    page_no = 1

    while True:
        if not await _assert_not_blocked(tab, f"category-page-{page_no}"):
            break

        await _wait_for(tab, "div#listContainer", timeout=settings.PAGE_TIMEOUT_SEC)
        await _wait_for(tab, 'nav[aria-label="pagination navigation"]', timeout=settings.PAGE_TIMEOUT_SEC)


        raw_cards = await tab.evaluate(JS_LIST_PAGE_CARDS)
        raw_cards = unwrap_remote(raw_cards)
        if not isinstance(raw_cards, list):
            raw_cards = []

        cards = [as_dict(x) for x in raw_cards]
        auction_n = sum(1 for x in cards if x.get("isAuction"))
        log(f"[cat] page={page_no} cards={len(cards)} auctions={auction_n}")

        for c in cards:
            # must be a machinerytrader listing detail
            href = abs_url(str(c.get("href") or ""))
            if not href.startswith("https://www.machinerytrader.com/"):
                continue
            if "/listing/for-sale/" not in href:
                continue

            # skip auction cards
            if c.get("isAuction"):
                continue

            listing_id = str(c.get("listingId") or "").strip() or listing_id_from_url(href)
            if not listing_id:
                continue

            if await already_have(col, listing_id):
                continue

            try:
                log(f"[open] {listing_id} {href}")
                doc = await _scrape_listing_detail(tab, href, category, settings)
                if doc and doc.get("_id"):
                    await upsert_listing(col, doc)
                    new_count += 1
                    log(f"[save] new id={listing_id} title={doc.get('title','')}")
            except Exception as e:
                log(f"[err] detail failed id={listing_id} err={e}")

            # back to list
            try:
                await tab.back()
                await _wait_for(tab, "div#listContainer", timeout=settings.PAGE_TIMEOUT_SEC)
                await _wait_for(tab, 'nav[aria-label="pagination navigation"]', timeout=settings.PAGE_TIMEOUT_SEC)

            except Exception:
                await tab.get(url)
                await _wait_for(tab, "div#listContainer", timeout=settings.PAGE_TIMEOUT_SEC)
                await _wait_for(tab, 'nav[aria-label="pagination navigation"]', timeout=settings.PAGE_TIMEOUT_SEC)


            # gentle pacing
            await asyncio.sleep(1.0 + random.random() * 3)

        if settings.MAX_PAGES_PER_CATEGORY and page_no >= settings.MAX_PAGES_PER_CATEGORY:
            break

        advanced = await _click_next_and_wait(tab, settings)
        if not advanced:
            break

        page_no += 1
        await asyncio.sleep(1.0 + random.random() * 3.0)

    await _goto_first_page(tab, settings)

    log(f"[cat:done] {category.get('label')} new={new_count} pages={page_no}")
    return new_count


async def _scrape_one_category_in_new_browser(category: Dict[str, Any], settings, col) -> int:
    browser = await uc.start(headless=settings.HEADLESS)
    try:
        tab = await browser.get(category["url"])
        await asyncio.sleep(0.8)
        await _close_popups(tab)

        if not await _assert_not_blocked(tab, "category-browser-start"):
            return 0

        return await _scrape_category(tab, category, col, settings)
    finally:
        try:
            await browser.stop()
        except Exception:
            pass


# ----------------------------
# Run orchestration
# ----------------------------
async def run_once(browser: Any, settings) -> int:
    col = get_collection(settings.MONGO_URI, settings.DB_NAME, settings.COLLECTION)

    start_tab = await browser.get(settings.START_URL)
    categories = await _open_categories_only(start_tab, settings.START_URL, settings.PAGE_TIMEOUT_SEC)
    if not categories:
        log("[run] no categories found")
        return 0

    raw_limit = getattr(settings, "CATEGORY_CONCURRENCY", None)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 2

    if limit <= 0:
        limit = len(categories)
    limit = min(limit, len(categories))

    log(f"[run] CATEGORY_CONCURRENCY={limit}")

    sem = asyncio.Semaphore(limit)

    async def worker(cat: Dict[str, Any]) -> int:
        async with sem:
            active = limit - sem._value
            log(f"[debug] ACTIVE_BROWSERS={active}/{limit} -> {cat.get('label')}")
            try:
                return await _scrape_one_category_in_new_browser(cat, settings, col)
            except Exception as e:
                log(f"[run] category failed {cat.get('label')} err={e}")
                return 0

    results = await asyncio.gather(*(worker(c) for c in categories))
    total_new = sum(int(x or 0) for x in results)

    log(f"[run] DONE total_new={total_new} categories={len(categories)} concurrency={limit}")
    return total_new


async def run_forever(browser: Any, settings) -> None:
    while True:
        try:
            new_count = await run_once(browser, settings)
            log(f"[sleep] Sleeping {settings.SLEEP_AFTER_FULL_RUN_SEC}s (24h default). new_count={new_count}")
            await _sleep(settings.SLEEP_AFTER_FULL_RUN_SEC)
        except KeyboardInterrupt:
            log("[stop] KeyboardInterrupt")
            break
        except Exception as e:
            log(f"[fatal] {e}")
            await _sleep(300)
