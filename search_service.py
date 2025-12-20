import os
import time
import logging
from urllib.parse import quote

from flask import Flask, request, jsonify

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

_CACHE = {}


def _bing_search(query: str, max_results: int = 5, timeout_ms: int = 20000):
    if not sync_playwright:
        raise RuntimeError("playwright is not installed. Install it and run: python -m playwright install chromium")

    query = (query or "").strip()
    if not query:
        return []

    url = f"https://www.bing.com/search?q={quote(query)}&setlang=en-US&cc=US"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        context.set_default_timeout(timeout_ms)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        # Bing can trigger internal redirects / additional navigation; avoid strict "visible" waits.
        page.wait_for_timeout(750)
        try:
            page.wait_for_selector("#b_results li.b_algo", state="attached", timeout=timeout_ms)
        except Exception:
            # Fallback: element may exist but Playwright can still time out while waiting for navigation.
            items_probe = page.query_selector_all("#b_results li.b_algo") or page.query_selector_all("li.b_algo")
            if not items_probe:
                html = page.content()
                lowered = html.lower()
                if "unusual traffic" in lowered or "verify you are a human" in lowered or "form=" in lowered and "captcha" in lowered:
                    raise RuntimeError("Bing blocked automated browsing (bot-check/captcha). Try again later or switch to another provider.")
                raise

        results = []
        items = page.query_selector_all("#b_results li.b_algo")
        if not items:
            items = page.query_selector_all("li.b_algo")
        for idx, li in enumerate(items[:max_results], start=1):
            a = li.query_selector("h2 a")
            title = (a.inner_text().strip() if a else "")
            link = (a.get_attribute("href") if a else "")
            p_el = li.query_selector("div p")
            snippet = (p_el.inner_text().strip() if p_el else "")
            if title or link or snippet:
                results.append({
                    "position": idx,
                    "title": title,
                    "url": link,
                    "snippet": snippet,
                    "source": "bing",
                })

        context.close()
        browser.close()
        return results


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/search")
def search():
    query = request.args.get("q", "")
    max_results = int(request.args.get("n", "5"))

    cache_ttl = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "600"))
    now = time.time()
    qkey = query.strip().lower()

    cached = _CACHE.get(qkey)
    if cached and (now - cached[0]) <= cache_ttl:
        return jsonify({"query": query, "results": cached[1], "cached": True})

    try:
        results = _bing_search(query=query, max_results=max_results)
    except Exception as e:
        logging.exception("search failed")
        return jsonify({"query": query, "results": [], "error": str(e)}), 500

    _CACHE[qkey] = (now, results)
    return jsonify({"query": query, "results": results, "cached": False})


if __name__ == "__main__":
    port = int(os.getenv("SEARCH_SERVICE_PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=False)
