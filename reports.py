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

def run_all_reports(fromdate, todate, conn):
    # List of report functions
    my_report_list = [
                tot_gr_USD_don,
                tot_gr_USD_dons_by_don,
                # tot_net_dons_p_yr,
                # ct_don,
                # don_b_cls,
                # dons_b_cls,
                # dons_in_period
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

#@title Total Net Donations By Year (Fxn 4)


# total net donations per year
def tot_net_dons_p_yr(startdate, enddate):

  conn, c = connect()

  donations_by_year  = c.execute("""
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
    #pseudo initialize each row
    combined_donations_by_year.append(["","","",""])
    for element in range(len(donations_by_year[row])):
      combined_donations_by_year[row][element] = donations_by_year[row][element]
    for element in range(len(donations_by_fiscal_year[row])):
      combined_donations_by_year[row][element + 2 ] = donations_by_fiscal_year[row][element]

  if len(donations_by_fiscal_year) == len(donations_by_year) + 1 :
    #pseudo initialize the last row
    combined_donations_by_year.append(["","","",""])
    combined_donations_by_year[row + 1][0] = ""
    combined_donations_by_year[row + 1][1] = ""
    combined_donations_by_year[row + 1][2] = donations_by_fiscal_year[row + 1][0]
    combined_donations_by_year[row + 1][3] = donations_by_fiscal_year[row + 1][1]
  else:
    pass

  conn.close()

  # 1 means table returned
  return (1, combined_donations_by_year , ['Year','sum(donation_net_USD)','Fiscal Year','sum(donation_net_USD)'])


# def run_all_reports(fromdate, todate, conn):
#     my_report_list = [
#                 tot_gr_USD_don,
#                 tot_gr_USD_dons_by_don
#                 # tot_net_dons_p_yr,
#                 # ct_don,
#                 # don_b_cls,
#                 # dons_b_cls,
#                 # dons_in_period
#                 ]

#     # Create a workbook
#     report_begin_date = fromdate[0:10]
#     report_run_date = todate[0:10]
#     wb_name = 'sig_nu_' + report_begin_date + '_' + report_run_date + '.xlsx'
#     workbook = xw.Workbook(wb_name)

#     for reports in my_report_list:
#         results = (reports(fromdate,todate, conn))
#         if results[0] == 0:
#             # do single stuff here

#             # create worksheet
#             sheet_name = reports.__name__
#             worksheet = workbook.add_worksheet(sheet_name)

#             # put data in sheet
#             # Start from the first cell. Rows and columns are zero indexed.
#             row = 0
#             col = 0
#             worksheet.write(row, col, results[2])
#             worksheet.write(row+1 , col, results[1])

#         else:
#             # do table stuff here
#             # create worksheet
#             sheet_name = reports.__name__
#             worksheet = workbook.add_worksheet(sheet_name)

#             # put data in sheet
#             # Start from the first cell. Rows and columns are zero indexed.
#             row = 0

#             # PUT HEADERS IN BEFORE LOOPING
#             for col, element in enumerate(results[2]):
#                 worksheet.write(row,col,element)

#             for row, entry in enumerate(results[1]):
#                 for col, item in enumerate(entry):
#                     worksheet.write(row+1, col, item)
 
#     workbook.close()