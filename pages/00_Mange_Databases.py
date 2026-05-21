import os
import shutil
import sqlite3
from datetime import datetime

import streamlit as st

import app_context as ctx


def main():
    st.title("Manage Databases")
    ctx.render_backup_warning()

    if "db_ops_enabled" not in st.session_state:
        st.session_state["db_ops_enabled"] = True

    db_files = ctx.list_db_files()
    if not db_files:
        st.info("No .db files found in the db/ folder.")
        ctx.render_drive_sidebar()
        return

    current_path = ctx.get_selected_db_path()
    current_name = os.path.basename(current_path)
    if current_name not in db_files:
        current_name = db_files[0]

    selected_name = st.selectbox("Database file", options=db_files, index=db_files.index(current_name))
    selected_path = os.path.join(ctx.DB_DIR, selected_name)
    if selected_path != current_path:
        ctx.set_selected_db_path(selected_path)
        current_path = selected_path

    st.caption(f"Active database: {current_path}")

    st.divider()
    st.subheader("Create Backup")
    if not st.session_state["db_ops_enabled"]:
        st.info("Refresh the page to do another backup create/restore.")
    live_db_files = [name for name in db_files if "backup" not in name.lower()]
    if not live_db_files:
        st.info("No non-backup databases available to back up.")
    else:
        backup_placeholder = "Select a database to back up"
        backup_source_options = [backup_placeholder] + live_db_files
        backup_source = st.selectbox(
            "Database to back up",
            options=backup_source_options,
            disabled=not st.session_state["db_ops_enabled"],
        )
        create_disabled = (
            not st.session_state["db_ops_enabled"] or backup_source == backup_placeholder
        )
        if st.button("Create Backup", disabled=create_disabled):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base, ext = os.path.splitext(backup_source)
            backup_name = f"{base}_backup_{timestamp}{ext}"
            src_path = os.path.join(ctx.DB_DIR, backup_source)
            dst_path = os.path.join(ctx.DB_DIR, backup_name)
            shutil.copy2(src_path, dst_path)
            st.success(f"Backup created: {backup_name}")
            st.info("Refresh the page to do another backup create/restore.")
            st.session_state["db_ops_enabled"] = False

    st.divider()
    st.subheader("Restore Backup")
    if not st.session_state["db_ops_enabled"]:
        st.info("Refresh the page to do another backup create/restore.")
    backup_files = [name for name in db_files if "backup" in name.lower()]
    if not backup_files:
        st.info("No backup databases available to restore.")
    else:
        restore_placeholder = "Select a backup to restore"
        backup_options = [restore_placeholder] + backup_files
        selected_backup = st.selectbox(
            "Backup file",
            options=backup_options,
            disabled=not st.session_state["db_ops_enabled"],
        )
        if selected_backup != restore_placeholder:
            backup_base, backup_ext = os.path.splitext(selected_backup)
            if "_backup_" in backup_base:
                live_base = backup_base.split("_backup_")[0]
            elif backup_base.endswith("_backup"):
                live_base = backup_base[: -len("_backup")]
            else:
                live_base = backup_base.replace("backup", "").rstrip("_")
            live_name = f"{live_base}{backup_ext}"

            if live_name not in db_files:
                st.warning(
                    f"No live database found for this backup. It will be restored as {live_name}."
                )
                if st.button("Restore Backup", disabled=not st.session_state["db_ops_enabled"]):
                    src_path = os.path.join(ctx.DB_DIR, selected_backup)
                    dst_path = os.path.join(ctx.DB_DIR, live_name)
                    shutil.copy2(src_path, dst_path)
                    st.success(f"Restored {selected_backup} to {live_name}")
                    st.info("Refresh the page to do another backup create/restore.")
                    st.session_state["db_ops_enabled"] = False
            else:
                st.warning(f"This will overwrite {live_name} with {selected_backup}.")
                confirm = st.checkbox("I understand this will overwrite the live database")
                if st.button(
                    "Restore Backup",
                    disabled=(not confirm) or (not st.session_state["db_ops_enabled"]),
                ):
                    src_path = os.path.join(ctx.DB_DIR, selected_backup)
                    dst_path = os.path.join(ctx.DB_DIR, live_name)
                    shutil.copy2(src_path, dst_path)
                    st.success(f"Restored {selected_backup} to {live_name}")
                    st.info("Refresh the page to do another backup create/restore.")
                    st.session_state["db_ops_enabled"] = False

        st.divider()
        st.subheader("Create Database")
        if not st.session_state["db_ops_enabled"]:
            st.info("Refresh the page to do another backup create/restore.")
        new_db_name = st.text_input(
            "New database name",
            placeholder="example.db",
            disabled=not st.session_state["db_ops_enabled"],
        )
        normalized_name = new_db_name.strip()
        if normalized_name and not normalized_name.lower().endswith(".db"):
            normalized_name = f"{normalized_name}.db"

        name_conflict = normalized_name in db_files
        name_has_backup = "backup" in normalized_name.lower()
        name_empty = normalized_name == ""

        if name_empty:
            st.info("Enter a name for the new database.")
        elif name_has_backup:
            st.warning("Database names cannot contain the word 'backup'.")
        elif name_conflict:
            st.warning("A database with that name already exists.")

        create_db_disabled = (
            (not st.session_state["db_ops_enabled"])
            or name_empty
            or name_has_backup
            or name_conflict
        )
        if st.button("Create Database", disabled=create_db_disabled):
            new_db_path = os.path.join(ctx.DB_DIR, normalized_name)
            conn = sqlite3.connect(new_db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON;")
                schema_files = [
                    "donors.sql",
                    "aliases.sql",
                    "trans_source.sql",
                    "donations.sql",
                    "notes.sql",
                ]
                for file_name in schema_files:
                    sql_path = os.path.join("schema_sql", file_name)
                    with open(sql_path, "r", encoding="utf-8") as sql_file:
                        conn.executescript(sql_file.read())
                conn.commit()
                st.success(f"Database created: {normalized_name}")
                st.info("Refresh the page to do another backup create/restore.")
                st.session_state["db_ops_enabled"] = False
            finally:
                conn.close()

    ctx.render_drive_sidebar()


if __name__ == "__main__":
    main()
