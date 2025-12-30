#處理 Google Agent
import google.generativeai as genai
import asyncio
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search, AgentTool, ToolContext, FunctionTool 


import google.generativeai as genai
from config import settings
import traceback
import re

# ==========================================
# 0. 初始化設定
# ==========================================
try:
    if settings.GOOGLE_API_KEY:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
    else:
        print("⚠️ Warning: GOOGLE_API_KEY not found in settings.")
except Exception as e:
    print(f"⚠️ Failed to configure Gemini: {e}")

def get_chat_session():
    """建立對話 Session"""
    model = genai.GenerativeModel('gemini-2.5-flash')
    return model.start_chat(history=[])

def extract_ticker_from_text(text: str):
    """從對話中提取股票代號"""
    if not text: return "NONE"
    match = re.search(r'\b[A-Z]{2,5}\b', text.upper())
    return match.group(0) if match else "NONE"

def generate_investment_memo(ticker: str, context: str):
    """
    產生投資備忘錄 (被 stock.py 呼叫)
    """
    print(f"🤖 [AI Service] Generating memo for {ticker}...")
    if not settings.GOOGLE_API_KEY:
        return "❌ Error: GOOGLE_API_KEY missing."

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        You are a professional investment analyst.
        Target: {ticker}
        
        Data Context:
        {context}
        
        Task: Write a structured investment memo (Markdown).
        Include: Company Overview, Financial Health (Profitability, Growth, Leverage), and Investment Verdict.
        """
        response = model.generate_content(prompt)
        return response.text if response and response.text else "AI returned empty content."
    except Exception as e:
        traceback.print_exc()
        return f"AI Generation Failed: {str(e)}"









