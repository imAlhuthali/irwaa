#!/usr/bin/env python3
"""
Simple test bot to diagnose connection issues
Forces polling mode and basic logging with health endpoint
"""

import os
import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import threading

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get token from environment
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found in environment variables")
    exit(1)

logger.info(f"Bot token starts with: {BOT_TOKEN[:10]}...")

async def start_command(update: Update, context):
    """Handle /start command"""
    logger.info(f"Received /start from user {update.effective_user.id}")
    try:
        await update.message.reply_text(
            "🎉 Bot is working! The /start command is received successfully.\n\n"
            "مرحباً! البوت يعمل بشكل صحيح! 👋"
        )
        logger.info("Start message sent successfully")
    except Exception as e:
        logger.error(f"Error sending start message: {e}")

async def echo_handler(update: Update, context):
    """Echo all messages for testing"""
    logger.info(f"Received message from user {update.effective_user.id}: {update.message.text}")
    try:
        await update.message.reply_text(f"Echo: {update.message.text}")
        logger.info("Echo message sent successfully")
    except Exception as e:
        logger.error(f"Error sending echo message: {e}")

def start_health_server():
    """Start health server in background"""
    health_app = FastAPI()
    
    @health_app.get("/health")
    async def health():
        return JSONResponse({
            "status": "healthy",
            "message": "Simple test bot running",
            "mode": "polling"
        })
    
    @health_app.get("/")
    async def root():
        return JSONResponse({
            "message": "Simple Telegram Test Bot",
            "status": "running"
        })
    
    port = int(os.getenv('PORT', 8000))
    logger.info(f"Starting health server on port {port}")
    
    config = uvicorn.Config(health_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    def run_server():
        asyncio.run(server.serve())
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    logger.info("Health server started in background")

async def main():
    """Main function"""
    logger.info("Starting simple test bot...")
    
    # Start health server first
    start_health_server()
    
    try:
        # Create application
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_handler))
        
        logger.info("Handlers added successfully")
        
        # Initialize and start
        await app.initialize()
        await app.start()
        logger.info("Bot initialized and started")
        
        # Force polling mode (ignore PORT environment variable)
        logger.info("Starting polling mode...")
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Polling started successfully")
        
        # Keep running
        logger.info("Bot is now running in polling mode...")
        while True:
            await asyncio.sleep(10)
            logger.info("Bot still running...")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        logger.info("Shutting down bot...")
        try:
            await app.stop()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())