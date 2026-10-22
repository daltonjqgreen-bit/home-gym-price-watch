"""Build site/index.html and site/data.json from the newest snapshot plus price history."""
import csv, glob, gzip, io, json, os, shutil

DEAL_MIN_DAYS = 14      # need two weeks of history before calling anything a real deal
NEAR_LOW = 1.03         # within 3% of our lowest recorded price counts as "at our low"

def newest_snapshot():
    files = sorted(glob.glob("data/snapshots/*.csv.gz"))
    if not files:
        raise SystemExit("No snapshots yet. Run fetch.py first.")
    with gzip.open(files[-1], "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f)), os.path.basename(files[-1])[:10]

def main():
    rows, date = newest_snapshot()
    ph = json.load(open("data/product_history.json"))
    prods = {}
    for r in rows:
        k = r["product_id"]
        p = prods.setdefault(k, {"brand": r["brand"], "name": r["product"], "url": r["url"],
                                 "sd": r["scratch_and_dent"] == "yes", "variants": []})
        p["variants"].append(r)
    brands = sorted({p["brand"] for p in prods.values()})
    out = []
    for k, p in prods.items():
        vs = p["variants"]
        instock = [v for v in vs if v["in_stock"] == "yes"]
        pool = instock or vs
        best = min(pool, key=lambda v: float(v["price"]))
        price = float(best["price"])
        cap = float(best["compare_at_price"]) if best["compare_at_price"] else None
        h = ph.get(k, {})
        low = min(h.get("low", price), price)
        days = h.get("days", 1)
        if days < DEAL_MIN_DAYS:
            status = 0   # too early
        elif price <= low * NEAR_LOW:
            status = 2   # real deal
        else:
            status = 1   # above our low
        md = None
        if h.get("changed") == date and h.get("prev") and price < h["prev"]:
            md = h["prev"]
        out.append({
            "b": brands.index(p["brand"]), "n": p["name"], "u": p["url"],
            "p": price, "c": cap if cap and cap > price else None,
            "lo": low, "lod": h.get("low_date", date), "f": h.get("first", date), "d": days,
            "s": 1 if instock else 0, "sd": 1 if p["sd"] else 0, "md": md,
            "v": len(vs), "st": status,
        })
    out.sort(key=lambda x: (x["b"], x["n"].lower()))
    counts = {b: sum(1 for x in out if x["b"] == i) for i, b in enumerate(brands)}
    first = min(x["f"] for x in out)
    meta = {"date": date, "since": first, "brands": brands, "counts": counts,
            "total": len(out), "variants": len(rows), "deal_min_days": DEAL_MIN_DAYS}
    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w") as f:
        json.dump({"meta": meta, "items": out}, f, separators=(",", ":"))
    html = open("templates/index.html", encoding="utf-8").read()
    html = html.replace("__META__", json.dumps(meta))
    with open("site/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    open("site/.nojekyll", "w").close()
    print(f"Built site: {len(out)} products ({counts}) from snapshot {date}")

if __name__ == "__main__":
    main()
