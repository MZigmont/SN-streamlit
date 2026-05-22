CREATE TABLE donations(
my_trans_id_pk integer primary key autoincrement,
source_trans_id text,
date_time numeric NOT NULL,
alias_id_fk int NOT NULL, --foreign key
trans_source_id_fk int NOT NULL, --foreign key
donation_currrency text NOT NULL,
donation_gross_amt real NOT NULL,
fee_currency text,
fee_amt real,
conversion_rate real,
donation_gross_USD real NOT NULL,
fee_USD real,
donation_net_USD real NOT NULL,
constraint alias_id_fk foreign key (alias_id_fk) references aliases(alias_id_pk),
constraint trans_source_id_fk foreign key (trans_source_id_fk) references trans_source(source_id_pk)
);
