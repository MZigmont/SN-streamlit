import validation
import pandas as pd

def get_duplicated_source_trans_IDs(conn):
    output_df = pd.read_sql_query(validation.no_dupes_donations, conn)
    return output_df

def show_duplicate_source_trans_IDs(conn, source_trans_ID):
    find_IDs = """
        SELECT *
        FROM donations
        WHERE
            source_trans_id = ?
        """
    output_df = pd.read_sql_query(find_IDs, conn, params=(source_trans_ID,))
    return output_df

def keep_donation(conn, source_trans_id, my_trans_id_pk):
    sql_code = """
        DELETE
        FROM donations
        WHERE
            source_trans_id = ? AND
            my_trans_id_pk <> ? 
        """
    
    cursor = conn.cursor()
    cursor.execute(sql_code, (source_trans_id, my_trans_id_pk))
    return