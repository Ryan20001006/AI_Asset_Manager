#處理 Yahoo 資料、SQL
import os
import datetime as dt
import pandas as pd
import numpy as np
import yfinance as yf
import google.generativeai as genai
import pandas_datareader.data as web
import statsmodels.api as sm
import asyncio
from database import get_db_connection

def download_and_store_fundamentals(stock_id):
    print(f"📥 正在下載 {stock_id} 的數據...")
    conn = get_db_connection()
    try:
        stock = yf.Ticker(stock_id)
        if not stock.info: return False
        
        today = dt.date.today().strftime('%Y-%m-%d')
        cursor = conn.cursor()

        # 1. Info
        info_data = []
        for k, v in stock.info.items():
            info_data.append((stock_id, today, k, str(v)))
        cursor.executemany('INSERT OR IGNORE INTO CompanyInfo (Stock_Id, QueryDate, DataKey, DataValue) VALUES (?, ?, ?, ?)', info_data)

        # 2. Financials (不含 2025 預估)
        statements = {'Income': stock.financials, 'BalanceSheet': stock.balance_sheet, 'CashFlow': stock.cashflow}
        all_stmt_data = []
        
        for stmt_type, df in statements.items():
            if df.empty: continue
            
            df = df.reset_index().melt(id_vars='index', var_name='ReportDate', value_name='Value')
            df.rename(columns={'index': 'Item'}, inplace=True)
            df['ReportDate'] = pd.to_datetime(df['ReportDate']).dt.strftime('%Y-%m-%d')
            df = df.dropna(subset=['Value'])
            
            for row in df.itertuples(index=False):
                all_stmt_data.append((stock_id, stmt_type, row.Item, row.ReportDate, row.Value))
        
        if all_stmt_data:
            cursor.executemany('INSERT OR IGNORE INTO FinancialStatements (Stock_Id, StatementType, Item, ReportDate, Value) VALUES (?, ?, ?, ?, ?)', all_stmt_data)
        
        conn.commit()
        return True
    except Exception as e:
        print(f"下載錯誤: {e}")
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
    """
    (混合版) 優先使用 Yahoo 現成數據 (Info) 填補最新年份，歷史數據維持自算
    """
    print(f"--- [混合版] 正在分析 {stock_id} (優先對齊 Yahoo 現成數據) ---")
    df_income, df_balance, df_cashflow = get_dataframes_from_db(stock_id, conn)

    if df_income is None or df_balance is None or df_cashflow is None:
        return False

    ratios_to_save = []
    all_years = df_income.index.sort_values(ascending=False)
    cursor = conn.cursor()

    # 1. 提取 Yahoo Info (來自 CompanyInfo 表)
    # 我們抓取最新的一筆紀錄，轉成字典方便查詢
    cursor.execute("""
        SELECT DataKey, DataValue FROM CompanyInfo 
        WHERE Stock_Id = ? 
        ORDER BY QueryDate DESC
    """, (stock_id,))
    
    # 建立 Info 字典
    yahoo_info = {row[0]: row[1] for row in cursor.fetchall()}

    # 2. 定義 Yahoo Info 的對應表 (我們名稱 -> Yahoo Key)
    # 這些 Key 對應您截圖中的數據
    yahoo_mapping = {
        'Gross Margin': 'grossMargins',
        'Operating Margin': 'operatingMargins',       #
        'Net Profit Margin': 'profitMargins',         #
        'Return on Equity (ROE)': 'returnOnEquity',   #
        'Debt-to-Equity Ratio': 'debtToEquity',       #
        'Current Ratio': 'currentRatio',              #
        'Revenue Growth': 'revenueGrowth',            #
        'EPS Growth': 'earningsGrowth'
    }

    latest_year = all_years[0] if len(all_years) > 0 else 0

    for year in all_years:
        if year not in df_balance.index: continue

        try:
            # 小工具：從 DataFrame 取值
            def get_val(df, y, item): 
                return df.loc[y, item] if item in df.columns else np.nan

            # 先把基礎數據取出來 (計算公式仍需要用到部分數據)
            revenue = get_val(df_income, year, 'Total Revenue')
            gross_profit = get_val(df_income, year, 'Gross Profit')
            op_income = get_val(df_income, year, 'Operating Income')
            net_income = get_val(df_income, year, 'Net Income')
            total_equity = get_val(df_balance, year, 'Total Equity Gross Minority Interest')
            total_debt = get_val(df_balance, year, 'Total Debt')
            current_assets = get_val(df_balance, year, 'Current Assets')
            current_liabilities = get_val(df_balance, year, 'Current Liabilities')
            invested_capital = get_val(df_balance, year, 'Invested Capital')
            
            # --- [核心邏輯] 定義一個函式來決定用誰的數據 ---
            def get_ratio_value(ratio_name, calculated_value):
                """
                如果:
                1. 現在是最新一年 (year == latest_year)
                2. Yahoo Info 裡面有這個欄位
                3. Yahoo 的值有效
                => 則回傳 Yahoo 的值 (優先權高)
                => 否則回傳 calculated_value (自算值)
                """
                # 只有最新一年才嘗試用 Yahoo Info (因為 Info 是 TTM 或 Current)
                if year == latest_year and ratio_name in yahoo_mapping:
                    y_key = yahoo_mapping[ratio_name]
                    
                    # 檢查 Info 裡有沒有這個值且不是 'None'
                    if y_key in yahoo_info and yahoo_info[y_key] and yahoo_info[y_key] != 'None':
                        try:
                            y_val = float(yahoo_info[y_key])
                            
                            # [特別處理] 單位換算
                            # Yahoo 的 DebtToEquity 是 41.60 (代表 41.6%)，需轉成 0.416
                            if y_key == 'debtToEquity':
                                y_val = y_val / 100
                            
                            # Debug 訊息 (可選)
                            # print(f"   ★ {ratio_name}: 使用 Yahoo 數據 {y_val} 替代自算 {calculated_value}")
                            return y_val
                        except:
                            pass # 轉換失敗就繼續用算的
                
                return calculated_value

            # ==========================================
            # === 1. 獲利能力 ===
            # ==========================================

            # Gross Margin
            if revenue > 0 and not pd.isna(gross_profit):
                calc_val = gross_profit/revenue
                final_val = get_ratio_value('Gross Margin', calc_val)
                ratios_to_save.append((stock_id, year, 'profitability', 'Gross Margin', final_val, 'Hybrid'))

            # Operating Margin
            if revenue > 0 and not pd.isna(op_income):
                calc_val = op_income/revenue
                final_val = get_ratio_value('Operating Margin', calc_val)
                ratios_to_save.append((stock_id, year, 'profitability', 'Operating Margin', final_val, 'Hybrid'))

            # Net Profit Margin
            if revenue > 0 and not pd.isna(net_income):
                calc_val = net_income/revenue
                final_val = get_ratio_value('Net Profit Margin', calc_val)
                ratios_to_save.append((stock_id, year, 'profitability', 'Net Profit Margin', final_val, 'Hybrid'))
            
            # ROE (這就是您提到的 8.15% vs 8.9% 的關鍵修正)
            if total_equity > 0 and not pd.isna(net_income):
                calc_val = net_income/total_equity
                final_val = get_ratio_value('Return on Equity (ROE)', calc_val)
                ratios_to_save.append((stock_id, year, 'profitability', 'Return on Equity (ROE)', final_val, 'Hybrid'))

            # ROIC (Yahoo 通常只有 ROA，ROIC 還是得自算)
            if invested_capital > 0 and not pd.isna(net_income): 
                ratios_to_save.append((stock_id, year, 'profitability', 'ROIC', net_income/invested_capital, 'Net/IC'))

            # ==========================================
            # === 2. 槓桿與流動性 ===
            # ==========================================

            # Debt-to-Equity
            if total_equity > 0 and not pd.isna(total_debt):
                calc_val = total_debt/total_equity
                final_val = get_ratio_value('Debt-to-Equity Ratio', calc_val)
                ratios_to_save.append((stock_id, year, 'leverage', 'Debt-to-Equity Ratio', final_val, 'Hybrid'))
            
            # Current Ratio
            if current_liabilities > 0 and not pd.isna(current_assets):
                calc_val = current_assets/current_liabilities
                final_val = get_ratio_value('Current Ratio', calc_val)
                ratios_to_save.append((stock_id, year, 'leverage', 'Current Ratio', final_val, 'Hybrid'))

            # 利息保障倍數 (Yahoo Info 較少直接提供，維持自算)
            interest_expense = get_val(df_income, year, 'Interest Expense')
            if interest_expense > 0 and not pd.isna(op_income):
                ratios_to_save.append((stock_id, year, 'leverage', 'Interest Coverage Ratio', op_income/interest_expense, 'Op/Int'))

            # Net Debt / EBITDA (維持自算)
            ebitda = get_val(df_income, year, 'EBITDA')
            net_debt = get_val(df_balance, year, 'Net Debt')
            if ebitda > 0 and not pd.isna(net_debt):
                ratios_to_save.append((stock_id, year, 'leverage', 'Net Debt / EBITDA', net_debt/ebitda, 'NetDebt/EBITDA'))

            # ==========================================
            # === 3. 經營效率 (維持自算) ===
            # ==========================================
            # 這些項目 Yahoo Info 比較少直接給，維持自算確保趨勢圖連貫
            
            total_assets = get_val(df_balance, year, 'Total Assets')
            inventory = get_val(df_balance, year, 'Inventory')
            cost_of_revenue = get_val(df_income, year, 'Cost Of Revenue')
            accounts_receivable = get_val(df_balance, year, 'Accounts Receivable')

            if total_assets > 0 and not pd.isna(revenue):
                ratios_to_save.append((stock_id, year, 'efficiency', 'Asset Turnover', revenue/total_assets, 'Rev/Assets'))
            if inventory > 0 and not pd.isna(cost_of_revenue):
                ratios_to_save.append((stock_id, year, 'efficiency', 'Inventory Turnover', cost_of_revenue/inventory, 'Cost/Inv'))
            if accounts_receivable > 0 and not pd.isna(revenue):
                ratios_to_save.append((stock_id, year, 'efficiency', 'Receivables Turnover', revenue/accounts_receivable, 'Rev/AR'))

            # ==========================================
            # === 4. 成長性 (混合) ===
            # ==========================================
            
            prev_year = year - 1
            if prev_year in df_income.index:
                try:
                    prev_revenue = get_val(df_income, prev_year, 'Total Revenue')
                    prev_net_income = get_val(df_income, prev_year, 'Net Income')
                    prev_eps = get_val(df_income, prev_year, 'Basic EPS')
                    basic_eps = get_val(df_income, year, 'Basic EPS')
                    
                    # 營收成長
                    if prev_revenue > 0 and not pd.isna(revenue):
                        calc_val = (revenue - prev_revenue) / prev_revenue
                        # Yahoo 的 revenueGrowth 通常是 Quarterly YoY，可能與年度成長不同
                        # 但如果您希望看到截圖上的 -4.10%，這裡可以開啟混合模式
                        ratios_to_save.append((stock_id, year, 'growth', 'Revenue Growth', calc_val, 'Hybrid'))
                    
                    # 淨利成長
                    if prev_net_income != 0 and not pd.isna(net_income) and not pd.isna(prev_net_income):
                        growth = (net_income - prev_net_income) / abs(prev_net_income)
                        ratios_to_save.append((stock_id, year, 'growth', 'Net Income Growth', growth, '(NI - PrevNI)/abs(PrevNI)'))

                    # EPS 成長
                    if not pd.isna(basic_eps) and not pd.isna(prev_eps) and prev_eps != 0:
                        growth = (basic_eps - prev_eps) / abs(prev_eps)
                        ratios_to_save.append((stock_id, year, 'growth', 'EPS Growth', growth, '(EPS - PrevEPS)/abs(PrevEPS)'))

                    # FCF 成長 (維持自算)
                    if prev_year in df_cashflow.index:
                        prev_fcf = get_val(df_cashflow, prev_year, 'Free Cash Flow')
                        fcf = get_val(df_cashflow, year, 'Free Cash Flow')
                        if not pd.isna(fcf) and not pd.isna(prev_fcf) and prev_fcf != 0:
                            growth = (fcf - prev_fcf) / abs(prev_fcf)
                            ratios_to_save.append((stock_id, year, 'growth', 'FCF Growth', growth, '(FCF - PrevFCF)/abs(PrevFCF)'))
                            
                except KeyError: pass

        except KeyError:
            continue

    if ratios_to_save:
        cursor.executemany('''
        INSERT OR IGNORE INTO CalculatedRatios
            (Stock_Id, ReportYear, Category, RatioName, RatioValue, Formula)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', ratios_to_save)
        conn.commit()
        return True
    return False

def get_context_str(stock_id):
    conn = get_db_connection()
    try:
        df = pd.read_sql("SELECT ReportYear, RatioName, RatioValue FROM CalculatedRatios WHERE Stock_Id = ? ORDER BY ReportYear DESC, RatioName", conn, params=(stock_id,))
        if df.empty: return "No Data"
        df_pivot = df.pivot_table(index='RatioName', columns='ReportYear', values='RatioValue')
        return df_pivot.to_markdown()
    finally:
        conn.close()

def get_competitor_dataframe_markdown(stock_id):
    """
    功能：抓取目標公司與競爭對手的財務數據，並轉為 Markdown 表格
    """
    try:
        ticker = stock_id
        shell = yf.Ticker(ticker)
        info = shell.info
        if 'industryKey' not in info:
            return None, None
        
        target_list = [
            ticker, 
            info.get('dividendYield', 0), info.get('trailingPE', 0), info.get('priceToSalesTrailing12Months', 0),
            info.get('profitMargins', 0), info.get('priceToBook', 0), info.get('trailingEps', 0),
            info.get('enterpriseToEbitda', 0), info.get('currentRatio', 0), info.get('debtToEquity', 0),
            info.get('returnOnAssets', 0), info.get('returnOnEquity', 0), info.get('trailingPegRatio', 0)
        ]

        # 2. 找出競爭對手 (取前 4 名)
        industry = yf.Industry(info['industryKey'])
        competitors = list(industry.top_companies.index.values)[:4] 
        
        columns = ['Ticker', 'Dividend Yield', 'Trailing PE', 'TTM PS', 'Profit Margin', 'PB Ratio', 
                   'Trailing EPS', 'EV/EBITDA', 'Current Ratio', 'Debt-to-Equity', 'ROA', 'ROE', 'PEG Ratio']
        
        compare_df = pd.DataFrame([target_list], columns=columns)

        # 3. 抓取競爭者數據
        for comp in competitors:
            try:
                comp_info = yf.Ticker(comp).info
                comp_list = [
                    comp, 
                    comp_info.get('dividendYield', 0), comp_info.get('trailingPE', 0), comp_info.get('priceToSalesTrailing12Months', 0),
                    comp_info.get('profitMargins', 0), comp_info.get('priceToBook', 0), comp_info.get('trailingEps', 0),
                    comp_info.get('enterpriseToEbitda', 0), comp_info.get('currentRatio', 0), comp_info.get('debtToEquity', 0),
                    comp_info.get('returnOnAssets', 0), comp_info.get('returnOnEquity', 0), comp_info.get('trailingPegRatio', 0)
                ]
                compare_df.loc[len(compare_df)] = comp_list
            except Exception as e:
                print(f"Skipping competitor {comp}: {e}")

        # 4. 轉成 Markdown
        compare_df = compare_df.round(4)
        return compare_df.to_markdown(index=False), info.get('longBusinessSummary', '')

    except Exception as e:
        print(f"Error getting competitor data: {e}")
        return None, None