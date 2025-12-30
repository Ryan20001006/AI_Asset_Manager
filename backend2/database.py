#負責資料庫連線
import sqlite3
from config import settings

def get_db_connection():
    return sqlite3.connect(settings.DB_NAME)

def create_fundamental_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS CompanyInfo (
        sno INTEGER PRIMARY KEY AUTOINCREMENT,
        Stock_Id TEXT, QueryDate DATE, DataKey TEXT, DataValue TEXT,
        UNIQUE(Stock_Id, DataKey, QueryDate)
    );''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS FinancialStatements (
        sno INTEGER PRIMARY KEY AUTOINCREMENT,
        Stock_Id TEXT, StatementType TEXT, Item TEXT, ReportDate DATE, Value REAL,
        UNIQUE(Stock_Id, StatementType, Item, ReportDate)
    );''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS FinancialRatios (
        sno INTEGER PRIMARY KEY AUTOINCREMENT,
        Stock_Id TEXT, ReportYear INT, Category TEXT, RatioName TEXT, RatioValue REAL, Formula TEXT,
        UNIQUE(Stock_Id, ReportYear, RatioName)
    );''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS AIReports (
        Stock_Id TEXT,
        ReportDate DATE,
        NewsAnalysis TEXT,
        CompetitorAnalysis TEXT,
        PRIMARY KEY (Stock_Id, ReportDate)
    );''')

    conn.commit()
    conn.close()
    pass