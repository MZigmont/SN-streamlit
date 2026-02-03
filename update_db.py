import pandas as pd

def push_temp_table_to_live(temp_table, live_table, field_list, conn):
    c = conn.cursor()
    comma_sep_string = ", ".join(field_list)
    push_to_live = f"""
            INSERT INTO {live_table}
            SELECT {comma_sep_string} FROM {temp_table}"""
    c.execute(push_to_live)
    return

def create_staging_tables(cursor):
    temp_table_create = """
    CREATE TEMP TABLE temp_donations AS
    SELECT *, CAST(NULL as TEXT) AS query_type FROM donations WHERE 1=0;"""
    cursor.execute(temp_table_create)

    temp_table_create = """
    CREATE TEMP TABLE temp_donors AS
    SELECT *,
        CAST(NULL as TEXT) AS matched_phone, 
        CAST(NULL as TEXT) AS matched_email, 
        CAST(NULL as INTEGER) AS prev_max_id 
    FROM donors WHERE 1=0;"""
    cursor.execute(temp_table_create)

    temp_table_create = """
    CREATE TEMP TABLE temp_aliases AS
    SELECT * FROM aliases WHERE 1=0;"""
    cursor.execute(temp_table_create)

def get_latest_transaction(conn):
    temp_get_latest = """
    SELECT MAX(d.date_time), ts.source_name FROM donations d
    INNER JOIN trans_source ts ON
        d.trans_source_id_fk = ts.source_id_pk
    GROUP BY d.trans_source_id_fk"""
    return pd.read_sql_query(temp_get_latest, conn) 