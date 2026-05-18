import csv #csv is a package that comes from python
import sqlite3 #sqlite3 is a pkg that comes from python
from datetime import datetime #from a megapackage, import datetime subpackage
import time #time is a package
import sys #system commands
import pandas as pd
import validation as val
import update_db as udb


raw_table_name = "raw_paypal_data" 
def ingest_data(df: pd.DataFrame, conn):
    df.columns = (
        df.columns
            .str.lower()
            .str.replace(" ","_")
            .str.replace("/","_")
    )

    df['datetime'] = pd.to_datetime(
        df['date'].astype(str) + ' ' + df['time'].astype(str) , format='mixed'
    )
    
    parts = df['name'].str.split()

    df['my_first_name']  = parts.str[0]
    df['my_last_name']   = parts.str[-1]
    df['my_middle_name'] = parts.str[1:-1].str.join(' ')

    df.to_sql(raw_table_name, conn, if_exists='replace', index=False)
    cursor = conn.cursor()
    udb.create_staging_tables(cursor)

    # alias match is on phone or email or (first_name and last_name)
    def alias_match(match_type: str):
        return f"""
        insert into temp_donations
        select null , --my_trans_id_pk
            rpd.transaction_id , -- source_trans_id
            max(rpd.datetime) , --date_time
            max(a.alias_id_pk) ,
            2 , --trans_source_id_fk
            rpd.currency , --donation_currency
            max(rpd.gross), 
            rpd.currency , --fee_currency
            rpd.fee , --fee amt
            null , --conversion_rate
            max(rpd.gross) as gross_USD_donation, --donation_gross_USD
            rpd.fee as USD_fee , --fee_USD ,
            max(rpd.net ) , --donation_net_USD
            '{match_type}'
        from raw_paypal_data rpd
        LEFT JOIN aliases a 
            ON rpd.contact_phone_number COLLATE NOCASE = a.alias_phone COLLATE NOCASE
            OR rpd.from_email_address COLLATE NOCASE = a.alias_email COLLATE NOCASE
            OR (rpd.my_first_name COLLATE NOCASE = a.alias_first_name COLLATE NOCASE and
            rpd.my_last_name COLLATE NOCASE = a.alias_last_name COLLATE NOCASE)
        LEFT JOIN donations d
            ON rpd.transaction_id =  d.source_trans_id
            and d.trans_source_id_fk = 2
        LEFT JOIN temp_donations td
            ON rpd.transaction_id = td.source_trans_id
        where (rpd.type ='General Payment'
            or rpd.type ='Mobile Payment')
            and rpd.status = 'Completed'
            and rpd.net > 0
            and rpd.currency ='USD'
            and d.alias_id_fk is NULL --record is new donation not in database
            and a.alias_id_pk is not null --alias exists
            and td.source_trans_id is NULL --first time, no effect, second time, makes sure we don't insert duplicate transactions
        GROUP BY rpd.transaction_id;
        """
    
    # --FOREIGN CURRENCY VIA THE GENERAL CURRENCY MECHANISM
    # --type = 'General Currency Conversion'
    # --AND
    # --currency is not 'USD'
    # --in left join raw_paypal_data with itself
    # --t1 (left copy) contains identity of who gave donation
    # --t2 contains the amounts of donations in USD
    # --join using t1.transaction_id and t2.reference_txn_id
    # --AND t2.currency ='USD'

    def alias_match_non_USD(match_type: str):
        return f"""
        insert into temp_donations
        select null , --my_trans_id_pk
            rpd.transaction_id , -- source_trans_id
            max(rpd.datetime) , --date_time
            max(a.alias_id_pk) ,
            2 , --trans_source_id_fk
            max(rpd.currency) , --donation_currency ,
            max(rpd.gross), 
            max(rpd.currency) , --fee_currency
            max(rpd.fee) , --fee amt
            max(rpd2.net/rpd.net) , --conversion_rate
            max(rpd2.net/rpd.net * rpd.gross) as gross_USD_donation, --donation_gross_USD
            max(rpd2.net/rpd.net * rpd.fee) as USD_fee , --fee_USD ,
            max(rpd.net ) , --donation_net_USD
            '{match_type}'
        from raw_paypal_data rpd
        LEFT JOIN raw_paypal_data rpd2
            on rpd.transaction_id = rpd2.reference_txn_id and 
            (rpd.type = 'General Payment' or rpd.type = 'Mobile Payment')
            and rpd.currency is not 'USD' and
            rpd2.type ='General Currency Conversion' and
            rpd2.currency ='USD'
        LEFT JOIN aliases a 
            ON rpd.contact_phone_number COLLATE NOCASE = a.alias_phone COLLATE NOCASE
            OR rpd.from_email_address COLLATE NOCASE = a.alias_email COLLATE NOCASE
            OR (rpd.my_first_name COLLATE NOCASE = a.alias_first_name COLLATE NOCASE and
            rpd.my_last_name COLLATE NOCASE = a.alias_last_name COLLATE NOCASE)
        LEFT JOIN donations d
            ON rpd.transaction_id =  d.source_trans_id
            and d.trans_source_id_fk = 2
        LEFT JOIN temp_donations td
            ON rpd.transaction_id = td.source_trans_id
            and td.trans_source_id_fk = 2
        where (rpd.type ='General Payment'
            or rpd.type ='Mobile Payment')
            and rpd.status = 'Completed'
            and rpd.net > 0
            and rpd.currency <> 'USD'
            and rpd2.transaction_id is not null
            and d.alias_id_fk is NULL --record is new donation not in database
            and a.alias_id_pk is not null --alias exists
            and td.source_trans_id is NULL --first time, no effect, second time, makes sure we don't insert duplicate transactions
        GROUP BY rpd.transaction_id;
        """
