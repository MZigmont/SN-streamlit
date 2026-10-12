# Sigma Nu Donations Database Tool

A Streamlit application for managing Sigma Nu donations in a SQLite database, with Google sign-in and Google Drive synchronization.

## Features

- Import donation transactions from BluePay, CardPointe, and PayPal.
- Browse and correct records, add manual donations and notes, and generate reports.
- Send donor emails, manage backups, and import or export database tables.
- Download the database from Google Drive and sync local changes back to Drive.

## Getting started

Run these commands from the repository root (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Follow [LOGIN_SETUP.md](LOGIN_SETUP.md) to configure Google authentication, approved administrator emails, and Drive access in `.streamlit/secrets.toml`. Configure Gmail credentials if using donor emails.

Start the application:

```powershell
python -m streamlit run Home.py
```

Sign in with an approved Google account and use **Download Database from Google Drive** to load the donation database. The default local database is `db/sigma_nu_donations.db`; the Drive file ID is configured in `app_context.py`.

## Project structure

- `Home.py` — application entry point.
- `pages/` — database management, imports, reports, and email pages.
- `ingestion/` — payment processor import logic.
- `schema_sql/` — database schema SQL.
- `tests/` — authentication and Google Drive tests.

Keep credentials and donor data out of version control. Local secrets and database files are excluded by `.gitignore`.

## Deployment Instructions

- https://sn-donation.streamlit.app/
