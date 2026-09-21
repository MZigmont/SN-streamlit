import streamlit as st

import app_context as ctx
from authentication import require_admin


def main():
    require_admin()
    st.title("Database Sync")
    ctx.render_backup_warning()
    st.write("Use the sidebar controls to download or sync the database with Google Drive.")

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn, current_page="download_sync")
    if sync_clicked:
        st.stop()

    if conn is None:
        st.info("Download the database to enable other pages.")
    else:
        st.success("Database file is ready.")


if __name__ == "__main__":
    main()
