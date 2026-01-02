# backend2/services/backtest_service.py
import yfinance as yf
import pandas as pd
import numpy as np

def calculate_metrics(daily_returns):
    """計算 CAGR, Sharpe, Max Drawdown"""
    if daily_returns.empty:
        return None
    
    # 總報酬
    total_return = (daily_returns + 1).prod() - 1
    
    # 年化報酬率 (CAGR) - 假設 252 個交易日
    days = len(daily_returns)
    cagr = (total_return + 1) ** (252 / days) - 1 if days > 0 else 0
    
    # 夏普比率 (Sharpe Ratio) - 假設無風險利率 4%
    rf = 0.04
    excess_returns = daily_returns - (rf / 252)
    std = daily_returns.std() * np.sqrt(252)
    sharpe = (excess_returns.mean() * 252) / std if std != 0 else 0
    
    # 最大回撤 (Max Drawdown)
    cumulative = (1 + daily_returns).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    max_drawdown = drawdown.min()
    
    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown
    }

def run_backtest(ticker_symbol, period="5y"):
    """
    執行回測：比較目標股票 vs S&P 500 (SPY)
    更穩健的版本：自動處理 Adj Close / Close 以及欄位索引問題
    """
    print(f"📈 正在回測 {ticker_symbol} 過去 {period} 績效...")
    
    try:
        tickers = [ticker_symbol, "SPY"]
        
        # 1. 下載數據 (先不指定欄位，下載全部回來檢查)
        # auto_adjust=False 確保嘗試抓取原始 Adj Close，但也準備好 Fallback
        df = yf.download(tickers, period=period, progress=False, auto_adjust=False)
        
        if df.empty:
            return {"status": "error", "message": "Yahoo Finance returned no data."}

        # 2. 決定使用哪個價格欄位 (優先找 Adj Close，沒有就用 Close)
        # yfinance 的 columns 可能是 MultiIndex: ('Adj Close', 'AAPL')
        price_col_name = 'Adj Close'
        
        # 檢查第一層 index 是否有 'Adj Close'
        if 'Adj Close' not in df.columns.get_level_values(0):
            if 'Close' in df.columns.get_level_values(0):
                print("⚠️ Warning: 'Adj Close' not found, using 'Close' instead.")
                price_col_name = 'Close'
            else:
                return {"status": "error", "message": f"Price columns not found. Columns: {df.columns}"}

        # 取出價格數據
        data = df[price_col_name]
        
        # 3. 處理欄位對應
        # 如果只下載到一個 ticker (另一個失敗)，data 可能是 Series 或只有一欄的 DataFrame
        if isinstance(data, pd.Series):
            data = data.to_frame()
            
        # 找出正確的 Stock Column 與 Benchmark Column
        # 有時候 yfinance 會自動將 ticker 轉大寫，這裡做個對應
        cols = data.columns
        stock_col = next((c for c in cols if c.upper() == ticker_symbol.upper()), None)
        bench_col = next((c for c in cols if c.upper() == "SPY"), None)

        if not stock_col:
            # 嘗試修復：如果是單一股票下載，欄位可能就是該股票名稱
            if len(cols) == 1:
                stock_col = cols[0]
            else:
                return {"status": "error", "message": f"Ticker {ticker_symbol} data missing in response."}

        # 4. 資料前處理
        # 移除空值
        data = data.dropna(subset=[stock_col])
        
        # 計算日報酬
        stock_returns = data[stock_col].pct_change().dropna()
        stock_metrics = calculate_metrics(stock_returns)
        
        # 計算 Benchmark
        bench_metrics = None
        bench_returns = None
        if bench_col:
            bench_returns = data[bench_col].pct_change().dropna()
            bench_metrics = calculate_metrics(bench_returns)

        # 5. 準備圖表數據 (累計報酬)
        stock_cum = (1 + stock_returns).cumprod()
        bench_cum = (1 + bench_returns).cumprod() if bench_returns is not None else None
        
        # 合併成一個 DataFrame 以便輸出
        chart_df = pd.DataFrame({'stock': stock_cum})
        if bench_cum is not None:
            chart_df = chart_df.join(bench_cum.rename('benchmark'), how='left')
        
        # 補值 (有些日期 SPY 有交易但個股沒有，或是反過來)
        chart_df = chart_df.fillna(method='ffill').fillna(1.0)
        
        chart_data_list = []
        for date, row in chart_df.iterrows():
            chart_data_list.append({
                "date": date.strftime('%Y-%m-%d'),
                "stock_cumulative": row['stock'],
                "benchmark_cumulative": row.get('benchmark', 1.0)
            })
            
        return {
            "status": "success",
            "ticker": ticker_symbol,
            "period": period,
            "metrics": {
                "stock": stock_metrics,
                "benchmark": bench_metrics
            },
            "chart_data": chart_data_list
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}