#Yahoo Finance API
from fastapi import APIRouter, HTTPException
from schemas import StockRequest
from services.data_service import download_and_store_fundamentals, calculate_financial_ratios, get_db_connection, get_competitor_dataframe_markdown, search_symbol_alpha_vantage
from services.ai_service import run_ai_analysis_agent
import pandas as pd
import datetime as dt

router = APIRouter()

@router.post("/api/analyze")
def analyze(req: StockRequest):
    ticker = req.ticker.upper()
    if not download_and_store_fundamentals(ticker):
        raise HTTPException(status_code=404, detail="Download failed")
    conn = get_db_connection()
    calculate_financial_ratios(ticker, conn)
    df = pd.read_sql("SELECT * FROM CalculatedRatios WHERE Stock_Id = ?", conn, params=(ticker,))
    conn.close()
    return {"status": "success", "data": df.to_dict(orient="records")}

@router.get("/api/search")
def search_ticker(keyword: str):
    """
    Frontend callingback: GET /api/search?keyword=Tencent
    """
    if not keyword:
        return {"status": "error", "message": "Plese insert key words."}
        
    results = search_symbol_alpha_vantage(keyword)
    return {"status": "success", "data": results}

@router.post("/api/analyze_ai/{stock_id}")
async def analyze_stock_ai(stock_id: str):
    stock_id = stock_id.upper()
    conn = get_db_connection()
    print(f"Preparing {stock_id} analysis data...")
    comparison_md, summary = get_competitor_dataframe_markdown(stock_id)
    
    if not comparison_md or not summary:
        conn.close()
        return {"status": "error", "message": "Failed to collect Yahoo Finance data or competitor data"}

    try:
        news_analysis, competitor_analysis = await run_ai_analysis_agent(stock_id, summary, comparison_md)
    except Exception as e:
        conn.close()
        return {"status": "error", "message": f"AI Model failed: {str(e)}"}


    today = dt.date.today().strftime("%Y-%m-%d")
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO AIReports (Stock_Id, ReportDate, NewsAnalysis, CompetitorAnalysis)
        VALUES (?, ?, ?, ?)
    ''', (stock_id, today, news_analysis, competitor_analysis))
    
    conn.commit()
    conn.close()
    
    return {
        "status": "success", 
        "data": {
            "news_analysis": news_analysis,
            "competitor_analysis": competitor_analysis
        }
    }

@router.get("/api/get_ai_report/{stock_id}")
def get_ai_report(stock_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ReportDate, NewsAnalysis, CompetitorAnalysis 
        FROM AIReports 
        WHERE Stock_Id = ? 
        ORDER BY ReportDate DESC 
        LIMIT 1
    ''', (stock_id.upper(),))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "date": row[0],
            "news_analysis": row[1],
            "competitor_analysis": row[2]
        }
    else:
        return {"message": "No Report Generated"}