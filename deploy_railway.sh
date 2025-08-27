#!/bin/bash

# Railway Deployment Script for Telegram Learning Bot
echo "🚀 Deploying Telegram Learning Bot to Railway..."

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Please install it first:"
    echo "npm install -g @railway/cli"
    exit 1
fi

# Login to Railway (if not already logged in)
echo "🔐 Checking Railway authentication..."
if ! railway status &> /dev/null; then
    echo "Please login to Railway first:"
    echo "railway login"
    exit 1
fi

# Create new Railway project
echo "📦 Creating Railway project..."
railway init

# Add PostgreSQL database
echo "🗄️ Adding PostgreSQL database..."
railway add --database postgresql

# Set environment variables
echo "⚙️ Setting environment variables..."
echo "Please set these environment variables in Railway dashboard:"
echo "1. BOT_TOKEN=your_telegram_bot_token"
echo "2. ADMIN_IDS=your_admin_user_ids (comma-separated)"
echo "3. USE_WEBHOOK=true"
echo "4. WEBHOOK_HOST=0.0.0.0"
echo "5. WEBHOOK_PORT=8000"
echo "6. DEBUG=false"
echo "7. LOG_LEVEL=INFO"

echo ""
echo "The DATABASE_URL will be automatically set by Railway when you add PostgreSQL."

# Deploy the application
echo "🚢 Deploying application..."
railway up

echo "✅ Deployment initiated!"
echo ""
echo "Next steps:"
echo "1. Wait for deployment to complete"
echo "2. Get your app URL: railway domain"
echo "3. Set WEBHOOK_URL environment variable to your Railway app URL"
echo "4. Update your bot webhook URL with Telegram"
echo "5. Monitor logs: railway logs"
echo ""
echo "Your bot should be ready! 🎉"