import pandas as pd
import streamlit as st

import app_context as ctx
from authentication import require_admin
import backups


def main():
    require_admin()
    st.title("Manage Backups")
    ctx.render_backup_warning()

    if "db_ops_enabled" not in st.session_state:
        st.session_state["db_ops_enabled"] = True
    if not st.session_state["db_ops_enabled"]:
        st.info("Refresh the page to continue making database changes.")

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn, current_page="manage_backup_tables")
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    cursor = conn.cursor()

    query = "SELECT name FROM sqlite_master WHERE type='table';"
    cursor.execute(query)
    all_tables = [row[0] for row in cursor.fetchall()]
    non_backup_tables = [
        name
        for name in all_tables
        if "backup_" not in name and "raw_" not in name and "temp_" not in name
    ]
    backup_tables = [name for name in all_tables if "backup_" in name]

    if st.session_state["db_ops_enabled"]:
        with st.expander("Create a backup", expanded=False):
            st.subheader("Select Table you want to backup")
            if not non_backup_tables:
                st.info("No tables available to back up.")
            else:
                create_placeholder = "Select a table to back up"
                create_options = [create_placeholder] + non_backup_tables
                selected_backup = st.selectbox("Select a Table:", options=create_options)
                if selected_backup != create_placeholder:
                    st.subheader(f"You selected {selected_backup} to create a backup table.")

                    if st.button(
                        f"YES, make a backup of {selected_backup}",
                        disabled=not st.session_state["db_ops_enabled"],
                    ):
                        backup_tablename = backups.create_backup(selected_backup, conn)
                        st.success(f"Backup created, {backup_tablename}")
                        st.info("Refresh the page to continue making database changes.")
                        st.session_state["db_ops_enabled"] = False
    else:
        st.write("Create a backup (refresh required)")

    if st.session_state["db_ops_enabled"]:
        with st.expander("Delete a backup", expanded=False):
            st.subheader("Select BACKUP Table you want to delete")
            if not backup_tables:
                st.info("No backup tables available to delete.")
            else:
                delete_placeholder = "Select a backup table to delete"
                delete_options = [delete_placeholder] + backup_tables
                selected_backup = st.selectbox(
                    "Select a Table:",
                    options=delete_options,
                    key="delete_backup",
                )
                if selected_backup != delete_placeholder:
                    st.subheader(f"You selected {selected_backup} to delete.")
                    if st.button(
                        f"YES, delete {selected_backup}",
                        disabled=not st.session_state["db_ops_enabled"],
                    ):
                        backups.delete_backup(selected_backup, conn)
                        st.success(f"You just deleted {selected_backup}")
                        st.info("Refresh the page to continue making database changes.")
                        st.session_state["db_ops_enabled"] = False
    else:
        st.write("Delete a backup (refresh required)")

    if st.session_state["db_ops_enabled"]:
        with st.expander("Restore from a backup", expanded=False):
            st.subheader("Select BACKUP Table you want to restore")
            if not backup_tables:
                st.info("No backup tables available to restore.")
            else:
                restore_placeholder = "Select a backup table to restore"
                restore_options = [restore_placeholder] + backup_tables
                selected_backup = st.selectbox(
                    "Select a Table:",
                    options=restore_options,
                    key="restore_backup",
                )
                if selected_backup != restore_placeholder:
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
                        if st.button(
                            f"YES, overwrite {target_table} with data from {selected_backup}",
                            disabled=not st.session_state["db_ops_enabled"],
                        ):
                            backups.restore_backup(target_table, selected_backup, conn)
                            st.success(f"{target_table} was overwritten by {selected_backup}")
                            st.info("Refresh the page to continue making database changes.")
                            st.session_state["db_ops_enabled"] = False
                    else:
                        st.error("Fieldnames of tables do not match.")
    else:
        st.write("Restore from a backup (refresh required)")


if __name__ == "__main__":
    main()
