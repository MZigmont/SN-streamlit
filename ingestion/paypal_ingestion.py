import csv #csv is a package that comes from python
import sqlite3 #sqlite3 is a pkg that comes from python
from datetime import datetime #from a megapackage, import datetime subpackage
import time #time is a package
import sys #system commands
import pandas as pd
import validation as val
import update_db as udb

# TO DO: 1/5/2026 - GET BLUPAY DATA FROM 9/1/25 TEST NEW VALIDATION, code written in validation.py
# TO DO: 2/2/2026 - WRITE CARDPOINTE INGESTION CODE

raw_table_name = "raw_paypal_data" 
def ingest_data(df: pd.DataFrame, conn):
    df.columns = (
        df.columns
            .str.lower()
            .str.replace(" ","_")
            .str.replace("/","_")
    )
    parts = df['name'].str.split(expand=True)
    df['my_first_name']  = parts[0]
    df['my_last_name']   = parts.iloc[:, -1]
    df['my_middle_name'] = parts.iloc[:, 1:-1].apply(
        lambda x: ' '.join(x.dropna()), axis=1
    )
    df.to_sql(raw_table_name, conn, if_exists='replace', index=False)
    cursor = conn.cursor()
    udb.create_staging_tables(cursor)

    # alias match is on phone or email or (first_name and last_name)
    alias_match = """
        insert into temp_donations
        select null , --my_trans_id_pk
            rpd.transaction_id , -- source_trans_id
            max(rpd.date || ' ' || rpd.time) , --date_time
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
            'alias match'
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

    alias_match_non_USD = """
        insert into temp_donations
        select null , --my_trans_id_pk
            rpd.transaction_id , -- source_trans_id
            max(rpd.date || ' ' || rpd.time) , --date_time
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
            'alias match non USD old'
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
        where (rpd.type ='General Payment'
            or rpd.type ='Mobile Payment')
            and rpd.currency <> 'USD'
            and rpd2.transaction_id is not null
            and d.alias_id_fk is NULL --record is new donation not in database
            and a.alias_id_pk is not null --alias exists
            and td.source_trans_id is NULL --first time, no effect, second time, makes sure we don't insert duplicate transactions
        GROUP BY rpd.transaction_id;
        """
# user intiatied currency conversion with the
# the NEW paypal process
    alias_match_non_USD_user_iniated = """
    with temp1 as (
    select distinct rpd1.* ,
    first_value(abs(rpd3.net/rpd2.net)) over (partition by rpd1.transaction_id order by rpd1.date ASC , rpd1.time ASC , rpd2.date ASC, rpd2.time ASC) as conversion_rate
    from raw_paypal_data rpd1
    left join raw_paypal_data rpd2
    on
        rpd2.type = 'User Initiated Currency Conversion' and rpd2.currency = rpd1.currency and
        rpd1.date || ' ' || rpd1.time <= rpd2.date || ' ' || rpd2.time
    left join raw_paypal_data rpd3
    on
        rpd2.transaction_id = rpd3.reference_txn_id
    where
        rpd1.currency is not 'USD' and (rpd1.type = 'General Payment' or rpd1.type = 'Mobile Payment')
    order by rpd1.date ASC , rpd1.time ASC , rpd2.date ASC, rpd2.time ASC
    ) insert into temp_donations
    select NULL ,
        temp1.transaction_id ,
        temp1.date || ' ' || temp1.time as date_time,
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
        'alias_match_non_USD_user_iniated'
    from temp1
        LEFT JOIN aliases a 
            ON temp1.contact_phone_number COLLATE NOCASE = a.alias_phone COLLATE NOCASE
            OR temp1.from_email_address COLLATE NOCASE = a.alias_email COLLATE NOCASE
            OR (temp1.my_first_name COLLATE NOCASE = a.alias_first_name COLLATE NOCASE and
            temp1.my_last_name COLLATE NOCASE = a.alias_last_name COLLATE NOCASE)
        LEFT JOIN raw_paypal_data rpd
        on temp1.transaction_id = rpd.reference_txn_id and
        rpd.type = 'General Currency Conversion'
        LEFT JOIN donations d
        on temp1.transaction_id = d.source_trans_id
        LEFT JOIN temp_donations td
            ON rpd.transaction_id = td.source_trans_id
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
        select null ,
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
    cursor.execute(alias_match)
    cursor.execute(alias_match_non_USD)
    cursor.execute(alias_match_non_USD_user_iniated)
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
    cursor.execute(alias_match)
    cursor.execute(alias_match_non_USD)
    cursor.execute(alias_match_non_USD_user_iniated)
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
            'validation_dict':validation_dict}

