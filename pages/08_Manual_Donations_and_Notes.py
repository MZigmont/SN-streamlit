from datetime import datetime

import pandas as pd
import streamlit as st

import app_context as ctx
import constants


def main():
    st.title("Manual Donations and Notes")
    ctx.render_backup_warning()

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn)
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    st.subheader("Add Note to Donation")
    trans_id_input = st.text_input("Transaction ID")
    if st.button("Search transaction"):
        if not trans_id_input.strip():
            st.warning("Enter a transaction ID to search.")
        else:
            donation_row = pd.read_sql_query(
                f"SELECT * FROM {constants.DONATIONS_TABLE} WHERE my_trans_id_pk = ?",
                conn,
                params=(trans_id_input.strip(),),
            )
            if donation_row.empty:
                st.info("No donation found for that transaction ID.")
            else:
                st.dataframe(donation_row)
                existing_notes = pd.read_sql_query(
                    "SELECT * FROM notes WHERE my_trans_id_fk = ?",
                    conn,
                    params=(trans_id_input.strip(),),
                )
                st.subheader("Existing Notes")
                if existing_notes.empty:
                    st.info("No notes found for this transaction.")
                else:
                    st.dataframe(existing_notes)
                note_text = st.text_input("Note")
                if st.button("Add note"):
                    if not note_text.strip():
                        st.warning("Enter a note before saving.")
                    else:
                        conn.execute(
                            "INSERT INTO notes (my_trans_id_fk, note) VALUES (?, ?)",
                            (int(trans_id_input.strip()), note_text.strip()),
                        )
                        conn.commit()
                        st.success("Note added.")

    st.divider()
    st.subheader("Manual Donations")

    donor_id_input = st.text_input("Donor ID", key="manual_donor_id")
    if "show_donors" not in st.session_state:
        st.session_state["show_donors"] = False

    if st.button("Show all donors"):
        st.session_state["show_donors"] = not st.session_state["show_donors"]

    if st.session_state["show_donors"]:
        donors_df = pd.read_sql_query(
            f"SELECT * FROM {constants.DONORS_TABLE} ORDER BY donor_reporting_name, donor_class_year",
            conn,
        )
        st.dataframe(donors_df)

    confirmed_donor = False
    if st.button("Confirm donor"):
        if not donor_id_input.strip():
            st.warning("Enter a donor ID to confirm.")
        else:
            donor_df = pd.read_sql_query(
                f"SELECT * FROM {constants.DONORS_TABLE} WHERE donor_id_pk = ?",
                conn,
                params=(donor_id_input.strip(),),
            )
            if donor_df.empty:
                st.error("Donor ID not found.")
            else:
                confirmed_donor = True
                st.session_state["confirmed_donor_id"] = int(donor_id_input.strip())
                st.dataframe(donor_df)

    if "confirmed_donor_id" in st.session_state:
        confirmed_donor = True

    if confirmed_donor:
        donor_id = st.session_state["confirmed_donor_id"]
        aliases_df = pd.read_sql_query(
            f"SELECT * FROM {constants.ALIASES_TABLE} WHERE donor_id_fk = ?",
            conn,
            params=(donor_id,),
        )
        if aliases_df.empty:
            st.info("No aliases found for this donor.")
            return

        alias_labels = [str(row["alias_id_pk"]) for _, row in aliases_df.iterrows()]
        selected_alias = st.radio("Select alias for donation", alias_labels, key="alias_pick")
        st.dataframe(aliases_df)

        table_info = pd.read_sql_query(
            f"PRAGMA table_info({constants.DONATIONS_TABLE});",
            conn,
        )
        manual_fields = table_info[
            ~table_info["name"].isin(["my_trans_id_pk", "alias_id_fk"])
        ]

        if "manual_preview" not in st.session_state:
            st.session_state["manual_preview"] = None

        with st.form("manual_donation_form"):
            form_values = {}
            for _, row in manual_fields.iterrows():
                col_name = row["name"]
                col_type = (row["type"] or "").lower()
                is_required = row["notnull"] == 1
                label_suffix = " (required)" if is_required else " (optional)"

                if col_name == "trans_source_id_fk":
                    source_rows = pd.read_sql_query(
                        f"SELECT source_id_pk, source_name FROM {constants.TRANS_SOURCE_TABLE}",
                        conn,
                    )
                    if source_rows.empty:
                        st.warning("No transaction sources found.")
                        form_values[col_name] = None
                    else:
                        options = list(source_rows["source_id_pk"])
                        form_values[col_name] = st.selectbox(
                            f"{col_name}{label_suffix}",
                            options=options,
                            format_func=lambda v: source_rows.set_index("source_id_pk")
                            .loc[v, "source_name"],
                            key=f"manual_{col_name}",
                        )
                elif col_name == "date_time":
                    form_values[col_name] = st.datetime_input(
                        f"{col_name}{label_suffix}",
                        value=datetime.now(),
                        key=f"manual_{col_name}",
                    )
                elif "int" in col_type:
                    form_values[col_name] = st.number_input(
                        f"{col_name}{label_suffix}",
                        value=None,
                        step=1,
                        format="%d",
                        key=f"manual_{col_name}",
                    )
                elif "real" in col_type or "numeric" in col_type or "decimal" in col_type:
                    form_values[col_name] = st.number_input(
                        f"{col_name}{label_suffix}",
                        value=None,
                        key=f"manual_{col_name}",
                    )
                else:
                    form_values[col_name] = st.text_input(
                        f"{col_name}{label_suffix}",
                        key=f"manual_{col_name}",
                    )

            note_text = st.text_input("Note (optional)", key="manual_note")
            submit_preview = st.form_submit_button("Submit")

        if submit_preview:
            errors = []
            donation_payload = {}
            for _, row in manual_fields.iterrows():
                col_name = row["name"]
                col_type = (row["type"] or "").lower()
                is_required = row["notnull"] == 1
                raw_value = form_values[col_name]

                if isinstance(raw_value, str):
                    raw_value = raw_value.strip()

                if raw_value in (None, ""):
                    if is_required:
                        errors.append(f"{col_name} is required.")
                    donation_payload[col_name] = None
                    continue

                try:
                    if col_name == "date_time" and isinstance(raw_value, datetime):
                        donation_payload[col_name] = raw_value.isoformat(sep=" ")
                    elif "int" in col_type:
                        donation_payload[col_name] = int(raw_value)
                    elif "real" in col_type or "numeric" in col_type or "decimal" in col_type:
                        donation_payload[col_name] = float(raw_value)
                    else:
                        donation_payload[col_name] = str(raw_value)
                except (TypeError, ValueError):
                    errors.append(f"Invalid value for {col_name}.")

            if errors:
                for error in errors:
                    st.error(error)
            else:
                donation_payload["alias_id_fk"] = int(selected_alias)
                st.session_state["manual_preview"] = {
                    "donation": donation_payload,
                    "note": note_text.strip(),
                }

        if st.session_state.get("manual_preview"):
            preview = st.session_state["manual_preview"]
            st.subheader("Preview")
            st.write("Donation row")
            st.dataframe(pd.DataFrame([preview["donation"]]))
            if preview["note"]:
                st.write("Note")
                st.dataframe(
                    pd.DataFrame(
                        [{"my_trans_id_fk": "(new)", "note": preview["note"]}]
                    )
                )

            if st.button("Confirm and insert"):
                donation_columns = ["alias_id_fk"] + [row["name"] for _, row in manual_fields.iterrows()]
                donation_values = [preview["donation"][col] for col in donation_columns]
                placeholders = ",".join(["?"] * len(donation_columns))
                insert_sql = (
                    f"INSERT INTO {constants.DONATIONS_TABLE}"
                    f" ({', '.join(donation_columns)})"
                    f" VALUES ({placeholders})"
                )
                cursor.execute(insert_sql, donation_values)
                new_trans_id = cursor.lastrowid

                if preview["note"]:
                    cursor.execute(
                        "INSERT INTO notes (my_trans_id_fk, note) VALUES (?, ?)",
                        (new_trans_id, preview["note"]),
                    )

                conn.commit()
                st.success("Manual donation added.")
                st.session_state["manual_preview"] = None


if __name__ == "__main__":
    main()
