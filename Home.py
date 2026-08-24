import streamlit as st

import app_context as ctx


def main():
    st.title("Sigma Nu Donations Database Tool")
    ctx.render_backup_warning()
    st.write("Use this website to manage the Sigma Nu donations database.")

    st.subheader("High-Level Workflow")
    st.markdown(
        """
            Download donation transaction records from the credit card payment processors to a local folder.
        1. Use the **Ingest Data** page to upload the processor data into the website.
        2. Use the **Run Reports** page to analyze the data in the Sigma Nu database.
        3. Use the **Send Emails** page to automatically send emails to donors.
        """
    )

    st.info(
        "Other functionality, such as database corrections, table download/upload, "
        "and database syncing, is available on the other pages. Instructions for "
        "those pages are provided there."
    )

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn, current_page="home")
    if sync_clicked:
        st.stop()

    if conn is None:
        st.info("Download the database to enable the other pages.")
    else:
        st.success("Database file is ready.")

if __name__ == "__main__":
    main()
