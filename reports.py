import pandas as pd
import io
from openpyxl import Workbook

#@title Total Gross USD Donations
# total gross USD donations
def tot_gr_USD_don(startdate, enddate, conn):

    c = conn.cursor()

    total_donations = c.execute("""
    select
        sum( donation_gross_USD )
    from donations
    where
        date_time >= ? and
        date_time <= ?
    """,(startdate,enddate)).fetchall()[0][0]

    #print
    print(f'The sum of gross USD donations for the period ({startdate} - {enddate}) was ' +
            f'${total_donations:,.2f}')


    # 0 means single datapoint returned
    return (0, total_donations, 'Total Gross USD Donations')


# total gross USD donations by donor reporting name
def tot_gr_USD_dons_by_don(startdate, enddate, conn):

    c = conn.cursor()

    donations_by_donor = c.execute("""
    select
        d3.donor_reporting_name ,
        sum( donation_gross_USD ),
        d3.donor_class_year
    from donations d2
    left join aliases a1
    on d2.alias_id_fk = a1.alias_id_pk
    left join donors d3
    on a1.donor_id_fk = d3.donor_id_pk
    where
        date_time >= ? and
        date_time <= ?
    group by d3.donor_reporting_name
    order by sum(d2.donation_gross_USD ) DESC , d3.donor_class_year ASC , d3.donor_last_name ASC
    """,(startdate,enddate)).fetchall()

    # for_printing = []
    # # unpack each item in the list
    # for row in donations_by_donor:
    #     # unpack next item in sublist
    #     for element in row:
    #         for_printing.append(element)

    # for item in for_printing:
    #     print(item)

    # 1 means table returned
    return (1, donations_by_donor, ['donor_reporting_name','sum( donation_gross_USD )', 'donor_class_year'])

#@title Total Net Donations By Year
# total net donations per year
def tot_net_dons_p_yr(startdate, enddate, conn):

    c = conn.cursor()

    donations_by_year = c.execute("""
    SELECT strftime('%Y', date_time), sum(donation_net_USD) from donations
    GROUP BY strftime('%Y', date_time)
    ORDER BY strftime('%Y', date_time) ASC
    """).fetchall()

    print('Year  Donations')
    for row in donations_by_year:
        print(row)

    donations_by_fiscal_year = c.execute("""
    SELECT strftime('%Y', date(date_time , '+92 day'))as FiscalYear, sum(donation_net_USD) from donations
    GROUP BY strftime('%Y', date(date_time , '+92 day'))
    ORDER BY strftime('%Y', date(date_time , '+92 day')) ASC
    """).fetchall()

    print('Fiscal Year  Donations')
    for row in donations_by_fiscal_year:
        print(row)

    combined_donations_by_year = []
    for row in range(len(donations_by_year)):
        # pseudo initialize each row
        combined_donations_by_year.append(["", "", "", ""])
        for element in range(len(donations_by_year[row])):
            combined_donations_by_year[row][element] = donations_by_year[row][element]
        for element in range(len(donations_by_fiscal_year[row])):
            combined_donations_by_year[row][element + 2] = donations_by_fiscal_year[row][element]

    if len(donations_by_fiscal_year) == len(donations_by_year) + 1:
        # pseudo initialize the last row
        combined_donations_by_year.append(["", "", "", ""])
        combined_donations_by_year[row + 1][0] = ""
        combined_donations_by_year[row + 1][1] = ""
        combined_donations_by_year[row + 1][2] = donations_by_fiscal_year[row + 1][0]
        combined_donations_by_year[row + 1][3] = donations_by_fiscal_year[row + 1][1]
    else:
        pass

    # 1 means table returned
    return (1, combined_donations_by_year, ['Year', 'sum(donation_net_USD)', 'Fiscal Year', 'sum(donation_net_USD)'])

#@title Count of Unique Donors Function (Fxn 5)
# Count of Donors
def ct_don(startdate, enddate, conn):

    c = conn.cursor()

    count = c.execute("""
    select
        count( distinct d3.donor_reporting_name )
    from donations d2
    left join aliases a1
    on d2.alias_id_fk = a1.alias_id_pk
    left join donors d3
    on a1.donor_id_fk = d3.donor_id_pk
    where
        date_time >= ? and
        date_time <= ?
    """,(startdate, enddate)).fetchall()[0][0]

    print('The count of unique donors for the period ({} - {}) was '.format(startdate, enddate) +
            '{:,}'.format(count) +'.\n')

    # 0 means single datapoint returned
    return (0, count, 'Count of Donors')

