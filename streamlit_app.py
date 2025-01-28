import streamlit as st
import sqlite3
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import io
import pandas as pd

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive']
DB_FILE_NAME = 'sigma_nu_donations.db'

# Authenticate and connect to Google Drive
def google_drive_auth():
    """Authenticate with Google Drive API."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def get_file_metadata(service, file_id):
    try:
        return service.files().get(fileId=file_id).execute()
    except Exception as e:
        st.error(f"Error fetching file metadata: {e}")
        return None

def download_db_file(service, file_id, local_file):
    """Download the database file from Google Drive."""
    file_metadata = get_file_metadata(service, file_id)
    if file_metadata:
        request = service.files().get_media(fileId=file_id)
        with io.FileIO(local_file, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            st.success("Database file downloaded successfully.")
    else:
        st.error("File not found or inaccessible.")

def upload_db_file(service, file_id, local_file):
    """Upload the updated database file to Google Drive."""
    media = MediaFileUpload(local_file, mimetype='application/x-sqlite3', resumable=True)
    service.files().update(fileId=file_id, media_body=media).execute()
    st.success("Database file updated successfully on Google Drive.")

# Streamlit App
def main():
    st.title("SQLite Database Editor with Google Drive Sync")

    # Google Drive Authentication
    service = google_drive_auth()

    # File ID of the database on Google Drive (replace this with your file ID)
    FILE_ID = '1L61qdt5NiBeo1K3H7tYZzCNU1vAjRuNb'

    # Check if the local database file exists
    if not os.path.exists(DB_FILE_NAME):
        st.warning("The local database file is missing. Please download it from Google Drive.")

    # Button to download the database file
    if st.button("Download Database from Google Drive"):
        download_db_file(service, FILE_ID, DB_FILE_NAME)

    # Only proceed if the database file exists locally
    if os.path.exists(DB_FILE_NAME):
        # Connect to the SQLite database
        conn = sqlite3.connect(DB_FILE_NAME)
        cursor = conn.cursor()

        # UI Options
        st.sidebar.header("Database Operations")
        operation = st.sidebar.radio("Choose an Operation", ['View Data', 'Insert Data', 'Update Data'])

        if operation == 'View Data':
            st.subheader("Database Contents")
            query = "SELECT name FROM sqlite_master WHERE type='table';"
            cursor.execute(query)
            tables = [row[0] for row in cursor.fetchall()]
            st.write(tables)
            table_name = st.text_input("Enter table name to view", "")
            if st.button("Load Table"):
                try:
                    query = f"SELECT * FROM {table_name}"
                    data = pd.read_sql_query(query, conn) 
                    # (f"SELECT * FROM {table_name}").fetchall()
                    st.dataframe(data)
                except Exception as e:
                    st.error(f"Error: {e}")

        elif operation == 'Insert Data':
            st.subheader("Insert New Data")
            table_name = st.text_input("Table Name", "")
            columns = st.text_input("Columns (comma-separated)", "")
            values = st.text_input("Values (comma-separated)", "")
            if st.button("Insert"):
                try:
                    query = f"INSERT INTO {table_name} ({columns}) VALUES ({values})"
                    cursor.execute(query)
                    conn.commit()
                    st.success("Data inserted successfully!")
                except Exception as e:
                    st.error(f"Error: {e}")

        elif operation == 'Update Data':
            st.subheader("Update Data")
            table_name = st.text_input("Table Name", "")
            set_clause = st.text_input("SET clause (e.g., column1 = 'value')", "")
            condition = st.text_input("WHERE clause (optional)", "")
            if st.button("Update"):
                try:
                    query = f"UPDATE {table_name} SET {set_clause}"
                    if condition:
                        query += f" WHERE {condition}"
                    cursor.execute(query)
                    conn.commit()
                    st.success("Data updated successfully!")
                except Exception as e:
                    st.error(f"Error: {e}")

        # Upload the updated database file back to Google Drive
        if st.button("Sync Database with Google Drive"):
            conn.close()
            upload_db_file(service, FILE_ID, DB_FILE_NAME)

        # Close connection on app exit
        st.sidebar.text("Close the app to release database lock.")

if __name__ == "__main__":
    main()
