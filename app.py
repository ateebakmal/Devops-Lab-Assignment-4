"""
REST API for Lab Assignment 4.

  GET /                 -> HTML page showing the registration number
  GET /get?keyword=...  -> JSON { registration, newssource, keyword, url, summary }
  GET /health           -> liveness probe
"""
import logging
import threading
import time

from flask import Flask, Response, jsonify, request
from markupsafe import escape

import config
import scraper
from summarizer import summarize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("app")

app = Flask(__name__)

# Headless Chrome is memory-hungry; one browser at a time keeps a 1 GB
# free-tier EC2 instance alive under concurrent requests.
_browser_lock = threading.Lock()

# Small in-memory cache so repeated evaluation hits do not re-scrape.
_cache = {}
_CACHE_TTL = 600  # seconds


def _cached(keyword):
    entry = _cache.get(keyword.lower())
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>News Summarizer API</title>
<style>
  :root {
    --bg: #f5f6f8; --card: #ffffff; --fg: #15181d; --muted: #5c6470;
    --line: #dfe3e8; --accent: #2f6fed;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #14171c; --card: #1c2027; --fg: #eef1f5; --muted: #9aa4b2;
      --line: #2c323b; --accent: #6b9bff;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 32px 16px; background: var(--bg); color: var(--fg);
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height: 1.55;
  }
  .wrap { max-width: 720px; margin: 0 auto; }
  .card {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 24px; margin-bottom: 18px;
  }
  h1 { font-size: 1.4rem; margin: 0 0 4px; }
  .reg {
    font-size: 2rem; font-weight: 700; letter-spacing: 0.5px;
    color: var(--accent); margin: 8px 0 2px; word-break: break-all;
  }
  .label { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em;
           color: var(--muted); }
  dl { display: grid; grid-template-columns: max-content 1fr; gap: 8px 16px; margin: 0; }
  dt { color: var(--muted); }
  dd { margin: 0; }
  code {
    background: var(--bg); border: 1px solid var(--line); border-radius: 6px;
    padding: 2px 6px; font-size: 0.9em; word-break: break-all;
  }
  form { display: flex; gap: 8px; flex-wrap: wrap; }
  input {
    flex: 1 1 200px; padding: 10px 12px; border-radius: 8px;
    border: 1px solid var(--line); background: var(--bg); color: var(--fg);
    font-size: 1rem;
  }
  button {
    padding: 10px 18px; border-radius: 8px; border: 0; background: var(--accent);
    color: #fff; font-size: 1rem; cursor: pointer;
  }
  .note { color: var(--muted); font-size: 0.88rem; }
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <span class="label">Registration Number</span>
    <div class="reg">__REGISTRATION__</div>
    <h1>Selenium News Summarizer API</h1>
    <p class="note">CSC418 &ndash; DevOps for Cloud Computing &middot; Lab Assignment 4</p>
  </div>

  <div class="card">
    <dl>
      <dt>News source</dt><dd>__NEWSSOURCE__ (#__SOURCENUM__)</dd>
      <dt>Summarizer</dt><dd>__SUMMARIZER__</dd>
      <dt>Endpoint</dt><dd><code>GET /get?keyword=&lt;string&gt;</code></dd>
      <dt>Port</dt><dd><code>__PORT__</code></dd>
    </dl>
  </div>

  <div class="card">
    <p class="label">Try it</p>
    <form action="/get" method="get">
      <input name="keyword" placeholder="e.g. economy" required>
      <button type="submit">Get summary</button>
    </form>
    <p class="note">Scraping runs a real headless Chrome session, so the first
       response for a keyword usually takes 15&ndash;40 seconds.</p>
  </div>
</div>
</body>
</html>
"""


@app.get("/")
def index():
    html = (
        PAGE_TEMPLATE
        .replace("__REGISTRATION__", escape(config.REGISTRATION))
        .replace("__NEWSSOURCE__", escape(config.NEWS_SOURCE_NAME))
        .replace("__SOURCENUM__", str(config.SOURCE_NUMBER))
        .replace("__SUMMARIZER__", "Extractive (term-frequency)")
        .replace("__PORT__", str(config.PORT))
    )
    return Response(html, mimetype="text/html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "registration": config.REGISTRATION})


@app.get("/get")
def get_summary():
    keyword = (request.args.get("keyword") or "").strip()

    payload = {
        "registration": config.REGISTRATION,
        "newssource": config.NEWS_SOURCE_NAME,
        "keyword": keyword,
        "url": "",
        "summary": "",
    }

    if not keyword:
        payload["summary"] = "Missing required query parameter: keyword"
        return jsonify(payload), 400

    cached = _cached(keyword)
    if cached:
        payload.update(cached)
        return jsonify(payload)

    try:
        with _browser_lock:
            result = scraper.scrape(keyword)
        text = result.get("text") or ""
        title = result.get("title") or ""

        summary = summarize(text, config.SUMMARY_SENTENCES)
        if summary and title:
            summary = title + ". " + summary
        if not summary:
            # Fall back to the headline if the body could not be extracted.
            summary = title or "Article found but no readable text could be extracted."

        payload["url"] = result.get("url", "")
        payload["summary"] = summary
        _cache[keyword.lower()] = (
            time.time(),
            {"url": payload["url"], "summary": payload["summary"]},
        )
        return jsonify(payload)

    except LookupError as exc:
        payload["summary"] = str(exc)
        return jsonify(payload), 404
    except Exception as exc:  # noqa: BLE001 - always answer with the required shape
        log.exception("Scrape failed for keyword %r", keyword)
        payload["summary"] = "Error while scraping: " + str(exc)
        return jsonify(payload), 500


if __name__ == "__main__":
    log.info(
        "Registration %s -> source #%s %s",
        config.REGISTRATION, config.SOURCE_NUMBER, config.NEWS_SOURCE_NAME,
    )
    app.run(host="0.0.0.0", port=config.PORT)
