#處理 Google Agent
import google.generativeai as genai
import asyncio
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search, AgentTool, ToolContext, FunctionTool 


chat_session = None

def get_chat_session():
    """確保有一個活著的對話 Session"""
    global chat_session
    if chat_session is None:
        # 初始化一個有記憶的模型
        model = genai.GenerativeModel("gemini-2.5-flash")
        chat_session = model.start_chat(history=[])
    return chat_session

def extract_ticker_from_text(text: str):
    """Agent 耳朵：增強版意圖識別"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Role: Financial Extraction Engine
    Task: Extract ticker from input. Support Chinese.
    Input: "{text}"
    Output: ONLY the ticker (e.g. SHEL.L, AAPL). If none, output NONE.
    """
    try:
        return model.generate_content(prompt).text.strip()
    except:
        return "NONE"
    
async def run_ai_analysis_agent(stock_id, summary, comparison_markdown):
    print(f"--- AI Agent: Analyzing News for {stock_id} ---")
    google_news_agent = Agent(
        name="GoogleNewsAgent",
        model="gemini-2.5-flash",
        instruction="""You are a specialized news arrangement agent for a given company. 
    
        For a given company:
        1. Use 'google_search' to find the company's summary.
        2. Read the company's summary and then use 'google_search' to find current related news that would affect the company's stock price.
        3. Generate comment with important points and analysis about the company's stock future performance base on the news.
        """,
        tools = [google_search],
        output_key="google_news_arrangement",
    )
    
    news_runner = InMemoryRunner(agent=google_news_agent)
    news_prompt = f"""{stock_id} summary: 
    {summary}"""
    
    news_response = await news_runner.run_debug(news_prompt)
    news_text = "News analysis failed or no output generated."
    try:
        for event in news_response:
            if event.actions and event.actions.state_delta and "google_news_arrangement" in event.actions.state_delta:
                news_text = event.actions.state_delta["google_news_arrangement"]
                break 
    except Exception as e:
        print(f"Error parsing news output: {e}")
        news_text = str(news_response) 

    print(f"--- AI Agent: Analyzing Competitors for {stock_id} ---")
    competitors_agent = Agent(
        name="CompetitorsAgent",
        model="gemini-2.5-flash",
        instruction="""You are a specialized agent to compare the target company to its competitors.

        For a given company:
        1. Use 'competitors_compare' to get the target company and its main competitors' financial ratio data.
        2. Check the "status" field in it response for errors.
        3. Aanlyse the financial ratio data, summarize the most important points and provide some insights that might affect the target companies' 
        stock price.
        4. Analyze the provided "Competitor Financial Ratios" data.
        5. Analyze the provided "DCF Valuation Model" result.
        6. Summarize the most important points, providing insights on whether the stock is undervalued or overvalued compared to peers and its intrinsic value.
    
        If any tool returns status "error", explain the issue to the user clearly.""",
            #tools = [competitors_compare],
        output_key="comparing_competitors",
    )

    comp_runner = InMemoryRunner(agent=competitors_agent)
    comp_prompt = f"""
    Please analyze the following data for {stock_id}:
    
    === [1] DCF Valuation Model Result ===
    {valuation_text}
    
    === [2] Competitor Financial Ratios ===
    {comparison_markdown}
    """
    
    comp_response = await comp_runner.run_debug(comp_prompt)
    comp_text = "Competitor analysis failed or no output generated."
    try:
        for event in comp_response:
            if event.actions and event.actions.state_delta and "comparing_competitors" in event.actions.state_delta:
                comp_text = event.actions.state_delta["comparing_competitors"]
                break
    except Exception as e:
        print(f"Error parsing competitor output: {e}")
        comp_text = str(comp_response)

    return str(news_text), str(comp_text)









