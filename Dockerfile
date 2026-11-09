# ---------------------------------------------------------------------------
# CSC418 Lab Assignment 4
# Selenium + headless Chrome news scraper exposing a REST API on port 7000.
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROME_BIN=/usr/local/bin/chrome \
    CHROMEDRIVER_BIN=/usr/local/bin/chromedriver

# ---------------------------------------------------------------------------
# 1. Chrome browser + matching ChromeDriver
#    Both come from Google's "Chrome for Testing" channel, which publishes the
#    browser and the driver at identical version numbers - that guarantees the
#    two never drift apart.
# ---------------------------------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl jq unzip fonts-liberation fonts-noto-color-emoji \
        libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcairo2 \
        libcups2 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0 libgtk-3-0 \
        libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 \
        libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 \
        libu2f-udev xdg-utils; \
    \
    JSON_URL="https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"; \
    curl -sSL "$JSON_URL" -o /tmp/cft.json; \
    CHROME_URL="$(jq -r '.channels.Stable.downloads.chrome[]       | select(.platform=="linux64") | .url' /tmp/cft.json)"; \
    DRIVER_URL="$(jq -r '.channels.Stable.downloads.chromedriver[] | select(.platform=="linux64") | .url' /tmp/cft.json)"; \
    echo "Chrome:       $CHROME_URL"; \
    echo "ChromeDriver: $DRIVER_URL"; \
    \
    curl -sSL "$CHROME_URL" -o /tmp/chrome.zip; \
    curl -sSL "$DRIVER_URL" -o /tmp/chromedriver.zip; \
    unzip -q /tmp/chrome.zip       -d /opt; \
    unzip -q /tmp/chromedriver.zip -d /opt; \
    ln -s /opt/chrome-linux64/chrome             /usr/local/bin/chrome; \
    ln -s /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver; \
    chmod +x /opt/chrome-linux64/chrome /opt/chromedriver-linux64/chromedriver; \
    \
    chrome --version; \
    chromedriver --version; \
    \
    apt-get purge -y --auto-remove jq unzip; \
    rm -rf /tmp/*.zip /tmp/cft.json /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# 2. Python dependencies (Selenium, Flask, Gunicorn)
# ---------------------------------------------------------------------------
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# 3. Application code
# ---------------------------------------------------------------------------
COPY config.py scraper.py summarizer.py app.py ./

# Override at run time with:  docker run -e REGISTRATION=FA22-BDS-045 ...
ENV REGISTRATION=FA23-BDS-004 \
    PORT=7000

# Run as a non-root user; Chrome still needs --no-sandbox inside a container.
RUN useradd --create-home --shell /bin/bash scraper && chown -R scraper:scraper /app
USER scraper

EXPOSE 7000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','7000')+'/health',timeout=4)"

# The container starts the API automatically.
# 1 worker + threads: headless Chrome is memory-hungry, and the app already
# serialises browser sessions with a lock.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-7000} --workers 1 --threads 4 --timeout 300 --access-logfile - app:app"]
