#負責資料庫連線
import sqlite3
from config import settings

def get_db_connection():
    return sqlite3.connect(settings.DB_NAME)

def create_fundamental_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 公司基本資訊
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS CompanyInfo (
        sno INTEGER PRIMARY KEY AUTOINCREMENT,
        Stock_Id TEXT, QueryDate DATE, DataKey TEXT, DataValue TEXT,
        UNIQUE(Stock_Id, DataKey, QueryDate)
    );''')
    
    # 2. 財報數據
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS FinancialStatements (
        sno INTEGER PRIMARY KEY AUTOINCREMENT,
        Stock_Id TEXT, StatementType TEXT, Item TEXT, ReportDate DATE, Value REAL,
        UNIQUE(Stock_Id, StatementType, Item, ReportDate)
    );''')
    
    # 3. 財務比率
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS FinancialRatios (
        sno INTEGER PRIMARY KEY AUTOINCREMENT,
        Stock_Id TEXT, ReportYear INT, Category TEXT, RatioName TEXT, RatioValue REAL, Formula TEXT,
        UNIQUE(Stock_Id, ReportYear, RatioName)
    );''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS AI_Analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Stock_Id TEXT,
        ReportDate DATE,
        AnalysisContent TEXT,
        CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(Stock_Id, ReportDate)
    );''')

    conn.commit()
    conn.close()
    print("✅ 資料庫表格初始化完成 (Standardized tables created)")