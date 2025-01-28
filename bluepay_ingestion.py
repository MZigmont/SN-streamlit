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
 
def ingest_data(df: pd.DataFrame, table_name, conn):
    df.to_sql(table_name, conn, if_exists='replace', index=False)

def dummy():
    def question_marks(length):
        results='('+'?,'*length
        results=results[:-1]+')'
        return results

    file = input("""Please enter the EXACT filename of the Bluepay data you'd like to ingest.\n
    You can copy and paste the filename from the above drive mounting code:\n""")

    #open the file and then convert it to a list of lists (rows and data elements)
    # 2020-08-26 IMPLEMENT FILE SELECTION PROCESS FOR USER
    csvfile = open(file, 'r', newline='')

    csvreader = csv.reader(csvfile, delimiter=',')

    conn=sqlite3.connect('sigma_nu_donations.db')
    c=conn.cursor()

    c.execute("delete from raw_bluepay_data")

    print('Ingestion beginning for BluePay data')
    # this code REQUIRES a header row in the raw data
    next(csvreader)
    row_number=0

    for row in csvreader:
        if len(row)>0:
            #these are the column numbers of the fields we want
            #0    2    3    11    15    21    22    23    24    25    26    27    29    30    31    32    48    49    50    51    57    58    59    60    70
            #c.execute("INSERT INTO TABLE_NAME VALUES (?, ?, ?)", (value1, value2, value3))
            columns=[0,2,3,11,15,21,22,23,24,25,26,27,29,30,31,32,48,49,50,51,57,58,59,60,70]

            #this would have padded the string to 5 char with leading zeros row[25]=row[25].rjust(5,'0')

            row[26]=row[26].replace('-','') #remove dashes from all phone numbers

            c.execute("INSERT INTO raw_bluepay_data VALUES "+question_marks(len(columns)), tuple((row[i] for i in columns)))
            row_number = row_number +1

    print('{:,} records ingested.'.format(row_number))

    # data processing starts here
    # -- production order 1,2,1,3,4,1

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
