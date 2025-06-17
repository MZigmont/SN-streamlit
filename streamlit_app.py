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
import bluepay_ingestion as bi
import validation_display as vd
import error_correction as ec

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

def download_db_file(service, file_id, local_file):
    """Download the database file from Google Drive."""
    try:
        request = service.files().get_media(fileId=file_id)
        with io.FileIO(local_file, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        st.success("Database file downloaded successfully.")
    except Exception as e:
        st.error(f"Error downloading file: {e}")

def upload_db_file(service, file_id, local_file):
    """Upload the updated database file to Google Drive."""
    try:
        media = MediaFileUpload(local_file, mimetype='application/x-sqlite3', resumable=True)
        service.files().update(fileId=file_id, media_body=media).execute()
        st.success("Database file updated successfully on Google Drive.")
    except Exception as e:
        st.error(f"Error uploading file: {e}")

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
        operation = st.sidebar.radio("Choose an Operation", ['View Data', 'Insert Data', 'Update Data', 'Upload CSV', "FIX DATABASE"])

        if operation == 'View Data':
            st.subheader("Database Contents")
            query = "SELECT name FROM sqlite_master WHERE type='table';"
            cursor.execute(query)
            tables = [row[0] for row in cursor.fetchall()]
            st.write("Tables in Database:", tables)
            table_name = st.text_input("Enter table name to view", "")
            if st.button("Load Table"):
                try:
                    query = f"SELECT * FROM {table_name}"
                    data = pd.read_sql_query(query, conn)
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

        elif operation == 'Upload CSV':
            st.subheader("Upload CSV File")
            uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])
            if uploaded_file is not None:
                try:
                    # Read CSV into DataFrame
                    df = pd.read_csv(uploaded_file, dtype={"zip": str}, keep_default_na=False)
                    st.text("raw_data")
                    st.dataframe(df)
                    results_dict = bi.ingest_data(df, conn)
                    staged_data = results_dict['temp_donations']
                    staged_donors = results_dict['temp_donors']
                    staged_aliases = results_dict['temp_aliases']
                    validation_dict = results_dict['validation_dict']

                    st.text("temp_donations")
                    st.dataframe(staged_data)
                    st.text("staged_donors")
                    st.dataframe(staged_donors)
                    st.text("staged_aliases")
                    st.dataframe(staged_aliases)

                    vd.display(validation_dict)
                    
                    # Insert data into a table
                    # table_name = st.text_input("Enter table name to insert data into", "")
                    # if st.button("Insert CSV Data into Table"):
                    #     df.to_sql(table_name, conn, if_exists='append', index=False)
                    #     st.success(f"Data successfully inserted into {table_name}")
                except Exception as e:
                    st.error(f"Error processing the CSV file: {e}")
        elif operation == 'FIX DATABASE':

            st.subheader("WRITE THE CODE AND DO THE MAGIC")
            
            # Sample DataFrame
            df = ec.get_duplicated_source_trans_IDs(conn)

            if len(df) == 0:
                st.write("There are NO duplicate source trans IDs")
            else:
                st.write("## Data Table")
                st.dataframe(df)
                
                # Use index as values and format_func to show readable labels
                selected_index = st.selectbox(
                    "Select a row:",
                    options=df.index,  # Values passed through
                    format_func=lambda i: f"trans_id {df.loc[i, 'source_trans_id']}, {df.loc[i, 'source_name']}, {df.loc[i, 'COUNT(*)']}"
                )
                selected_trans_id = df.loc[selected_index, 'source_trans_id']
                results_df = ec.show_duplicate_source_trans_IDs(conn, selected_trans_id)
                st.dataframe(results_df)

                # Generate radio button labels from DataFrame rows
                row_labels = [f"{row['my_trans_id_pk']}" for _, row in results_df.iterrows()]

                # Let user select one row
                selected_label = st.radio("Select a row TO KEEP:", row_labels)

                # Find the selected row in the DataFrame
                selected_index_2 = row_labels.index(selected_label)
                selected_row = results_df.iloc[selected_index_2]

                st.write("### Selected Row")
                st.write(selected_row.to_frame().T)  # display as single-row DataFrame

                if st.button("KEEP Selected Row, delete all others"):
                    ec.keep_donation(conn, selected_trans_id, selected_label)
                    conn.commit()
                    st.success("Row kept and others deleted!")

# TO DO: 6/9/2025 - make sure no error shows when there are no duplicate transactions

# TO DO: 5/12/2025 - make UI to help user resolve validation errors, start with duplicate source trans ids in donations


        # Upload the updated database file back to Google Drive
        if st.button("Sync Database with Google Drive"):
            conn.close()
            upload_db_file(service, FILE_ID, DB_FILE_NAME)

        # Close connection on app exit
        st.sidebar.text("Close the app to release database lock.")

if __name__ == "__main__":
    main()
