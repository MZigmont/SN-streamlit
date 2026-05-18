# TO DO: 4/7/2025 - do a few validation queries:
#   DONE:   check for duplicate IDs in raw data
#   DONE:   check that every valid transaction in raw data was accounted for
#   DONE:   check that donations has no duplicate IDs
#   DONE:   check that no two donors in temp_donors has exact first and last name
#   DONE:   check that no duplicate donors for whatever definition in donors
#   DONE:   check that there are no duplicate aliases, e.g. same value in each field


import pandas as pd

# validating tables regardless of bluepay/paypal source
def validate_agnostic(conn, raw_data_tablename:str, trans_id_fieldname:str):
    
    # making sure no duplicates in temp_donations table, bluepay/paypal agnostic
    no_dupes_trans_id = """
        SELECT source_trans_id, COUNT(*) AS count
        FROM temp_donations
        GROUP BY source_trans_id
        HAVING COUNT(*) > 1"""
    cursor=conn.cursor()
    cursor.execute(no_dupes_trans_id)
    rows = cursor.fetchall()  # Fetch all results
    no_dupes_rowcount = len(rows)  # Count the number of rows

    # looking for dupes in the raw data passed into the validation function, bluepay/paypal agnostic
    no_dupes_raw_data = f"""
        SELECT {trans_id_fieldname}, COUNT(*) AS count
        FROM {raw_data_tablename}
        GROUP BY {trans_id_fieldname}
        HAVING COUNT(*) > 1"""
    cursor.execute(no_dupes_raw_data)
    rows = cursor.fetchall()  # Fetch all results
    no_dupes_rowcount_raw = len(rows)  # Count the number of rows

    # checking for dupes in official donations table, bluepay/paypal agnostic
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
    no_dupes_donations_df = pd.read_sql_query(no_dupes_donations, conn)

    # checking for dupes in temp donors table, bluepay/paypal agnostic
    no_dupes_temp_donors = """
        SELECT donor_last_name, donor_first_name, COUNT(*)
        FROM temp_donors
        GROUP BY donor_last_name, donor_first_name
        HAVING COUNT(*) > 1"""
    no_dupes_temp_donors_df = pd.read_sql_query(no_dupes_temp_donors, conn)

    # checking for dupes in official donors table, bluepay/paypal agnostic
    no_dupes_donors = """
        SELECT donor_reporting_name, donor_class_year, COUNT(*)
        FROM donors
        GROUP BY donor_reporting_name, donor_class_year
        HAVING COUNT(*) > 1"""
    no_dupes_donors_df = pd.read_sql_query(no_dupes_donors, conn)

    # checking for dupes in temp_aliases, bluepay/paypal agnostic
    no_dupes_temp_aliases = """
        SELECT GROUP_CONCAT(alias_id_pk) AS duplicate_ids, alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state, COUNT(*)
        FROM temp_aliases
        GROUP BY alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state
        HAVING COUNT(*) > 1"""
    no_dupes_temp_aliases_df = pd.read_sql_query(no_dupes_temp_aliases, conn)

    # this looks for rows in alias table where every non-primary key field is the same, bluepay/paypal agnostic
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
            #"unaccounted_trans_df":unaccounted_trans_df ,
            "no_dupes_donations_df":no_dupes_donations_df ,
            "no_dupes_temp_donors_df":no_dupes_temp_donors_df ,
            "no_dupes_donors_df":no_dupes_donors_df ,
            "no_dupes_temp_aliases_df":no_dupes_temp_aliases_df ,
            "no_dupes_aliases_df":no_dupes_aliases_df}
 
