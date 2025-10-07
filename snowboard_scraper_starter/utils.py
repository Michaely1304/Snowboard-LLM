import time, re, requests, urllib.robotparser as robotparser
from urllib.parse import urljoin, urlparse
from typing import Optional, Dict

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SnowboardBot/0.1; +https://example.com/bot)"
}

def can_fetch(base_url: str, path: str, ua: str = DEFAULT_HEADERS["User-Agent"]) -> bool:
    """Check robots.txt for permission."""
    try:
        rp = robotparser.RobotFileParser()
        robots_url = urljoin(base_url, "/robots.txt")
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(ua, urljoin(base_url, path))
    except Exception:
        # If robots fetch fails, err on the safe side: disallow
        return False

def http_get(url: str, headers: Optional[Dict] = None, timeout: int = 20):
    """GET with basic retry/backoff."""
    h = DEFAULT_HEADERS.copy()
    if headers:
        # allow config override
        h.update({"User-Agent": headers.get("user_agent", h["User-Agent"])})
        for k, v in headers.items():
            if k.lower() != "user_agent":
                h[k] = v

    for i in range(4):
        try:
            r = requests.get(url, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r
            elif 400 <= r.status_code < 500:
                return None
        except requests.RequestException:
            pass
        time.sleep(1.5 * (i + 1))
    return None

def absolute_link(base_url: str, href: str) -> str:
    return urljoin(base_url, href)
