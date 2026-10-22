# Home Gym Price Watch

Is that home gym sale real? A free site that checks prices at REP Fitness, Titan Fitness and Bells of Steel once a day and shows the lowest price recorded so far.

- `fetch.py` reads each store's public product listing (one request per page, a pause between pages, an honest user agent) and saves `data/snapshots/YYYY-MM-DD.csv.gz` with product, brand, variant, price, compare-at price, in-stock status, scratch-and-dent flag, URL and date. It also updates `data/history.json` (per option) and `data/product_history.json` (per product, cheapest in-stock option).
- `build_site.py` builds `site/index.html` and `site/data.json`.
- `.github/workflows/daily-prices.yml` runs every day at 6:00 AM Hawaii time, commits the new snapshot and redeploys GitHub Pages.

"Real deal" means today's price is within 3% of the lowest price recorded, after at least 14 days of history on that product. Not affiliated with any store.
