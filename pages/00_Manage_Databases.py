import os
import shutil
import sqlite3
from contextlib import closing
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
        ctx.render_drive_sidebar(current_page="manage_databases")
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

    schema_files = [
        "donors.sql",
        "aliases.sql",
        "trans_source.sql",
        "donations.sql",
        "notes.sql",
    ]
    schema_table_names = {os.path.splitext(f)[0] for f in schema_files}

    def _normalize_schema(sql_text):
        return " ".join(sql_text.replace(";", "").split()).lower()

    def _load_schema_sql():
        schema_map = {}
        for file_name in schema_files:
            sql_path = os.path.join("schema_sql", file_name)
            with open(sql_path, "r", encoding="utf-8") as sql_file:
                schema_map[os.path.splitext(file_name)[0]] = _normalize_schema(sql_file.read())
        return schema_map

    def _load_db_schema(conn):
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL;"
        ).fetchall()
        return {name: _normalize_schema(sql) for name, sql in rows}

    def _load_schema_details(conn, table_names=None):
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        ).fetchall()
        details = {}
        for (table_name,) in rows:
            if table_names and table_name not in table_names:
                continue
            col_rows = conn.execute(f"PRAGMA table_info({table_name});").fetchall()
            fk_rows = conn.execute(f"PRAGMA foreign_key_list({table_name});").fetchall()
            columns = {}
            for cid, name, col_type, notnull, default_value, pk in col_rows:
                columns[name] = {
                    "type": col_type or "",
                    "notnull": bool(notnull),
                    "default": default_value,
                    "pk": pk,
                }
            foreign_keys = []
            for row in fk_rows:
                foreign_keys.append(
                    {
                        "table": row[2],
                        "from": row[3],
                        "to": row[4],
                        "on_update": row[5],
                        "on_delete": row[6],
                        "match": row[7],
                    }
                )
            details[table_name] = {"columns": columns, "foreign_keys": foreign_keys}
        return details

    def _schema_details_from_files():
        with closing(sqlite3.connect(":memory:")) as temp_conn:
            temp_conn.execute("PRAGMA foreign_keys = ON;")
            for file_name in schema_files:
                sql_path = os.path.join("schema_sql", file_name)
                with open(sql_path, "r", encoding="utf-8") as sql_file:
                    temp_conn.executescript(sql_file.read())
            return _load_schema_details(temp_conn, schema_table_names)

    def _format_column(col_name, col_info):
        parts = [col_name, col_info["type"].strip()]
        if col_info["pk"]:
            parts.append("PRIMARY KEY")
        if col_info["notnull"]:
            parts.append("NOT NULL")
        if col_info["default"] is not None:
            parts.append(f"DEFAULT {col_info['default']}")
        return " ".join([p for p in parts if p])

    def _format_fk(fk):
        return (
            f"{fk['from']} -> {fk['table']}.{fk['to']} "
            f"ON UPDATE {fk['on_update']} ON DELETE {fk['on_delete']}"
        )

    def _backup_db_file(db_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(os.path.basename(db_path))
        backup_name = f"{base}_backup_{timestamp}{ext}"
        backup_path = os.path.join(ctx.DB_DIR, backup_name)
        shutil.copy2(db_path, backup_path)
        return backup_name, backup_path

    def _rebuild_database(db_path, migrate_data=True):
        temp_path = f"{db_path}.rebuild"
        if os.path.exists(temp_path):
            os.remove(temp_path)
        with closing(sqlite3.connect(temp_path)) as new_conn:
            new_conn.execute("PRAGMA foreign_keys = ON;")
            try:
                for file_name in schema_files:
                    sql_path = os.path.join("schema_sql", file_name)
                    with open(sql_path, "r", encoding="utf-8") as sql_file:
                        new_conn.executescript(sql_file.read())

                if migrate_data:
                    with closing(sqlite3.connect(db_path)) as old_conn:
                        old_conn.execute("PRAGMA foreign_keys = ON;")
                        for table_name in [os.path.splitext(f)[0] for f in schema_files]:
                            old_cols = [
                                row[1]
                                for row in old_conn.execute(
                                    f"PRAGMA table_info({table_name});"
                                ).fetchall()
                            ]
                            new_cols = [
                                row[1]
                                for row in new_conn.execute(
                                    f"PRAGMA table_info({table_name});"
                                ).fetchall()
                            ]
                            shared_cols = [col for col in old_cols if col in new_cols]
                            if not shared_cols:
                                raise ValueError(f"No shared columns for {table_name}")
                            col_list = ", ".join(shared_cols)
                            placeholders = ", ".join(["?"] * len(shared_cols))
                            rows = old_conn.execute(
                                f"SELECT {col_list} FROM {table_name};"
                            ).fetchall()
                            new_conn.execute(f"DELETE FROM {table_name};")
                            if rows:
                                new_conn.executemany(
                                    f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders});",
                                    rows,
                                )
                new_conn.commit()
            except Exception:
                new_conn.rollback()
                raise

        os.replace(temp_path, db_path)

    with st.expander("Create Backup", expanded=False):
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

    with st.expander("Restore Backup", expanded=False):
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

    with st.expander("Create Database", expanded=False):
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

    with closing(sqlite3.connect(current_path)) as active_conn:
        active_schema = {
            name: sql
            for name, sql in _load_db_schema(active_conn).items()
            if name in schema_table_names
        }
        active_details = _load_schema_details(active_conn, schema_table_names)
    file_details = _schema_details_from_files()
    mismatched_tables = []
    for table_name in sorted(schema_table_names):
        if active_details.get(table_name) != file_details.get(table_name):
            mismatched_tables.append(table_name)
    schema_matches = len(mismatched_tables) == 0

    with st.expander("Verify Schema", expanded=False):
        if schema_matches:
            st.success("Database schema matches schema_sql.")
        else:
            st.warning("Database schema does not match schema_sql.")
            for table_name in mismatched_tables:
                active_table = active_details.get(table_name)
                file_table = file_details.get(table_name)
                if active_table == file_table:
                    continue
                with st.container(border=True):
                    st.markdown(f"**Schema diff: `{table_name}`**")
                    if not active_table:
                        st.error("Table missing in database.")
                    if not file_table:
                        st.error("Table missing in schema_sql.")

                    if active_table and file_table:
                        active_cols = active_table["columns"]
                        file_cols = file_table["columns"]
                        added_cols = sorted(set(file_cols) - set(active_cols))
                        removed_cols = sorted(set(active_cols) - set(file_cols))
                        common_cols = sorted(set(file_cols) & set(active_cols))

                        if added_cols:
                            st.write("Columns missing in database")
                            st.code(
                                "\n".join(
                                    _format_column(col, file_cols[col]) for col in added_cols
                                ),
                                language="text",
                            )
                        if removed_cols:
                            st.write("Columns missing in schema_sql")
                            st.code(
                                "\n".join(
                                    _format_column(col, active_cols[col]) for col in removed_cols
                                ),
                                language="text",
                            )

                        changed_cols = []
                        for col in common_cols:
                            if active_cols[col] != file_cols[col]:
                                changed_cols.append(col)
                        if changed_cols:
                            st.write("Columns with differences")
                            lines = []
                            for col in changed_cols:
                                lines.append("Database: " + _format_column(col, active_cols[col]))
                                lines.append("Schema:   " + _format_column(col, file_cols[col]))
                                lines.append("")
                            st.code("\n".join(lines).strip(), language="text")

                        active_fks = {_format_fk(fk) for fk in active_table["foreign_keys"]}
                        file_fks = {_format_fk(fk) for fk in file_table["foreign_keys"]}
                        missing_fks = sorted(file_fks - active_fks)
                        extra_fks = sorted(active_fks - file_fks)

                        if missing_fks:
                            st.write("Foreign keys missing in database")
                            st.code("\n".join(missing_fks), language="text")
                        if extra_fks:
                            st.write("Foreign keys missing in schema_sql")
                            st.code("\n".join(extra_fks), language="text")

            st.info("Rebuild will create a backup automatically before changes.")
            if not st.session_state.get("db_ops_enabled", True):
                st.info("Refresh the page to do another backup create/restore.")
            else:
                if st.button("Rebuild schema and migrate data"):
                    backup_name, _ = _backup_db_file(current_path)
                    try:
                        _rebuild_database(current_path, migrate_data=True)
                        st.success(
                            f"Database rebuilt with migrated data. Backup saved as {backup_name}."
                        )
                        st.info("Refresh the page to do another backup create/restore.")
                        st.session_state["db_ops_enabled"] = False
                    except Exception as exc:
                        st.session_state["schema_rebuild_failed"] = True
                        st.session_state["schema_rebuild_error"] = str(exc)
                        st.warning(
                            "Data migration failed. You can rebuild without migrating data."
                        )

                if st.session_state.get("schema_rebuild_failed"):
                    st.warning(
                        f"Migration failure detail: {st.session_state.get('schema_rebuild_error')}"
                    )
                    if st.button("Rebuild without data"):
                        backup_name, _ = _backup_db_file(current_path)
                        _rebuild_database(current_path, migrate_data=False)
                        st.success(
                            "Database rebuilt without data. "
                            f"Backup saved as {backup_name}."
                        )
                        st.info("Refresh the page to do another backup create/restore.")
                        st.session_state["db_ops_enabled"] = False

    ctx.render_drive_sidebar(current_page="manage_databases")


if __name__ == "__main__":
    main()
