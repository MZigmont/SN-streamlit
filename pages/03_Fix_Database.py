import pandas as pd
import streamlit as st

import app_context as ctx
from authentication import require_admin
import constants
import validation


def main():
    require_admin()
    st.title("Fix Database")
    ctx.render_backup_warning()

    if "db_ops_enabled" not in st.session_state:
        st.session_state["db_ops_enabled"] = True
    if not st.session_state["db_ops_enabled"]:
        st.info("Refresh the page to continue making database changes.")
    actions_enabled = st.session_state["db_ops_enabled"]

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn, current_page="fix_database")
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    duplicate_df = validation.NO_DUPES_DONATIONS.execute(conn)
    donation_label = (
        "Duplicate source transaction IDs in donations (none found)"
        if duplicate_df.empty
        else f"Duplicate source transaction IDs in donations ({len(duplicate_df)} found)"
    )
    if actions_enabled:
        with st.expander(donation_label, expanded=False):
            if duplicate_df.empty:
                st.info("No duplicate source transaction IDs found in donations.")
            else:
                placeholder = f"Select a duplicate transaction ID ({len(duplicate_df)} found)"
                duplicate_options = [placeholder] + list(duplicate_df.index)
                selected_index = st.selectbox(
                    "Duplicate transaction",
                    options=duplicate_options,
                    format_func=lambda i: (
                        i
                        if isinstance(i, str)
                        else (
                            f"{duplicate_df.loc[i, 'source_trans_id']} "
                            f"({duplicate_df.loc[i, 'source_name']}) "
                            f"- {duplicate_df.loc[i, 'COUNT(*)']} rows"
                        )
                    ),
                    disabled=not st.session_state["db_ops_enabled"],
                )

                if selected_index != placeholder:
                    selected_trans_id = duplicate_df.loc[selected_index, "source_trans_id"]
                    selected_source_name = duplicate_df.loc[selected_index, "source_name"]

                    source_id_df = pd.read_sql_query(
                        f"SELECT source_id_pk FROM {constants.TRANS_SOURCE_TABLE} WHERE source_name = ?",
                        conn,
                        params=(selected_source_name,),
                    )
                    if source_id_df.empty:
                        st.error("Unable to resolve the transaction source for this duplicate set.")
                    else:
                        trans_source_id_fk = int(source_id_df.loc[0, "source_id_pk"])
                        results_df = pd.read_sql_query(
                            f"""
                            SELECT *
                            FROM {constants.DONATIONS_TABLE}
                            WHERE source_trans_id = ? AND trans_source_id_fk = ?
                            """,
                            conn,
                            params=(str(selected_trans_id), trans_source_id_fk),
                        )
                        if results_df.empty:
                            st.info("No matching donation rows found for this transaction ID.")
                        else:
                            st.dataframe(results_df)

                            row_labels = [str(row["my_trans_id_pk"]) for _, row in results_df.iterrows()]
                            selected_label = st.radio(
                                "Select a row TO KEEP:",
                                row_labels,
                                disabled=not st.session_state["db_ops_enabled"],
                            )
                            selected_row = results_df[results_df["my_trans_id_pk"] == int(selected_label)]

                            st.write("### Selected Row")
                            st.dataframe(selected_row)

                            if st.button(
                                "KEEP Selected Row, delete all others",
                                disabled=not st.session_state["db_ops_enabled"],
                            ):
                                conn.execute(
                                    f"""
                                    DELETE FROM {constants.DONATIONS_TABLE}
                                    WHERE source_trans_id = ?
                                      AND trans_source_id_fk = ?
                                      AND my_trans_id_pk <> ?
                                    """,
                                    (selected_trans_id, trans_source_id_fk, int(selected_label)),
                                )
                                conn.commit()
                                st.success("Row kept and others deleted!")
                                st.info("Refresh the page to continue making database changes.")
                                st.session_state["db_ops_enabled"] = False
    else:
        st.write(f"{donation_label} (refresh required)")

    donors_dup_df = validation.NO_DUPES_DONORS.execute(conn)
    donors_label = (
        "Duplicate donors (none found)"
        if donors_dup_df.empty
        else f"Duplicate donors ({len(donors_dup_df)} found)"
    )
    if actions_enabled:
        with st.expander(donors_label, expanded=False):
            if donors_dup_df.empty:
                st.info("No duplicate donors found.")
            else:
                donors_placeholder = f"Select a duplicate donor set ({len(donors_dup_df)} found)"
                donors_options = [donors_placeholder] + list(donors_dup_df.index)
                selected_donor_index = st.selectbox(
                    "Duplicate donor set",
                    options=donors_options,
                    format_func=lambda i: (
                        i
                        if isinstance(i, str)
                        else (
                            f"{donors_dup_df.loc[i, 'donor_reporting_name']} "
                            f"({donors_dup_df.loc[i, 'donor_class_year']}) "
                            f"- {donors_dup_df.loc[i, 'COUNT(*)']} rows"
                        )
                    ),
                    key="donor_set",
                    disabled=not st.session_state["db_ops_enabled"],
                )

                if selected_donor_index != donors_placeholder:
                    donor_name = donors_dup_df.loc[selected_donor_index, "donor_reporting_name"]
                    donor_year = donors_dup_df.loc[selected_donor_index, "donor_class_year"]
                    donor_rows = pd.read_sql_query(
                        f"""
                        SELECT *
                        FROM {constants.DONORS_TABLE}
                        WHERE donor_reporting_name = ? AND donor_class_year = ?
                        """,
                        conn,
                        params=(donor_name, donor_year),
                    )
                    if donor_rows.empty:
                        st.info("No donor rows found for this duplicate set.")
                    else:
                        st.dataframe(donor_rows)

                        donor_labels = [str(row["donor_id_pk"]) for _, row in donor_rows.iterrows()]
                        selected_donor_label = st.radio(
                            "Select a donor TO KEEP:",
                            donor_labels,
                            key="keep_donor",
                            disabled=not st.session_state["db_ops_enabled"],
                        )
                        kept_donor_id = int(selected_donor_label)
                        selected_donor_row = donor_rows[donor_rows["donor_id_pk"] == kept_donor_id]

                        st.write("### Selected Donor Row")
                        st.dataframe(selected_donor_row)

                        if st.button(
                            "KEEP Selected Donor, delete all others",
                            disabled=not st.session_state["db_ops_enabled"],
                        ):
                            donors_to_delete = [
                                donor_id
                                for donor_id in donor_labels
                                if int(donor_id) != kept_donor_id
                            ]
                            if donors_to_delete:
                                placeholders = ",".join(["?"] * len(donors_to_delete))
                                conn.execute(
                                    f"""
                                    UPDATE {constants.ALIASES_TABLE}
                                    SET donor_id_fk = ?
                                    WHERE donor_id_fk IN ({placeholders})
                                    """,
                                    (kept_donor_id, *[int(d) for d in donors_to_delete]),
                                )
                                conn.execute(
                                    f"DELETE FROM {constants.DONORS_TABLE} WHERE donor_id_pk IN ({placeholders})",
                                    [int(d) for d in donors_to_delete],
                                )
                                conn.commit()
                                st.success("Donor kept, aliases reassigned, and duplicates deleted!")
                                st.info("Refresh the page to continue making database changes.")
                                st.session_state["db_ops_enabled"] = False
                            else:
                                st.info("No duplicate donors to delete for this selection.")
    else:
        st.write(f"{donors_label} (refresh required)")

    aliases_dup_df = validation.NO_DUPES_ALIASES.execute(conn)
    alias_label = (
        "Duplicate aliases (none found)"
        if aliases_dup_df.empty
        else f"Duplicate aliases ({len(aliases_dup_df)} found)"
    )
    if actions_enabled:
        with st.expander(alias_label, expanded=False):
            if aliases_dup_df.empty:
                st.info("No duplicate aliases found.")
            else:
                alias_placeholder = f"Select a duplicate alias set ({len(aliases_dup_df)} found)"
                alias_options = [alias_placeholder] + list(aliases_dup_df.index)
                selected_alias_index = st.selectbox(
                    "Duplicate alias set",
                    options=alias_options,
                    format_func=lambda i: (
                        i
                        if isinstance(i, str)
                        else (
                            f"{aliases_dup_df.loc[i, 'alias_first_name']} "
                            f"{aliases_dup_df.loc[i, 'alias_last_name']} "
                            f"- {aliases_dup_df.loc[i, 'COUNT(*)']} rows"
                        )
                    ),
                    disabled=not st.session_state["db_ops_enabled"],
                )

                if selected_alias_index != alias_placeholder:
                    duplicate_ids = aliases_dup_df.loc[selected_alias_index, "duplicate_ids"]
                    duplicate_id_list = [int(value) for value in duplicate_ids.split(",") if value]
                    if not duplicate_id_list:
                        st.info("No alias IDs found for this duplicate set.")
                    else:
                        placeholders = ",".join(["?"] * len(duplicate_id_list))
                        alias_rows = pd.read_sql_query(
                            f"SELECT * FROM {constants.ALIASES_TABLE} WHERE alias_id_pk IN ({placeholders})",
                            conn,
                            params=duplicate_id_list,
                        )
                        if alias_rows.empty:
                            st.info("No alias rows found for this duplicate set.")
                        else:
                            st.dataframe(alias_rows)

                            alias_labels = [str(row["alias_id_pk"]) for _, row in alias_rows.iterrows()]
                            selected_alias_label = st.radio(
                                "Select a row TO KEEP:",
                                alias_labels,
                                key="keep_alias",
                                disabled=not st.session_state["db_ops_enabled"],
                            )
                            kept_alias_id = int(selected_alias_label)
                            selected_alias_row = alias_rows[alias_rows["alias_id_pk"] == kept_alias_id]

                            st.write("### Selected Alias Row")
                            st.dataframe(selected_alias_row)

                            if st.button(
                                "KEEP Selected Alias, delete all others",
                                disabled=not st.session_state["db_ops_enabled"],
                            ):
                                aliases_to_delete = [
                                    alias_id
                                    for alias_id in duplicate_id_list
                                    if alias_id != kept_alias_id
                                ]
                                if aliases_to_delete:
                                    placeholders = ",".join(["?"] * len(aliases_to_delete))
                                    conn.execute(
                                        f"""
                                        UPDATE {constants.DONATIONS_TABLE}
                                        SET alias_id_fk = ?
                                        WHERE alias_id_fk IN ({placeholders})
                                        """,
                                        (kept_alias_id, *aliases_to_delete),
                                    )
                                    conn.execute(
                                        f"DELETE FROM {constants.ALIASES_TABLE} WHERE alias_id_pk IN ({placeholders})",
                                        aliases_to_delete,
                                    )
                                    conn.commit()
                                    st.success("Alias kept, donations reassigned, and duplicates deleted!")
                                    st.info("Refresh the page to continue making database changes.")
                                    st.session_state["db_ops_enabled"] = False
                                else:
                                    st.info("No duplicate aliases to delete for this selection.")
    else:
        st.write(f"{alias_label} (refresh required)")

    donors_df = pd.read_sql_query(
        f"SELECT * FROM {constants.DONORS_TABLE} ORDER BY donor_reporting_name, donor_class_year",
        conn,
    )

    manual_alias_label = "Add manual alias"
    if actions_enabled:
        with st.expander(manual_alias_label, expanded=False):
            if donors_df.empty:
                st.info("No donors found.")
            else:
                donor_options = list(donors_df.index)
                selected_alias_donor_index = st.selectbox(
                    "Donor for new alias",
                    options=donor_options,
                    format_func=lambda i: (
                        f"{donors_df.loc[i, 'donor_reporting_name']} "
                        f"({donors_df.loc[i, 'donor_class_year']}) "
                        f"- ID {donors_df.loc[i, 'donor_id_pk']}"
                    ),
                    key="manual_alias_donor",
                    disabled=not st.session_state["db_ops_enabled"],
                )
                alias_donor_id = int(
                    donors_df.loc[selected_alias_donor_index, "donor_id_pk"]
                )
                selected_alias_donor = donors_df[
                    donors_df["donor_id_pk"] == alias_donor_id
                ]

                st.write("### Selected donor")
                st.dataframe(selected_alias_donor)

                existing_aliases = pd.read_sql_query(
                    f"""
                    SELECT *
                    FROM {constants.ALIASES_TABLE}
                    WHERE donor_id_fk = ?
                    ORDER BY alias_id_pk
                    """,
                    conn,
                    params=(alias_donor_id,),
                )
                st.write("### Existing aliases")
                if existing_aliases.empty:
                    st.info("No aliases found for this donor.")
                else:
                    st.dataframe(existing_aliases)

                alias_table_info = pd.read_sql_query(
                    f"PRAGMA table_info({constants.ALIASES_TABLE});",
                    conn,
                )
                manual_alias_fields = alias_table_info[
                    ~alias_table_info["name"].isin(["alias_id_pk", "donor_id_fk"])
                ]

                with st.form("manual_alias_form"):
                    alias_payload = {}
                    for _, row in manual_alias_fields.iterrows():
                        col_name = row["name"]
                        alias_payload[col_name] = st.text_input(
                            col_name,
                            key=f"manual_alias_{col_name}",
                            disabled=not st.session_state["db_ops_enabled"],
                        )
                    submitted_alias = st.form_submit_button(
                        "Add alias",
                        disabled=not st.session_state["db_ops_enabled"],
                    )

                if submitted_alias:
                    cleaned_payload = {
                        col_name: value.strip() or None
                        for col_name, value in alias_payload.items()
                    }
                    has_alias_detail = any(
                        value is not None for value in cleaned_payload.values()
                    )
                    if not has_alias_detail:
                        st.error("Enter at least one alias field before saving.")
                    else:
                        alias_columns = ["donor_id_fk"] + list(cleaned_payload.keys())
                        alias_values = [
                            alias_donor_id,
                            *[cleaned_payload[col] for col in cleaned_payload],
                        ]
                        placeholders = ",".join(["?"] * len(alias_columns))
                        conn.execute(
                            f"""
                            INSERT INTO {constants.ALIASES_TABLE}
                            ({", ".join(alias_columns)})
                            VALUES ({placeholders})
                            """,
                            alias_values,
                        )
                        conn.commit()
                        st.success("Manual alias added.")
                        st.info("Refresh the page to continue making database changes.")
                        st.session_state["db_ops_enabled"] = False
    else:
        st.write(f"{manual_alias_label} (refresh required)")

    edit_donor_label = "Edit donor datapoint"
    if actions_enabled:
        with st.expander(edit_donor_label, expanded=False):
            if donors_df.empty:
                st.info("No donors found.")
            else:
                donor_table_info = pd.read_sql_query(
                    f"PRAGMA table_info({constants.DONORS_TABLE});",
                    conn,
                )
                editable_fields = donor_table_info[
                    donor_table_info["name"] != "donor_id_pk"
                ]
                donor_options = list(donors_df.index)
                selected_edit_index = st.selectbox(
                    "Donor",
                    options=donor_options,
                    format_func=lambda i: (
                        f"{donors_df.loc[i, 'donor_reporting_name']} "
                        f"({donors_df.loc[i, 'donor_class_year']}) "
                        f"- ID {donors_df.loc[i, 'donor_id_pk']}"
                    ),
                    key="edit_donor",
                    disabled=not st.session_state["db_ops_enabled"],
                )
                selected_donor_id = int(donors_df.loc[selected_edit_index, "donor_id_pk"])
                selected_donor_row = donors_df[
                    donors_df["donor_id_pk"] == selected_donor_id
                ]

                st.write("### Current donor row")
                st.dataframe(selected_donor_row)

                field_options = list(editable_fields["name"])
                selected_field = st.selectbox(
                    "Field to edit",
                    options=field_options,
                    key="edit_donor_field",
                    disabled=not st.session_state["db_ops_enabled"],
                )
                selected_field_info = editable_fields[
                    editable_fields["name"] == selected_field
                ].iloc[0]
                field_type = (selected_field_info["type"] or "").lower()
                field_required = selected_field_info["notnull"] == 1
                current_value = selected_donor_row.iloc[0][selected_field]
                if pd.isna(current_value):
                    current_display = ""
                elif "int" in field_type:
                    current_display = str(int(current_value))
                else:
                    current_display = str(current_value)
                edit_input_key = f"edit_donor_{selected_donor_id}_{selected_field}"

                with st.form("edit_donor_datapoint_form"):
                    st.text_input(
                        "Current value",
                        value=current_display,
                        key=f"{edit_input_key}_current",
                        disabled=True,
                    )
                    new_value_input = st.text_input(
                        "New value",
                        value=current_display,
                        key=f"{edit_input_key}_new",
                        help="Leave blank to store NULL when the field allows it.",
                        disabled=not st.session_state["db_ops_enabled"],
                    )
                    submitted_edit = st.form_submit_button(
                        "Update donor datapoint",
                        disabled=not st.session_state["db_ops_enabled"],
                    )

                if submitted_edit:
                    new_value = new_value_input.strip()
                    if new_value == "":
                        if field_required:
                            st.error(f"{selected_field} is required.")
                        else:
                            conn.execute(
                                f"""
                                UPDATE {constants.DONORS_TABLE}
                                SET {selected_field} = NULL
                                WHERE donor_id_pk = ?
                                """,
                                (selected_donor_id,),
                            )
                            conn.commit()
                            st.success("Donor datapoint updated.")
                            st.info("Refresh the page to continue making database changes.")
                            st.session_state["db_ops_enabled"] = False
                    else:
                        try:
                            if "int" in field_type:
                                parsed_value = int(new_value)
                            else:
                                parsed_value = new_value
                        except ValueError:
                            st.error(f"Invalid value for {selected_field}. Enter a whole number.")
                        else:
                            conn.execute(
                                f"""
                                UPDATE {constants.DONORS_TABLE}
                                SET {selected_field} = ?
                                WHERE donor_id_pk = ?
                                """,
                                (parsed_value, selected_donor_id),
                            )
                            conn.commit()
                            st.success("Donor datapoint updated.")
                            st.info("Refresh the page to continue making database changes.")
                            st.session_state["db_ops_enabled"] = False
    else:
        st.write(f"{edit_donor_label} (refresh required)")

    merge_label = "Merge donors"
    if actions_enabled:
        with st.expander(merge_label, expanded=False):
            if donors_df.empty:
                st.info("No donors found.")
            else:
                donor_options = list(donors_df.index)
                main_index = st.selectbox(
                    "Main donor",
                    options=donor_options,
                    format_func=lambda i: (
                        f"{donors_df.loc[i, 'donor_reporting_name']} "
                        f"({donors_df.loc[i, 'donor_class_year']}) "
                        f"- ID {donors_df.loc[i, 'donor_id_pk']}"
                    ),
                    key="main_donor",
                    disabled=not st.session_state["db_ops_enabled"],
                )
                main_donor_id = int(donors_df.loc[main_index, "donor_id_pk"])
                main_aliases = pd.read_sql_query(
                    f"SELECT * FROM {constants.ALIASES_TABLE} WHERE donor_id_fk = ?",
                    conn,
                    params=(main_donor_id,),
                )
                st.write("### Main donor aliases")
                st.dataframe(main_aliases)

                main_donations = pd.read_sql_query(
                    f"""
                    SELECT d.*
                    FROM {constants.DONATIONS_TABLE} d
                    LEFT JOIN {constants.ALIASES_TABLE} a
                        ON d.alias_id_fk = a.alias_id_pk
                    WHERE a.donor_id_fk = ?
                    """,
                    conn,
                    params=(main_donor_id,),
                )
                st.write("### Main donor donations")
                st.dataframe(main_donations)

                merge_candidates = [i for i in donor_options if i != main_index]
                if not merge_candidates:
                    st.info("No other donors available to merge.")
                else:
                    merge_index = st.selectbox(
                        "Merging donor",
                        options=merge_candidates,
                        format_func=lambda i: (
                            f"{donors_df.loc[i, 'donor_reporting_name']} "
                            f"({donors_df.loc[i, 'donor_class_year']}) "
                            f"- ID {donors_df.loc[i, 'donor_id_pk']}"
                        ),
                        key="merging_donor",
                        disabled=not st.session_state["db_ops_enabled"],
                    )
                    merge_donor_id = int(donors_df.loc[merge_index, "donor_id_pk"])

                    merge_aliases = pd.read_sql_query(
                        f"SELECT * FROM {constants.ALIASES_TABLE} WHERE donor_id_fk = ?",
                        conn,
                        params=(merge_donor_id,),
                    )
                    st.write("### Merging donor aliases")
                    st.dataframe(merge_aliases)

                    merge_donations = pd.read_sql_query(
                        f"""
                        SELECT d.*
                        FROM {constants.DONATIONS_TABLE} d
                        LEFT JOIN {constants.ALIASES_TABLE} a
                            ON d.alias_id_fk = a.alias_id_pk
                        WHERE a.donor_id_fk = ?
                        """,
                        conn,
                        params=(merge_donor_id,),
                    )
                    st.write("### Merging donor donations")
                    st.dataframe(merge_donations)

                    if st.button(
                        "Merge donor into main",
                        disabled=not st.session_state["db_ops_enabled"],
                    ):
                        conn.execute(
                            f"""
                            UPDATE {constants.ALIASES_TABLE}
                            SET donor_id_fk = ?
                            WHERE donor_id_fk = ?
                            """,
                            (main_donor_id, merge_donor_id),
                        )
                        conn.execute(
                            f"DELETE FROM {constants.DONORS_TABLE} WHERE donor_id_pk = ?",
                            (merge_donor_id,),
                        )
                        conn.commit()
                        st.success("Donor merged and aliases reassigned.")
                        st.info("Refresh the page to continue making database changes.")
                        st.session_state["db_ops_enabled"] = False
    else:
        st.write(f"{merge_label} (refresh required)")


if __name__ == "__main__":
    main()
