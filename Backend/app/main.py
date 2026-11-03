
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import (
    farms,
    ponds,
    feed,
    water_quality,
    growth,
    harvest,
    stocking,
    upload,
    chat,
    feed_prediction,
)

app = FastAPI(
    title="AquaLLM API",
    description="AI-powered Aquaculture Intelligence Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Welcome to AquaLLM API",
        "status": "running",
    }


app.include_router(farms.router)
app.include_router(ponds.router)
app.include_router(feed.router)
app.include_router(water_quality.router)
app.include_router(growth.router)
app.include_router(harvest.router)
app.include_router(stocking.router)
app.include_router(upload.router)
app.include_router(chat.router)

# Feed prediction and weekly forecast
app.include_router(feed_prediction.router)
