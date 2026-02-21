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
  const abs = (u) => {
    try { return new URL(u, location.origin).toString(); } catch(e) { return u || ""; }
  };
  const text = (el) => (el ? (el.textContent || "").replace(/\s+/g, " ").trim() : "");

  const wrappers = Array.from(document.querySelectorAll("#listContainer .list-listing-card-wrapper"));
  return wrappers.map(w => {
    // main listing node (has id + data attrs)
    const main =
      w.querySelector(".listing-card-grid[data-listing-id]") ||
      w.querySelector("[data-listing-id]") ||
      w.querySelector("div[id][data-price], div[id][data-item-name]") ||
      null;

    const listingId =
      (main && (main.getAttribute("data-listing-id") || "")) ||
      (w.querySelector("[data-listing-id]")?.getAttribute("data-listing-id") || "") ||
      (w.querySelector("div[id]")?.id || "");

    // prefer title link
    const a =
      w.querySelector("a.list-listing-title-link[href]") ||
      w.querySelector("a.view-listing-details-link[href]") ||
      w.querySelector("a[href*='/listing/for-sale/']");

    const href = a ? abs(a.getAttribute("href") || "") : "";

    // auction detection: if Current Bid / auction price exists, skip later
    const hasAuctionPrice = !!w.querySelector(".auction-price");
    const hasLot = !!w.querySelector(".lot-number, .live-tile, .left-flavor.at");
    const isAuction = hasAuctionPrice || hasLot || /auctiontime\.com|equipmentfacts\.com/i.test(href);

    // retail price text (if present)
    const priceText = text(w.querySelector(".retail-price-container .price"));

    // images: collect visible src + any data-src style
    const imgs = Array.from(w.querySelectorAll("img.listing-main-img"))
      .map(img => img.getAttribute("src") || img.getAttribute("data-src") || "")
      .filter(Boolean)
      .map(abs);

    // de-dupe
    const images = Array.from(new Set(imgs));

    return {
      listingId,
      href,
      isAuction,
      priceText,
      images
    };
  });
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
  const abs = (u) => {
    try { return new URL(u, location.origin).toString(); } catch(e) { return u || ""; }
  };

  const uniq = (arr) => Array.from(new Set((arr || []).filter(Boolean)));

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
    out.machineLocationText = full;

    const street = norm(loc.querySelector("span.detail__machine-location-address")?.textContent || "");
    let tail = full;
    if (street && tail.includes(street)) {
      tail = tail.split(street).slice(1).join(street).trim();
    }
    out.city = norm((tail.split(",")[0] || "").trim());
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
  // Specs (ALL sections) + Updated
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
          if (/^updated$/i.test(k)) updatedText = v;
        }
      }
    }
  }

  out.specs = specs;
  out.updatedText = updatedText;

  // --------------------
  // Images (USE ONE SOURCE: thumbnails)
  // --------------------
  const imgSet = [];

  // Prefer thumbs: usually includes ALL images
  document.querySelectorAll(".mc-thumb-slider img").forEach(img => {
    const u = img.getAttribute("data-src") || img.getAttribute("src") || "";
    if (u) imgSet.push(abs(u));
  });

  // Fallback: if no thumbs, take the main image
  if (imgSet.length === 0) {
    const main = document.querySelector(".mc-img img");
    if (main) {
      const u = main.getAttribute("data-fullscreen") || main.getAttribute("src") || "";
      if (u) imgSet.push(abs(u));
    }
  }

  out.images = uniq(imgSet);

  return out;
})()
""".strip()