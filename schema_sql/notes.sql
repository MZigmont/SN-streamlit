CREATE TABLE notes(
	notes_id_pk integer primary key autoincrement,
	my_trans_id_fk int,
	note text,
	constraint my_trans_id_fk foreign key (my_trans_id_fk) references donations(my_trans_id_pk)
);
