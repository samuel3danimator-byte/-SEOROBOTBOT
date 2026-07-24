"""
Self-hosted Google SERP scraper.

IMPORTANT: Scraping Google's search results page violates Google's Terms
of Service. This will get rate-limited or CAPTCHA-blocked, especially from
a shared cloud IP (like Railway's), sometimes within days of regular use.
"""

import random
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) "
    "Gecko/20100101 Firefox/127.0",
]


def _clean_domain(url_or_domain: str) -> str:
    if "://" not in url_or_domain:
        url_or_domain = "http://" + url_or_domain
    netloc = urlparse(url_or_domain).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def google_rank(keyword: str, domain: str, max_results: int = 100, delay: float = 3.0):
    """
    Search Google for `keyword` and return the 1-based position of the
    first organic result belonging to `domain`. Returns None if not found
    in the first `max_results` results, or if the scrape fails/gets blocked.
    """
    target_domain = _clean_domain(domain)
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
    }

    position = 0
    start = 0
    per_page = 10

    while start < max_results:
        params = {"q": keyword, "num": per_page, "start": start, "hl": "en"}
        try:
            resp = requests.get(
                "https://www.google.com/search",
                params=params,
                headers=headers,
                timeout=10,
            )
        except requests.RequestException:
            return None

        if resp.status_code != 200:
            return None  # Likely a block/CAPTCHA page.

        soup = BeautifulSoup(resp.text, "html.parser")
        page_links = []
        seen = set()
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            m = re.match(r"^/url\?q=(https?[^&]+)", href)
            url = m.group(1) if m else (href if href.startswith("http") else None)
            if not url:
                continue
            if "google.com" in urlparse(url).netloc:
                continue
            if url not in seen:
                seen.add(url)
                page_links.append(url)

        if not page_links:
            break

        for url in page_links:
            position += 1
            link_domain = _clean_domain(url)
            if link_domain == target_domain or link_domain.endswith("." + target_domain):
                return position
            if position >= max_results:
                return None

        start += per_page
        time.sleep(delay)

    return None
