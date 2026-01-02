#Alpha Vantage Source API
from fastapi import APIRouter, HTTPException
from schemas import StockRequest
from services.data_service import (
    download_and_store_fundamentals, 
    calculate_financial_ratios, 
    get_db_connection, 
    get_competitor_dataframe_markdown, 
    search_symbol_alpha_vantage,
    get_context_str
)
from services.ai_service import generate_investment_memo
from services.backtest_service import run_backtest
import pandas as pd
import numpy as np
import datetime as dt

router = APIRouter()

@router.post("/api/analyze")
def analyze(req: StockRequest):
    ticker = req.ticker.upper()
    if not download_and_store_fundamentals(ticker):
        raise HTTPException(status_code=404, detail="Download failed")
    
    conn = get_db_connection()
    try:
        calculate_financial_ratios(ticker, conn)
        
        df = pd.read_sql("SELECT * FROM FinancialRatios WHERE Stock_Id = ?", conn, params=(ticker,))
        data_list = df.to_dict(orient="records")
        
        for row in data_list:
            for key, value in row.items():
                if isinstance(value, (float, np.floating)):
                    if np.isnan(value) or np.isinf(value):
                        row[key] = None
        
        return {"status": "success", "data": data_list}
    finally:
        conn.close()

@router.get("/api/search")
def search_ticker(keyword: str):
    if not keyword:
        return {"status": "error", "message": "請輸入關鍵字"}
        
    results = search_symbol_alpha_vantage(keyword)
    return {"status": "success", "data": results}

@router.post("/api/analyze_ai/{stock_id}")
def analyze_stock_ai(stock_id: str):
    stock_id = stock_id.upper()
    conn = get_db_connection()
    try:
        comparison_md = get_competitor_dataframe_markdown([stock_id], conn)
        summary = get_context_str(stock_id, conn)
        if not summary or "No financial data" in summary:
             download_and_store_fundamentals(stock_id)
             summary = get_context_str(stock_id, conn)
             comparison_md = get_competitor_dataframe_markdown([stock_id], conn)

        if not summary:
            return {"status": "error", "message": "無法取得數據，請確認後端已下載財報"}
        
        ai_report = generate_investment_memo(stock_id, summary + "\n\n" + comparison_md)
        today = dt.date.today().strftime("%Y-%m-%d")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM AI_Analysis WHERE Stock_Id = ? AND ReportDate = ?", (stock_id, today))
        row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE AI_Analysis 
                SET AnalysisContent = ?, CreatedAt = CURRENT_TIMESTAMP 
                WHERE Stock_Id = ? AND ReportDate = ?
            """, (ai_report, stock_id, today))
        else:
            cursor.execute("""
                INSERT INTO AI_Analysis (Stock_Id, ReportDate, AnalysisContent)
                VALUES (?, ?, ?)
            """, (stock_id, today, ai_report))
        
        conn.commit()
        
        return {"status": "success", "ticker": stock_id}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"AI 模型執行失敗: {str(e)}"}
    finally:
        conn.close()

@router.get("/api/get_ai_report/{stock_id}")
def get_ai_report(stock_id: str):
    stock_id = stock_id.upper()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ReportDate, AnalysisContent 
            FROM AI_Analysis 
            WHERE Stock_Id = ? 
            ORDER BY ReportDate DESC 
            LIMIT 1
        ''', (stock_id,))
        
        row = cursor.fetchone()
        
        if row:
            return {
                "date": row[0],
                "news_analysis": row[1],
                "competitor_analysis": "" 
            }
        else:
            return {}
    finally:
        conn.close()

@router.get("/api/backtest/{ticker}")
def backtest_stock(ticker: str):
    return run_backtest(ticker.upper())