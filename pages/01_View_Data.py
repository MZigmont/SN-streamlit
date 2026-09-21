import pandas as pd
import streamlit as st

import app_context as ctx
from authentication import require_admin


def main():
    require_admin()
    st.title("View Data")
    ctx.render_backup_warning()

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn, current_page="view_data")
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    cursor = conn.cursor()

    st.subheader("Database Contents")
    query = "SELECT name FROM sqlite_master WHERE type='table';"
    cursor.execute(query)
    tables = [row[0] for row in cursor.fetchall()]

    raw_tables = sorted([name for name in tables if name.startswith("raw_")])
    backup_tables = sorted([name for name in tables if name.startswith("backup_")])
    live_tables = sorted(
        [name for name in tables if not name.startswith("raw_") and not name.startswith("backup_")]
    )

    table_groups = {
        "live": live_tables,
        "raw": raw_tables,
        "backup": backup_tables,
    }

    category = st.selectbox("Table group", ["live", "raw", "backup"])
    group_tables = table_groups[category]
    if group_tables:
        table_name = st.selectbox("Table", group_tables)
    else:
        st.info("No tables in this group.")
        table_name = ""
    if table_name and st.button("Load Table"):
        try:
            query = f"SELECT * FROM {table_name}"
            data = pd.read_sql_query(query, conn)
            st.dataframe(data)
        except Exception as e:
            st.error(f"Error: {e}")


if __name__ == "__main__":
    main()
