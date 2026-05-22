CREATE TABLE donors(
donor_id_pk integer primary key autoincrement,
donor_reporting_name text NOT NULL,
donor_last_name text,
donor_first_name text,
donor_middle_name text,
donor_class_year int
);
