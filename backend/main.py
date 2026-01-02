
import config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import create_fundamental_tables
from routers import stock, agent


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    create_fundamental_tables()
    print("\n Current API List:")
    for route in app.routes:
        print(f"   {route.methods}  {route.path}")
    print("----------------------------\n")

app.include_router(stock.router)
app.include_router(agent.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
