import pandas as pd
import streamlit as st

import app_context as ctx
import backups


def main():
    st.title("Manage Backups")
    ctx.render_backup_warning()

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn)
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    cursor = conn.cursor()

    selected_index = st.selectbox(
        "Select a row:",
        options=["Create a backup", "Delete a backup", "Restore from a backup"],
    )
    if selected_index == "Create a backup":
        st.subheader("Select Table you want to backup")
        query = "SELECT name FROM sqlite_master WHERE type='table';"
        cursor.execute(query)
        tables = [row[0] for row in cursor.fetchall() if "backup_" not in row[0]]

        selected_backup = st.selectbox("Select a Table:", options=tables)
        st.subheader(f"You selected {selected_backup} to create a backup table.")

        if st.button(f"YES, make a backup of {selected_backup}"):
            backup_tablename = backups.create_backup(selected_backup, conn)
            st.success(f"Backup created, {backup_tablename}")

    elif selected_index == "Delete a backup":
        st.subheader("Select BACKUP Table you want to delete")
        query = "SELECT name FROM sqlite_master WHERE type='table';"
        cursor.execute(query)
        tables = [row[0] for row in cursor.fetchall() if "backup_" in row[0]]

        selected_backup = st.selectbox("Select a Table:", options=tables)
        st.subheader(f"You selected {selected_backup} to delete.")
        if st.button(f"YES, delete {selected_backup}"):
            backups.delete_backup(selected_backup, conn)
            st.success(f"You just deleted {selected_backup}")

    elif selected_index == "Restore from a backup":
        st.subheader("Select BACKUP Table you want to restore")
        query = "SELECT name FROM sqlite_master WHERE type='table';"
        cursor.execute(query)
        tables = [row[0] for row in cursor.fetchall() if "backup_" in row[0]]

        selected_backup = st.selectbox("Select a Table:", options=tables)
        parts = selected_backup.split("_")

        target_table = "_".join(parts[1:-2])
        st.subheader(f"You've selected {selected_backup} to overwrite {target_table}")

        selected_backup_df = pd.read_sql_query(
            f"PRAGMA table_info({selected_backup});",
            conn,
        )
        st.subheader(f"{selected_backup}")
        st.dataframe(selected_backup_df)

        target_table_df = pd.read_sql_query(
            f"PRAGMA table_info({target_table});",
            conn,
        )
        st.subheader(f"{target_table}")
        st.dataframe(target_table_df)

        if len(selected_backup_df) != len(target_table_df):
            st.error(
                f"Backup table {selected_backup} has {len(selected_backup_df)} columns.\n"
                f"Target table {target_table} has {len(target_table_df)} fields.\n"
                f"{target_table} was NOT overwritten."
            )
        elif (target_table_df["name"] == selected_backup_df["name"]).all():
            st.write("Fieldnames match!")
            if st.button(f"YES, overwrite {target_table} with data from {selected_backup}"):
                backups.restore_backup(target_table, selected_backup, conn)
                st.success(f"{target_table} was overwritten by {selected_backup}")
        else:
            st.error("Fieldnames of tables do not match.")


if __name__ == "__main__":
    main()
