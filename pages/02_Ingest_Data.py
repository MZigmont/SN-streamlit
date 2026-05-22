import pandas as pd
import streamlit as st

import app_context as ctx
import ingestion.bluepay_ingestion as bi
import ingestion.paypal_ingestion as pi
import ingestion.cardpointe_ingestion as ci
import update_db as udb
import validation_display as vd


def main():
    st.title("Ingest Data")
    ctx.render_backup_warning()

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn)
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    latest_df = udb.get_latest_transaction(conn)
    latest_df = latest_df.rename(
        columns={
            "source_name": "Source",
            "MAX(d.date_time)": "Latest Transaction",
        }
    )
    latest_df = latest_df[["Source", "Latest Transaction"]]
    st.dataframe(latest_df)
    payment_processor = st.selectbox(
        "What source is the file?",
        ["Bluepay / Clover", "Paypal", "CardPointe"],
    )
    st.subheader("Upload CSV File")
    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded_file is not None:
        try:
            df = pd.read_csv(
                uploaded_file,
                dtype={
                    "zip": str,
                    "Zip/Postal Code": str,
                    "phone": str,
                    "Contact Phone Number": str,
                },
                keep_default_na=False,
            )
            with st.expander("Uploaded CSV", expanded=False):
                st.dataframe(df)
            if payment_processor == "Bluepay / Clover":
                results_dict = bi.ingest_data(df, conn)
            elif payment_processor == "Paypal":
                results_dict = pi.ingest_data(df, conn)
            elif payment_processor == "CardPointe":
                results_dict = ci.ingest_data(df, conn)
            else:
                st.error(f"Unexpected radio button value {payment_processor}")
                raise NotImplementedError("Unexpected radio button value")

            temp_raw_data = results_dict["temp_raw_data"]
            staged_data = results_dict["temp_donations"]
            staged_donors = results_dict["temp_donors"]
            staged_aliases = results_dict["temp_aliases"]
            validation_dict = results_dict["validation_dict"]
            with st.expander("Raw Data Preview", expanded=False):
                st.dataframe(temp_raw_data)
            staged_donations_label = "Staged Donations"
            if staged_data.empty:
                staged_donations_label += " (empty)"
            with st.expander(staged_donations_label, expanded=False):
                st.dataframe(staged_data)
            staged_donors_label = "Staged Donors"
            if staged_donors.empty:
                staged_donors_label += " (empty)"
            with st.expander(staged_donors_label, expanded=False):
                st.dataframe(staged_donors)
            staged_aliases_label = "Staged Aliases"
            if staged_aliases.empty:
                staged_aliases_label += " (empty)"
            with st.expander(staged_aliases_label, expanded=False):
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


if __name__ == "__main__":
    main()
