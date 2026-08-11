import uvicorn
from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="FindYourBuddy API")

app.include_router(health.router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", reload=True)
