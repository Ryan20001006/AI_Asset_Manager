#處理 DCF、Fama-French

import os
import datetime as dt
import pandas as pd
import numpy as np
import yfinance as yf
import google.generativeai as genai
import pandas_datareader.data as web
import statsmodels.api as sm


def calculate_fama_french_coe(ticker_symbol, lookback_years=5):
    """計算 Fama-French 權益成本"""
    print(f"📊 [模型 1/3] 計算 Fama-French CoE ({ticker_symbol})...")
    end_date = dt.datetime.now()
    start_date = end_date - dt.timedelta(days=lookback_years*365)
    
    try:
        ff_data = web.DataReader('F-F_Research_Data_Factors', 'famafrench', start_date, end_date)[0]
        ff_data = ff_data / 100
        ff_data.index = ff_data.index.to_timestamp()
    except Exception:
        print("⚠️ Fama-French 數據獲取失敗，使用 Fallback 10%")
        return 0.10 

    ticker = yf.Ticker(ticker_symbol)
    stock = ticker.history(start=start_date, end=end_date, interval='1mo')
    if stock.empty: return 0.10

    stock_returns = stock['Close'].pct_change().dropna()
    stock_returns.index = stock_returns.index.to_period('M')
    ff_data.index = ff_data.index.to_period('M')
    
    data = pd.merge(stock_returns, ff_data, left_index=True, right_index=True)
    data.columns = ['Stock_Return', 'Mkt-RF', 'SMB', 'HML', 'RF']
    data['Excess_Return'] = data['Stock_Return'] - data['RF']
    
    X = sm.add_constant(data[['Mkt-RF', 'SMB', 'HML']])
    model = sm.OLS(data['Excess_Return'], X).fit()
    
    exp_mkt = data['Mkt-RF'].mean() * 12
    exp_smb = data['SMB'].mean() * 12
    exp_hml = data['HML'].mean() * 12
    rf = data['RF'].iloc[-1] * 12
    
    coe = rf + (model.params['Mkt-RF'] * exp_mkt) + (model.params['SMB'] * exp_smb) + (model.params['HML'] * exp_hml)
    return coe

def project_fcf_from_eps_filtered(ticker_symbol):
    """使用 Forward EPS 預測 FCF"""
    print(f"🔮 [模型 2/3] 預測 FCF ({ticker_symbol})...")
    stock = yf.Ticker(ticker_symbol)
    
    def filter_post_2020(df):
        df.columns = pd.to_datetime(df.columns)
        return df[[c for c in df.columns if c.year >= 2021]]

    try:
        financials = filter_post_2020(stock.financials)
        cashflow = filter_post_2020(stock.cashflow)
        
        net_income = financials.loc['Net Income']
        fcf = cashflow.loc['Operating Cash Flow'] - abs(cashflow.loc['Capital Expenditure'])
        
        ratios = (fcf / net_income).replace([np.inf, -np.inf], np.nan).dropna()
        avg_ratio = ratios.mean() if not ratios.empty else 1.0
        
        forward_eps = stock.info.get('forwardEps') or stock.info.get('trailingEps')
        return forward_eps * avg_ratio
    except Exception:
        return 0

def calculate_dcf(ticker_symbol, coe, fcfps_FTM, projection_years=5, terminal_growth_rate=0.00):
    """執行 DCF 估值 (0% 成長率)"""
    print(f"💰 [模型 3/3] 執行最終 DCF 估值...")
    stock = yf.Ticker(ticker_symbol)
    info = stock.info
    
    current_price = info.get('currentPrice')
    currency = info.get('currency', 'USD')
    if currency == 'GBp':
        current_price = current_price / 100
        currency = 'GBP'
        
    shares = info.get('sharesOutstanding')
    financials = stock.financials
    balance = stock.balance_sheet
    
    try:
        int_exp = abs(financials.loc['Interest Expense'].iloc[0]) if 'Interest Expense' in financials.index else 0
        debt = balance.loc['Total Debt'].iloc[0] if 'Total Debt' in balance.index else 0
        tax_rate = 0.21
        cost_debt = (int_exp / debt) * (1 - tax_rate) if debt > 0 else 0.05
        
        mkt_cap = shares * current_price
        total_val = mkt_cap + debt
        wacc = ((mkt_cap/total_val) * coe) + ((debt/total_val) * cost_debt)
    except:
        wacc = coe
    
    growth_rate_projection = 0.00 # 0% 成長
    future_fcf = [fcfps_FTM * shares * ((1 + growth_rate_projection) ** i) for i in range(1, projection_years + 1)]
    
    term_val = (future_fcf[-1] * (1 + terminal_growth_rate)) / (wacc - terminal_growth_rate)
    disc_fcfs = sum([f / ((1 + wacc) ** (i + 1)) for i, f in enumerate(future_fcf)])
    disc_tv = term_val / ((1 + wacc) ** projection_years)
    
    intrinsic_val = (disc_fcfs + disc_tv) / shares
    status = "低估 (Undervalued)" if intrinsic_val > current_price else "高估 (Overvalued)"
    
    return f"""
    [Advanced DCF Valuation]
    - Ticker: {ticker_symbol}
    - Current Price: {current_price:.2f} {currency}
    - Fair Value: {intrinsic_val:.2f} {currency}
    - Conclusion: {status}
    --------------------------------
    - WACC: {wacc:.2%}
    - Proj. FCF/Share: {fcfps_FTM:.2f}
    - Growth Assumption: 0.0%
    """

def run_advanced_valuation(ticker):
    """總指揮函式"""
    coe = calculate_fama_french_coe(ticker) or 0.10
    fcf_ftm = project_fcf_from_eps_filtered(ticker)
    if fcf_ftm <= 0: return "Error: Insufficient Data for Valuation"
    return calculate_dcf(ticker, coe, fcf_ftm)