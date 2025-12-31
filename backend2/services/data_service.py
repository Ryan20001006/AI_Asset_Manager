import requests
import datetime as dt
import pandas as pd
import numpy as np
import time
import json
import traceback 
from database import get_db_connection
from config import settings

def safe_float(val, debug_name=""):
    """防止 'None', 'null' 等字串導致 crash"""
    if val is None: return 0.0
    s_val = str(val).strip()
    if s_val.lower() in ['none', 'null', '-', '']: return 0.0
    try:
        return float(s_val)
    except:
        return 0.0

AV_MAPPING = {
    "totalRevenue": "Total Revenue",
    "grossProfit": "Gross Profit",
    "operatingIncome": "Operating Income",
    "netIncome": "Net Income",
    "costOfRevenue": "Cost Of Revenue",
    "interestExpense": "Interest Expense",
    "ebitda": "EBITDA",
    "reportedEPS": "Basic EPS",
    "totalAssets": "Total Assets",
    "totalCurrentAssets": "Current Assets",
    "totalCurrentLiabilities": "Current Liabilities",
    "totalShareholderEquity": "Total Equity Gross Minority Interest",
    "inventory": "Inventory",
    "currentNetReceivables": "Accounts Receivable",
    "cashAndCashEquivalentsAtCarryingValue": "Cash And Cash Equivalents",
    "operatingCashflow": "Operating Cash Flow",
    "capitalExpenditures": "Capital Expenditure",
    "dividendPayout": "Cash Dividends Paid"
}

def download_and_store_fundamentals(stock_id):
    print(f"📥 [Backend 2] Alpha Vantage: 下載 {stock_id} (含股價/5年財報)...")
    conn = get_db_connection()
    api_key = settings.ALPHA_VANTAGE_API_KEY
    
    if not api_key:
        print("❌ 錯誤: 未設定 ALPHA_VANTAGE_API_KEY")
        return False

    try:
        cursor = conn.cursor()
        today = dt.date.today().strftime('%Y-%m-%d')
        url_quote = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={stock_id}&apikey={api_key}"
        r_quote = requests.get(url_quote).json()
        current_price = safe_float(r_quote.get("Global Quote", {}).get("05. price"))
        
        info_data = []
        if current_price > 0:
            info_data.append((stock_id, today, 'currentPrice', str(current_price)))
        url_overview = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={stock_id}&apikey={api_key}"
        r_overview = requests.get(url_overview).json()
        
        overview_map = {
            'Symbol': 'symbol', 'Name': 'longName', 'Industry': 'industry', 
            'Sector': 'sector', 'PERatio': 'trailingPE', 'PEG': 'trailingPegRatio',
            'BookValue': 'priceToBook', 'DividendYield': 'dividendYield',
            'EPS': 'trailingEps', 'ProfitMargin': 'profitMargins',
            'OperatingMargin': 'operatingMargins', 'ReturnOnEquityTTM': 'returnOnEquity',
            'ReturnOnAssetsTTM': 'returnOnAssets',
            'MarketCapitalization': 'marketCap'
        }
        
        for av_key, db_key in overview_map.items():
            val = r_overview.get(av_key)
            if val and str(val) != 'None':
                info_data.append((stock_id, today, db_key, str(val)))
        
        rev_ttm = safe_float(r_overview.get('RevenueTTM'))
        gp_ttm = safe_float(r_overview.get('GrossProfitTTM'))
        if rev_ttm != 0:
            info_data.append((stock_id, today, 'grossMargins', str(gp_ttm / rev_ttm)))

        cursor.executemany('INSERT OR IGNORE INTO CompanyInfo (Stock_Id, QueryDate, DataKey, DataValue) VALUES (?, ?, ?, ?)', info_data)

        functions = {'Income': 'INCOME_STATEMENT', 'BalanceSheet': 'BALANCE_SHEET', 'CashFlow': 'CASH_FLOW'}
        all_stmt_data = []

        for stmt_type, func_name in functions.items():
            url = f"https://www.alphavantage.co/query?function={func_name}&symbol={stock_id}&apikey={api_key}"
            r = requests.get(url).json()
            print(f"🔍 [{stmt_type}] API 回應: {str(r)[:200]}...")
            time.sleep(1) # API Rate Limit 保護
            
            reports = r.get('annualReports', [])
            if not reports: continue
                
            for report in reports:
                report_date = report.get('fiscalDateEnding')
                if stmt_type == 'BalanceSheet':
                    short = safe_float(report.get('shortTermDebt'))
                    long_d = safe_float(report.get('longTermDebt'))
                    total_debt = short + long_d
                    cash = safe_float(report.get('cashAndCashEquivalentsAtCarryingValue'))
                    equity = safe_float(report.get('totalShareholderEquity'))
                    
                    all_stmt_data.append((stock_id, stmt_type, 'Total Debt', report_date, total_debt))
                    all_stmt_data.append((stock_id, stmt_type, 'Net Debt', report_date, total_debt - cash))
                    all_stmt_data.append((stock_id, stmt_type, 'Invested Capital', report_date, equity + total_debt - cash))

                if stmt_type == 'CashFlow':
                    op = safe_float(report.get('operatingCashflow'))
                    cap = safe_float(report.get('capitalExpenditures'))
                    all_stmt_data.append((stock_id, stmt_type, 'Free Cash Flow', report_date, op - cap))
                for av_key, val in report.items():
                    if av_key in AV_MAPPING:
                        clean_val = safe_float(val)
                        all_stmt_data.append((stock_id, stmt_type, AV_MAPPING[av_key], report_date, clean_val))

        if all_stmt_data:
            cursor.executemany('INSERT OR IGNORE INTO FinancialStatements (Stock_Id, StatementType, Item, ReportDate, Value) VALUES (?, ?, ?, ?, ?)', all_stmt_data)
            conn.commit()
            print("✅ Alpha Vantage 數據下載完成")
            return True
        return False

    except Exception as e:
        print(f"Backend 2 下載失敗: {e}")
        traceback.print_exc()
        return False
    finally:
        conn.close()

