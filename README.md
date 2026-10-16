# News Dashboard

A small tool that pulls tech/startup news from RSS feeds, tags it against a keyword list, stores it in SQLite, and shows it in a password-protected Streamlit dashboard for triage (mark articles as new / watching / story lead, add notes).

A GitHub Actions workflow runs the ingest daily and commits the refreshed database back to the repo, so the dashboard stays current without anyone needing to run anything by hand.

## Project layout

- `config.py` — `RSS_FEEDS` and `KEYWORDS`
- `db.py` — SQLite storage (`news.db`)
- `ingest.py` — fetches feeds, tags articles, and inserts new ones
- `app.py` — Streamlit dashboard (filtering, tagging, status triage, password gate)
- `.github/workflows/ingest.yml` — daily scheduled run of `ingest.py`, auto-commits `news.db` if it changed
- `.streamlit/config.toml` — theme (colors, font)
- `.streamlit/secrets.toml` — **not committed**; holds the dashboard password (see below)

## Running locally

### 1. Set up the environment

```powershell
py -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
```

### 2. Set a local password

The dashboard is gated behind a password read from `st.secrets["password"]`. Create `.streamlit/secrets.toml` (this file is git-ignored, so it stays local):

```toml
password = Available on request
```

### 3. Pull some articles

```powershell
.\venv\Scripts\python.exe ingest.py
```

`news.db` is tracked in git and kept fresh by the GitHub Actions workflow, so this step is only needed if you want to refresh it manually (e.g. testing a `config.py` change) — `git pull` will usually already have today's data.

### 4. Run the dashboard

```powershell
.\venv\Scripts\streamlit.exe run app.py
```

Open the URL it prints (defaults to `http://localhost:8501`) and enter the password from step 2.

## Automatic ingestion (GitHub Actions)

`.github/workflows/ingest.yml` runs daily at 03:00 UTC and can also be triggered manually from the repo's **Actions** tab (`Ingest news` → **Run workflow**). It installs `requirements.txt`, runs `ingest.py`, and — if `news.db` changed — commits it back to `main` as `github-actions[bot]`. No setup is needed for this beyond the workflow file already being in the repo; it uses the default `GITHUB_TOKEN` (granted `contents: write` in the workflow) to push.

## Deploying to Streamlit Community Cloud

1. Push the repo to GitHub (already done) and make sure `requirements.txt` and `.streamlit/config.toml` are committed — the app's dependencies and theme won't apply on Cloud otherwise.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app pointing at this repo, `main` branch, `app.py` as the entry point.
3. In the app's **Settings → Secrets**, add:
   ```toml
   password = "<your real password>"
   ```
   This is the Cloud equivalent of the local `.streamlit/secrets.toml` file — it's never committed to git, just pasted into Streamlit's own secrets UI.
4. Deploy. The app will read whatever `news.db` is currently checked into `main`; since GitHub Actions keeps that fresh daily, the deployed dashboard stays up to date automatically without redeploying.
