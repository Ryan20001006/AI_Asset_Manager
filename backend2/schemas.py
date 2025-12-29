#定義傳輸格式 (Pydantic)
from pydantic import BaseModel

class StockRequest(BaseModel):
    ticker: str
    
class ChatRequest(BaseModel):
    message: str