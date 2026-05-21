import csv #csv is a package that comes from python
import sqlite3 #sqlite3 is a pkg that comes from python
from datetime import datetime #from a megapackage, import datetime subpackage
import time #time is a package
import sys #system commands
import pandas as pd
import validation as val
import update_db as udb
from constants import (
    ALIASES_TABLE,
    CARDPOINTE_RAW_TABLE_NAME,
    DONATIONS_TABLE,
    DONORS_TABLE,
    TEMP_ALIASES_TABLE,
    TEMP_DONATIONS_TABLE,
    TEMP_DONORS_TABLE,
)

def ingest_data(df: pd.DataFrame, conn):
    df.columns = (
        df.columns
            .str.lower()
            .str.replace(" ","_")
            .str.replace("#","num")
    )
    
    df['date'] = pd.to_datetime(df['date'], format='mixed')

    df["amount"] = df["amount"].str.replace("$", "", regex=False)\
                         .str.replace(",", "", regex=False)\
                         .astype(float)
    parts = df['name'].str.split()

    df['my_first_name']  = parts.str[0]
    df['my_last_name']   = parts.str[-1]
    df['my_middle_name'] = parts.str[1:-1].str.join(' ')

    df.to_sql(CARDPOINTE_RAW_TABLE_NAME, conn, if_exists='replace', index=False)
    cursor = conn.cursor()
    udb.create_staging_tables(cursor)

    # alias match is on phone or email or (first_name and last_name)
    # "B" & Bluepay ID = cardpointe "Transaction #""
    # TO DO:  02/02/2026 - replace former bluepay fieldnames with cardpointe fieldnames
    # TO DO:  when ingesting cardpointe, check for duplicates in bluepay ALSO VICE VERSA

    def alias_match(match_type: str):
        return f"""
        insert into {TEMP_DONATIONS_TABLE}
        select null ,
            rcd.transaction_num ,
            max(rcd.date) ,
            max(a.alias_id_pk) ,
            4 ,
            'USD' ,
            max(rcd.amount),
            'USD' ,
            null ,
            null ,
            max(rcd.amount),
            null ,
            max(rcd.amount) ,
            '{match_type}'
        from {CARDPOINTE_RAW_TABLE_NAME} rcd
        LEFT join {DONATIONS_TABLE} d
            ON (rcd.transaction_num = d.source_trans_id
            AND d.trans_source_id_fk = 4) 
            OR (rcd.transaction_num = 'B' || d.source_trans_id 
            AND d.trans_source_id_fk = 1)
        LEFT JOIN {ALIASES_TABLE} a 
            ON rcd.phone_number COLLATE NOCASE = a.alias_phone COLLATE NOCASE
            OR rcd.email COLLATE NOCASE = a.alias_email COLLATE NOCASE
            OR (rcd.my_first_name COLLATE NOCASE = a.alias_first_name COLLATE NOCASE and
            rcd.my_last_name COLLATE NOCASE = a.alias_last_name COLLATE NOCASE)
        LEFT JOIN {TEMP_DONATIONS_TABLE} td
            ON (rcd.transaction_num = td.source_trans_id
            AND td.trans_source_id_fk = 4) 
            OR (rcd.transaction_num = 'B' || td.source_trans_id 
            AND td.trans_source_id_fk = 1)
        where rcd.method in ('SALE') and
             rcd.amount > 0 and
             rcd.status = 'PROCESSED' and
             d.source_trans_id is NULL and
             a.alias_id_pk is not NULL and
             td.source_trans_id is NULL
        GROUP BY rcd.transaction_num
        """
    
    new_donors = f"""
    insert into {TEMP_DONORS_TABLE}
    select NULL ,
        max(rcd.my_first_name) || ' ' || max(rcd.my_last_name) ,
        max(rcd.my_last_name) ,
        max(rcd.my_first_name) ,
        '' ,
        NULL ,
        rcd.phone_number , 
        rcd.email,
        NULL 
    from {CARDPOINTE_RAW_TABLE_NAME} rcd
    LEFT join {DONATIONS_TABLE} d
            ON (rcd.transaction_num = d.source_trans_id
            AND d.trans_source_id_fk = 4) 
            OR (rcd.transaction_num = 'B' || d.source_trans_id 
            AND d.trans_source_id_fk = 1)
    LEFT join {TEMP_DONATIONS_TABLE} td
        ON (rcd.transaction_num = td.source_trans_id
        AND d.trans_source_id_fk = 4) 
        OR (rcd.transaction_num = 'B' || td.source_trans_id 
        AND d.trans_source_id_fk = 1)
    where d.source_trans_id is NULL and 
        td.source_trans_id is NULL and
        rcd.method in ('SALE') and
        rcd.amount > 0 and
        rcd.status = 'PROCESSED'
    group by
        rcd.email ,
        rcd.phone_number """
    
    new_prev_max_id_query = f"""
    update {TEMP_DONORS_TABLE} set prev_max_id = (
        select max(donor_id_pk) from {DONORS_TABLE})
    """

    #  NOTE: in between these queries, temp_donors gets pushed to the live donors table
    new_aliases_for_new_donors = f"""
        insert into {TEMP_ALIASES_TABLE}
        select distinct null ,
            d.donor_id_pk ,
            rcd.my_first_name ,
            rcd.email ,
            rcd.phone_number ,
            rcd.address,
            '', --this is addr2 in alias table
            rcd.city ,
            rcd.zip ,
            'USA' , --this is country in alias table
            rcd.my_middle_name ,
            rcd.my_last_name ,
            rcd.state
        from {TEMP_DONORS_TABLE} td
        left join {CARDPOINTE_RAW_TABLE_NAME} rcd
        on
            rcd.phone_number = td.matched_phone and
            rcd.email = td.matched_email 
        left join {DONORS_TABLE} d
        on
            td.donor_first_name = d.donor_first_name and
            td.donor_last_name = d.donor_last_name and
            td.prev_max_id < d.donor_id_pk
        where
            rcd.method in ('SALE') and
            rcd.amount > 0 and
            rcd.status = 'PROCESSED'
        """

