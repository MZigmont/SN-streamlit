from pathlib import Path
import sqlite3
import unittest

import pandas as pd

from ingestion.cardpointe_ingestion import ingest_data


class CardpointeIngestionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        schema_dir = Path(__file__).resolve().parents[1] / 'schema_sql'
        for table in ('donors', 'aliases', 'donations', 'trans_source'):
            self.conn.executescript((schema_dir / f'{table}.sql').read_text())
        self.conn.execute("""
            INSERT INTO donors (donor_id_pk, donor_reporting_name,
                                donor_first_name, donor_last_name)
            VALUES (1, 'Existing Donor', 'Existing', 'Donor')
        """)
        self.conn.execute("""
            INSERT INTO aliases (alias_id_pk, donor_id_fk, alias_first_name,
                                 alias_last_name, alias_email, alias_phone)
            VALUES (1, 1, 'Existing', 'Donor', 'existing@example.com', '5551234567')
        """)
        self.conn.commit()

    def row(self, **changes):
        row = {
            'Transaction #': 'R123', 'Date': '10/01/2026 8:00:00 AM',
            'Method': 'SALE', 'Status': 'PROCESSED', 'Amount': '$25.00',
            'Name': 'Existing Donor', 'Email': 'existing@example.com',
            'Phone Number': '5551234567', 'Address': '123 Example St',
            'City': 'Boston', 'State': 'MA', 'Zip': '02124',
        }
        row.update(changes)
        return row

    def test_existing_alias_matches_do_not_create_donors_or_aliases(self):
        # Exercise each supported way to recognize an existing donor.
        rows = [
            self.row(**{'Name': 'Changed Name', 'Phone Number': '5550000000'}),
            self.row(**{'Transaction #': 'R124', 'Name': 'Other Name',
                        'Email': 'other@example.com'}),
            self.row(**{'Transaction #': 'R125', 'Email': 'new@example.com',
                        'Phone Number': '5559999999'}),
        ]
        result = ingest_data(pd.DataFrame(rows), self.conn)
        self.assertTrue(result['temp_donors'].empty)
        self.assertTrue(result['temp_aliases'].empty)
        self.assertEqual(len(result['temp_donations']), 3)
        self.assertEqual(set(result['temp_donations']['alias_id_fk']), {1})
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM donors').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM aliases').fetchone()[0], 1)

    def test_unmatched_donor_is_still_created(self):
        result = ingest_data(pd.DataFrame([self.row(**{
            'Name': 'New Person', 'Email': 'new@example.com',
            'Phone Number': '5550000000',
        })]), self.conn)
        self.assertEqual(len(result['temp_donors']), 1)
        self.assertEqual(len(result['temp_aliases']), 1)
        self.assertEqual(len(result['temp_donations']), 1)
        self.assertEqual(result['temp_donations'].iloc[0]['query_type'], 'new donor')
        self.assertEqual(result['temp_aliases'].iloc[0]['donor_id_fk'], 2)

    def test_previously_imported_transactions_are_skipped(self):
        for source, stored_id, incoming_id in [(4, 'R123', 'R123'), (1, '123', 'B123')]:
            with self.subTest(source=source):
                self.conn.execute("""
                    INSERT INTO donations (source_trans_id, date_time, alias_id_fk,
                        trans_source_id_fk, donation_currrency, donation_gross_amt,
                        donation_gross_USD, donation_net_USD)
                    VALUES (?, '2026-10-01', 1, ?, 'USD', 25, 25, 25)
                """, (stored_id, source))
        result = ingest_data(pd.DataFrame([
            self.row(), self.row(**{'Transaction #': 'B123'}),
        ]), self.conn)
        for table in ('temp_donors', 'temp_aliases', 'temp_donations'):
            self.assertTrue(result[table].empty)


if __name__ == '__main__':
    unittest.main()