def get_dataframes_from_db(stock_id, conn):
    query = "SELECT StatementType, Item, ReportDate, Value FROM FinancialStatements WHERE Stock_Id = ?"
    df_all = pd.read_sql(query, conn, params=(stock_id,))
    
    if df_all.empty:
        return None, None, None

    def get_pivot(stmt_type):
        d = df_all[df_all['StatementType'] == stmt_type]
        if d.empty: return pd.DataFrame()
        p = d.pivot_table(index='ReportDate', columns='Item', values='Value')
        p.index = pd.to_datetime(p.index).year
        return p.sort_index(ascending=False)

    return get_pivot('Income'), get_pivot('BalanceSheet'), get_pivot('CashFlow')

def calculate_financial_ratios(stock_id, conn):
    print(f"🧮 [Backend 2] 計算 {stock_id} 財務比率 (DB Mode)...")
    
    income, balance, cash = get_dataframes_from_db(stock_id, conn)
    if income is None or balance is None: 
        return False

    ratios = []
    years = income.index
    
    df_info = pd.read_sql("SELECT DataKey, DataValue FROM CompanyInfo WHERE Stock_Id = ?", conn, params=(stock_id,))
    info_dict = dict(zip(df_info['DataKey'], df_info['DataValue']))
    current_price = safe_float(info_dict.get('currentPrice', 0))

    for year in years:
        try:
            def get_val(df, item):
                if df is not None and item in df.columns and year in df.index:
                    return safe_float(df.loc[year, item])
                return 0.0
            
            rev = get_val(income, 'Total Revenue')
            net_income = get_val(income, 'Net Income')
            gross_profit = get_val(income, 'Gross Profit')
            op_income = get_val(income, 'Operating Income')
            cost_of_rev = get_val(income, 'Cost Of Revenue')
            interest = get_val(income, 'Interest Expense')
            ebitda = get_val(income, 'EBITDA')
            eps = get_val(income, 'Basic EPS')
            
            equity = get_val(balance, 'Total Equity Gross Minority Interest')
            total_assets = get_val(balance, 'Total Assets')
            total_debt = get_val(balance, 'Total Debt')
            net_debt = get_val(balance, 'Net Debt')
            inventory = get_val(balance, 'Inventory')
            receivables = get_val(balance, 'Accounts Receivable')
            curr_assets = get_val(balance, 'Current Assets')
            curr_liab = get_val(balance, 'Current Liabilities')
            inv_cap = get_val(balance, 'Invested Capital')
            
            fcf = get_val(cash, 'Free Cash Flow')

            if equity: ratios.append((stock_id, year, 'Profitability', 'Return on Equity (ROE)', net_income / equity, 'Net Income / Equity'))
            if rev:
                ratios.append((stock_id, year, 'Profitability', 'Gross Margin', gross_profit / rev, 'Gross Profit / Revenue'))
                ratios.append((stock_id, year, 'Profitability', 'Operating Margin', op_income / rev, 'Operating Income / Revenue'))
                ratios.append((stock_id, year, 'Profitability', 'Net Profit Margin', net_income / rev, 'Net Income / Revenue'))

            prev_year = year - 1
            if prev_year in years:
                prev_rev = get_val(income, 'Total Revenue')
                prev_ni = get_val(income, 'Net Income')
                prev_eps = get_val(income, 'Basic EPS')
                prev_fcf = get_val(cash, 'Free Cash Flow')

                if prev_rev: ratios.append((stock_id, year, 'Growth', 'Revenue Growth', (rev - prev_rev)/abs(prev_rev), 'YoY'))
                if prev_ni: ratios.append((stock_id, year, 'Growth', 'Net Income Growth', (net_income - prev_ni)/abs(prev_ni), 'YoY'))
                if prev_eps: ratios.append((stock_id, year, 'Growth', 'EPS Growth', (eps - prev_eps)/abs(prev_eps), 'YoY'))
                if prev_fcf: ratios.append((stock_id, year, 'Growth', 'FCF Growth', (fcf - prev_fcf)/abs(prev_fcf), 'YoY'))

            if equity: ratios.append((stock_id, year, 'Leverage', 'Debt-to-Equity Ratio', total_debt / equity, 'Total Debt / Equity'))
            if curr_liab: ratios.append((stock_id, year, 'Leverage', 'Current Ratio', curr_assets / curr_liab, 'CA / CL'))
            if interest: ratios.append((stock_id, year, 'Leverage', 'Interest Coverage Ratio', op_income / interest, 'EBIT / Interest'))
            if ebitda: ratios.append((stock_id, year, 'Leverage', 'Net Debt / EBITDA', net_debt / ebitda, 'Net Debt / EBITDA'))

            if total_assets: ratios.append((stock_id, year, 'Efficiency', 'Asset Turnover', rev / total_assets, 'Revenue / Total Assets'))
            if inventory: ratios.append((stock_id, year, 'Efficiency', 'Inventory Turnover', cost_of_rev / inventory, 'COGS / Inventory'))
            if receivables: ratios.append((stock_id, year, 'Efficiency', 'Receivables Turnover', rev / receivables, 'Revenue / AR'))
            
            if inv_cap:
                nopat = op_income * 0.75 
                ratios.append((stock_id, year, 'Return', 'ROIC', nopat / inv_cap, 'NOPAT / Invested Capital'))

        except Exception as e:
            print(f"計算 {year} 錯誤: {e}")
            continue

    if ratios:
        cursor = conn.cursor()
        cursor.executemany('INSERT OR REPLACE INTO FinancialRatios (Stock_Id, ReportYear, Category, RatioName, RatioValue, Formula) VALUES (?, ?, ?, ?, ?, ?)', ratios)
        conn.commit()
        return True
    
    return False

