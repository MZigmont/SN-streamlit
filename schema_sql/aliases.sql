CREATE TABLE aliases(
alias_id_pk integer primary key autoincrement,
donor_id_fk int,--foreign key
alias_first_name text,
alias_email text,
alias_phone text,
alias_address_1 text,
alias_address_2 text,
alias_city text,
alias_zip text,
alias_country text, alias_middle_name TEXT, alias_last_name TEXT, alias_state TEXT,
constraint donor_id_fk foreign key (donor_id_fk) references donors(donor_id_pk)
);
