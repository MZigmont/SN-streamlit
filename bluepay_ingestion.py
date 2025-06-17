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

raw_table_name = "raw_bluepay_data" 
def ingest_data(df: pd.DataFrame, conn):
    df.to_sql(raw_table_name, conn, if_exists='replace', index=False)
    cursor = conn.cursor()
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

    # alias match is on phone or email or (first_name and last_name)
    alias_match = """
        insert into temp_donations
        select null ,
            rbd.id ,
            max(rbd.issue_date) ,
            max(a.alias_id_pk) ,
            1 ,
            'USD' ,
            max(case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end),
            'USD' ,
            null ,
            null ,
            max(case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end),
            null ,
            max(case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end) ,
            'alias match'
        from raw_bluepay_data rbd
        left join donations d
            on rbd.id = d.source_trans_id
        LEFT JOIN aliases a 
            ON rbd.phone COLLATE NOCASE = a.alias_phone COLLATE NOCASE
            OR rbd.email COLLATE NOCASE = a.alias_email COLLATE NOCASE
            OR (rbd.name1 COLLATE NOCASE = a.alias_first_name COLLATE NOCASE and
            rbd.name2 COLLATE NOCASE = a.alias_last_name COLLATE NOCASE)
        where rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
             rbd.amount > 0 and
             rbd.status = '1' and
             d.source_trans_id is NULL and
             a.alias_id_pk is not NULL
        GROUP BY rbd.id
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
        on rbd.id = d.source_trans_id
    left join temp_donations td
        on rbd.id = td.source_trans_id
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

    insert_new_donors = """
    insert into donors
    select 
            NULL,
            donor_reporting_name,
            donor_last_name,
            donor_first_name,
            donor_middle_name,
            donor_class_year
    from temp_donors
    """

    new_aliases_for_new_donors = """
        insert into temp_aliases
        select null ,
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

    insert_new_aliases = """
        insert into aliases
        select *
        from temp_aliases
        """

# same as alias_match except we also check against temp_donations
    donations_for_new_donors = """
        insert into temp_donations
        select null ,
            rbd.id ,
            max(rbd.issue_date) ,
            max(a.alias_id_pk) ,
            1 ,
            'USD' ,
            max(case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end),
            'USD' ,
            null ,
            null ,
            max(case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end),
            null ,
            max(case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end) ,
            'new donors'
        from raw_bluepay_data rbd
        left join donations d
            on rbd.id = d.source_trans_id
        LEFT JOIN aliases a 
            ON rbd.phone COLLATE NOCASE = a.alias_phone COLLATE NOCASE
            OR rbd.email COLLATE NOCASE = a.alias_email COLLATE NOCASE
            OR (rbd.name1 COLLATE NOCASE = a.alias_first_name COLLATE NOCASE and
            rbd.name2 COLLATE NOCASE = a.alias_last_name COLLATE NOCASE)
        LEFT JOIN temp_donations td
            ON rbd.id = td.source_trans_id
        where rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
             rbd.amount > 0 and
             rbd.status = '1' and
             d.source_trans_id is NULL and
             a.alias_id_pk is not NULL and
             td.source_trans_id is NULL
        GROUP BY rbd.id
        """

# when instr(rbd.name1 ,' ') = 0
#         then lower(rbd.name1)
#         else
#             lower(substr(rbd.name1 ,1,instr(rbd.name1 ,' ')-1))
#         end ,
#     lower(rbd.name2)
    
    cursor.execute(alias_match)
    cursor.execute(new_donors)
    cursor.execute(new_prev_max_id_query)
    cursor.execute(insert_new_donors)
    cursor.execute(new_aliases_for_new_donors)
    cursor.execute(insert_new_aliases)
    cursor.execute(donations_for_new_donors)

    data_donors = pd.read_sql_query("SELECT * FROM temp_donors", conn)
    data_aliases = pd.read_sql_query("SELECT * FROM temp_aliases", conn)
    data_donations = pd.read_sql_query("SELECT * FROM temp_donations", conn)

    validation_dict = val.validate(conn, "raw_bluepay_data" , "id")

    return {'temp_donations':data_donations, 
            'temp_donors':data_donors, 
            'temp_aliases':data_aliases,
            'validation_dict':validation_dict}

