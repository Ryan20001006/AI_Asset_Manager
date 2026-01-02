#處理 Google Agent
import google.generativeai as genai
import asyncio
import traceback
import re
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search, AgentTool, ToolContext, FunctionTool 
from services.tech_service import run_technical_analysis # [NEW] 匯入工具
from config import settings



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
    
async def run_technical_agent(ticker: str):
    print(f"--- AI Agent: Running Technical Analysis for {ticker} ---")
    
    # 定義工具
    tech_tool = FunctionTool(run_technical_analysis)
    
    # 定義 Agent (參考 LLM.py)
    tech_agent = Agent(
        name="TechnicalAnalystAgent",
        model="gemini-2.5-flash",
        instruction=(
            f"You are a professional Technical Analyst specializing in {ticker}. "
            "Your task is to analyze data from the technical tools provided and generate a high-quality Trade Note. "
            "The note MUST include: a Buy/Sell/Hold recommendation, MA trend status, S&R levels, and backtesting metrics (CAGR and Sharpe). "
            "The entire output must be written in professional business English (or Traditional Chinese if requested). Keep it structured and concise."
        ),
        tools=[tech_tool],
        output_key="technical_report"
    )
    
    runner = InMemoryRunner(agent=tech_agent)
    
    # Prompt
    prompt = f"Please generate a concise technical analysis report and trade recommendation for {ticker}."
    
    response = await runner.run_debug(prompt)
    
    # 解析回應
    final_text = "Technical analysis failed."
    try:
        # 嘗試從 state_delta 獲取
        for event in response:
            if event.actions and event.actions.state_delta and "technical_report" in event.actions.state_delta:
                final_text = event.actions.state_delta["technical_report"]
                break
        
        # 如果 state_delta 沒抓到 (有時候 runner 行為不同)，嘗試直接抓最後的文字
        if final_text == "Technical analysis failed." and response:
             # 簡單抓取最後一個 model 回應
             for event in reversed(response):
                if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                     final_text = event.content.parts[0].text
                     break
    except Exception as e:
        print(f"Error parsing tech agent output: {e}")
        final_text = str(response)
        
    return final_text

async def run_technical_agent(ticker: str):
    print(f"--- AI Agent: Running Technical Analysis for {ticker} ---")
    
    tech_tool = FunctionTool(run_technical_analysis)
    
    # [NEW] 更新 Instruction：加入 Momentum 和 Sentiment 的解讀指南
    # 這裡參考了 Notebook 裡的 System Prompt: "You are a senior technical analyst..."
    instruction = (
        f"You are a Senior Technical Analyst specializing in {ticker}. "
        "Your goal is to write a concise, professional technical summary based on the provided tool output. "
        
        "You must analyze three key areas:\n"
        "1. **Trend**: Use MA50/MA200 and ADX to determine trend direction and strength.\n"
        "2. **Momentum**: Use RSI (Overbought > 70, Oversold < 30) and MACD Histogram (Bullish > 0).\n"
        "3. **Sentiment**: Use MFI (Money Flow) and Volume Change to gauge market participation.\n\n"
        
        "Output Format:\n"
        "- **Executive Summary**: A clear Buy/Sell/Hold signal with reasoning.\n"
        "- **Momentum & Sentiment**: Specific commentary on RSI, MACD, and Volume.\n"
        "- **Backtest Insight**: Mention the historical Sharpe Ratio and CAGR.\n\n"
        
        "Do NOT invent numbers. Use the data strictly from the tool output."
    )
    
    tech_agent = Agent(
        name="TechnicalAnalystAgent",
        model="gemini-2.5-flash",
        instruction=instruction,
        tools=[tech_tool],
        output_key="technical_report"
    )
    
    runner = InMemoryRunner(agent=tech_agent)
    
    # Prompt 也稍微更新，強調要包含這兩個面向
    prompt = f"Analyze the technical indicators for {ticker}, specifically focusing on Momentum and Sentiment."
    
    response = await runner.run_debug(prompt)
    
    # ... (原本的解析回應程式碼保持不變) ...
    # (為了節省篇幅，解析回應的 try-except 區塊請直接沿用上一次的代碼)
    final_text = "Technical analysis failed."
    try:
        for event in response:
            if event.actions and event.actions.state_delta and "technical_report" in event.actions.state_delta:
                final_text = event.actions.state_delta["technical_report"]
                break
        if final_text == "Technical analysis failed." and response:
             for event in reversed(response):
                if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                     final_text = event.content.parts[0].text
                     break
    except Exception as e:
        print(f"Error parsing tech agent output: {e}")
        final_text = str(response)

    return final_text