#@title Donors by Class (Fxn 6)
# count of donors by class, sorted by most unique donors and classes oldest to youngest
def don_b_cls(startdate, enddate, conn):

    c = conn.cursor()

    donors_and_class = c.execute("""
    select
        count( distinct d3.donor_reporting_name ) ,
        d3.donor_class_year
    from donations d2
    left join aliases a1
    on d2.alias_id_fk = a1.alias_id_pk
    left join donors d3
    on a1.donor_id_fk = d3.donor_id_pk
    where
        date_time >= ? and
        date_time <= ?
    group by d3.donor_class_year
    order by count ( distinct d3.donor_reporting_name ) DESC ,
        d3.donor_class_year ASC
        """,(startdate,enddate)).fetchall()

    print('Unique Donors\tClass\n')
    for row in donors_and_class:
        print("{0:,}".format(row[0]) + "\t\t" + "{0:}".format(row[1]) + "\n")

    # 1 means table returned
    return (1, donors_and_class, ['Unique Donors' ,'donor_class_year'])

#@title Donations by Class (Fxn 7)
# total gross USD donations by class
def dons_b_cls(startdate, enddate, conn):

    c = conn.cursor()

    donations_and_class = c.execute("""
    select
        d3.donor_class_year ,
        sum( donation_gross_USD )
    from donations d2
    left join aliases a1
    on d2.alias_id_fk = a1.alias_id_pk
    left join donors d3
    on a1.donor_id_fk = d3.donor_id_pk
    where
        date_time >= ? and
        date_time <= ?
    group by d3.donor_class_year
    order by sum(d2.donation_gross_USD ) DESC , d3.donor_class_year ASC
    """,(startdate, enddate)).fetchall()

    print('Class\t\tDonations\n')
    for row in donations_and_class:
        print("{0:}".format(row[0]) + "\t\t" + "{0:,.2f}".format(row[1]) + "\n")

    # 1 means table returned
    return (1, donations_and_class, ['Class' , 'sum( donation_gross_USD )'])

#@title All Donations in Period (Fxn 8)
# donations in period
def dons_in_period(startdate, enddate, conn):

    c = conn.cursor()

    donations_in_period = c.execute("""
    SELECT d.my_trans_id_pk,
        d.source_trans_id,
        d.date_time,
        a.alias_first_name ,
        a.alias_middle_name ,
        a.alias_last_name ,
        ts.source_name ,
        d.donation_currrency,
        d.donation_gross_amt,
        d.fee_currency,
        d.fee_amt,
        d.conversion_rate,
        d.donation_gross_USD,
        d.fee_USD,
        d.donation_net_USD
    FROM donations d
    LEFT JOIN aliases a
        on d.alias_id_fk = a.alias_id_pk
    LEFT JOIN trans_source ts
        on d.trans_source_id_fk = ts.source_id_pk
    WHERE d.date_time >= ? AND
        d.date_time <= ?
    """,(startdate, enddate)).fetchall()

    print(str(len(donations_in_period)) + ' records in period fetched')

    # 1 means table returned
    return (1, donations_in_period,
        ['my_trans_id_pk',
        'source_trans_id',
        'date_time',
        'alias_first_name' ,
        'alias_middle_name' ,
        'alias_last_name' ,
        'source_name' ,
        'donation_currrency',
        'donation_gross_amt',
        'fee_currency',
        'fee_amt',
        'conversion_rate',
        'donation_gross_USD',
        'fee_USD',
        'donation_net_USD'])

def run_all_reports(fromdate, todate, conn):
    # List of report functions
    my_report_list = [
                tot_gr_USD_don,
                tot_gr_USD_dons_by_don,
                tot_net_dons_p_yr,
                ct_don,
                don_b_cls,
                dons_b_cls,
                dons_in_period
    ]

    # Create a new workbook using openpyxl
    report_begin_date = fromdate[0:10]
    report_run_date = todate[0:10]
    wb_name = f'sig_nu_{report_begin_date}_{report_run_date}.xlsx'
    workbook = Workbook()

    # Create an in-memory binary stream to save the file
    output = io.BytesIO()

    # Loop through each report function
    for report in my_report_list:
        results = report(fromdate, todate, conn)

        if results[0] == 0:
            # Handle case for summary results (only 2 elements)
            sheet_name = report.__name__
            worksheet = workbook.create_sheet(title=sheet_name)

            worksheet.append([results[2]])  # Write headers or summary data
            worksheet.append([results[1]])  # Write data

        else:
            # Handle case for table results (3 elements)
            sheet_name = report.__name__
            worksheet = workbook.create_sheet(title=sheet_name)

            # Write headers
            worksheet.append(results[2])

            # Write data
            for entry in results[1]:
                worksheet.append(entry)

    # Save the workbook to the in-memory stream
    workbook.save(output)
    output.seek(0)  # Move to the beginning of the stream

    # Return the in-memory stream to be used by Streamlit for downloading
    return output , wb_name