def search_symbol_alpha_vantage(keyword: str):
    print(f"🔍 [Backend 2] Search: {keyword}")
    api_key = settings.ALPHA_VANTAGE_API_KEY
    if not api_key: return []
    try:
        url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={keyword}&apikey={api_key}"
        res = requests.get(url).json()
        raw = res.get("bestMatches", [])
        return [{
            "symbol": i.get("1. symbol"),
            "name": i.get("2. name"),
            "type": i.get("3. type"),
            "region": i.get("4. region"),
            "currency": i.get("8. currency")
        } for i in raw]
    except Exception as e:
        print(f"搜尋錯誤: {e}")
        return []


def get_competitor_dataframe_markdown(ticker_list, conn):
    if not ticker_list:
        return "無競爭對手數據"
    
    placeholders = ','.join(['?']*len(ticker_list))
    query = f"""
    SELECT Stock_Id, RatioName, RatioValue
    FROM FinancialRatios
    WHERE Stock_Id IN ({placeholders})
      AND ReportYear = (SELECT MAX(ReportYear) FROM FinancialRatios)
      AND RatioName IN ('Return on Equity (ROE)', 'Gross Margin', 'Net Profit Margin', 'Debt-to-Equity Ratio')
    """
    
    try:
        df = pd.read_sql(query, conn, params=ticker_list)
        if df.empty:
            return "資料庫中暫無競爭對手數據"
        pivot = df.pivot_table(index='Stock_Id', columns='RatioName', values='RatioValue')
        return pivot.to_markdown()
    except Exception as e:
        return f"無法產生比較表: {e}"

# ========================================================
# 7. [新增] 產生 AI Context String (這次補上的關鍵函式)
# ========================================================
def get_context_str(stock_id, conn):
    """
    彙整公司基本資料與最近 5 年的財務指標，轉成文字給 LLM 閱讀。
    """
    # 1. 讀取 Info
    cursor = conn.cursor()
    cursor.execute("SELECT DataKey, DataValue FROM CompanyInfo WHERE Stock_Id = ?", (stock_id,))
    info = {row[0]: row[1] for row in cursor.fetchall()}
    
    # 2. 讀取 Ratios
    query = "SELECT ReportYear, Category, RatioName, RatioValue FROM FinancialRatios WHERE Stock_Id = ? ORDER BY ReportYear DESC, Category"
    df = pd.read_sql(query, conn, params=(stock_id,))
    
    if df.empty:
        return f"No financial data available for {stock_id}."
        
    # 3. 組裝文字
    res = [f"=== Financial Analysis for {stock_id} ==="]
    if 'longName' in info: res.append(f"Company Name: {info['longName']}")
    if 'sector' in info: res.append(f"Sector: {info['sector']}")
    if 'industry' in info: res.append(f"Industry: {info['industry']}")
    if 'marketCap' in info: res.append(f"Market Cap: {info['marketCap']}")
    
    res.append("\n=== Key Financial Ratios (Historical) ===")
    
    years = sorted(df['ReportYear'].unique(), reverse=True)
    for year in years:
        res.append(f"\n[Year {year}]")
        year_data = df[df['ReportYear'] == year]
        
        # 依類別分群顯示
        for cat in year_data['Category'].unique():
            res.append(f"  * {cat}:")
            cat_data = year_data[year_data['Category'] == cat]
            for _, row in cat_data.iterrows():
                res.append(f"    - {row['RatioName']}: {row['RatioValue']:.4f}")
                
    return "\n".join(res)