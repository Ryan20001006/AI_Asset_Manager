# tech_agent.py
# This is the core calculation module for the Shell (SHEL) Technical Analysis Agent.
# It includes logic for Data Ingestion, Trend Indicators (MA), Price Patterns (S&R), and Trend Filtering (ADX).

# backend2/services/tech_service.py

# backend2/services/tech_service.py

import yfinance as yf
import pandas as pd
import pandas_ta as ta  # [NEW] 引入 pandas_ta
import numpy as np

# ==========================================
# 核心計算邏輯 (整合 Momentum & Sentiment)
# ==========================================

def fetch_stock_data(ticker: str, years: int = 2) -> pd.DataFrame:
    """下載 OHLCV 數據"""
    try:
        # 下載較短的區間即可滿足技術指標計算 (2年足夠)
        df = yf.download(ticker, period=f"{years}y", progress=False, auto_adjust=False)
        
        # 處理 MultiIndex (yfinance 新版相容性)
        if isinstance(df.columns, pd.MultiIndex):
            # 如果第一層有 'Adj Close'，優先使用
            if 'Adj Close' in df.columns.get_level_values(0):
                 # 這裡為了保留 OHLCV 結構，我們做扁平化處理
                 df.columns = df.columns.get_level_values(0)
            else:
                 df.columns = df.columns.get_level_values(0)

        if df.empty:
            return pd.DataFrame()
            
        # 確保索引是 DateTime
        df.index = pd.to_datetime(df.index)
        
        # 欄位名稱標準化
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        # 檢查是否有缺少欄位 (有時候 yfinance 會缺 Adj Close，就用 Close)
        if "Adj Close" in df.columns:
            df["Close"] = df["Adj Close"] # 使用調整後收盤價計算指標更準確
            
        return df[required_cols]
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()

def calculate_momentum_sentiment(df: pd.DataFrame):
    """
    [NEW] 來自 Notebook 的邏輯：計算 RSI, MACD, ADX, MFI
    """
    if len(df) < 30:
        return {"Error": "Insufficient data"}

    # 1. RSI (Momentum)
    df["RSI"] = ta.rsi(df["Close"], length=14)
    
    # 2. MACD (Momentum)
    # ta.macd 回傳三個欄位: MACD_12_26_9, MACDh_12_26_9 (Hist), MACDs_12_26_9 (Signal)
    macd_df = ta.macd(df["Close"])
    df = pd.concat([df, macd_df], axis=1)
    
    # 3. ADX (Trend Strength)
    adx_df = ta.adx(df["High"], df["Low"], df["Close"], length=14)
    df = pd.concat([df, adx_df], axis=1)

    # 4. MFI (Sentiment / Money Flow)
    df["MFI"] = ta.mfi(df["High"], df["Low"], df["Close"], df["Volume"], length=14)

    # 5. Volume Change (Sentiment)
    df["Volume_Change"] = df["Volume"].pct_change() * 100

    # --- 取最新一筆數據 ---
    latest = df.iloc[-1]
    
    # 為了安全起見，使用 .get() 避免欄位名稱因版本不同而報錯
    # pandas_ta 的欄位命名通常是 MACDh_12_26_9
    macd_hist_col = [c for c in df.columns if "MACDh" in c]
    macd_hist = latest[macd_hist_col[0]] if macd_hist_col else 0
    
    adx_col = [c for c in df.columns if "ADX" in c and "14" in c]
    adx_val = latest[adx_col[0]] if adx_col else 0

    return {
        "RSI_14": round(latest["RSI"], 2),
        "MACD_Histogram": round(macd_hist, 4),
        "ADX_14": round(adx_val, 2),
        "MFI_14": round(latest["MFI"], 2),
        "Volume_Change_Pct": round(latest["Volume_Change"], 2)
    }

def calculate_ma_trend(df: pd.DataFrame):
    """原有的 MA 趨勢判斷"""
    if len(df) < 200:
        return {"TrendStatus": "Unknown"}
        
    latest = df.iloc[-1]
    ma50 = df['Close'].rolling(50).mean().iloc[-1]
    ma200 = df['Close'].rolling(200).mean().iloc[-1]
    
    trend = "Bullish (Uptrend)" if ma50 > ma200 else "Bearish (Downtrend)"
    
    return {
        "TrendStatus": trend,
        "MA_50": round(ma50, 2),
        "MA_200": round(ma200, 2),
        "Price_Relation": "Price > MA50" if latest['Close'] > ma50 else "Price < MA50"
    }

def simple_backtest(df: pd.DataFrame):
    """原有的簡易回測"""
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()
    df['Signal'] = np.where(df['MA50'] > df['MA200'], 1, 0)
    df['Returns'] = df['Close'].pct_change()
    df['Strategy'] = df['Signal'].shift(1) * df['Returns']
    
    cum_ret = (1 + df['Strategy']).cumprod().iloc[-1] - 1
    std = df['Strategy'].std()
    sharpe = (df['Strategy'].mean() / std * np.sqrt(252)) if std != 0 else 0
    
    return {
        "CAGR_5Y": f"{cum_ret/5:.2%}", # 簡單估算
        "Sharpe_Ratio": round(sharpe, 2)
    }

# ==========================================
# Agent Tool 主函式
# ==========================================
def run_technical_analysis(ticker: str):
    """
    執行綜合技術分析：包含 Momentum, Sentiment, Trend, Backtest
    """
    ticker = ticker.upper()
    df = fetch_stock_data(ticker, years=5) # 抓5年是為了回測，但指標只算近期
    
    if df.empty:
        return {"Error": "No data found"}
        
    current_price = df.iloc[-1]['Close']
    
    # 1. 計算各種指標
    mom_sent_report = calculate_momentum_sentiment(df)
    ma_report = calculate_ma_trend(df)
    backtest_report = simple_backtest(df)
    
    # 2. 整合所有數據回傳
    return {
        "Ticker": ticker,
        "CurrentPrice": round(current_price, 2),
        "Momentum_Sentiment_Indicators": mom_sent_report, # [NEW] 來自 Notebook 的精華
        "Trend_Analysis": ma_report,
        "Backtest_Metrics": backtest_report,
        "Data_Date": df.index[-1].strftime('%Y-%m-%d')
    }