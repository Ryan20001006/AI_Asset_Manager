#負責讀取設定
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

class Settings:
    DB_NAME = "stock.db"
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

settings = Settings()

if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)