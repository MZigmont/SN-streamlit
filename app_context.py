import os
import sqlite3

import streamlit as st

from google_drive_interface import google_drive_auth, download_db_file, upload_db_file

DB_DIR = "db"
DB_FILE_NAME = "db/sigma_nu_donations.db"
FILE_ID = "1L61qdt5NiBeo1K3H7tYZzCNU1vAjRuNb"


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


@st.cache_resource
def get_drive_service():
    return google_drive_auth()


def render_drive_sidebar(conn=None):
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
