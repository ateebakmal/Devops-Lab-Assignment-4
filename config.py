"""
Configuration for the Lab Assignment 4 news-scraping API.

The only value you normally need to change is REGISTRATION (or set the
REGISTRATION environment variable). The assigned news source is derived
automatically using the formula from the assignment:

    last_three_digits_of_registration % 20 + 1
"""
import os
import re

# ---------------------------------------------------------------------------
# YOUR REGISTRATION NUMBER  <-- change this (or pass -e REGISTRATION=... to docker run)
# ---------------------------------------------------------------------------
REGISTRATION = os.environ.get("REGISTRATION", "FA23-BDS-004")

# Port the REST API listens on (the assignment mandates 7000)
PORT = int(os.environ.get("PORT", "7000"))

# How long Selenium waits for pages/elements, in seconds
PAGE_TIMEOUT = int(os.environ.get("PAGE_TIMEOUT", "30"))

# Number of sentences in the generated summary
SUMMARY_SENTENCES = int(os.environ.get("SUMMARY_SENTENCES", "5"))


# ---------------------------------------------------------------------------
# News source table (S.No 1-20 exactly as listed in the assignment PDF)
# ---------------------------------------------------------------------------
# "search" is a template; {q} is replaced with the URL-encoded keyword.
# "allow" is a list of URL substrings that mark a link as a real article.
# "deny" filters out navigation / category / tag links.
NEWS_SOURCES = {
    1: {
        "name": "DAWN News Pakistan",
        "home": "https://www.dawn.com/",
        "search": "https://www.dawn.com/search?q={q}",
        "allow": ["/news/"],
        "deny": ["/authors/", "/tag/", "/latest-news"],
    },
    2: {
        "name": "ARY News Pakistan",
        "home": "https://arynews.tv/",
        "search": "https://arynews.tv/?s={q}",
        "allow": ["arynews.tv/"],
        "deny": ["/category/", "/author/", "/tag/", "?s=", "/page/"],
    },
    3: {
        "name": "The News International Pakistan",
        "home": "https://www.thenews.com.pk/",
        "search": "https://www.thenews.com.pk/search?search={q}",
        "allow": ["/print/", "/latest/"],
        "deny": ["/writer/", "/category/", "/tag/"],
    },
    4: {
        "name": "Pakistan Today",
        "home": "https://www.pakistantoday.com.pk/",
        "search": "https://www.pakistantoday.com.pk/?s={q}",
        "allow": ["pakistantoday.com.pk/20"],
        "deny": ["/category/", "/author/", "/tag/", "?s=", "/page/"],
    },
    5: {
        # ProPakistani does not serve WordPress search: /?s=<kw> returns a 404
        # page. The site embeds a Google Custom Search Engine whose results are
        # rendered client-side at /search/?q=<kw> -- which is exactly why this
        # scraper needs a real browser rather than a plain HTTP fetch.
        "name": "ProPakistani",
        "home": "https://propakistani.pk/",
        "search": "https://propakistani.pk/search/?q={q}",
        "result_selector": ".gsc-webResult a.gs-title[href], .gsc-result a.gs-title[href]",
        "allow": ["propakistani.pk/20"],
        "deny": ["/category/", "/author/", "/tag/", "?s=", "/page/", "/search/"],
    },
    6: {
        "name": "TechJuice",
        "home": "https://www.techjuice.pk/",
        "search": "https://www.techjuice.pk/?s={q}",
        "allow": ["techjuice.pk/"],
        "deny": ["/category/", "/author/", "/tag/", "?s=", "/page/"],
    },
    7: {
        "name": "The Nation Pakistan",
        "home": "https://www.nation.com.pk/",
        "search": "https://www.nation.com.pk/search?q={q}",
        "allow": ["/20"],
        "deny": ["/writer/", "/category/", "/tag/"],
    },
    8: {
        "name": "Islamabad Post",
        "home": "https://islamabadpost.com.pk/",
        "search": "https://islamabadpost.com.pk/?s={q}",
        "allow": ["islamabadpost.com.pk/"],
        "deny": ["/category/", "/author/", "/tag/", "?s=", "/page/"],
    },
    9: {
        "name": "Al Jazeera Media Network",
        "home": "https://www.aljazeera.com/",
        "search": "https://www.aljazeera.com/search/{q}",
        "allow": ["/news/", "/features/", "/opinions/", "/economy/", "/sports/"],
        "deny": ["/tag/", "/author/", "/search/"],
    },
    10: {
        "name": "NPR",
        "home": "https://www.npr.org/",
        "search": "https://www.npr.org/search/?query={q}",
        "allow": ["npr.org/20"],
        "deny": ["/sections/", "/people/", "/podcasts/"],
    },
    11: {
        "name": "Deutsche Welle",
        "home": "https://www.dw.com/en/",
        "search": "https://www.dw.com/search/?languageCode=en&item={q}",
        "allow": ["/a-"],
        "deny": ["/t-", "/search/"],
    },
    12: {
        "name": "Euronews",
        "home": "https://www.euronews.com/",
        "search": "https://www.euronews.com/search?query={q}",
        "allow": ["euronews.com/20"],
        "deny": ["/tag/", "/search"],
    },
    13: {
        "name": "NHK World Japan",
        "home": "https://www3.nhk.or.jp/nhkworld/en/",
        "search": "https://www3.nhk.or.jp/nhkworld/en/search/?q={q}",
        "allow": ["/news/", "/shows/"],
        "deny": ["/search/", "/tags/"],
    },
    14: {
        "name": "China Daily",
        "home": "https://www.chinadaily.com.cn/",
        "search": "https://newssearch.chinadaily.com.cn/en/search?query={q}",
        "allow": ["chinadaily.com.cn/a/"],
        "deny": ["/search"],
    },
    15: {
        "name": "ABC News Australia",
        "home": "https://www.abc.net.au/news",
        "search": "https://www.abc.net.au/search?query={q}&configure%5BgetRankingInfo%5D=true",
        "allow": ["/news/20"],
        "deny": ["/search", "/topic/"],
    },
    16: {
        "name": "Wired Magazine",
        "home": "https://www.wired.com/",
        "search": "https://www.wired.com/search/?q={q}",
        "allow": ["/story/"],
        "deny": ["/tag/", "/category/", "/search/"],
    },
    17: {
        "name": "TechCrunch",
        "home": "https://techcrunch.com/",
        "search": "https://techcrunch.com/?s={q}",
        "allow": ["techcrunch.com/20"],
        "deny": ["/category/", "/author/", "/tag/", "?s=", "/page/"],
    },
    18: {
        "name": "Ars Technica",
        "home": "https://arstechnica.com/",
        "search": "https://arstechnica.com/search/?q={q}",
        "allow": ["arstechnica.com/"],
        "deny": ["/search/", "/author/", "/civis", "/store/"],
    },
    19: {
        "name": "The Verge",
        "home": "https://www.theverge.com/",
        "search": "https://www.theverge.com/search?q={q}",
        "allow": ["theverge.com/"],
        "deny": ["/search", "/authors/", "/tags/", "/hubs/"],
    },
    20: {
        "name": "MIT Technology Review",
        "home": "https://www.technologyreview.com/",
        "search": "https://www.technologyreview.com/search/?s={q}",
        "allow": ["/20"],
        "deny": ["/search/", "/topic/", "/author/"],
    },
}


def last_three_digits(registration: str) -> int:
    """Pull the last three digits out of a registration number of any format."""
    digits = re.sub(r"\D", "", registration or "")
    if not digits:
        raise ValueError(
            f"No digits found in REGISTRATION={registration!r}. "
            "Set it to your real registration number, e.g. FA22-BDS-045."
        )
    return int(digits[-3:])


def assigned_source_number(registration: str = REGISTRATION) -> int:
    """Apply the assignment formula: last_three_digits % 20 + 1."""
    return last_three_digits(registration) % 20 + 1


def assigned_source(registration: str = REGISTRATION) -> dict:
    return NEWS_SOURCES[assigned_source_number(registration)]


SOURCE_NUMBER = assigned_source_number()
SOURCE = assigned_source()
NEWS_SOURCE_NAME = SOURCE["name"]
