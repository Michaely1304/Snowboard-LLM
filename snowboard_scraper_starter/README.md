# Snowboard Scraper Starter (Config-Driven)

This is a **polite, config-driven web scraping starter** to collect snowboard product data
for your recommendation/chatbot dataset. It outputs a consolidated CSV using the minimal schema:

- Brand, Name, Gender, Profile, Flex, Park, All_Mountain, Powder, Carving, Splitboard,
  Description_raw, Source_url, Desc_summary, Key_features, Rationale_hint

> ⚠️ **Important:** Always review a site's Terms of Service and `robots.txt` before scraping.
Keep request rates low (this template uses a delay). Prefer official APIs or data exports if available.

## Quick Start

1. Create a virtual env and install deps:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

2. Edit `config.yaml` with your **list pages** and **CSS selectors** for each site.
   The provided demo is **placeholder-only**.

3. Run the scraper:
```bash
python scrape.py --site demo1
# or all sites in config
python scrape.py --all
```

4. Results:
- `data/snowboards_scraped.csv` (aggregated across sites)
- `data/raw/{site}.csv` (per-site raw capture for debugging)

## Config Schema (`config.yaml`)

```yaml
sites:
  demo1:
    base_url: "https://example.com"
    delay_sec: 2
    headers:
      user_agent: "Mozilla/5.0 (compatible; SnowboardBot/0.1; +https://example.com/bot)"
    list_pages:
      - "https://example.com/snowboards?page=1"
      - "https://example.com/snowboards?page=2"
    selectors:
      product_link: "a.product-card::attr(href)"
      item:
        brand: "div.brand"
        name: "h1.product-title"
        gender: "span.gender"
        profile: "span.profile"
        flex: "span.flex"
        description: "div.description"
        terrain_blob: "div.terrain"  # e.g., "park 6; all mountain 10; powder 6"
  demo2:
    base_url: "https://example2.com"
    delay_sec: 2
    list_pages:
      - "https://example2.com/boards"
    selectors:
      product_link: "a.board-tile::attr(href)"
      item:
        brand: "span.brand"
        name: "h1.title"
        gender: "span.gender"
        profile: "li:contains('Profile')"
        flex: "li:contains('Flex')"
        description: "section.copy"
        terrain_blob: "ul.terrain-scores"
```

> **Tip:** Use your browser devtools to confirm selectors. Keep them simple and specific.

## Extending
- Add more fields (waist width, sidecut, lengths) by extending selectors and `normalize_row` in `parsers.py`.
- Add `boots`/`bindings` by duplicating the site blocks and adding CSV outputs.
- If a site uses dynamic JS rendering, switch to Selenium/Playwright (not included here).

## Legal/Ethical Notes
- Attribute `Source_url`.
- Keep `Description_raw` short. Prefer your own `Desc_summary` in user output.
- If a site disallows scraping, don't scrape it. Ask for permission or use public feeds.
