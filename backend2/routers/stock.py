#股票相關 API
from fastapi import APIRouter, HTTPException
from schemas import StockRequest
from services.data_service import (
    download_and_store_fundamentals, 
    calculate_financial_ratios, 
    get_db_connection, 
    get_competitor_dataframe_markdown, 
    search_symbol_alpha_vantage,
    get_context_str  # 確保有 import 這個
)
from services.ai_service import generate_investment_memo
import pandas as pd
import datetime as dt

router = APIRouter()

@router.post("/api/analyze")
def analyze(req: StockRequest):
    ticker = req.ticker.upper()
    # 下載數據
    if not download_and_store_fundamentals(ticker):
        raise HTTPException(status_code=404, detail="Download failed")
    
    conn = get_db_connection()
    try:
        # 計算比率 (需傳入 conn)
        calculate_financial_ratios(ticker, conn)
        
        # 讀取結果
        df = pd.read_sql("SELECT * FROM CalculatedRatios WHERE Stock_Id = ?", conn, params=(ticker,))
        
        return {"status": "success", "data": df.to_dict(orient="records")}
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
        # 1. 取得競爭對手分析 (✅ 修正：傳入 conn)
        # 這裡假設比較自己，實際應用可傳入同業列表
        comparison_md = get_competitor_dataframe_markdown([stock_id], conn)
        
        # 2. 取得財務摘要 (✅ 修正：傳入 conn)
        summary = get_context_str(stock_id, conn)

        # 如果沒資料，嘗試下載
        if not summary or "No financial data" in summary:
             download_and_store_fundamentals(stock_id)
             # 下載後重新讀取
             summary = get_context_str(stock_id, conn)
             comparison_md = get_competitor_dataframe_markdown([stock_id], conn)

        if not summary:
            return {"status": "error", "message": "無法取得數據，請確認後端已下載財報"}

        # 3. 呼叫 AI 生成報告
        # 這裡改用 generate_investment_memo (這是我們在 ai_service 定義的名稱)
        # 報告內容會包含 news_analysis 和 competitor_analysis 的整合
        ai_report = generate_investment_memo(stock_id, summary + "\n\n" + comparison_md)

        # 4. 存入資料庫
        today = dt.date.today().strftime("%Y-%m-%d")
        cursor = conn.cursor()

        # 檢查是否已有今日報告
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
        
        # 抓取最新的一份報告 (讀取 AI_Analysis 表格)
        cursor.execute('''
            SELECT ReportDate, AnalysisContent 
            FROM AI_Analysis 
            WHERE Stock_Id = ? 
            ORDER BY ReportDate DESC 
            LIMIT 1
        ''', (stock_id,))
        
        row = cursor.fetchone()
        
        if row:
            # 為了相容前端格式，將整份報告放在 news_analysis 欄位回傳
            # competitor_analysis 可留空或放一樣的
            return {
                "date": row[0],
                "news_analysis": row[1],
                "competitor_analysis": "" 
            }
        else:
            # 回傳空 JSON 讓前端知道沒資料
            return {}
    finally:
        conn.close()