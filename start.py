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
    """Main startup function with fallback health server"""
    try:
        logger.info("🚀 Starting Educational Telegram Bot...")
        
        # Check if required environment variables are available
        bot_token = os.getenv('BOT_TOKEN')
        admin_ids = os.getenv('ADMIN_IDS') 
        
        if not bot_token or not admin_ids:
            logger.warning("⚠️ Missing BOT_TOKEN or ADMIN_IDS - starting health server only")
            logger.info("Please set environment variables in Railway dashboard:")
            logger.info("- BOT_TOKEN: Your Telegram bot token")
            logger.info("- ADMIN_IDS: Comma-separated admin user IDs")
            
            # Start simple health server for Railway health checks
            from health_server import app
            import uvicorn
            port = int(os.getenv("PORT", 8000))
            
            config = uvicorn.Config(
                app, 
                host="0.0.0.0", 
                port=port,
                access_log=True
            )
            server = uvicorn.Server(config)
            await server.serve()
            
        else:
            # Import and run the main bot application
            from main import main as run_bot
            await run_bot()
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        logger.info("🔧 Starting fallback health server...")
        
        # Start health server as fallback
        try:
            from health_server import app
            import uvicorn
            port = int(os.getenv("PORT", 8000))
            
            config = uvicorn.Config(
                app,
                host="0.0.0.0", 
                port=port,
                access_log=True
            )
            server = uvicorn.Server(config)
            await server.serve()
        except Exception as fallback_error:
            logger.error(f"❌ Even fallback server failed: {fallback_error}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())