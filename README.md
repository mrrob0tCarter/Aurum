# Aurum

# Aurum

A cross-platform app for aggregating and displaying data from multiple sources — built entirely in Python.

## What is Aurum?

Build a single app that runs on desktop (Windows, macOS, Linux) and mobile (Android, iOS) using only Python — UI, backend, and data fetching included. It pulls data from various websites and APIs, processes it on a backend service, and presents it in a clean interface.

## Tech Stack

- **Flet** — cross-platform UI
- **FastAPI** — backend API
- **Uvicorn** — server
- **Requests** — HTTP client
- **BeautifulSoup4** — HTML parsing
- **Playwright** *(planned)* — dynamic scraping

## Roadmap

- [x] Set up Python virtual environment
- [x] Install core dependencies
- [x] Choose project name
- [ ] Build "Hello, world" Flet window
- [ ] Create first FastAPI endpoint
- [ ] Connect Flet to FastAPI
- [ ] Implement first data source
- [ ] Add second data source
- [ ] Package for Windows
- [ ] Package for Android
- [ ] Package for iOS

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/aurum.git
cd aurum
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt