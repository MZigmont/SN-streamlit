from datetime import date

import streamlit as st

import app_context as ctx
import reports


def main():
    st.title("Run Reports")
    ctx.render_backup_warning()

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn)
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    default_startdate = date(date.today().year, 1, 1)
    default_enddate = date.today()

    start_date, end_date = st.date_input(
        "Select a date range",
        value=(default_startdate, default_enddate),
    )
    st.write(f"Start: {start_date}, End: {end_date}")

    if st.button(f"Run Reports for period {start_date} to {end_date}"):
        output, wb_name = reports.run_all_reports(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            conn,
        )
        st.download_button(
            label="Download Excel file",
            data=output,
            file_name=wb_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()
