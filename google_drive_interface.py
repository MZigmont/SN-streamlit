import tempfile
from pathlib import Path
import os

import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from authentication import require_admin
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

def _reconnect_drive():
    st.warning("Google Drive authorization is missing or expired. Sign in again to reconnect.")
    if st.button("Reconnect Google Drive", key="reconnect_google_drive"):
        st.login("google")
    st.stop()


def google_drive_auth():
    """Build a Drive client using only the current administrator's access token."""
    require_admin(render_sidebar=False)
    token = st.user.tokens.get("access")
    if not token or st.session_state.get("expired_drive_token") == token:
        _reconnect_drive()
    st.session_state.pop("expired_drive_token", None)
    return build("drive", "v3", credentials=Credentials(token=token))


def _handle_drive_error(error, action):
    if isinstance(error, HttpError) and error.resp.status == 401:
        st.session_state["expired_drive_token"] = st.user.tokens.get("access")
        st.rerun()
    elif isinstance(error, HttpError) and error.resp.status == 403:
        st.error("Google Drive denied access. Grant Drive permission at sign-in and check that your account is an Editor of the database file.")
    else:
        st.error(f"Could not {action} the database. Check the connection and file access, then try again.")


def download_db_file(service, file_id, local_file):
    """Download a file from Google Drive to a local path."""
    temp_path = None
    try:
        destination = Path(local_file)
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = service.files().get_media(fileId=file_id)
        with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent, delete=False) as file_handle:
            temp_path = Path(file_handle.name)
            downloader = MediaIoBaseDownload(file_handle, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        os.replace(temp_path, destination)
        st.success("Database file downloaded successfully.")
    except Exception as e:
        _handle_drive_error(e, "download")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def upload_db_file(service, file_id, local_file):
    """Upload a local file to replace an existing file in Google Drive."""
    try:
        media = MediaFileUpload(local_file, mimetype="application/x-sqlite3", resumable=True)
        service.files().update(fileId=file_id, media_body=media).execute()
        st.success("Database file updated successfully on Google Drive.")
    except Exception as e:
        _handle_drive_error(e, "upload")
