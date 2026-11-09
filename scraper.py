"""
Selenium + headless Chrome scraper.

Flow:
  1. Open the assigned news site's search page for the keyword.
  2. Pick the first link that looks like a real article.
  3. Open that article and extract its title + body text.

Article extraction is generic (largest block of <p> text) so the same code
works across all 20 news sources in the assignment table.
"""
import logging
import os
import time
from urllib.parse import quote_plus, urljoin, urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config

log = logging.getLogger(__name__)

CHROME_BINARY = os.environ.get("CHROME_BIN", "/usr/local/bin/chrome")
CHROMEDRIVER = os.environ.get("CHROMEDRIVER_BIN", "/usr/local/bin/chromedriver")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

CONSENT_LABELS = [
    "accept all", "accept cookies", "i agree", "agree", "got it",
    "allow all", "accept", "continue",
]


def build_driver():
    """Create a headless Chrome driver tuned for running inside a container."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")
    options.add_argument("--user-agent=" + USER_AGENT)
    if os.path.exists(CHROME_BINARY):
        options.binary_location = CHROME_BINARY

    if os.path.exists(CHROMEDRIVER):
        service = Service(executable_path=CHROMEDRIVER)
    else:
        service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(config.PAGE_TIMEOUT)
    return driver


def _dismiss_consent(driver):
    """Best-effort click on cookie/consent banners that hide search results."""
    upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lower = "abcdefghijklmnopqrstuvwxyz"
    for label in CONSENT_LABELS:
        xpath = (
            "//button[contains(translate(normalize-space(.), '"
            + upper + "', '" + lower + "'), '" + label + "')]"
        )
        try:
            buttons = driver.find_elements(By.XPATH, xpath)
        except WebDriverException:
            continue
        for button in buttons[:2]:
            try:
                if button.is_displayed():
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(0.5)
                    return
            except WebDriverException:
                continue


def _is_article_link(href, source, search_host):
    """Decide whether a link from the results page points at a real article."""
    if not href or not href.startswith("http"):
        return False
    parsed = urlparse(href)

    # Stay on the news site (allow subdomains of the same registrable domain).
    host_parts = search_host.split(".")
    root = ".".join(host_parts[-2:]) if len(host_parts) >= 2 else search_host
    if root not in parsed.netloc:
        return False

    lowered = href.lower()
    for bad in source.get("deny", []):
        if bad in lowered:
            return False

    allow = source.get("allow", [])
    if allow and not any(good in lowered for good in allow):
        return False

    # Reject bare section pages: a real article URL has a slug of some length.
    if len(parsed.path.rstrip("/")) < 12:
        return False
    return True


def find_first_result(driver, keyword, source):
    """Return (url, link_text) for the first article in the search results."""
    search_url = source["search"].format(q=quote_plus(keyword))
    log.info("Searching: %s", search_url)
    driver.get(search_url)

    try:
        WebDriverWait(driver, config.PAGE_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "a"))
        )
    except TimeoutException:
        pass

    _dismiss_consent(driver)

    # Several of the news sites in the assignment table render their results
    # client-side (ProPakistani embeds a Google Custom Search widget, for
    # example). Wait for the site's own result container when we know it.
    result_selector = source.get("result_selector")
    if result_selector:
        try:
            WebDriverWait(driver, config.PAGE_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, result_selector))
            )
        except TimeoutException:
            log.warning("Result selector %r did not appear; falling back to all links",
                        result_selector)

    # Give lazy-loaded results a moment and scroll to trigger more.
    for _ in range(3):
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        except WebDriverException:
            pass
        time.sleep(1.2)

    search_host = urlparse(search_url).netloc

    # Prefer anchors inside the real result container; fall back to every link.
    anchors = []
    if result_selector:
        try:
            anchors = driver.find_elements(By.CSS_SELECTOR, result_selector)
        except WebDriverException:
            anchors = []
    if not anchors:
        anchors = driver.find_elements(By.TAG_NAME, "a")

    seen = set()
    candidates = []
    for anchor in anchors:
        try:
            href = anchor.get_attribute("href")
            text = (anchor.text or "").strip()
        except WebDriverException:
            continue
        if not href:
            continue
        href = urljoin(search_url, href).split("#")[0]
        if href in seen:
            continue
        seen.add(href)
        if _is_article_link(href, source, search_host):
            candidates.append((href, text))

    if not candidates:
        raise LookupError(
            "No article results found on " + source["name"]
            + " for keyword '" + keyword + "'."
        )

    # Prefer the first candidate that actually has headline text attached.
    for href, text in candidates:
        if len(text) > 15:
            return href, text
    return candidates[0]


BOILERPLATE_PREFIXES = (
    "share ", "follow us", "subscribe", "advertisement",
    "copyright", "read more", "also read", "sign up",
)

# Regions that contain <p> tags but are not article text. These are stripped
# from the DOM before extraction, otherwise reader comments and "related
# stories" blurbs leak into the summary.
NOISE_SELECTORS = (
    "#comments", ".comments-area", ".comment-list", ".commentlist",
    ".comment-body", ".comment-respond", "#respond", "#disqus_thread",
    ".related-posts", ".related-articles", ".read-more", ".newsletter",
    "nav", "header", "footer", "aside", "form", "noscript",
)

CONTENT_SELECTORS = (
    "article",
    "main",
    "[itemprop='articleBody']",
    ".story__content",
    ".article-content",
    ".post-content",
    ".entry-content",
    "#content",
    "body",
)


def extract_article(driver, url):
    """Return (title, body_text) for an article URL."""
    log.info("Opening article: %s", url)
    driver.get(url)

    try:
        WebDriverWait(driver, config.PAGE_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "p"))
        )
    except TimeoutException:
        pass

    _dismiss_consent(driver)
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    except WebDriverException:
        pass
    time.sleep(1.0)

    # Strip comment threads, related-story rails, nav and footers before we
    # read any <p>, so only genuine article prose survives.
    try:
        driver.execute_script(
            "arguments[0].forEach(function (sel) {"
            "  document.querySelectorAll(sel).forEach(function (el) { el.remove(); });"
            "});",
            list(NOISE_SELECTORS),
        )
    except WebDriverException:
        log.warning("Could not strip noise elements; summary may include comments")

    title = ""
    try:
        element = driver.find_element(By.CSS_SELECTOR, "h1")
        title = (element.text or "").strip()
    except WebDriverException:
        pass
    if not title:
        try:
            element = driver.find_element(By.CSS_SELECTOR, "meta[property='og:title']")
            title = (element.get_attribute("content") or "").strip()
        except WebDriverException:
            pass
    if not title:
        title = (driver.title or "").strip()

    # Find the container holding the most article text, then read its <p> tags.
    containers = []
    for selector in CONTENT_SELECTORS:
        try:
            containers.extend(driver.find_elements(By.CSS_SELECTOR, selector))
        except WebDriverException:
            continue

    best_text = ""
    for container in containers:
        try:
            paragraphs = container.find_elements(By.TAG_NAME, "p")
        except WebDriverException:
            continue
        chunks = []
        for paragraph in paragraphs:
            try:
                piece = (paragraph.text or "").strip()
            except WebDriverException:
                continue
            if len(piece) < 40:
                continue
            if piece.lower().startswith(BOILERPLATE_PREFIXES):
                continue
            chunks.append(piece)
        text = "\n".join(chunks)
        if len(text) > len(best_text):
            best_text = text

    return title, best_text


def scrape(keyword, source=None):
    """Search, open the first result and return its title, url and body text."""
    source = source or config.SOURCE
    driver = None
    try:
        driver = build_driver()
        url, link_text = find_first_result(driver, keyword, source)
        title, body = extract_article(driver, url)
        return {
            "url": url,
            "title": title or link_text,
            "text": body,
        }
    finally:
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException:
                pass
