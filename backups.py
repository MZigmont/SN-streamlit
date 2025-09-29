from datetime import datetime

def create_backup(tablename, conn):
    c = conn.cursor()
    # Generate table name with datestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_table = f"backup_{tablename}_{timestamp}"

    make_backup_table = f"""CREATE TABLE {new_table} AS
                    SELECT * FROM {tablename};"""
    c.execute(make_backup_table)
    return new_table

def delete_backup(tablename, conn):
    c = conn.cursor()
    if "backup_" in tablename:
        c.execute(f"""DROP TABLE {tablename}""")
    else:
        raise ValueError(f"Table {tablename} is not a backup table")
    return

def restore_backup(live_table, restoring_table, conn):
    c = conn.cursor()
    if "backup_" in restoring_table and "backup_" not in live_table:
        restore_backup_table = f"""
        -- Disable foreign key checks
        PRAGMA foreign_keys = OFF;
                        
        DELETE FROM {live_table};
        INSERT INTO {live_table}
        SELECT * FROM {restoring_table};

        -- Re-enable foreign key checks
        PRAGMA foreign_keys = ON;"""
        c.executescript(restore_backup_table)
    else:
        raise ValueError(f"Live Table {live_table} is a backup or Restoring Table {restoring_table} is not a backup")
    return