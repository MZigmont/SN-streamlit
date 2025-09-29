# TO DO: 4/7/2025 - do a few validation queries:
#   DONE:   check for duplicate IDs in raw data
#   DONE:   check that every valid transaction in raw data was accounted for
#   DONE:   check that donations has no duplicate IDs
#   DONE:   check that no two donors in temp_donors has exact first and last name
#   DONE:   check that no duplicate donors for whatever definition in donors
#   DONE:   check that there are no duplicate aliases, e.g. same value in each field


import pandas as pd

no_dupes_donations = """
        SELECT source_trans_id, source_name, COUNT(*)
        FROM donations
        LEFT JOIN trans_source
        ON
            donations.trans_source_id_fk = trans_source.source_id_pk
        WHERE
            trans_source.source_id_pk <> 3
        GROUP BY source_trans_id, trans_source_id_fk
        HAVING COUNT(*) > 1"""

def validate(conn, raw_data_tablename:str, trans_id_fieldname:str):
    no_dupes_trans_id = """
        SELECT source_trans_id, COUNT(*) AS count
        FROM temp_donations
        GROUP BY source_trans_id
        HAVING COUNT(*) > 1"""
    cursor=conn.cursor()
    cursor.execute(no_dupes_trans_id)
    rows = cursor.fetchall()  # Fetch all results
    no_dupes_rowcount = len(rows)  # Count the number of rows

    no_dupes_raw_data = f"""
        SELECT {trans_id_fieldname}, COUNT(*) AS count
        FROM {raw_data_tablename}
        GROUP BY {trans_id_fieldname}
        HAVING COUNT(*) > 1"""
    cursor.execute(no_dupes_raw_data)
    rows = cursor.fetchall()  # Fetch all results
    no_dupes_rowcount_raw = len(rows)  # Count the number of rows

    # TO DO: 9/8/2025 - FIX THE BELOW and continue ingesting real data from Bluepay
    # this query checks for transactions in the raw data that should have made it into the temp_donations table
    # but did not.  query returns rows in raw data that are unaccounted for
    all_unaccounted_trans = f"""
        SELECT rbd.*
        FROM {raw_data_tablename} as rbd
        LEFT JOIN temp_donations td
            ON
            td.source_trans_id = rbd.id
        LEFT JOIN donations d
            ON
            rbd.id = d.source_trans_id
        where rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
            rbd.amount > 0 and
            rbd.status = '1' and
            td.source_trans_id is NULL and
            d.source_trans_id is NULL"""
    unaccounted_trans_df = pd.read_sql_query(all_unaccounted_trans, conn)

    no_dupes_donations_df = pd.read_sql_query(no_dupes_donations, conn)

    no_dupes_temp_donors = """
        SELECT donor_last_name, donor_first_name, COUNT(*)
        FROM temp_donors
        GROUP BY donor_last_name, donor_first_name
        HAVING COUNT(*) > 1"""
    no_dupes_temp_donors_df = pd.read_sql_query(no_dupes_temp_donors, conn)

    no_dupes_donors = """
        SELECT donor_reporting_name, COUNT(*)
        FROM donors
        GROUP BY donor_reporting_name
        HAVING COUNT(*) > 1"""
    no_dupes_donors_df = pd.read_sql_query(no_dupes_donors, conn)

    no_dupes_temp_aliases = """
        SELECT alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state, COUNT(*)
        FROM temp_aliases
        GROUP BY alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state
        HAVING COUNT(*) > 1"""
    no_dupes_temp_aliases_df = pd.read_sql_query(no_dupes_temp_aliases, conn)

# this looks for rows in alias table where every non-primary key field is the same
    no_dupes_aliases = """
        SELECT GROUP_CONCAT(alias_id_pk) AS duplicate_ids, alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state, COUNT(*)
        FROM aliases
        GROUP BY alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state
        HAVING COUNT(*) > 1"""
    no_dupes_aliases_df = pd.read_sql_query(no_dupes_aliases, conn)

    return {"no_dupes_rowcount":no_dupes_rowcount , 
            "no_dupes_rowcount_raw":no_dupes_rowcount_raw , 
            "unaccounted_trans_df":unaccounted_trans_df ,
            "no_dupes_donations_df":no_dupes_donations_df ,
            "no_dupes_temp_donors_df":no_dupes_temp_donors_df ,
            "no_dupes_donors_df":no_dupes_donors_df ,
            "no_dupes_temp_aliases_df":no_dupes_temp_aliases_df ,
            "no_dupes_aliases_df":no_dupes_aliases_df}
 