# user intiatied currency conversion with the
# the NEW paypal process
    def alias_match_non_USD_user_iniated(match_type: str):
        return f"""
    with temp1 as (
    select distinct rpd1.* ,
    first_value(abs(rpd3.net/rpd2.net)) over (partition by rpd1.transaction_id order by rpd1.date ASC , rpd1.time ASC , rpd2.date ASC, rpd2.time ASC) as conversion_rate
    from raw_paypal_data rpd1
    left join raw_paypal_data rpd2
    on
        rpd2.type = 'User Initiated Currency Conversion' and rpd2.currency = rpd1.currency and
        rpd1.datetime <= rpd2.datetime
    left join raw_paypal_data rpd3
    on
        rpd2.transaction_id = rpd3.reference_txn_id
    where
        rpd1.currency is not 'USD' and (rpd1.type = 'General Payment' or rpd1.type = 'Mobile Payment')
        and rpd1.status = 'Completed'
        and rpd1.net > 0
    order by rpd1.date ASC , rpd1.time ASC , rpd2.date ASC, rpd2.time ASC
    ) insert into temp_donations
    select NULL ,
        temp1.transaction_id ,
        temp1.datetime as date_time,
        a.alias_id_pk ,
        2 as trans_source_id_fk,
        temp1.currency as donation_currency,
        temp1.gross as donation_gross_amt,
        temp1.currency as fee_currency,
        temp1.fee as fee_amt,
        temp1.conversion_rate as conversion_rate,
        temp1.gross * temp1.conversion_rate as donation_gross_USD ,
        temp1.fee * temp1.conversion_rate as fee_USD ,
        temp1.net * temp1.conversion_rate as donation_net_USD , 
        '{match_type}'
    from temp1
        LEFT JOIN aliases a 
            ON temp1.contact_phone_number COLLATE NOCASE = a.alias_phone COLLATE NOCASE
            OR temp1.from_email_address COLLATE NOCASE = a.alias_email COLLATE NOCASE
            OR (temp1.my_first_name COLLATE NOCASE = a.alias_first_name COLLATE NOCASE and
            temp1.my_last_name COLLATE NOCASE = a.alias_last_name COLLATE NOCASE)
        LEFT JOIN raw_paypal_data rpd -- explicitly removes 'General Currency Conversion' to avoid double counting
            on temp1.transaction_id = rpd.reference_txn_id and
            rpd.type = 'General Currency Conversion'
        LEFT JOIN donations d
            on temp1.transaction_id = d.source_trans_id
            and d.trans_source_id_fk = 2
        LEFT JOIN temp_donations td
            ON temp1.transaction_id = td.source_trans_id
            and td.trans_source_id_fk = 2
    where rpd.transaction_id is NULL and
        d.my_trans_id_pk is NULL and
        a.alias_id_pk is NOT NULL 
        and td.source_trans_id is NULL --first time, no effect, second time, makes sure we don't insert duplicate transactions"""

