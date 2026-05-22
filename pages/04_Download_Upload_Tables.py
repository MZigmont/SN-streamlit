import pandas as pd
import streamlit as st

import app_context as ctx
import backups


def on_click():
    st.session_state["button_enabled"] = False


def main():
    st.title("Download / Upload Tables")
    ctx.render_backup_warning()

    if "button_enabled" not in st.session_state:
        st.session_state["button_enabled"] = True

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn)
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    cursor = conn.cursor()

    query = "SELECT name FROM sqlite_master WHERE type='table';"
    cursor.execute(query)
    tables = [
        row[0]
        for row in cursor.fetchall()
        if "backup_" not in row[0]
        and "raw_" not in row[0]
        and "temp_" not in row[0]
    ]

    with st.expander("Download Table", expanded=False):
        st.subheader("Select Table you want to download as .csv")
        if not tables:
            st.info("No eligible tables available for download.")
        else:
            download_placeholder = "Select a table to download"
            download_options = [download_placeholder] + tables
            selected_backup = st.selectbox("Select a Table:", options=download_options)
            if selected_backup != download_placeholder:
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
                    mime="text/csv",
                )

                st.dataframe(output_df)

    with st.expander("Upload Table", expanded=False):
        st.write("Upload the .csv file to replace a Table")
        st.info("A backup will be created automatically before the table is replaced.")
        st.subheader("Upload .csv")
        uploaded_file = st.file_uploader("Choose a .csv file", type=["csv"])

        if uploaded_file is not None:
            df = pd.read_csv(
                uploaded_file,
                dtype={"zip": str},
                keep_default_na=True,
                na_values=[""],
            )
            st.subheader("This is what you uploaded")
            st.dataframe(df)
            st.subheader("Please select the table to OVERWRITE with your uploaded data")
            if not tables:
                st.info("No eligible tables available to overwrite.")
            else:
                overwrite_placeholder = "Select a table to overwrite"
                overwrite_options = [overwrite_placeholder] + tables
                overwriting_table = st.selectbox(
                    label="Select the table to OVERWRITE:",
                    options=overwrite_options,
                )

                if overwriting_table != overwrite_placeholder and st.button(
                    f"Confirm that you want to overwrite selected table {overwriting_table}",
                    on_click=on_click,
                    disabled=not st.session_state["button_enabled"],
                ):
                    backups.create_backup(overwriting_table, conn)
                    st.success("Backup created.")

                    existing_table_df = pd.read_sql_query(
                        f"PRAGMA table_info({overwriting_table});",
                        conn,
                    )
                    st.dataframe(existing_table_df)
                    st.write(df.dtypes)

                    if len(existing_table_df["name"]) != len(df.columns):
                        st.error(
                            f"Uploaded table has {len(df.columns)} columns.\n"
                            f"Existing table {overwriting_table} has "
                            f"{len(existing_table_df['name'])} fields.\n"
                            f"{overwriting_table} was NOT overwritten."
                        )
                    elif (existing_table_df["name"] == df.columns).all():
                        st.write("Fieldnames match!")
                        df.to_sql(
                            "temp_table_csv_direct_edit",
                            conn,
                            if_exists="replace",
                            index=False,
                        )
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
                        cursor.executescript(table_overwrite_sql_code)
                    else:
                        st.error(
                            "Fieldnames of uploaded table do not match selected table.\n"
                            f"{overwriting_table} was NOT overwritten."
                        )


if __name__ == "__main__":
    main()