def dummy():
        #@title #5. PAYPAL ingestion code below
    '''
    Created on Jun 24, 2020

    @author: mike zigmont
    '''
    # this is a comment
    import csv #csv is a package that comes from python
    import sqlite3 #sqlite3 is a pkg that comes from python
    from datetime import datetime #from a megapackage, import datetime subpackage
    import time #time is a package


    def question_marks(length):
        results='('+'?,'*length
        results=results[:-1]+')'
        return results

    #breaks a string into components based on given character as a delimiter and returns the 1st name (1), middle name (2), or last name (3)
    def get_specific_name(my_string , my_delimiter, my_name=1):
        my_list=my_string.split(my_delimiter)
        if len(my_list) <1:
            return ''
        elif my_name==1:
            return my_list[0]
        elif my_name==3:
            if len(my_list)>1:
                return my_list[-1]
            else:
                return ''
        elif my_name==2:
            if len(my_list)<=2:
                return ''
            else:
                return ' '.join(my_list[1:-1])
        else:
            return ''

    file = input("""Please enter the EXACT filename of the PayPal data you'd like to ingest.\n
    You can copy and paste the filename from the above drive mounting code:\n""")

    #open the file and then convert it to a list of lists (rows and data elements)
    csvfile = open(file, 'r', newline='')

    csvreader = csv.reader(csvfile, delimiter=',')

    conn=sqlite3.connect(r'sigma_nu_donations.db')
    c=conn.cursor()

    #delete data from existing raw_paypal_data table
    c.execute("DELETE from raw_paypal_data")

    next(csvreader)
    row_number=1

    for row in csvreader:
        if len(row)>0:
            row_number+=1
            #these are the column numbers of the fields we want
            #0    1    2    3    4    5    6    7    8    9    10    11    12    13    14    15    16    17    18    19    20    21    22    23    24    25    26    27    28    29    30    31    32    33    34    35    36    37    38    39    40
            #c.execute("INSERT INTO TABLE_NAME VALUES (?, ?, ?)", (value1, value2, value3))
            #list of column indexes
            columns=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43]
            #convert date (first element of row) into format appropriate for sql database
            row[0]=datetime.strptime(row[0],'%m/%d/%Y').strftime('%Y-%m-%d')
            #add the first name, middle name, last name date to row
            row.append(get_specific_name(row[3], ' ', 1))
            row.append(get_specific_name(row[3], ' ', 2))
            row.append(get_specific_name(row[3], ' ', 3))
            #insert each record into the database
            c.execute("INSERT INTO raw_paypal_data VALUES " + question_marks(len(columns)), tuple((row[i] for i in columns)))


    # -- *******    PAYPAL code    *******
    # data processing starts here
    # -- production order 1.1 1.2 1.3,2,1.1 1.2 1.3,3,4,1.1 1.2 1.3, MAKE query 5 to show user any transations that weren't inserted
    # -- 1.1 1.2 1.3 PAYPAL specific, exact alias match
    # --1.1 USD DONATIONS ONLY
    # --type = 'Mobile Payment' or "General Payment'
    # --AND
    # --currency = 'USD'
    exact_alias_match_1_1 = """
    insert into donations
    select null , --my_trans_id_pk
    t1.transaction_id , -- source_trans_id
    t1.date || ' ' || t1.time , --date_time
    aliases.alias_id_pk , --alias_id_fk
    2 , --trans_source_id_fk
    t1.currency , --donation_currency
    t1.gross , --donation_gross_amt
    t1.currency , --fee_currency
    t1.fee , --fee_amt
    null , --conversion_rate
    t1.gross as gross_USD_donation , --donation_gross_USD
    t1.fee as USD_fee , --fee_USD
    t1.net --donation_net_USD
        from raw_paypal_data t1
        left join aliases
        on t1.my_first_name = aliases.alias_first_name and
            t1.from_email_address = aliases.alias_email and
            t1.contact_phone_number = aliases.alias_phone and
            t1.address_line_1 = aliases.alias_address_1 and
            t1.address_line_2_district_neighborhood = aliases.alias_address_2 and
            t1.town_city = aliases.alias_city and
            t1.zip_postal_code = aliases.alias_zip and
            t1.country = aliases.alias_country and
            t1.my_middle_name = aliases.alias_middle_name and
            t1.my_last_name = aliases.alias_last_name and
            t1.state_province_region_county_territory_prefecture_republic = aliases.alias_state
        left join donations d
        on t1.transaction_id = d.source_trans_id
        where (t1.type ='General Payment'
            or t1.type ='Mobile Payment')
            and t1.currency ='USD'
            and d.alias_id_fk is NULL
            and aliases.alias_id_pk is not null;
            """

    # --1.2 FOREIGN CURRENCY VIA THE GENERAL CURRENCY MECHANISM
    # --type = 'General Currency Conversion'
    # --AND
    # --currency is not 'USD'
    # --in FROM left join raw_paypal_data with itself
    # --t1 (left copy) contains identity of who gave donation
    # --t2 contains the amounts of donations in USD
    # --join using t1.transaction_id and t2.reference_txn_id
    # --AND t2.currency ='USD'
    exact_alias_match_1_2 = """
    insert into donations
    select null , --my_trans_id_pk
    t1.transaction_id , -- source_trans_id
    t1.date || ' ' || t1.time , --date_time
    aliases.alias_id_pk , --alias_id_fk
    2 , --trans_source_id_fk
    t1.currency , --donation_currency
    t1.gross , --donation_gross_amt
    t1.currency , --fee_currency
    t1.fee , --fee_amt
    t2.net/t1.net , --conversion_rate
    t2.net/t1.net * t1.gross as gross_USD_donation , --donation_gross_USD
    t2.net/t1.net * t1.fee as USD_fee , --fee_USD
    t2.net --donation_net_USD
        from raw_paypal_data t1 inner join raw_paypal_data t2
        on t1.transaction_id = t2.reference_txn_id and (t1.type = 'General Payment' or t1.type = 'Mobile Payment') and t1.currency is not 'USD' and
        t2.type ='General Currency Conversion' and
        t2.currency ='USD'
        inner join aliases
        on t1.my_first_name = aliases.alias_first_name and
            t1.from_email_address = aliases.alias_email and
            t1.contact_phone_number = aliases.alias_phone and
            t1.address_line_1 = aliases.alias_address_1 and
            t1.address_line_2_district_neighborhood = aliases.alias_address_2 and
            t1.town_city = aliases.alias_city and
            t1.zip_postal_code = aliases.alias_zip and
            t1.country = aliases.alias_country and
            t1.my_middle_name = aliases.alias_middle_name and
            t1.my_last_name = aliases.alias_last_name and
            t1.state_province_region_county_territory_prefecture_republic = aliases.alias_state
        left join donations d
        on t1.transaction_id = d.source_trans_id
        where
            d.alias_id_fk is NULL;
            """


    # -- 1.3 General Payments in non USD currency, matched to user initiated currency transactions
    exact_alias_match_1_3 = """
    with temp1 as (
    select distinct t1.* ,
    first_value(abs(t3.net/t2.net)) over (partition by t1.transaction_id order by t1.date ASC , t1.time ASC , t2.date ASC, t2.time ASC) as conversion_rate
    from raw_paypal_data t1
    left join raw_paypal_data t2
    on
        t2.type = 'User Initiated Currency Conversion' and t2.currency = t1.currency and
        t1.date || ' ' || t1.time <= t2.date || ' ' || t2.time
    left join raw_paypal_data t3
    on
        t2.transaction_id = t3.reference_txn_id
    where
        t1.currency is not 'USD' and (t1.type = 'General Payment' or t1.type = 'Mobile Payment')
    order by t1.date ASC , t1.time ASC , t2.date ASC, t2.time ASC
    ) insert into donations
    select NULL ,
    temp1.transaction_id ,
    temp1.date || ' ' || temp1.time as date_time,
    aliases.alias_id_pk ,
    2 as trans_source_id_fk,
    temp1.currency as donation_currency,
    temp1.gross as donation_gross_amt,
    temp1.currency as fee_currency,
    temp1.fee as fee_amt,
    temp1.conversion_rate as conversion_rate,
    temp1.gross * temp1.conversion_rate as donation_gross_USD ,
    temp1.fee * temp1.conversion_rate as fee_USD ,
    temp1.net * temp1.conversion_rate as donation_net_USD
    from temp1
        inner join aliases
        on temp1.my_first_name = aliases.alias_first_name and
            temp1.from_email_address = aliases.alias_email and
            temp1.contact_phone_number = aliases.alias_phone and
            temp1.address_line_1 = aliases.alias_address_1 and
            temp1.address_line_2_district_neighborhood = aliases.alias_address_2 and
            temp1.town_city = aliases.alias_city and
            temp1.zip_postal_code = aliases.alias_zip and
            temp1.country = aliases.alias_country and
            temp1.my_middle_name = aliases.alias_middle_name and
            temp1.my_last_name = aliases.alias_last_name and
            temp1.state_province_region_county_territory_prefecture_republic = aliases.alias_state
        left join raw_paypal_data rpd
        on temp1.transaction_id = rpd.reference_txn_id and
        rpd.type = 'General Currency Conversion'
        left join donations d
        on temp1.transaction_id = d.source_trans_id
    where rpd.transaction_id is NULL and
        d.my_trans_id_pk is NULL;
        """

    exact_alias_match_1_3_select = """
    with temp1 as (
    select distinct t1.* ,
    first_value(-t3.net/t2.net) over (partition by t1.transaction_id order by t1.date ASC , t1.time ASC , t2.date ASC, t2.time ASC) as conversion_rate
    from raw_paypal_data t1
    left join raw_paypal_data t2
    on
        t2.type = 'User Initiated Currency Conversion' and t2.currency = t1.currency and
        t1.date || ' ' || t1.time <= t2.date || ' ' || t2.time
    left join raw_paypal_data t3
    on
        t2.transaction_id = t3.reference_txn_id
    where
        t1.currency is not 'USD' and (t1.type = 'General Payment' or t1.type = 'Mobile Payment')
    order by t1.date ASC , t1.time ASC , t2.date ASC, t2.time ASC
    )
    select NULL ,
    temp1.transaction_id ,
    temp1.date || ' ' || temp1.time as date_time,
    aliases.alias_id_pk ,
    2 as trans_source_id_fk,
    temp1.currency as donation_currency,
    temp1.gross as donation_gross_amt,
    temp1.currency as fee_currency,
    temp1.fee as fee_amt,
    temp1.conversion_rate as conversion_rate,
    temp1.gross * temp1.conversion_rate as donation_gross_USD ,
    temp1.fee * temp1.conversion_rate as fee_USD ,
    temp1.net * temp1.conversion_rate as donation_net_USD
    from temp1
        inner join aliases
        on temp1.my_first_name = aliases.alias_first_name and
            temp1.from_email_address = aliases.alias_email and
            temp1.contact_phone_number = aliases.alias_phone and
            temp1.address_line_1 = aliases.alias_address_1 and
            temp1.address_line_2_district_neighborhood = aliases.alias_address_2 and
            temp1.town_city = aliases.alias_city and
            temp1.zip_postal_code = aliases.alias_zip and
            temp1.country = aliases.alias_country and
            temp1.my_middle_name = aliases.alias_middle_name and
            temp1.my_last_name = aliases.alias_last_name and
            temp1.state_province_region_county_territory_prefecture_republic = aliases.alias_state
        left join raw_paypal_data rpd
        on temp1.transaction_id = rpd.reference_txn_id and
        rpd.type = 'General Currency Conversion'
        left join donations d
        on temp1.transaction_id = d.source_trans_id
    where rpd.transaction_id is NULL and
        d.my_trans_id_pk is NULL;
        """
    #-- 2 PARTIAL alias matches, i.e. new aliases for existing donors
    partial_alias = """
    insert into aliases
    select null ,
        a.donor_id_fk ,
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
    from raw_paypal_data rpd
    left join donations d
        on rpd.transaction_id = d.source_trans_id
    left join aliases a
        on lower(rpd.from_email_address ) = lower(a.alias_email)
        or ( lower(rpd.my_first_name ) = lower(a.alias_first_name)
            and lower(rpd.my_last_name ) = lower(a.alias_last_name)
            and rpd.contact_phone_number = a.alias_phone )
    where (rpd.type ='General Payment'
            or rpd.type ='Mobile Payment') and
        d.source_trans_id is NULL and
        a.donor_id_fk is not NULL
    group by
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
    """

    #-- 3 NEW donors
    new_donors = """
    insert into donors
    select NULL ,
        rpd.my_first_name || ' ' || rpd.my_middle_name || ' ' || rpd.my_last_name ,
        rpd.my_last_name ,
        rpd.my_first_name ,
        rpd.my_middle_name ,
        NULL
    from raw_paypal_data rpd
    left join donations d
        on rpd.transaction_id = d.source_trans_id
    where d.source_trans_id is NULL and
        (rpd.type ='General Payment'
            or rpd.type ='Mobile Payment')
    group by rpd.my_last_name ,
        rpd.my_first_name ,
        rpd.my_middle_name
    """

    #-- 4 NEW aliases for newly inserted donors
    new_aliases = """
    insert into aliases
    select null ,
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
    from raw_paypal_data rpd
    left join aliases a
    on
        rpd.address_line_1 = a.alias_address_1 and
        rpd.address_line_2_district_neighborhood = a.alias_address_2 and
        rpd.town_city = a.alias_city and
        rpd.state_province_region_county_territory_prefecture_republic = a.alias_state and
        rpd.zip_postal_code = a.alias_zip and
        rpd.contact_phone_number = a.alias_phone and
        rpd.from_email_address = a.alias_email and
        rpd.my_first_name = a.alias_first_name and
        rpd.my_last_name = a.alias_last_name
    left join donors d
    on
        rpd.my_first_name = d.donor_first_name and
        rpd.my_middle_name = d.donor_middle_name and
        rpd.my_last_name = d.donor_last_name
    where (rpd.type ='General Payment'
            or rpd.type ='Mobile Payment') and
        a.alias_id_pk is null
    group by
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
    """
    # - 9/7/22 - UPDATE FUNCTION TO EXECUTE 3 PARTS
    def execute_exact_alias_match(i):
        query_list = [exact_alias_match_1_1, exact_alias_match_1_2, exact_alias_match_1_3]
        for index, query in enumerate(query_list):
            try:
                c.execute(query)
                correct_rowcount = c.rowcount
                if index == 2:
                    c.execute(exact_alias_match_1_3_select)
                    correct_rowcount = len(c.fetchall())
                print('Executing Exact Alias Match {}, subquery 1.{}'.format(i, index + 1))

            except sqlite3.Error as er:
                print('Exact Alias Match {}, subquery 1.{} failed with the following error'.format(i, index + 1))
                print(er)
                conn.close()
                sys.exit(1)
            print('SUCCESS for Exact Alias Match {} query, subquery 1.{}.  {:,} transactions inserted.'.format(i, index + 1, correct_rowcount))

        return

    # 1 2 1 3 4 1
    #1
    execute_exact_alias_match(1)

    #2
    try:
        print('Executing Partial Alias Match 2')
        c.execute(partial_alias)
    except sqlite3.Error as er:
        print('Partial Alias Match 2 failed with the following error')
        print(er)
        conn.close()
        sys.exit(1)
    print('SUCCESS for Partial Alias Match 2 query.  {:,} aliases inserted.'.format(c.rowcount))

    #1 2nd instance
    execute_exact_alias_match(2)

    #3
    try:
        print('Executing New Donors Match 3')
        c.execute(new_donors)
    except sqlite3.Error as er:
        print('New Donors Match 3 failed with the following error')
        print(er)
        conn.close()
        sys.exit(1)
    print('SUCCESS for New Donors Match 3 query.  {:,} donors inserted.'.format(c.rowcount))

    #4
    try:
        print('Executing New Aliases for Existing Donors Match 4')
        c.execute(new_aliases)
    except sqlite3.Error as er:
        print('New Aliases for Existing Donors Match 4 failed with the following error')
        print(er)
        conn.close()
        sys.exit(1)
    print('SUCCESS for New Aliases for Existing Donors Match 4 query.  {:,} aliases inserted.'.format(c.rowcount))

    #1 3rd instance
    execute_exact_alias_match(3)

    conn.commit()
    conn.close()