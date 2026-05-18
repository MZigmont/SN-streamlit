#@title #4. BLUEPAY ingestion code below
'''Created on Jun 14, 2020

@author: mike zigmont
'''
# this is a comment
import csv #csv is a package that comes from python
import sqlite3 #sqlite3 is a pkg that comes from python
from datetime import datetime #from a megapackage, import datetime subpackage
import time #time is a package
import sys #system commands
import pandas as pd
import validation as val
import update_db as udb

raw_table_name = "raw_bluepay_data" 
def ingest_data(df: pd.DataFrame, conn):
    df.to_sql(raw_table_name, conn, if_exists='replace', index=False)
    cursor = conn.cursor()
    udb.create_staging_tables(cursor)

    df['issue_date'] = pd.to_datetime(df['issue_date'], format='mixed')

    # alias match is on phone or email or (first_name and last_name)
    def alias_match(match_type: str):
        return f"""
        insert into temp_donations
        select null ,
            rbd.id ,
            max(rbd.issue_date) , -- aggregation req b/c GROUP BY below
            max(a.alias_id_pk) , -- aggregation req b/c GROUP BY below
            1 ,
            'USD' ,
            max(case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end), -- GROSS when 'VOID' OR 'REFUND' (use negative of amount)
            'USD' ,
            null ,
            null ,
            max(case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end),  -- GROSS USD when not 'SALE' use neg amt
            null ,
            max(case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end) , -- GROSS NET USD when not 'SALE' use neg amt
            '{match_type}'
        from raw_bluepay_data rbd
        LEFT JOIN donations d
            ON (rbd.id = d.source_trans_id
            AND d.trans_source_id_fk = 1) 
            OR ('B' || rbd.id = d.source_trans_id 
            AND d.trans_source_id_fk = 4)
        LEFT JOIN aliases a 
            ON rbd.phone COLLATE NOCASE = a.alias_phone COLLATE NOCASE -- COLLATE NOCASE is the syntax for ignoring case
            OR rbd.email COLLATE NOCASE = a.alias_email COLLATE NOCASE
            OR (rbd.name1 COLLATE NOCASE = a.alias_first_name COLLATE NOCASE and
            rbd.name2 COLLATE NOCASE = a.alias_last_name COLLATE NOCASE)
        LEFT JOIN temp_donations td
            ON (rbd.id = td.source_trans_id -- first time called, this does noting.  second time around, this ignores transactions already in td
            AND td.trans_source_id_fk = 1) 
            OR ('B' || rbd.id = td.source_trans_id 
            AND td.trans_source_id_fk = 4) 
        where rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
             rbd.amount > 0 and
             rbd.status = '1' and
             d.source_trans_id is NULL and
             a.alias_id_pk is not NULL and
             td.source_trans_id is NULL 
        GROUP BY rbd.id -- we group b/c a donation will match with multiple aliases
        """

    new_donors = """
    insert into temp_donors
    select NULL ,
        max(rbd.name1) || ' ' || max(rbd.name2) ,
        max(rbd.name2) ,
        max(rbd.name1) ,
        '' ,
        NULL ,
        rbd.phone , 
        rbd.email,
        NULL 
    from raw_bluepay_data rbd
    left join donations d
        ON (rbd.id = d.source_trans_id
        AND d.trans_source_id_fk = 1) 
        OR ('B' || rbd.id = d.source_trans_id 
        AND d.trans_source_id_fk = 4)
    left join temp_donations td
        ON (rbd.id = td.source_trans_id -- first time called, this does noting.  second time around, this ignores transactions already in td
        AND td.trans_source_id_fk = 1) 
        OR ('B' || rbd.id = td.source_trans_id 
        AND td.trans_source_id_fk = 4) 
    where d.source_trans_id is NULL and 
        td.source_trans_id is NULL and
        rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
        rbd.amount > 0 and
        rbd.status = '1'
    group by
        rbd.email ,
        rbd.phone """
    
    new_prev_max_id_query = """
    update temp_donors set prev_max_id = (
        select max(donor_id_pk) from donors)
    """

    new_aliases_for_new_donors = """
        insert into temp_aliases
        select distinct null ,
            d.donor_id_pk ,
            rbd.name1 ,
            rbd.email ,
            rbd.phone ,
            rbd.addr1 ,
            rbd.addr2 ,
            rbd.city ,
            rbd.zip ,
            rbd.country ,
            '' ,
            rbd.name2 ,
            rbd.state
        from temp_donors td
        left join raw_bluepay_data rbd
        on
            rbd.phone = td.matched_phone and
            rbd.email = td.matched_email 
        left join donors d
        on
            td.donor_first_name = d.donor_first_name and
            td.donor_last_name = d.donor_last_name and
            td.prev_max_id < d.donor_id_pk
        where
            rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
            rbd.amount > 0 and
            rbd.status = '1'
        """

# when instr(rbd.name1 ,' ') = 0
#         then lower(rbd.name1)
#         else
#             lower(substr(rbd.name1 ,1,instr(rbd.name1 ,' ')-1))
#         end ,
#     lower(rbd.name2)
    
    cursor.execute(alias_match('alias match'))
    cursor.execute(new_donors)
    cursor.execute(new_prev_max_id_query)
    udb.push_temp_table_to_live("temp_donors", "donors", [
            "NULL",
            "donor_reporting_name",
            "donor_last_name",
            "donor_first_name",
            "donor_middle_name",
            "donor_class_year"], conn)
    cursor.execute(new_aliases_for_new_donors)
    udb.push_temp_table_to_live("temp_aliases", "aliases", ["*"], conn)
    cursor.execute(alias_match('new donor'))
    udb.push_temp_table_to_live("temp_donations", "donations", 
                                ["my_trans_id_pk", "source_trans_id", "date_time", "alias_id_fk", "trans_source_id_fk", "donation_currrency",
                                 "donation_gross_amt", "fee_currency", "fee_amt", "conversion_rate", "donation_gross_USD", "fee_USD", "donation_net_USD"],
                                 conn)

    data_donors = pd.read_sql_query("SELECT * FROM temp_donors", conn)
    data_aliases = pd.read_sql_query("SELECT * FROM temp_aliases", conn)
    data_donations = pd.read_sql_query("SELECT * FROM temp_donations", conn)

    validation_dict = val.validate_bluepay(conn, "raw_bluepay_data" , "id")

    return {'temp_donations':data_donations, 
            'temp_donors':data_donors, 
            'temp_aliases':data_aliases,
            'validation_dict':validation_dict,
            'temp_raw_data':df}
