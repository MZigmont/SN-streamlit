import io
import os

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]


def google_drive_auth():
    """Authenticate with Google Drive using Streamlit secrets and a cached token."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            drive_secrets = st.secrets["google_drive"]
            client_config = {
                "installed": {
                    "client_id": drive_secrets["client_id"],
                    "client_secret": drive_secrets["client_secret"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def download_db_file(service, file_id, local_file):
    """Download a file from Google Drive to a local path."""
    try:
        request = service.files().get_media(fileId=file_id)
        with io.FileIO(local_file, "wb") as file_handle:
            downloader = MediaIoBaseDownload(file_handle, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        st.success("Database file downloaded successfully.")
    except Exception as e:
        st.error(f"Error downloading file: {e}")


def upload_db_file(service, file_id, local_file):
    """Upload a local file to replace an existing file in Google Drive."""
    try:
        media = MediaFileUpload(local_file, mimetype="application/x-sqlite3", resumable=True)
        service.files().update(fileId=file_id, media_body=media).execute()
        st.success("Database file updated successfully on Google Drive.")
    except Exception as e:
        st.error(f"Error uploading file: {e}")
