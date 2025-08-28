#!/usr/bin/env python3
"""
Standalone health server for Railway deployment
Provides health check endpoint independently of main bot
"""

import os
import asyncio
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Educational Telegram Bot Health Server")

@app.get("/health")
async def health_check():
    """Simple health check that always responds"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": "production",
        "service": "educational-telegram-bot",
        "port": os.getenv("PORT", "8000")
    })

@app.get("/")
async def root():
    """Root endpoint"""
    return JSONResponse({
        "message": "Educational Telegram Bot API",
        "status": "running",
        "health_endpoint": "/health"
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        access_log=True
    )