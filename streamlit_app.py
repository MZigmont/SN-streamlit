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
import reports
from datetime import datetime
from datetime import date
import backups
import update_db as udb

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

# Define what happens when the button is clicked
def on_click():
    st.session_state["button_enabled"] = False

# Streamlit App
def main():
    # Initialize session state key
    if "button_enabled" not in st.session_state:
        st.session_state["button_enabled"] = True
    
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
        operation = st.sidebar.radio("Choose an Operation", ['View Data', 'Upload CSV', "FIX DATABASE", "Download/Upload Tables", "Run Reports", "Manage Backups"])

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
                    st.text("How do you want to proceed?")
                    if st.button("Commit the data to database?"):
                        conn.commit()
                        st.success("Data committed to the database!")

                    if st.button("Cancel"):
                        conn.rollback()
                        st.success("Database rolled back to prior state!")

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
                
        elif operation == "Download/Upload Tables":
            st.subheader("Select Table you want to download as .csv")
            query = "SELECT name FROM sqlite_master WHERE type='table';"
            cursor.execute(query)
            tables = [row[0] for row in cursor.fetchall() if "backup_" not in row[0]]
            
            selected_backup = st.selectbox(
                    "Select a Table:",
                    options=tables,  # Values passed through
                    )
            query = f"""
                SELECT *
                FROM {selected_backup}
                """
            output_df = pd.read_sql_query(query, conn)

            csv = output_df.to_csv(index=False)

            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"{selected_backup}.csv",
                mime="text/csv"
                )

            st.dataframe(output_df)

            st.write("Upload the .csv file to replace a Table")
            st.subheader("Upload .csv")
            uploaded_file = st.file_uploader("Choose a .csv file", type=['csv'])
            
            if uploaded_file is not None:
                # Read CSV into DataFrame
                df = pd.read_csv(uploaded_file, dtype={"zip": str}, keep_default_na=True, na_values=[''])
                st.subheader("This is what you uploaded")
                st.dataframe(df)
                st.subheader("Please select the table to OVERWRITE with your uploaded data")
                overwriting_table = st.selectbox(
                    label="Select the table to OVERWRITE:",
                    options=tables,
                    )
                

                
                if st.button(f"Confirm that you want to overwrite selected table {overwriting_table}",
                            on_click=on_click,
                            disabled=not st.session_state["button_enabled"]
                ):
                    # call the create_backup() function here
                    backups.create_backup(overwriting_table, conn)
                    st.success("Backup created.")
                    
                    # Execute PRAGMA and read into DataFrame
                    existing_table_df = pd.read_sql_query(f"PRAGMA table_info({overwriting_table});", conn)
                    st.dataframe(existing_table_df)
                    st.write(df.dtypes)

                    # Check if number of fieldnames/columns matches
                    if len(existing_table_df["name"]) != len(df.columns):
                        st.error(f"Uploaded table has {len(df.columns)} columns.  \n"
                                 f"Existing table {overwriting_table} has {len(existing_table_df["name"])} fields.  \n"
                                 f"{overwriting_table} was NOT overwritten.")
                    # Compare uploaded fieldnames with existing fieldnames
                    elif (existing_table_df["name"] == df.columns).all():
                        # fieldnames match, go ahead and overwrite
                        st.write("Fieldnames match!")
                        df.to_sql("temp_table_csv_direct_edit", conn, if_exists='replace', index=False)
                        table_overwrite_sql_code = f"""
                        -- Disable foreign key checks
                        PRAGMA foreign_keys = OFF;

                        DELETE FROM {overwriting_table};
                        INSERT INTO {overwriting_table} 
                        SELECT * FROM temp_table_csv_direct_edit;

                        -- Re-enable foreign key checks
                        PRAGMA foreign_keys = ON;

                        DROP TABLE temp_table_csv_direct_edit;
                        """
                        # this command automatically commits a transaction
                        cursor.executescript(table_overwrite_sql_code)
                    else:
                        st.error("Fieldnames of uploaded table do not match selected table.  \n"
                                 f"{overwriting_table} was NOT overwritten.")
        elif operation == "Run Reports":
            default_startdate = date(date.today().year,1,1)
            default_enddate = date.today()
            # Date range selector
            start_date, end_date = st.date_input(
                "Select a date range",

                value=(default_startdate, default_enddate)    
            )
            st.write(f"Start: {start_date}, End: {end_date}")
            
            if st.button(f"Run Reports for period {start_date} to {end_date}"):
                # Run reports here
                output , wb_name = reports.run_all_reports(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), conn)
                # Provide download button for the user
                st.download_button(
                    label="Download Excel file",
                    data=output,
                    file_name=wb_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        elif operation == "Manage Backups":
            # Use index as values and format_func to show readable labels
            selected_index = st.selectbox(
                "Select a row:",
                options=["Create a backup", "Delete a backup", "Restore from a backup"]
            )
            if selected_index == "Create a backup":
                st.subheader("Select Table you want to backup")
                query = "SELECT name FROM sqlite_master WHERE type='table';"
                cursor.execute(query)
                tables = [row[0] for row in cursor.fetchall() if "backup_" not in row[0]]
                
                selected_backup = st.selectbox(
                        "Select a Table:",
                        options=tables,  # Values passed through
                        )
                st.subheader(f"You selected {selected_backup} to create a backup table.")
                
                if st.button(f"YES, make a backup of {selected_backup}"):
                    backup_tablename = backups.create_backup(selected_backup, conn)
                    st.success(f"Backup created, {backup_tablename}")
                
            elif selected_index == "Delete a backup":
                # delete a table here
                st.subheader("Select BACKUP Table you want to delete")
                query = "SELECT name FROM sqlite_master WHERE type='table';"
                cursor.execute(query)
                tables = [row[0] for row in cursor.fetchall() if "backup_" in row[0]]
                
                selected_backup = st.selectbox(
                        "Select a Table:",
                        options=tables,  # Values passed through
                        )
                st.subheader(f"You selected {selected_backup} to delete.")
                if st.button(f"YES, delete {selected_backup}"):
                    backups.delete_backup(selected_backup, conn)
                    st.success(f"You just deleted {selected_backup}")

                pass
            elif selected_index == "Restore from a backup":
                # restore a table here
                st.subheader("Select BACKUP Table you want to restore")
                query = "SELECT name FROM sqlite_master WHERE type='table';"
                cursor.execute(query)
                tables = [row[0] for row in cursor.fetchall() if "backup_" in row[0]]
                
                selected_backup = st.selectbox(
                        "Select a Table:",
                        options=tables,  # Values passed through
                        )
                parts = selected_backup.split("_")

                # everything between the first and the second-to-last
                target_table = "_".join(parts[1:-2])
                st.subheader(f"You've selected {selected_backup} to overwrite {target_table}")
                
                # Execute PRAGMA and read into DataFrame
                selected_backup_df = pd.read_sql_query(f"PRAGMA table_info({selected_backup});", conn)
                st.subheader(f"{selected_backup}")
                st.dataframe(selected_backup_df)

                target_table_df = pd.read_sql_query(f"PRAGMA table_info({target_table});", conn)
                st.subheader(f"{target_table}")
                st.dataframe(target_table_df)

                # Check if number of fieldnames/columns matches
                if len(selected_backup_df) != len(target_table_df):
                    st.error(f"Backup table {selected_backup} has {len(selected_backup_df)} columns.  \n"
                                f"Target table {target_table} has {len(target_table_df)} fields.  \n"
                                f"{target_table} was NOT overwritten.")
                # Compare fieldnames of two tables
                elif (target_table_df["name"] == selected_backup_df["name"]).all():
                    # fieldnames match, go ahead and overwrite
                    st.write("Fieldnames match!")
                    if st.button(f"YES, overwrite {target_table} with data from {selected_backup}"):
                        backups.restore_backup(target_table, selected_backup, conn)
                        st.success(f"{target_table} was overwritten by {selected_backup}")
                else:
                    st.error("Fieldnames of tables do not match.  \n"
                                f"{overwriting_table} was NOT overwritten.")

# some legit source_trans_id are text!  HOW TO HANDLE??


# TO DO: 8/6/2025 - error thrown when user chooses first data in "Run Reports"
# TO DO: 8/11/2025 - update data from Bluepay and Paypal and then run code
# TO DO: 8/11/2025 - Show error message to user when they select a date range that contains no records
# TO DO: LATER - get email functionality to work
# TO DO: 7/21/2025 - build out reports
# TO DO: 7/21/2025 - figure out emailing



# TO DO: 5/12/2025 - make UI to help user resolve validation errors, start with duplicate source trans ids in donations


        # Upload the updated database file back to Google Drive
        if st.button("Sync Database with Google Drive"):
            conn.close()
            upload_db_file(service, FILE_ID, DB_FILE_NAME)

        # Close connection on app exit
        st.sidebar.text("Close the app to release database lock.")

if __name__ == "__main__":
    main()
