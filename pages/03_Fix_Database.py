import streamlit as st

import app_context as ctx
import error_correction as ec


def main():
    st.title("Fix Database")
    ctx.render_backup_warning()

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn)
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    st.subheader("Write the code and do the magic")

    df = ec.get_duplicated_source_trans_IDs(conn)

    if len(df) == 0:
        st.write("There are NO duplicate source trans IDs")
        return

    st.write("## Data Table")
    st.dataframe(df)

    selected_index = st.selectbox(
        "Select a row:",
        options=df.index,
        format_func=lambda i: (
            f"trans_id {df.loc[i, 'source_trans_id']}, "
            f"{df.loc[i, 'source_name']}, {df.loc[i, 'COUNT(*)']}"
        ),
    )
    selected_trans_id = df.loc[selected_index, "source_trans_id"]
    results_df = ec.show_duplicate_source_trans_IDs(conn, selected_trans_id)
    st.dataframe(results_df)

    row_labels = [f"{row['my_trans_id_pk']}" for _, row in results_df.iterrows()]

    selected_label = st.radio("Select a row TO KEEP:", row_labels)

    selected_index_2 = row_labels.index(selected_label)
    selected_row = results_df.iloc[selected_index_2]

    st.write("### Selected Row")
    st.write(selected_row.to_frame().T)

    if st.button("KEEP Selected Row, delete all others"):
        ec.keep_donation(conn, selected_trans_id, selected_label)
        conn.commit()
        st.success("Row kept and others deleted!")


if __name__ == "__main__":
    main()
