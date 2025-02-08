from tinydb import TinyDB

class LocatorDetailsDB:
    _instance = None

    def __new__(cls, db_path=None):
        if cls._instance is None:
            if db_path is None:
                raise ValueError("A database path must be provided for the first instantiation.")
            cls._instance = super(LocatorDetailsDB, cls).__new__(cls)
            cls._instance._db = TinyDB(db_path)
        return cls._instance

    @property
    def db(self):
        return self._instance._db

class LocatorStatsDB:
    _instance = None

    def __new__(cls, db_path=None):
        if cls._instance is None:
            if db_path is None:
                raise ValueError("A database path must be provided for the first instantiation.")
            cls._instance = super(LocatorStatsDB, cls).__new__(cls)
            cls._instance._db = TinyDB(db_path)
        return cls._instance

    @property
    def db(self):
        return self._instance._db