def push_temp_table_to_live(temp_table, live_table, field_list, conn):
    c = conn.cursor()
    comma_sep_string = ", ".join(field_list)
    push_to_live = f"""
            INSERT INTO {live_table}
            SELECT {comma_sep_string} FROM {temp_table}"""
    c.execute(push_to_live)
    return

