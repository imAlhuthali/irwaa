#!/bin/bash
set -e

echo "🚀 Starting Educational Telegram Bot on Railway..."

# Check if required environment variables are set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set"
    exit 1
fi

if [ -z "$BOT_TOKEN" ]; then
    echo "⚠️ BOT_TOKEN not set - starting in health-only mode"
fi

echo "✅ Environment variables checked"

# Initialize database tables
echo "🗄️ Initializing database tables..."
python init_db.py

if [ $? -eq 0 ]; then
    echo "✅ Database initialization successful"
else
    echo "❌ Database initialization failed"
    exit 1
fi

# Start the bot
echo "🤖 Starting Telegram bot..."
python start.py