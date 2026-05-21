# TO DO: 4/7/2025 - do a few validation queries:
#   DONE:   check for duplicate IDs in raw data
#   DONE:   check that every valid transaction in raw data was accounted for
#   DONE:   check that donations has no duplicate IDs
#   DONE:   check that no two donors in temp_donors has exact first and last name
#   DONE:   check that no duplicate donors for whatever definition in donors
#   DONE:   check that there are no duplicate aliases, e.g. same value in each field


from dataclasses import dataclass

import pandas as pd

import constants


@dataclass(frozen=True)
class ValidationQuery:
    short_name: str
    table_name: str
    query: str

    def execute(self, conn: "pd.io.sql.SQLDatabase") -> pd.DataFrame:
        return pd.read_sql_query(self.query, conn)


def _run_queries(conn, queries: list[ValidationQuery]) -> dict[str, pd.DataFrame]:
    return {query.short_name: query.execute(conn) for query in queries}


def _run_agnostic(
    conn,
    raw_data_query: ValidationQuery,
) -> dict[str, pd.DataFrame]:
    return _run_queries(
        conn,
        [
            NO_DUPES_TRANS_ID,
            raw_data_query,
            NO_DUPES_DONATIONS,
            NO_DUPES_TEMP_DONORS,
            NO_DUPES_DONORS,
            NO_DUPES_TEMP_ALIASES,
            NO_DUPES_ALIASES,
        ],
    )


NO_DUPES_TRANS_ID = ValidationQuery(
    short_name="Duplicate transaction IDs in temp donations",
    table_name=constants.TEMP_DONATIONS_TABLE,
    query=f"""
        SELECT source_trans_id, COUNT(*) AS count
        FROM {constants.TEMP_DONATIONS_TABLE}
        GROUP BY source_trans_id
        HAVING COUNT(*) > 1""",
)

NO_DUPES_DONATIONS = ValidationQuery(
    short_name="Duplicate transaction IDs in donations",
    table_name=constants.DONATIONS_TABLE,
    query=f"""
        SELECT source_trans_id, source_name, COUNT(*)
        FROM {constants.DONATIONS_TABLE}
        LEFT JOIN {constants.TRANS_SOURCE_TABLE}
        ON
            {constants.DONATIONS_TABLE}.trans_source_id_fk = {constants.TRANS_SOURCE_TABLE}.source_id_pk
        WHERE
            {constants.TRANS_SOURCE_TABLE}.source_id_pk <> 3
        GROUP BY source_trans_id, trans_source_id_fk
        HAVING COUNT(*) > 1""",
)

NO_DUPES_TEMP_DONORS = ValidationQuery(
    short_name="Duplicate donor names in temp donors",
    table_name=constants.TEMP_DONORS_TABLE,
    query=f"""
        SELECT donor_last_name, donor_first_name, COUNT(*)
        FROM {constants.TEMP_DONORS_TABLE}
        GROUP BY donor_last_name, donor_first_name
        HAVING COUNT(*) > 1""",
)

NO_DUPES_DONORS = ValidationQuery(
    short_name="Duplicate donors in donors",
    table_name=constants.DONORS_TABLE,
    query=f"""
        SELECT donor_reporting_name, donor_class_year, COUNT(*)
        FROM {constants.DONORS_TABLE}
        GROUP BY donor_reporting_name, donor_class_year
        HAVING COUNT(*) > 1""",
)

NO_DUPES_TEMP_ALIASES = ValidationQuery(
    short_name="Duplicate aliases in temp aliases",
    table_name=constants.TEMP_ALIASES_TABLE,
    query=f"""
        SELECT GROUP_CONCAT(alias_id_pk) AS duplicate_ids, alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state, COUNT(*)
        FROM {constants.TEMP_ALIASES_TABLE}
        GROUP BY alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state
        HAVING COUNT(*) > 1""",
)

NO_DUPES_ALIASES = ValidationQuery(
    short_name="Duplicate aliases in aliases",
    table_name=constants.ALIASES_TABLE,
    query=f"""
        SELECT GROUP_CONCAT(alias_id_pk) AS duplicate_ids, alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state, COUNT(*)
        FROM {constants.ALIASES_TABLE}
        GROUP BY alias_first_name, alias_email, alias_phone, alias_address_1, alias_address_2, alias_city, 
            alias_zip, alias_country, alias_middle_name, alias_last_name, alias_state
        HAVING COUNT(*) > 1""",
)

NO_DUPES_RAW_DATA_BLUEPAY = ValidationQuery(
    short_name="Duplicate transaction IDs in raw data",
    table_name=constants.BLUEPAY_RAW_TABLE_NAME,
    query=f"""
        SELECT {constants.BLUEPAY_TRANS_ID_FIELD}, COUNT(*) AS count
        FROM {constants.BLUEPAY_RAW_TABLE_NAME}
        GROUP BY {constants.BLUEPAY_TRANS_ID_FIELD}
        HAVING COUNT(*) > 1""",
)

NO_DUPES_RAW_DATA_CARDPOINTE = ValidationQuery(
    short_name="Duplicate transaction IDs in raw data",
    table_name=constants.CARDPOINTE_RAW_TABLE_NAME,
    query=f"""
        SELECT {constants.CARDPOINTE_TRANS_ID_FIELD}, COUNT(*) AS count
        FROM {constants.CARDPOINTE_RAW_TABLE_NAME}
        GROUP BY {constants.CARDPOINTE_TRANS_ID_FIELD}
        HAVING COUNT(*) > 1""",
)

