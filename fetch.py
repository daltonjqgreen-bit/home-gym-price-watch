"""Pull public Shopify product feeds and save today's price snapshot.

One request per page, a short pause between pages, and an honest user agent.
Writes data/snapshots/YYYY-MM-DD.csv.gz and updates data/history.json.
"""
import csv, gzip, io, json, os, re, sys, time, datetime, urllib.request, urllib.error

UA = "HomeGymPriceWatch/1.0 (price history site; +https://github.com/daltonjqgreen-bit/home-gym-price-watch)"
PAUSE = 2.0
STORES = [
    {"brand": "REP Fitness", "base": "https://repfitness.com"},
    {"brand": "Titan Fitness", "base": "https://titan.fitness",
     "scratch_collection": "scratch-and-dent"},
    {"brand": "Bells of Steel", "base": "https://bellsofsteel.us"},
]
SKIP = re.compile(r"gift card|e-gift|warranty|shipping protection|route package|insurance|donation|sample", re.I)
SCRATCH = re.compile(r"\bscratch(ed)?\b|\bdent(ed|s)?\b|\bblemish|\bblem\b|\bb-stock\b|\bcosmetic(ally)? (damage|blem)|\bopen[- ]box\b|\brefurb", re.I)
FIELDS = ["date", "brand", "product", "variant", "product_id", "variant_id", "price",
          "compare_at_price", "in_stock", "scratch_and_dent", "product_type", "url", "image"]

def get_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"  retry {i+1} {url}: {e}", file=sys.stderr)
            time.sleep(10 * (i + 1))
    raise RuntimeError(f"failed: {url}")

def all_products(base, path="/products.json"):
    out, page = [], 1
    while page <= 60:
        data = get_json(f"{base}{path}?limit=250&page={page}")
        prods = data.get("products", [])
        if not prods:
            break
        out.extend(prods)
        page += 1
        time.sleep(PAUSE)
    return out

def snapshot(today):
    rows = []
    for s in STORES:
        print(f"Fetching {s['brand']} ...")
        prods = all_products(s["base"])
        scratch_ids = set()
        if s.get("scratch_collection"):
            for p in all_products(s["base"], f"/collections/{s['scratch_collection']}/products.json"):
                scratch_ids.add(p["id"])
        n = 0
        for p in prods:
            if SKIP.search(p["title"]):
                continue
            is_scratch = p["id"] in scratch_ids or bool(SCRATCH.search(p["title"])) or \
                any(SCRATCH.search(t) for t in p.get("tags", []))
            img = (p.get("images") or [{}])[0].get("src", "")
            for v in p["variants"]:
                try:
                    price = float(v["price"])
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue
                cap = v.get("compare_at_price")
                cap = float(cap) if cap not in (None, "", "0.00") else ""
                rows.append({
                    "date": today, "brand": s["brand"], "product": p["title"].strip(),
                    "variant": "" if v["title"] == "Default Title" else v["title"],
                    "product_id": p["id"], "variant_id": v["id"], "price": f"{price:.2f}",
                    "compare_at_price": f"{cap:.2f}" if cap != "" else "",
                    "in_stock": "yes" if v.get("available") else "no",
                    "scratch_and_dent": "yes" if is_scratch else "no",
                    "product_type": p.get("product_type", ""),
                    "url": f"{s['base']}/products/{p['handle']}",
                    "image": img,
                })
                n += 1
        print(f"  {s['brand']}: {len(prods)} products, {n} variant rows")
    return rows

def product_prices(rows):
    """One 'from' price per product: cheapest in-stock variant, else cheapest variant."""
    best = {}
    for r in rows:
        k = str(r["product_id"])
        p, ok = float(r["price"]), r["in_stock"] == "yes"
        cur = best.get(k)
        if cur is None or (ok and not cur[1]) or (ok == cur[1] and p < cur[0]):
            best[k] = (p, ok)
    return {k: v[0] for k, v in best.items()}

def update_history(pairs, today, path):
    hist = json.load(open(path)) if os.path.exists(path) else {}
    for k, p in pairs:
        h = hist.get(k)
        if h is None:
            hist[k] = {"first": today, "low": p, "low_date": today, "high": p,
                       "last": p, "prev": None, "changed": None, "days": 1, "last_seen": today}
            continue
        if h["last_seen"] != today:
            h["days"] += 1
            if p != h["last"]:
                h["prev"], h["changed"] = h["last"], today
        h["last"], h["last_seen"] = p, today
        if p < h["low"]:
            h["low"], h["low_date"] = p, today
        h["high"] = max(h["high"], p)
    with open(path, "w") as f:
        json.dump(hist, f, separators=(",", ":"))

def main():
    today = os.environ.get("SNAP_DATE") or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-10))).date().isoformat()
    rows = snapshot(today)
    if len(rows) < 100:
        sys.exit(f"Only {len(rows)} rows; refusing to save a broken snapshot.")
    os.makedirs("data/snapshots", exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader(); w.writerows(rows)
    with gzip.open(f"data/snapshots/{today}.csv.gz", "wt", encoding="utf-8") as f:
        f.write(buf.getvalue())
    with open("data/latest.csv", "w", newline="", encoding="utf-8") as f:
        f.write(buf.getvalue())
    update_history(((str(r["variant_id"]), float(r["price"])) for r in rows), today, "data/history.json")
    update_history(product_prices(rows).items(), today, "data/product_history.json")
    print(f"Saved {len(rows)} rows for {today}")

if __name__ == "__main__":
    main()
