# JS snippets executed in the browser context

JS_GET_CATEGORIES = r"""
(() => {
  const out = [];
  const root = document.querySelector("div.categories");
  if (!root) return out;

  root.querySelectorAll("div.category[category-id]").forEach(cat => {
    const a = cat.querySelector("a.category-content[href]") || cat.querySelector("a[href]");
    if (!a) return;

    out.push({
      href: a.getAttribute("href") || "",
      label: (a.getAttribute("aria-label") || a.textContent || "").trim(),
      categoryId: cat.getAttribute("category-id") || ""
    });
  });

  return out;
})()
""".strip()

JS_LIST_PAGE_CARDS = r"""
(() => {
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const cards = [];
  const container = document.querySelector("#listContainer");
  if (!container) return cards;

  container.querySelectorAll("div.list-listing-card-wrapper").forEach(w => {
    const grid = w.querySelector("div.listing-card-grid.listing-data-selector");
    if (!grid) return;

    const listingId = grid.getAttribute("data-listing-id") || w.querySelector("[data-listing-id]")?.getAttribute("data-listing-id") || "";

    // Prefer View Details or title link
    const a =
      w.querySelector("a.view-listing-details-link[href]") ||
      w.querySelector("a.list-listing-title-link[href]") ||
      w.querySelector("a[aria-label^='View Details'][href]");

    const href = a ? (a.getAttribute("href") || "") : "";

    // Detect auction
    const priceBox = w.querySelector(".retail-price-container");
    const hasAuctionPrice = !!w.querySelector(".auction-price");
    const isAuctionByText = /current bid/i.test(norm(priceBox?.textContent || ""));
    const isAuctionByTiles = !!w.querySelector(".lot-number, .live-tile, .left-flavor.at");
    const isExternal = href.startsWith("http") && !href.includes("machinerytrader.com");
    const isAuction = hasAuctionPrice || isAuctionByText || isAuctionByTiles || isExternal;

    // Quick fields from card
    const title = norm(w.querySelector(".listing-portion-title")?.getAttribute("title") || w.querySelector(".listing-portion-title")?.textContent || "");
    const cardCategory = norm(w.querySelector(".listing-category")?.textContent || "");
    const priceText = norm(w.querySelector(".retail-price-container .price")?.textContent || "");

    // Image (first)
    const img = w.querySelector("img.listing-main-img");
    const image = img ? (img.getAttribute("src") || "") : "";

    // Location (card-level)
    const locationText = norm(w.querySelector(".machine-location")?.textContent || "");

    // Seller (card-level)
    const sellerText = norm(w.querySelector(".seller")?.textContent || "");
    const phone = norm(w.querySelector("a.phone-link strong")?.textContent || w.querySelector("a.phone-link")?.textContent || "");
    const phoneHref = w.querySelector("a.phone-link")?.getAttribute("href") || "";

    // data-* attrs (on the main listing node; in your sample: inside list-premium-listing)
    const root = w.querySelector("[data-item-name]") || w.querySelector("[data-currency]") || w.querySelector("[data-price]") || w;
    const currency = root.getAttribute("data-currency") || "";
    const brand = root.getAttribute("data-item-brand") || "";
    const itemCategory = root.getAttribute("data-item-category") || "";
    const itemName = root.getAttribute("data-item-name") || "";
    const priceNum = root.getAttribute("data-price") || "";
    const offers = root.getAttribute("data-offers") || "";

    // Specs visible on card (Hours, etc.)
    const specs = {};
    w.querySelectorAll(".list-spec .spec").forEach(s => {
      const k = norm(s.querySelector(".spec-label")?.textContent || "").replace(/:\s*$/,"");
      const v = norm(s.querySelector(".spec-value")?.textContent || "");
      if (k) specs[k] = v;
    });

    cards.push({
      listingId,
      href,
      isAuction,
      title,
      cardCategory,
      priceText,
      image,
      locationText,
      sellerText,
      phone,
      phoneHref,
      currency,
      brand,
      itemCategory,
      itemName,
      priceNum,
      offers,
      cardSpecs: specs,
    });
  });

  return cards;
})()
""".strip()

JS_IS_DISABLED = r"""
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return true;
  const aria = (el.getAttribute("aria-disabled") || "").toLowerCase() === "true";
  const disAttr = el.hasAttribute("disabled");
  const propDisabled = !!el.disabled;
  const cls = (el.className || "");
  const mui = cls.includes("Mui-disabled");
  return aria || disAttr || propDisabled || mui;
}
""".strip()

