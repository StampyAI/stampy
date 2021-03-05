import sqlite3

###########################################################################
#   SQLite Database Wrapper
###########################################################################


class Database:
    def __init__(self, name=None):
        self.connected = False
        self.conn = None
        self.cursor = None

        if name:
            self.open(name)

    def open(self, name):
        print("Connecting to database: " + name)
        try:
            self.conn = sqlite3.connect(name)
            self.cursor = self.conn.cursor()
            self.connected = True

        except sqlite3.Error as e:
            print("Error connecting to database!", e)

    def close(self):
        if self.conn:
            self.connected = False
            self.conn.commit()
            self.cursor.close()
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.connected = False
        self.close()

    def get(self, table, columns, limit=None):
        query = "SELECT {0} from {1}".format(columns, table)
        # Limit goes at the end...
        if limit is not None:
            query += " LIMIT {0}".format(limit)
        query += ";"
        self.cursor.execute(query)

        return self.cursor.fetchall()

    def get_last(self, table, columns):
        return self.get(table, columns, limit=1)[0]

    def query(self, sql, args=None):
        if args:
            self.cursor.execute(sql, args)
        else:
            self.cursor.execute(sql)
        return self.cursor.fetchall()

    def commit(self):
        self.conn.commit()


"""
    def insert(self,table,columns,data):
        query = "INSERT INTO {0} ({1}) VALUES ({2});".format(table,columns,data)
        self.cursor.execute(query)
        self.conn.commit()

    def upsert(self,table,columns,data,update):
        query = "INSERT INTO {0} ({1}) VALUES ({2});".format(table,columns,data)
        query+=  "ON CONFLICT(name) DO UPDATE SET {0}".format(update)
        self.cursor.execute(query)
        self.conn.commit()
"""