def validate_bluepay(conn, raw_data_tablename:str, trans_id_fieldname:str):
    # this query checks for transactions in the raw data that should have made it into the temp_donations table
    # but did not.  query returns rows in raw data that are unaccounted for, bluepay specific code

    validation_dict = validate_agnostic(conn, raw_data_tablename, trans_id_fieldname)

    all_unaccounted_trans = f"""
        SELECT rbd.*
        FROM {raw_data_tablename} as rbd
        LEFT JOIN temp_donations td
            on (rbd.id = td.source_trans_id
            and td.trans_source_id_fk = 1) 
            or ('B' || rbd.id = td.source_trans_id 
            and td.trans_source_id_fk = 4)
        LEFT JOIN donations d
            on (rbd.id = d.source_trans_id
            and d.trans_source_id_fk = 1) 
            or ('B' || rbd.id = d.source_trans_id 
            and d.trans_source_id_fk = 4)       
        where NOT (rbd.trans_type in ('AUTH') or
            rbd.amount = 0 or
            rbd.status in ('0', 'E')) and
            td.source_trans_id is NULL and
            d.source_trans_id is NULL"""
    unaccounted_trans_df = pd.read_sql_query(all_unaccounted_trans, conn)
    validation_dict["unaccounted_trans_df"]=unaccounted_trans_df
    return validation_dict

def validate_cardpointe(conn, raw_data_tablename:str, trans_id_fieldname:str):
    # this query checks for transactions in the raw data that should have made it into the temp_donations table
    # but did not.  query returns rows in raw data that are unaccounted for, cardpointe specific code

    validation_dict = validate_agnostic(conn, raw_data_tablename, trans_id_fieldname)

    all_unaccounted_trans = f"""
        SELECT rcd.*
        FROM {raw_data_tablename} as rcd
        LEFT JOIN temp_donations td
            ON
            (rcd.{trans_id_fieldname} = td.source_trans_id
            and td.trans_source_id_fk = 4) 
            or (rcd.{trans_id_fieldname} = 'B' || td.source_trans_id 
            and td.trans_source_id_fk = 1)
        LEFT JOIN donations d
            ON
            (rcd.{trans_id_fieldname} = d.source_trans_id
            and d.trans_source_id_fk = 4) 
            or (rcd.{trans_id_fieldname} = 'B' || d.source_trans_id 
            and d.trans_source_id_fk = 1)
        where td.source_trans_id is NULL and
            d.source_trans_id is NULL and
            NOT (rcd.amount = 0 or
            rcd.status in ('DECLINED', 'FAILED', 'VERIFIED') or
            rcd.method = 'VERIFY')
            """
    # BELOW DEFINES WHAT WE THINK IS INVALID AS OF 3/2/26
    # amount = 0 is invalid
    # status = 'DECLINED' or 'FAILED' is invalid
    # status = 'VERIFIED' is invalid
    # method = 'VERIFY' is invalid

    unaccounted_trans_df = pd.read_sql_query(all_unaccounted_trans, conn)
    validation_dict["unaccounted_trans_df"]=unaccounted_trans_df
    return validation_dict

def validate_paypal(conn, raw_data_tablename:str, trans_id_fieldname:str):
    # this query checks for transactions in the raw data that should have made it into the temp_donations table
    # but did not.  query returns rows in raw data that are unaccounted for, paypal specific code

    validation_dict = validate_agnostic(conn, raw_data_tablename, trans_id_fieldname)

    all_unaccounted_trans = f"""
        SELECT rpd.*
        FROM {raw_data_tablename} as rpd
        LEFT JOIN temp_donations td
            ON
            td.source_trans_id = rpd.transaction_id
            and td.trans_source_id_fk = 2
        LEFT JOIN donations d
            ON
            rpd.transaction_id = d.source_trans_id
            and d.trans_source_id_fk = 2
        where NOT (rpd.type in ('General Currency Conversion', 
                            'User Initiated Currency Conversion', 
                            'User Initiated Withdrawal') OR rpd.net = 0) AND
            td.source_trans_id is NULL AND
            d.source_trans_id is NULL"""
    unaccounted_trans_df = pd.read_sql_query(all_unaccounted_trans, conn)
    validation_dict["unaccounted_trans_df"]=unaccounted_trans_df
    return validation_dict