NO_DUPES_RAW_DATA_PAYPAL = ValidationQuery(
    short_name="Duplicate transaction IDs in raw data",
    table_name=constants.PAYPAL_RAW_TABLE_NAME,
    query=f"""
        SELECT {constants.PAYPAL_TRANS_ID_FIELD}, COUNT(*) AS count
        FROM {constants.PAYPAL_RAW_TABLE_NAME}
        GROUP BY {constants.PAYPAL_TRANS_ID_FIELD}
        HAVING COUNT(*) > 1""",
)

UNACCOUNTED_BLUEPAY = ValidationQuery(
    short_name="Unaccounted Bluepay transactions",
    table_name=constants.BLUEPAY_RAW_TABLE_NAME,
    query=f"""
        SELECT rbd.*
        FROM {constants.BLUEPAY_RAW_TABLE_NAME} as rbd
        LEFT JOIN {constants.TEMP_DONATIONS_TABLE} td
            on (rbd.id = td.source_trans_id
            and td.trans_source_id_fk = 1) 
            or ('B' || rbd.id = td.source_trans_id 
            and td.trans_source_id_fk = 4)
        LEFT JOIN {constants.DONATIONS_TABLE} d
            on (rbd.id = d.source_trans_id
            and d.trans_source_id_fk = 1) 
            or ('B' || rbd.id = d.source_trans_id 
            and d.trans_source_id_fk = 4)       
        where NOT (rbd.trans_type in ('AUTH') or
            rbd.amount = 0 or
            rbd.status in ('0', 'E')) and
            td.source_trans_id is NULL and
            d.source_trans_id is NULL""",
)

UNACCOUNTED_CARDPOINTE = ValidationQuery(
    short_name="Unaccounted Cardpointe transactions",
    table_name=constants.CARDPOINTE_RAW_TABLE_NAME,
    query=f"""
        SELECT rcd.*
        FROM {constants.CARDPOINTE_RAW_TABLE_NAME} as rcd
        LEFT JOIN {constants.TEMP_DONATIONS_TABLE} td
            ON
            (rcd.{constants.CARDPOINTE_TRANS_ID_FIELD} = td.source_trans_id
            and td.trans_source_id_fk = 4) 
            or (rcd.{constants.CARDPOINTE_TRANS_ID_FIELD} = 'B' || td.source_trans_id 
            and td.trans_source_id_fk = 1)
        LEFT JOIN {constants.DONATIONS_TABLE} d
            ON
            (rcd.{constants.CARDPOINTE_TRANS_ID_FIELD} = d.source_trans_id
            and d.trans_source_id_fk = 4) 
            or (rcd.{constants.CARDPOINTE_TRANS_ID_FIELD} = 'B' || d.source_trans_id 
            and d.trans_source_id_fk = 1)
        where td.source_trans_id is NULL and
            d.source_trans_id is NULL and
            NOT (rcd.amount = 0 or
            rcd.status in ('DECLINED', 'FAILED', 'VERIFIED') or
            rcd.method = 'VERIFY')
            """,
)

UNACCOUNTED_PAYPAL = ValidationQuery(
    short_name="Unaccounted PayPal transactions",
    table_name=constants.PAYPAL_RAW_TABLE_NAME,
    query=f"""
        SELECT rpd.*
        FROM {constants.PAYPAL_RAW_TABLE_NAME} as rpd
        LEFT JOIN {constants.TEMP_DONATIONS_TABLE} td
            ON
            td.source_trans_id = rpd.transaction_id
            and td.trans_source_id_fk = 2
        LEFT JOIN {constants.DONATIONS_TABLE} d
            ON
            rpd.transaction_id = d.source_trans_id
            and d.trans_source_id_fk = 2
        where NOT (rpd.type in ('General Currency Conversion', 
                            'User Initiated Currency Conversion', 
                            'User Initiated Withdrawal') OR rpd.net = 0) AND
            td.source_trans_id is NULL AND
            d.source_trans_id is NULL""",
)

# validating tables regardless of bluepay/paypal source
def validate_bluepay(conn):
    # this query checks for transactions in the raw data that should have made it into the temp_donations table
    # but did not.  query returns rows in raw data that are unaccounted for, bluepay specific code

    validation_dict = _run_agnostic(conn, NO_DUPES_RAW_DATA_BLUEPAY)
    validation_dict.update(_run_queries(conn, [UNACCOUNTED_BLUEPAY]))
    return validation_dict

def validate_cardpointe(conn):
    # this query checks for transactions in the raw data that should have made it into the temp_donations table
    # but did not.  query returns rows in raw data that are unaccounted for, cardpointe specific code

    validation_dict = _run_agnostic(conn, NO_DUPES_RAW_DATA_CARDPOINTE)
    all_unaccounted_trans = UNACCOUNTED_CARDPOINTE
    # BELOW DEFINES WHAT WE THINK IS INVALID AS OF 3/2/26
    # amount = 0 is invalid
    # status = 'DECLINED' or 'FAILED' is invalid
    # status = 'VERIFIED' is invalid
    # method = 'VERIFY' is invalid

    validation_dict.update(_run_queries(conn, [all_unaccounted_trans]))
    return validation_dict

def validate_paypal(conn):
    # this query checks for transactions in the raw data that should have made it into the temp_donations table
    # but did not.  query returns rows in raw data that are unaccounted for, paypal specific code

    validation_dict = _run_agnostic(conn, NO_DUPES_RAW_DATA_PAYPAL)
    validation_dict.update(_run_queries(conn, [UNACCOUNTED_PAYPAL]))
    return validation_dict

