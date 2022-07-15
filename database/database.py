from structlog import get_logger
from threading import RLock
import sqlite3

###########################################################################
#   SQLite Database Wrapper
###########################################################################
log = get_logger()


class Database:
    def __init__(self, name=None):
        self.class_name = self.__class__.__name__
        self.connected = False
        self.conn = None
        self.cursor = None
        self.name = name
        self.lock = RLock()

    def open(self):
        name = self.name
        if name:
            try:
                self.conn = sqlite3.connect(name)
                self.cursor = self.conn.cursor()
                self.connected = True
                return
            except sqlite3.Error as e:
                log.error(self.class_name, error="Error connecting to database!", exception=e)
        log.error(self.class_name, error="Database not specified! Cannot open!")

    def close(self):
        if self.conn:
            self.conn.commit()
            self.cursor.close()
            self.conn.close()
        self.connected = False
        self.lock.release()

    def try_open(self):
        self.lock.acquire()
        while not self.connected:
            self.open()

    def __enter__(self):
        try:
            self.try_open()
            return self
        except sqlite3.Error:
            self.close()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def query(self, sql, args=None):
        self.try_open()
        if args is not None:
            self.cursor.execute(sql, args)
        else:
            self.cursor.execute(sql)
        data = self.cursor.fetchall()
        self.close()

        return data

    def commit(self):
        """
        This now commits with every query so this function is not necessary.
        Changed to pass to not break existing code.
        """
        pass


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
