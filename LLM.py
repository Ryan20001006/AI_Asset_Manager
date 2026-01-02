# LLM.py
# This is the minimal runner for the Technical Analyst Agent.
# It registers your quantitative tools to Gemini and generates an English report.

import asyncio
import os 
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool
from google.adk.models.google_llm import Gemini
from google.genai import types as genai_types

# Importing your core analysis function from tech_agent.py
from tech_agent import technical_analysis_summary 

# ⚠️ Please fill in your Google API Key
GOOGLE_API_KEY = "YOUR_API_KEY_HERE"

# ==========================================
# 1. Define Agent Instructions and Tools
# ==========================================

def get_system_instruction_text():
    """Sets the system persona and instructions for the Agent."""
    return (
        "You are a professional Technical Analyst specializing in Shell (SHEL) stock. "
        "Your task is to analyze data from the technical tools provided and generate a high-quality Trade Note IN ENGLISH. "
        "The note MUST include: a Buy/Sell/Hold recommendation, MA trend status, S&R levels, and backtesting metrics (CAGR and Sharpe). "
        "The entire output must be written in professional business English. Keep it structured and concise."
    )

def get_technical_agent_tools():
    """Registers the quantitative function as an LLM tool."""
    return [FunctionTool(technical_analysis_summary)]

# ==========================================
# 2. Execution Flow
# ==========================================

async def run_simple_agent():
    """Runs the Agent to generate the technical report."""
    
    if "YOUR_API_KEY_HERE" in GOOGLE_API_KEY or not GOOGLE_API_KEY: 
        raise Exception("Please replace GOOGLE_API_KEY with your actual API Key!")
    
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

    tools = get_technical_agent_tools()
    system_instruction = get_system_instruction_text()
    
    generation_config = genai_types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=tools
    )
    
    llm_model = Gemini(
        model_name="gemini-2.5-flash", 
        config=generation_config
    )
    
    simple_agent = Agent(
        model=llm_model,
        name="Technical_Analyst_Agent"
    )

    runner = InMemoryRunner(agent=simple_agent)
    
    # User query in English to prompt English response
    user_query = "Please generate a concise English technical analysis report and trade recommendation for Shell (SHEL)."

    print(f"Agent is processing request: {user_query}")
    
    # Running in debug mode to see step-by-step execution
    response = await runner.run_debug(user_query) 
    
    print("\n--- Final Trade Note (English) ---")
    
    # Extracting the final output from the response list
    if isinstance(response, list) and response:
        final_output = None
        for event in reversed(response):
            if hasattr(event, 'content') and hasattr(event.content, 'parts') and event.content.parts:
                 final_output = getattr(event.content.parts[0], 'text', None)
                 if final_output:
                     break
        
        if final_output:
            print(final_output)
        else:
            print("Note: The report text was printed above by the Runner. Execution successful.")
    else:
        print("Could not extract report from response. Raw response:")
        print(response)
        
    print("---------------------------------------------")

if __name__ == '__main__':
    try:
        asyncio.run(run_simple_agent())
    except Exception as e:
        print(f"Execution Error: {e}")