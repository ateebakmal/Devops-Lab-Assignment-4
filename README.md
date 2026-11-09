# CSC418 Lab Assignment 4 — Dockerised Selenium News Summarizer API

**Registration:** FA23-BDS-004
**Assigned news source:** ProPakistani (`004 % 20 + 1 = 5`)
**Language used for Selenium:** Python

A Docker image containing a development environment, the Chrome browser,
ChromeDriver and Selenium automation code. The container starts a REST API on
port **7000** automatically. Given a keyword, it searches ProPakistani, opens
the first search result, extracts the article text and returns an extractive
summary as JSON.

---

## API

### `GET /get?keyword=<string>`

```json
{
  "registration": "FA23-BDS-004",
  "newssource": "ProPakistani",
  "keyword": "economy",
  "url": "https://propakistani.pk/2025/01/01/some-article/",
  "summary": "..."
}
```

### `GET /`
HTML landing page displaying the registration number and the assigned news source.

### `GET /health`
Liveness probe used by the image's `HEALTHCHECK`.

**Sample call**

```
http://<EC2_PUBLIC_IP>:7000/get?keyword=economy
```

---

## Run the published image

```bash
docker pull <DOCKERHUB_USERNAME>/news-api:latest
docker run -d --name news-api -p 7000:7000 <DOCKERHUB_USERNAME>/news-api:latest
curl "http://localhost:7000/get?keyword=economy"
```

No environment variables or API keys are required.

---

## Build from source

```bash
git clone <THIS_REPO_URL>
cd <REPO>
docker build --platform linux/amd64 -t news-api:latest .
docker run -d -p 7000:7000 news-api:latest
```

> `--platform linux/amd64` matters if you build on an Apple Silicon Mac:
> Chrome for Testing only ships a `linux64` (x86-64) build, and EC2 general
> purpose instances are x86-64.

---

## Project layout

| File | Purpose |
|---|---|
| `Dockerfile` | Python 3.11 base + Chrome for Testing + matching ChromeDriver + app |
| `config.py` | Registration number, the 20-source table and the `% 20 + 1` formula |
| `scraper.py` | Selenium automation: search → first result → article text extraction |
| `summarizer.py` | Dependency-free extractive summarizer (term-frequency scoring) |
| `app.py` | Flask REST API (`/`, `/get`, `/health`) served by Gunicorn |
| `requirements.txt` | selenium, Flask, gunicorn |

---

## Design notes

**Why a real browser is required here.** ProPakistani does not serve
WordPress search results: `https://propakistani.pk/?s=<keyword>` returns a
`404` page. The site embeds a **Google Custom Search Engine** whose results
are injected into `https://propakistani.pk/search/?q=<keyword>` by JavaScript
after page load. A plain HTTP fetch sees an empty results container, so the
scraper waits on the CSE result nodes (`.gsc-webResult a.gs-title`) with
Selenium's `WebDriverWait` before reading links.

**Chrome / ChromeDriver version matching.** Both binaries are downloaded at
build time from Google's *Chrome for Testing* `Stable` channel, which publishes
the browser and the driver at identical version numbers. This removes the
classic "This version of ChromeDriver only supports Chrome version N" failure.

**Container-safe Chrome flags.** `--headless=new`, `--no-sandbox` (containers
run without the user namespaces Chrome's sandbox needs) and
`--disable-dev-shm-usage` (Docker gives `/dev/shm` only 64 MB, which crashes
Chrome's renderer). Images are disabled to cut memory and latency.

**Memory.** Headless Chrome needs roughly 400–700 MB. The app serialises
browser sessions behind a lock and Gunicorn runs a single worker, so a 1 GB
free-tier EC2 instance stays alive. A swap file is still recommended — see the
deployment guide.

**Summarization** is extractive and pure-Python: sentences are scored by the
normalised frequency of their non-stopword terms, with a mild lead bias
because news writing front-loads the key facts, then the top sentences are
restored to their original order. No model, no weights, no network call and no
API key - which keeps the image small and means the container works correctly
the moment it is pulled, with no configuration at all.

**Resilience.** `/get` always responds with the exact JSON shape required by
the assignment, including on error, so the automated evaluation script can
parse it either way.