# create the records for brand new PayPal donors
    new_donors = """
    insert into temp_donors
    select NULL ,
        max(rpd.my_first_name) || ' ' || max(rpd.my_last_name) ,
        max(rpd.my_last_name) ,
        max(rpd.my_first_name) ,
        max(rpd.my_middle_name) ,
        NULL ,
        rpd.contact_phone_number , 
        rpd.from_email_address,
        NULL 
    from raw_paypal_data rpd
    left join donations d
        on rpd.transaction_id = d.source_trans_id
        and d.trans_source_id_fk = 2
    left join temp_donations td
        on rpd.transaction_id = td.source_trans_id
    where d.source_trans_id is NULL and 
        td.source_trans_id is NULL and
        (rpd.type ='General Payment'
            or rpd.type ='Mobile Payment')
    group by
        rpd.from_email_address ,
        rpd.contact_phone_number """

    new_prev_max_id_query = """
    update temp_donors set prev_max_id = (
        select max(donor_id_pk) from donors)
    """


# PAYPAL NEW ALIASES with NEW DONORS 
    new_aliases_for_new_donors = """
        insert into temp_aliases
        select distinct null ,
            d.donor_id_pk ,
            rpd.my_first_name ,
            rpd.from_email_address ,
            rpd.contact_phone_number ,
            rpd.address_line_1 ,
            rpd.address_line_2_district_neighborhood ,
            rpd.town_city ,
            rpd.zip_postal_code ,
            rpd.country ,
            rpd.my_middle_name ,
            rpd.my_last_name ,
            rpd.state_province_region_county_territory_prefecture_republic
        from temp_donors td
        left join raw_paypal_data rpd
        on
            rpd.contact_phone_number = td.matched_phone and
            rpd.from_email_address = td.matched_email 
        left join donors d
        on
            td.donor_first_name = d.donor_first_name and
            td.donor_last_name = d.donor_last_name and
            td.prev_max_id < d.donor_id_pk
        where
            (rpd.type ='General Payment'
            or rpd.type ='Mobile Payment')
        """
    cursor.execute(alias_match('alias match USD'))
    cursor.execute(alias_match_non_USD('alias match non USD old'))
    cursor.execute(alias_match_non_USD_user_iniated('alias match non USD user iniated'))
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
    cursor.execute(alias_match('new donor USD'))
    cursor.execute(alias_match_non_USD('new donor non USD old'))
    cursor.execute(alias_match_non_USD_user_iniated('new donor non USD user iniated'))
    udb.push_temp_table_to_live("temp_donations", "donations", 
                                ["my_trans_id_pk", "source_trans_id", "date_time", "alias_id_fk", "trans_source_id_fk", "donation_currrency",
                                 "donation_gross_amt", "fee_currency", "fee_amt", "conversion_rate", "donation_gross_USD", "fee_USD", "donation_net_USD"],
                                 conn)

    data_donors = pd.read_sql_query("SELECT * FROM temp_donors", conn)
    data_aliases = pd.read_sql_query("SELECT * FROM temp_aliases", conn)
    data_donations = pd.read_sql_query("SELECT * FROM temp_donations", conn)

    validation_dict = val.validate_paypal(conn, raw_table_name , "transaction_id")

    return {'temp_donations':data_donations, 
            'temp_donors':data_donors, 
            'temp_aliases':data_aliases,
            'validation_dict':validation_dict,
            'temp_raw_data':df}