JS_CLICK = r"""
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return false;
  try {
    el.scrollIntoView({behavior:"instant", block:"center", inline:"center"});
  } catch(e) {}
  try { el.click(); return true; } catch(e) {}
  try {
    const evt = new MouseEvent("click", {bubbles:true, cancelable:true, view:window});
    el.dispatchEvent(evt);
    return true;
  } catch(e) {}
  return false;
}
""".strip()

JS_GET_DETAIL = r"""
(() => {
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const text = (sel) => norm(document.querySelector(sel)?.textContent || "");

  const out = {};
  out.url = location.href;

  // --------------------
  // Title
  // --------------------
  out.title =
    text("h1.detail__title") ||
    norm(document.querySelector("meta[property='og:title']")?.getAttribute("content") || "") ||
    text("h1");

  // --------------------
  // Price
  // --------------------
  out.priceText =
    text("strong.listing-prices__retail-price") ||
    text(".listing-prices__retail-price") ||
    text(".retail-price-container .price");

  // --------------------
  // Breadcrumbs
  // --------------------
  const crumbs = [];
  const bcRoot = document.querySelector("div.detail__breadcrumbs ul.breadcrumbs__list");
  if (bcRoot) {
    bcRoot.querySelectorAll("li.breadcrumbs__list-item").forEach(li => {
      const a = li.querySelector("a.breadcrumbs__link");
      const p = li.querySelector("p.breadcrumbs__link");
      const t = norm((a || p)?.textContent || "");
      if (t) crumbs.push(t.replace(/>\s*$/, "").trim());
    });
  }
  out.breadcrumbs = crumbs;

  // --------------------
  // Machine location (city only)
  // --------------------
  out.city = "";
  out.machineLocationText = "";

  const loc = document.querySelector("div.detail__machine-location");
  if (loc) {
    const full = norm(loc.textContent || "");
    // full often like: "Machine Location: 3431 SE 21st St Topeka, Kansas 66607"
    out.machineLocationText = full;

    // try to take the "City" part before comma after street
    // if we have an address span, remove it first
    const street = norm(loc.querySelector("span.detail__machine-location-address")?.textContent || "");
    let tail = full;
    if (street && tail.includes(street)) {
      tail = tail.split(street).slice(1).join(street).trim();
    }
    // tail now often: "Topeka, Kansas 66607"
    const city = norm((tail.split(",")[0] || "").trim());
    out.city = city;
  }

  // --------------------
  // Seller info
  // --------------------
  out.seller = { name: "", contact: "", phone: "" };

  const sellerRoot = document.querySelector("div.detail__contact-info");
  if (sellerRoot) {
    const name = norm(sellerRoot.querySelector(".dealer-contact__branch-name strong")?.textContent || "");
    const contactLine = norm(sellerRoot.querySelector(".dealer-contact__name")?.textContent || "");
    const phoneA = sellerRoot.querySelector("a[href^='tel:']");
    const phone = norm(phoneA?.textContent || "");

    out.seller = {
      name,
      contact: contactLine.replace(/^Contact:\s*/i, "").trim(),
      phone
    };
  }

  // --------------------
  // Specs (ALL sections)
  // --------------------
  const specs = {};
  let updatedText = "";

  const specsRoot = document.querySelector("div.detail__specs");
  if (specsRoot) {
    const kids = Array.from(specsRoot.children);
    let currentSection = "Specs";
    for (let i = 0; i < kids.length; i++) {
      const el = kids[i];
      if (el.matches && el.matches("h3.detail__specs-heading")) {
        currentSection = norm(el.textContent || "") || currentSection;
        if (!specs[currentSection]) specs[currentSection] = {};
      } else if (el.matches && el.matches("div.detail__specs-wrapper")) {
        if (!specs[currentSection]) specs[currentSection] = {};
        const labels = Array.from(el.querySelectorAll("div.detail__specs-label"));
        const values = Array.from(el.querySelectorAll("div.detail__specs-value"));
        const n = Math.min(labels.length, values.length);
        for (let j = 0; j < n; j++) {
          const k = norm(labels[j].textContent || "");
          const v = norm(values[j].textContent || "");

          if (k) specs[currentSection][k] = v;

          // Capture "Updated" date if present anywhere
          if (/^updated$/i.test(k)) updatedText = v;
        }
      }
    }
  }

  out.specs = specs;
  out.updatedText = updatedText;

  return out;
})()
""".strip()
