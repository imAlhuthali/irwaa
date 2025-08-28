#!/usr/bin/env python3
"""
Production Start Script for Educational Telegram Bot
Handles Railway deployment and ensures proper startup sequence
"""

import os
import sys
import asyncio
import logging

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs('content', exist_ok=True)

# Set up basic logging for startup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Main startup function"""
    try:
        logger.info("Starting Educational Telegram Bot...")
        
        # Check environment variables first
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token:
            logger.warning("BOT_TOKEN not set - starting health-only mode")
            await start_health_server()
            return
            
        from main import main as run_bot
        await run_bot()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        # Start health server as fallback
        await start_health_server()

async def start_health_server():
    """Start minimal health server for Railway"""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn
    
    app = FastAPI()
    
    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "waiting_for_config",
            "message": "Please set BOT_TOKEN and ADMIN_IDS environment variables"
        })
    
    @app.get("/")
    async def root():
        return JSONResponse({
            "message": "Educational Telegram Bot",
            "status": "Configuration required"
        })
    
    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())