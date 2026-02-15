from __future__ import annotations

import re
from urllib.parse import urljoin

BASE = "https://www.machinerytrader.com"


def abs_url(href: str) -> str:
    if not href:
        return ""
    return href if href.startswith("http") else urljoin(BASE, href)


def listing_id_from_url(url: str) -> str:
    m = re.search(r"/for-sale/(\d+)/", url)
    return m.group(1) if m else ""


def clean_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()