# when instr(rcd.name1 ,' ') = 0
#         then lower(rcd.name1)
#         else
#             lower(substr(rcd.name1 ,1,instr(rcd.name1 ,' ')-1))
#         end ,
#     lower(rcd.name2)
    
    cursor.execute(alias_match('alias match'))
    cursor.execute(new_donors)
    cursor.execute(new_prev_max_id_query)
    udb.push_temp_table_to_live(TEMP_DONORS_TABLE, DONORS_TABLE, [
            "NULL",
            "donor_reporting_name",
            "donor_last_name",
            "donor_first_name",
            "donor_middle_name",
            "donor_class_year"], conn)
    cursor.execute(new_aliases_for_new_donors)
    udb.push_temp_table_to_live(TEMP_ALIASES_TABLE, ALIASES_TABLE, ["*"], conn)
    cursor.execute(alias_match('new donor'))
    udb.push_temp_table_to_live(TEMP_DONATIONS_TABLE, DONATIONS_TABLE, 
                                ["my_trans_id_pk", "source_trans_id", "date_time", "alias_id_fk", "trans_source_id_fk", "donation_currrency",
                                 "donation_gross_amt", "fee_currency", "fee_amt", "conversion_rate", "donation_gross_USD", "fee_USD", "donation_net_USD"],
                                 conn)

    data_donors = pd.read_sql_query(
        f"SELECT * FROM {TEMP_DONORS_TABLE}",
        conn,
    )
    data_aliases = pd.read_sql_query(
        f"SELECT * FROM {TEMP_ALIASES_TABLE}",
        conn,
    )
    data_donations = pd.read_sql_query(
        f"SELECT * FROM {TEMP_DONATIONS_TABLE}",
        conn,
    )

    validation_dict = val.validate_cardpointe(conn)

# TODO: 2/23/2026 - test this and finish
    return {'temp_donations':data_donations, 
            'temp_donors':data_donors, 
            'temp_aliases':data_aliases,
            'validation_dict':validation_dict,
            'temp_raw_data':df}
