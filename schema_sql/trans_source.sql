CREATE TABLE trans_source( 
source_id_pk integer primary key autoincrement,
source_name text
);
INSERT INTO "trans_source" ("source_id_pk", "source_name") VALUES (1, 'BluePay');
INSERT INTO "trans_source" ("source_id_pk", "source_name") VALUES (2, 'PayPal');
INSERT INTO "trans_source" ("source_id_pk", "source_name") VALUES (3, 'Manual');;
