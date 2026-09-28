import os
import sqlite3

import streamlit as st

from google_drive_interface import google_drive_auth, download_db_file, upload_db_file

DB_DIR = "db"
DB_FILE_NAME = "db/sigma_nu_donations.db"
FILE_ID = "1L61qdt5NiBeo1K3H7tYZzCNU1vAjRuNb"

SIDEBAR_PAGES = [
    {
        "key": "home",
        "path": "Home.py",
        "label": "Home",
        "description": "High level instructions are here.",
    },
    {
        "key": "ingest_data",
        "path": "pages/02_Ingest_Data.py",
        "label": "1 Ingest Data",
        "description": "Import new transaction files from supported payment processors.",
    },
    {
        "key": "run_reports",
        "path": "pages/05_Run_Reports.py",
        "label": "2 Run Reports",
        "description": "Generate reports from the active donation database.",
    },
    {
        "key": "send_emails",
        "path": "pages/send_emails.py",
        "label": "3 Send Emails",
        "description": "Automatically send emails to donors.",
    },
    {
        "key": "manage_databases",
        "path": "pages/00_Manage_Databases.py",
        "label": "Manage Databases",
        "description": "Choose the active database, create backups, and restore database files.",
    },
    {
        "key": "view_data",
        "path": "pages/01_View_Data.py",
        "label": "View Data",
        "description": "Browse live, raw, and backup tables in the selected database.",
    },
    {
        "key": "fix_database",
        "path": "pages/03_Fix_Database.py",
        "label": "Fix Database",
        "description": "Clean up donor records, aliases, transactions, notes, and related data.",
    },
    {
        "key": "download_upload_tables",
        "path": "pages/04_Download_Upload_Tables.py",
        "label": "Download / Upload Tables",
        "description": "Export tables for review or upload table data back into the database.",
    },
    {
        "key": "manage_backup_tables",
        "path": "pages/06_Manage_Backup_Tables.py",
        "label": "Manage Backup Tables",
        "description": "Inspect, compare, and manage backup tables inside the database.",
    },
    {
        "key": "manual_donations_notes",
        "path": "pages/07_Manual_Donations_and_Notes.py",
        "label": "Manual Donations and Notes",
        "description": "Add manual donation records and notes that are not part of an import file.",
    },
    {
        "key": "download_sync",
        "path": "pages/08_Download_Sync.py",
        "label": "Database Sync",
        "description": "Download the database from Google Drive or sync your local changes.",
    },
]


def list_db_files():
    if not os.path.isdir(DB_DIR):
        return []
    return sorted(
        [name for name in os.listdir(DB_DIR) if name.lower().endswith(".db")]
    )


def get_default_db_path():
    available = list_db_files()
    if available:
        if os.path.basename(DB_FILE_NAME) in available:
            return DB_FILE_NAME
        return os.path.join(DB_DIR, available[0])
    return DB_FILE_NAME


def get_selected_db_path():
    if "selected_db_file" not in st.session_state:
        st.session_state["selected_db_file"] = get_default_db_path()
    return st.session_state["selected_db_file"]


def set_selected_db_path(db_path):
    st.session_state["selected_db_file"] = db_path


def ensure_db_exists(db_path):
    if not os.path.exists(db_path):
        st.warning(
            "The selected database file is missing. Download it from Google Drive or select another database."
        )
        return False
    return True


def get_db_connection():
    db_path = get_selected_db_path()
    if not ensure_db_exists(db_path):
        return None
    return sqlite3.connect(db_path)


def get_drive_service():
    return google_drive_auth()


def render_sidebar_navigation(current_page=None):
    st.sidebar.header("Navigation")
    for page in SIDEBAR_PAGES:
        st.sidebar.page_link(page["path"], label=page["label"])
        if page["key"] == current_page:
            st.sidebar.caption(page["description"])
    st.sidebar.divider()


def render_drive_sidebar(conn=None, current_page=None):
    render_sidebar_navigation(current_page)
    st.sidebar.header("Google Drive")
    service = get_drive_service()
    db_path = get_selected_db_path()

    if st.sidebar.button("Download Database from Google Drive"):
        download_db_file(service, FILE_ID, db_path)

    sync_disabled = conn is None
    if st.sidebar.button("Sync Database with Google Drive", disabled=sync_disabled):
        if conn is not None:
            conn.close()
        upload_db_file(service, FILE_ID, db_path)
        return True

    return False


def render_backup_warning():
    db_path = get_selected_db_path()
    if "backup" in os.path.basename(db_path).lower():
        st.warning("You are viewing a backup database file.")
