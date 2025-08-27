#!/usr/bin/env python3
"""
Railway Start Script for Telegram Learning Bot
Simple wrapper to ensure proper startup in Railway environment
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
        logger.info("🚀 Starting Telegram Learning Bot...")
        
        # Import and run the main application
        from main import main as run_bot
        await run_bot()
        
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())