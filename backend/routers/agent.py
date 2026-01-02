#AI Agent API
from fastapi import APIRouter
from schemas import ChatRequest
from services.ai_service import get_chat_session, extract_ticker_from_text
from services.data_service import download_and_store_fundamentals, calculate_financial_ratios, get_context_str
from services.valuation_service import run_advanced_valuation
from database import get_db_connection
import google.generativeai as genai
import pandas as pd

router = APIRouter()

@router.post("/api/agent-chat")
def agent_chat(req: ChatRequest):
    user_msg = req.message
    ticker = extract_ticker_from_text(user_msg)
    
    session = get_chat_session()


    if (ticker == "NONE" or " " in ticker or len(ticker) > 10) and not session.history:
        model = genai.GenerativeModel("gemini-2.5-flash")
        reply = model.generate_content(f"User said: '{user_msg}'. Reply politely as a financial assistant asking for a company name.").text
        return {"status": "chat", "message": reply}

    
    if (ticker == "NONE" or " " in ticker or len(ticker) > 10) and session.history:
        print(f"💬 使用者正在追問: {user_msg}")
        response = session.send_message(user_msg)
        return {"status": "chat", "message": response.text}

    try:
        download_and_store_fundamentals(ticker)
        conn = get_db_connection()
        calculate_financial_ratios(ticker, conn)
        
        df = pd.read_sql("SELECT * FROM CalculatedRatios WHERE Stock_Id = ?", conn, params=(ticker,))
        conn.close()
        data_records = df.to_dict(orient="records")
    
        dcf_report = run_advanced_valuation(ticker)

        context = get_context_str(ticker)
        final_prompt = f"""
        [System Update: New Market Data Loaded]
        Target Company: {ticker}
        
        Historical Ratios (2021-2024):
        {context}
        
        Valuation Model Result:
        {dcf_report}
        
        User Question: "{user_msg}"
        
        Instruction: Provide a comprehensive investment analysis. 
        Note: Remember this data for future follow-up questions.
        """
        
        response = session.send_message(final_prompt)
        
        return {
            "status": "analysis_complete",
            "ticker": ticker,
            "data": data_records,
            "reply": response.text
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error: {str(e)}"}
    