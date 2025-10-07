import argparse, os, sys, csv, time, re
import pandas as pd
import yaml
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm

from utils import http_get, can_fetch, absolute_link
from parsers import normalize_row

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
RAW_DIR = os.path.join(DATA_DIR, "raw")
os.makedirs(RAW_DIR, exist_ok=True)

def extract_from_ldjson_and_meta(html, url):
    soup = BeautifulSoup(html, "lxml")
    out = {"Brand":"", "Name":"", "Description_raw":"", "Gender":"", "Profile":"", "Flex":"", "Terrain_blob":"", "Source_url": url}

    # JSON-LD blocks
    for s in soup.find_all("script", {"type":"application/ld+json"}):
        try:
            data = json.loads(s.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if "Product" in str(item.get("@type")) or item.get("name") or item.get("brand"):
                out["Name"] = out["Name"] or (item.get("name") or "")
                b = item.get("brand")
                if isinstance(b, dict):
                    out["Brand"] = out["Brand"] or b.get("name","")
                elif isinstance(b, str):
                    out["Brand"] = out["Brand"] or b
                out["Description_raw"] = out["Description_raw"] or (item.get("description") or "")

    # Meta fallbacks
    if not out["Name"]:
        mt = soup.find("meta", {"property":"og:title"})
        if mt and mt.get("content"):
            out["Name"] = mt["content"]
    if not out["Description_raw"]:
        md = soup.find("meta", {"name":"description"}) or soup.find("meta", {"property":"og:description"})
        if md and md.get("content"):
            out["Description_raw"] = md["content"]

    # Heuristic gender/profile from title
    title_text = (soup.title.string if soup.title else "") + " " + out["Name"]
    tl = (title_text or "").lower()
    out["Gender"] = "womens" if ("women" in tl or "womens" in tl) else ("mens" if "men" in tl else "unisex")
    if "camber" in tl: out["Profile"] = "camber"
    elif "rocker" in tl: out["Profile"] = "rocker"
    elif "flat" in tl: out["Profile"] = "flat"
    else: out["Profile"] = out["Profile"] or ""
    return out


def extract_with_selector(soup, selector):
    """Safe extraction: skip empty selectors."""
    if not selector or not str(selector).strip():
        return None
    attr = None
    sel = selector
    m = re.search(r"::attr\(([^)]+)\)$", selector)
    if m:
        attr = m.group(1).strip()
        sel = selector[:m.start()]
    nodes = soup.select(sel) if hasattr(soup, "select") else []
    if not nodes:
        return None
    node = nodes[0]
    if attr:
        return node.get(attr)
    return node.get_text(" ", strip=True)

def _extract_links_by_selector(soup, base_url, selector):
    links = []
    if not selector:
        return links
    for a in soup.select(selector):
        href = a.get("href")
        if href:
            links.append(urljoin(base_url, href))
    return links

def _extract_links_by_regex(soup, base_url, pattern):
    links = []
    if not pattern:
        return links
    rx = re.compile(pattern)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        path = href if href.startswith("/") else urlparse(href).path
        if rx.search(path or ""):
            links.append(urljoin(base_url, href))
    return links

def _find_next_page(soup, base_url):
    # Try rel=next first
    ln = soup.find("link", rel=lambda v: v and "next" in v.lower())
    if ln and ln.get("href"):
        return urljoin(base_url, ln["href"])
    # Common "Next" anchors
    a = soup.find("a", string=lambda s: s and "next" in s.lower())
    if a and a.get("href"):
        return urljoin(base_url, a["href"])
    return None

def gather_product_links(site_cfg):
    """
    Crawl list pages:
      1) Try CSS selector (site_cfg['selectors']['product_link'])
      2) Fallback: regex (site_cfg['product_url_regex']) across all <a> tags
      3) Follow simple pagination (rel=next or 'Next' link) until none
    """
    base_url = site_cfg["base_url"]
    headers = site_cfg.get("headers")
    delay = site_cfg.get("delay_sec", 2)
    product_link_selector = site_cfg.get("selectors", {}).get("product_link", "")
    product_url_regex = site_cfg.get("product_url_regex", "")

    discovered = []
    visited = set()
    queue = list(site_cfg.get("list_pages", []))

    while queue:
        list_url = queue.pop(0)
        if list_url in visited:
            continue
        visited.add(list_url)

        # robots check
        if not can_fetch(base_url, list_url.replace(base_url, ""), ua=headers.get("user_agent","") if headers else ""):
            print(f"[robots] Disallowed list page: {list_url}")
            continue

        r = http_get(list_url, headers=headers)
        if not r:
            print(f"[warn] Failed to fetch list page: {list_url}")
            continue

        soup = BeautifulSoup(r.text, "lxml")
        # 1) Selector-based extraction (if provided)
        links = _extract_links_by_selector(soup, base_url, product_link_selector)
        # 2) Regex fallback
        if not links:
            links = _extract_links_by_regex(soup, base_url, product_url_regex)

        discovered.extend(links)

        # 3) Pagination discovery
        nxt = _find_next_page(soup, base_url)
        if nxt and nxt not in visited:
            queue.append(nxt)

        time.sleep(delay)

    # Deduplicate while preserving order
    seen, uniq = set(), []
    for l in discovered:
        if l not in seen:
            uniq.append(l); seen.add(l)
    return uniq

def parse_product(url, site_cfg):
    if not can_fetch(site_cfg["base_url"], url.replace(site_cfg["base_url"], ""),
                     ua=site_cfg.get("headers",{}).get("user_agent","")):
        print(f"[robots] Disallowed product: {url}")
        return None

    r = http_get(url, headers=site_cfg.get("headers"))
    if not r:
        print(f"[warn] Failed to fetch product: {url}")
        return None

    item_sel = site_cfg["selectors"].get("item", {})
    # If all item selectors are empty, use JSON-LD/meta extractor
    if not any((item_sel.get(k) or "").strip() for k in ["brand","name","gender","profile","flex","description","terrain_blob"]):
        return extract_from_ldjson_and_meta(r.text, url)

    # Otherwise use selector-based extraction
    soup = BeautifulSoup(r.text, "lxml")
    row = {
        "Brand": extract_with_selector(soup, item_sel.get("brand","")) or "",
        "Name": extract_with_selector(soup, item_sel.get("name","")) or "",
        "Gender": extract_with_selector(soup, item_sel.get("gender","")) or "unisex",
        "Profile": extract_with_selector(soup, item_sel.get("profile","")) or "",
        "Flex": extract_with_selector(soup, item_sel.get("flex","")) or "",
        "Description_raw": extract_with_selector(soup, item_sel.get("description","")) or "",
        "Terrain_blob": extract_with_selector(soup, item_sel.get("terrain_blob","")) or "",
        "Source_url": url,
    }
    return row

def run_site(site_name, cfg):
    site_cfg = cfg["sites"][site_name]
    print(f"==> Site: {site_name}")
    links = gather_product_links(site_cfg)
    print(f"Found {len(links)} product links")
    rows = []
    for url in tqdm(links):
        row = parse_product(url, site_cfg)
        if not row:
            continue
        nrow = normalize_row(row)
        rows.append(nrow)
        time.sleep(site_cfg.get("delay_sec", 2))
    df = pd.DataFrame(rows)
    raw_path = os.path.join(RAW_DIR, f"{site_name}.csv")
    df.to_csv(raw_path, index=False)
    return df

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=str, help="Site key in config.yaml")
    parser.add_argument("--all", action="store_true", help="Run all sites in config")
    args = parser.parse_args()

    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml"), "r"))
    site_keys = list(cfg.get("sites", {}).keys())
    if args.all:
        targets = site_keys
    elif args.site:
        if args.site not in site_keys:
            print(f"[error] Unknown site: {args.site}. Options: {site_keys}")
            sys.exit(1)
        targets = [args.site]
    else:
        print("Use --site <name> or --all")
        sys.exit(1)

    frames = []
    for s in targets:
        df = run_site(s, cfg)
        if df is not None and not df.empty:
            frames.append(df)

    if frames:
        out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["Brand","Name","Source_url"])
        out_cols = ["Brand","Name","Gender","Profile","Flex",
                    "Park","All_Mountain","Powder","Carving","Splitboard",
                    "Description_raw","Source_url","Desc_summary","Key_features","Rationale_hint"]
        for c in out_cols:
            if c not in out.columns: out[c] = ""
        out = out[out_cols]
        os.makedirs(os.path.join(DATA_DIR), exist_ok=True)
        out_path = os.path.join(DATA_DIR, "snowboards_scraped.csv")
        out.to_csv(out_path, index=False, quoting=csv.QUOTE_MINIMAL)
        print(f"Wrote {out_path} ({len(out)} rows)")
    else:
        print("No data collected. Check your config and selectors.")

if __name__ == "__main__":
    main()