def dummy():
    # TO DO: 3/10/25:
    # get txns not captured by 1
    # create new donors for each txn
    # create new alias for each donor
    # ingest via 1 
    # 
    # production order 1,3,4,1


    # 1
    exact_match = """
    insert into donations
    select null ,
        rbd.id ,
        rbd.issue_date ,
        a.alias_id_pk ,
        1 ,
        'USD' ,
        case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end ,
        'USD' ,
        null ,
        null ,
        case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end ,
        null ,
        case when rbd.trans_type = 'SALE' then rbd.amount else -rbd.amount end
    from raw_bluepay_data rbd
    left join donations d
        on rbd.id = d.source_trans_id
    left join aliases a
        on rbd.addr1 = a.alias_address_1
        and rbd.addr2 = a.alias_address_2
        and rbd.city = a.alias_city
        and rbd.state = a.alias_state
        and rbd.zip = a.alias_zip
        and rbd.phone = a.alias_phone
        and rbd.email = a.alias_email
        and rbd.name1 = a.alias_first_name
        and rbd.name2 = a.alias_last_name
        and rbd.country = a.alias_country
    where rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
        rbd.amount > 0 and
        rbd.status = '1' and
        d.source_trans_id is NULL and
        a.donor_id_fk is not NULL """

    # put 'VOID' and 'REFUND' text in above
    # for those cases, rbd.amount will be inserted with negative value

    # 2
    partial_alias = """
    insert into aliases
    select null ,
        a.donor_id_fk ,
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
    from raw_bluepay_data rbd
    left join donations d
        on rbd.id = d.source_trans_id
    left join aliases a
        on lower(rbd.email) = lower(a.alias_email)
        or ( lower(rbd.name1) = lower(a.alias_first_name)
            and lower(rbd.name2) = lower(a.alias_last_name)
            and rbd.phone = a.alias_phone )
    where rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
        rbd.amount > 0 and
        rbd.status = '1' and
        d.source_trans_id is NULL and
        a.donor_id_fk is not NULL
    group by
        rbd.name1 ,
        rbd.email ,
        rbd.phone ,
        rbd.addr1 ,
        rbd.addr2 ,
        rbd.city ,
        rbd.zip ,
        rbd.country ,
        rbd.name2 ,
        rbd.state """

    # put 'VOID' and 'REFUND' text in above
    # for those cases, just put the new alias in


    # 3
    new_donors = """
    insert into donors
    select NULL ,
        rbd.name1 || ' ' || rbd.name2 ,
        rbd.name2 ,
        rbd.name1 ,
        '' ,
        NULL
    from raw_bluepay_data rbd
    left join donations d
        on rbd.id = d.source_trans_id
    where d.source_trans_id is NULL and
        rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
        rbd.amount > 0 and
        rbd.status = '1'
    group by
    CASE
        when instr(rbd.name1 ,' ') = 0
        then lower(rbd.name1)
        else
            lower(substr(rbd.name1 ,1,instr(rbd.name1 ,' ')-1))
        end ,
    lower(rbd.name2) """

    # put 'VOID' and 'REFUND' text in above
    # for those cases, just put the new donor in


    # 4
    new_aliases_for_existing_donors = """
    insert into aliases
    select null ,
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
    from raw_bluepay_data rbd
    left join aliases a
    on
        rbd.addr1 = a.alias_address_1 and
        rbd.addr2 = a.alias_address_2 and
        rbd.city = a.alias_city and
        rbd.state = a.alias_state and
        rbd.zip = a.alias_zip and
        rbd.phone = a.alias_phone and
        rbd.email = a.alias_email and
        rbd.name1 = a.alias_first_name and
        rbd.name2 = a.alias_last_name
    left join donors d
    on
        --use string functions to compare first word of name1 field only
        CASE
            when instr(rbd.name1 ,' ') = 0
            then lower(rbd.name1)
            else
                lower(substr(rbd.name1 ,1,instr(rbd.name1 ,' ')-1))
            end  =
        --use string functions to compare first word of donor_first_name field only
        CASE
            when instr(d.donor_first_name ,' ') = 0
            then lower(d.donor_first_name)
            else
                lower(substr(d.donor_first_name ,1,instr(d.donor_first_name ,' ')-1))
            end
        and
        lower(rbd.name2) = lower(d.donor_last_name)
    where
        rbd.trans_type in ('SALE', 'VOID', 'REFUND') and
        rbd.amount > 0 and
        rbd.status = '1' and
        a.alias_id_pk is null
    group by rbd.name1 ,
        rbd.email ,
        rbd.phone ,
        rbd.addr1 ,
        rbd.addr2 ,
        rbd.city ,
        rbd.zip ,
        rbd.country ,
        rbd.name2 ,
        rbd.state """

    # put 'VOID' and 'REFUND' text in above
    # for those cases, just put the new alias in

    def execute_exact_match(i):
        try:
            print('Executing Exact Match {}'.format(i))
            c.execute(exact_match)
        except sqlite3.Error as er:
            print('Exact Match {} failed with the following error'.format(i))
            print(er)
            conn.close()
            sys.exit(1)
        print('SUCCESS for Exact Match {} query.  {:,} transactions inserted.'.format(i, c.rowcount))
        return

    # 1 2 1 3 4 1

    # 1
    execute_exact_match(1)

    # 2
    try:
        print('Executing Partial Alias Match 2')
        c.execute(partial_alias)
    except sqlite3.Error as er:
        print('Partial Alias Match 2 failed with the following error')
        print(er)
        conn.close()
        sys.exit(1)
    print('SUCCESS for Partial Alias Match 2 query.  {:,} aliases inserted.'.format(c.rowcount))

    # 1 (2nd instance)
    execute_exact_match(2)

    # 3
    try:
        print('Executing New Donors Match 3')
        c.execute(new_donors)
    except sqlite3.Error as er:
        print('New Donors Match 3 failed with the following error')
        print(er)
        conn.close()
        sys.exit(1)
    print('SUCCESS for New Donors Match 3 query.  {:,} donors inserted.'.format(c.rowcount))

    # 4
    try:
        print('Executing New Aliases for Existing Donors Match 4')
        c.execute(new_aliases_for_existing_donors)
    except sqlite3.Error as er:
        print('New Aliases for Existing Donors Match 4 failed with the following error')
        print(er)
        conn.close()
        sys.exit(1)
    print('SUCCESS for New Aliases for Existing Donors Match 4 query.  {:,} aliases inserted.'.format(c.rowcount))

    # 1 (3rd instance)
    execute_exact_match(3)

    # Final commit and close
    conn.commit()
    conn.close()
