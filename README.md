# MachineryTrader Scraper (Python + nodriver + MongoDB)

Scrapes **MachineryTrader.com** categories, paginates listings, opens each **fixed-price** card (skips **Current Bid** auctions),
extracts details, and stores results in MongoDB (dedup by listing id).

## What it does

- Opens https://www.machinerytrader.com/
- Reads all category links in `div.categories a.category-content`
- Opens one **tab per category** (best effort; falls back to sequential if tab creation isn't supported)
- For each category tab:
  - Scrapes listing cards from `#listContainer`
  - Skips cards that show **Current Bid**
  - Opens listing detail in the **same tab**
  - Scrapes:
    - `listingId` from URL (and uses it as Mongo `_id`)
    - `url`
    - `breadcrumbs` (flat list)
    - `title`
    - `priceText`
    - `city` (from machine location)
    - `seller` info (name, contact, phone)
    - `specs` (all sections + label/value pairs)
  - Goes to next page until **Next** is disabled

After all categories are scraped, it **does not exit**:

- Sleeps for 24 hours
- Repeats the whole run, only scraping **new IDs** (already in DB are skipped)

## Setup

### 1) Create `.env`

Copy `.env.example` to `.env` and fill your MongoDB connection.

### 2) Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3) Run

```bash
python -m src.main
```

## Notes

- If you see a cookie / consent modal, the scraper attempts to close it automatically. If it fails, close it manually once.
- `HEADLESS=false` is recommended initially for debugging.
