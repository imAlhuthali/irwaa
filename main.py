#!/usr/bin/env python3
"""
Educational Telegram Bot - Main Application
Handles webhook configuration and bot initialization
Version: 1.0.2 - Railway Production Ready
"""

import logging
import sys
import asyncio
import signal
import os
from datetime import datetime
from typing import Optional

from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters
)
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import json

# Production scalability imports with fallback
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    print("WARNING: Rate limiting dependencies not available, using basic implementation")
    RATE_LIMITING_AVAILABLE = False
    # Fallback implementations
    class MockLimiter:
        def __init__(self, *args, **kwargs):
            pass
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    
    Limiter = MockLimiter
    RateLimitExceeded = Exception
    
    def _rate_limit_exceeded_handler(*args, **kwargs):
        pass
    
    def get_remote_address(*args, **kwargs):
        return "0.0.0.0"

from config.settings import BotConfig
from models import get_database_manager
from handlers.student_handler import StudentHandler
from services.content_service import ContentService
from services.quiz_service import QuizService
from services.analytics_service import AnalyticsService
from services.learning_progression_service import LearningProgressionService
from utils.scheduler import TaskScheduler

# Optional production imports with fallbacks
try:
    from utils.cache import cache_manager
    CACHE_AVAILABLE = True
except ImportError:
    print("WARNING: Cache utilities not available, using mock implementation")
    CACHE_AVAILABLE = False
    class MockCacheManager:
        async def initialize(self): pass
        async def close(self): pass
    cache_manager = MockCacheManager()

try:
    from utils.circuit_breaker import with_database_circuit_breaker
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    print("WARNING: Circuit breaker not available, using direct calls")
    CIRCUIT_BREAKER_AVAILABLE = False
    def with_database_circuit_breaker(func):
        return func

try:
    from utils.monitoring import (
        comprehensive_health_check, 
        get_metrics_response,
        track_request,
        metrics_updater_task
    )
    MONITORING_AVAILABLE = True
except ImportError:
    print("WARNING: Monitoring utilities not available, using basic implementation")
    MONITORING_AVAILABLE = False
    
    async def comprehensive_health_check(bot_instance):
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {"basic": "operational"}
        }
    
    def get_metrics_response():
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("# Metrics not available\n")
    
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def track_request(endpoint: str):
        yield
    
    async def metrics_updater_task(bot_instance):
        pass

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure structured logging for production
PRODUCTION_MODE = os.getenv('ENVIRONMENT', 'development') == 'production'

if PRODUCTION_MODE:
    # Structured JSON logging for production
    try:
        import structlog
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            logger_factory=structlog.WriteLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        logger = structlog.get_logger(__name__)
        logging.info("✅ Structured logging initialized")
    except ImportError:
        logging.warning("Structured logging not available, using basic logging")
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO,
            handlers=[
                logging.FileHandler('logs/bot.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        logger = logging.getLogger(__name__)
else:
    # Traditional logging for development
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('logs/bot.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        try:
            self.config = BotConfig()
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            logger.error("Please set the required environment variables in Railway dashboard")
            raise
            
        self.app: Optional[Application] = None
        self.db_manager = None
        self.student_handler: Optional[StudentHandler] = None
        self.content_service: Optional[ContentService] = None
        self.quiz_service: Optional[QuizService] = None
        self.analytics_service: Optional[AnalyticsService] = None
        self.learning_service: Optional[LearningProgressionService] = None
        self.scheduler: Optional[TaskScheduler] = None
        
        # Initialize FastAPI with rate limiting for production scalability
        self.fastapi_app = FastAPI(title="Educational Telegram Bot API")
        
        # Rate limiter - Critical for 7000+ users protection
        if RATE_LIMITING_AVAILABLE:
            self.limiter = Limiter(
                key_func=get_remote_address,
                default_limits=["100/minute", "2000/hour"]  # Conservative limits for educational use
            )
            self.fastapi_app.state.limiter = self.limiter
            self.fastapi_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
            logger.info("✅ Rate limiting enabled")
        else:
            self.limiter = Limiter()  # Mock limiter
            logger.warning("⚠️ Rate limiting disabled (dependencies not available)")
        
    async def initialize(self):
        """Initialize all bot components"""
        try:
            # Initialize database with circuit breaker protection
            logger.info("Initializing database connection...")
            self.db_manager = get_database_manager()
            logger.info(f"Using database manager: {type(self.db_manager).__name__}")
            await self.db_manager.initialize()
            logger.info("Database tables created/verified successfully")
            
            # Initialize Redis cache for production scalability
            if CACHE_AVAILABLE:
                logger.info("Initializing cache layer...")
                await cache_manager.initialize()
                logger.info("Cache layer ready")
            else:
                logger.warning("Cache layer disabled (dependencies not available)")
            
            # Initialize services
            logger.info("Initializing services...")
            self.content_service = ContentService(self.db_manager)
            self.quiz_service = QuizService(self.db_manager)
            self.analytics_service = AnalyticsService(self.db_manager)
            self.learning_service = LearningProgressionService(
                self.db_manager, self.content_service, self.quiz_service
            )
            
            # Initialize handlers
            self.student_handler = StudentHandler(
                self.db_manager, self.content_service, 
                self.quiz_service, self.analytics_service, self.learning_service
            )
            
            # Initialize scheduler
            self.scheduler = TaskScheduler(
                self.db_manager, self.content_service, 
                self.quiz_service, self.analytics_service
            )
            
            # Initialize Telegram application
            logger.info("Initializing Telegram application...")
            self.app = Application.builder().token(self.config.BOT_TOKEN).build()
            
            # Setup handlers
            await self._setup_handlers()
            
            # Setup bot commands
            await self._setup_bot_commands()
            
            # Setup FastAPI webhook endpoint
            self._setup_webhook_endpoint()
            
            # Start scheduler
            await self.scheduler.start()
            
            # Start metrics updater for production monitoring
            if MONITORING_AVAILABLE:
                logger.info("Starting production monitoring...")
                asyncio.create_task(metrics_updater_task(self))
            else:
                logger.info("Basic monitoring active (enhanced monitoring disabled)")
            
            logger.info("Bot initialization completed successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise

    async def _setup_handlers(self):
        """Setup all message and callback handlers"""
        # Simple start command handler (no conversation needed for auto-registration)
        self.app.add_handler(CommandHandler('start', self.student_handler.start_command))
        
        # Text message handlers for main menu buttons
        self.app.add_handler(MessageHandler(
            filters.Regex('^📚 المواد الأسبوعية$'), 
            self.student_handler.weekly_materials
        ))
        self.app.add_handler(MessageHandler(
            filters.Regex('^📝 الاختبارات$'), 
            self.student_handler.quizzes
        ))
        self.app.add_handler(MessageHandler(
            filters.Regex('^📊 تقدمي$'), 
            self.student_handler.student_progress
        ))
        self.app.add_handler(MessageHandler(
            filters.Regex('^⚙️ الإعدادات$'), 
            self.student_handler.settings
        ))
        self.app.add_handler(MessageHandler(
            filters.Regex('^📞 التواصل$'), 
            self.student_handler.contact_support
        ))
        self.app.add_handler(MessageHandler(
            filters.Regex('^ℹ️ المساعدة$'), 
            self.student_handler.help_command
        ))
        
        # Callback query handler
        self.app.add_handler(CallbackQueryHandler(self.student_handler.handle_callback_query))
        
        # Admin command handlers
        self.app.add_handler(CommandHandler('admin', self._admin_command))
        self.app.add_handler(CommandHandler('stats', self._stats_command))
        self.app.add_handler(CommandHandler('broadcast', self._broadcast_command))
        
        # Help command
        self.app.add_handler(CommandHandler('help', self.student_handler.help_command))
        
        # Unknown message handler
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self._handle_unknown_message
        ))
        
        # Error handler
        self.app.add_error_handler(self._error_handler)

    async def _setup_bot_commands(self):
        """Setup bot commands menu"""
        commands = [
            BotCommand("start", "بدء استخدام البوت والتسجيل"),
            BotCommand("help", "عرض المساعدة والإرشادات"),
            BotCommand("admin", "لوحة التحكم الإدارية")
        ]
        
        await self.app.bot.set_my_commands(commands)

    def _setup_webhook_endpoint(self):
        """Setup FastAPI webhook endpoint"""
        @self.fastapi_app.post(f"/webhook/{self.config.BOT_TOKEN}")
        @self.limiter.limit("200/minute")  # Higher limit for webhook endpoint
        async def webhook_handler(request: Request):
            try:
                # Get update from request
                update_data = await request.json()
                update = Update.de_json(update_data, self.app.bot)
                
                # Process update
                await self.app.process_update(update)
                
                return JSONResponse({"status": "ok"})
                
            except Exception as e:
                logger.error(f"Webhook error: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")

        @self.fastapi_app.get("/health")
        @self.limiter.limit("50/minute")
        async def health_check():
            async with track_request("health_check"):
                health_data = await comprehensive_health_check(self)
                status_code = 200 if health_data['healthy'] else 503
                return JSONResponse(health_data, status_code=status_code)
        
        @self.fastapi_app.get("/metrics")
        @self.limiter.limit("30/minute")
        async def metrics():
            """Prometheus metrics endpoint for production monitoring"""
            return get_metrics_response()

        @self.fastapi_app.get("/")
        async def root():
            return JSONResponse({
                "message": "Telegram Educational Bot is running!",
                "version": "1.0.0",
                "status": "active"
            })

    async def set_webhook(self):
        """Set webhook for the bot"""
        webhook_url = f"{self.config.WEBHOOK_URL}/webhook/{self.config.BOT_TOKEN}"
        
        try:
            success = await self.app.bot.set_webhook(
                url=webhook_url,
                allowed_updates=["message", "callback_query", "inline_query"]
            )
            
            if success:
                logger.info(f"Webhook set successfully to: {webhook_url}")
            else:
                logger.error("Failed to set webhook")
                
            return success
            
        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
            return False

    async def remove_webhook(self):
        """Remove webhook and switch to polling mode"""
        try:
            await self.app.bot.delete_webhook()
            logger.info("Webhook removed successfully")
        except Exception as e:
            logger.error(f"Error removing webhook: {e}")

    async def start_polling(self):
        """Start bot in polling mode"""
        logger.info("Starting bot in polling mode...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

    async def start_webhook(self, host="0.0.0.0", port=8000):
        """Start bot in webhook mode"""
        logger.info(f"Starting webhook server on {host}:{port}")
        
        # Initialize telegram app
        await self.app.initialize()
        await self.app.start()
        
        # Set webhook only if WEBHOOK_URL is configured
        if self.config.WEBHOOK_URL:
            webhook_success = await self.set_webhook()
            if not webhook_success:
                logger.error("Failed to set webhook, but continuing with HTTP server...")
        else:
            # No webhook URL configured, so remove any existing webhook and use polling + HTTP server
            logger.info("No WEBHOOK_URL configured, removing webhook and starting polling in background...")
            await self.remove_webhook()
            
            # Start polling in background
            import asyncio
            asyncio.create_task(self.app.updater.start_polling(drop_pending_updates=True))
        
        # Start FastAPI server (always serve HTTP endpoints for health checks)
        config = uvicorn.Config(
            app=self.fastapi_app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def _admin_command(self, update: Update, context):
        """Handle admin commands"""
        user = update.effective_user
        
        if user.id not in self.config.ADMIN_IDS:
            await update.message.reply_text("غير مخول للوصول للوحة الإدارية.")
            return
        
        admin_text = (
            "🔧 لوحة التحكم الإدارية\n\n"
            "الأوامر المتاحة:\n"
            "/stats - إحصائيات البوت\n"
            "/broadcast - إرسال رسالة جماعية\n"
            "/users - قائمة المستخدمين\n"
            "/analytics - تحليلات مفصلة"
        )
        
        await update.message.reply_text(admin_text)

    async def _stats_command(self, update: Update, context):
        """Show bot statistics"""
        user = update.effective_user
        
        if user.id not in self.config.ADMIN_IDS:
            await update.message.reply_text("غير مخول للوصول لهذا الأمر.")
            return
        
        try:
            stats = await self.analytics_service.get_bot_statistics()
            
            stats_text = (
                f"📊 إحصائيات البوت\n\n"
                f"👥 إجمالي المستخدمين: {stats.get('total_users', 0)}\n"
                f"✅ المستخدمون النشطون: {stats.get('active_users', 0)}\n"
                f"📝 الاختبارات المكتملة: {stats.get('completed_quizzes', 0)}\n"
                f"📚 المواد المنشورة: {stats.get('published_materials', 0)}\n"
                f"📅 تاريخ آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            await update.message.reply_text(stats_text)
            
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            await update.message.reply_text("حدث خطأ في جلب الإحصائيات.")

    async def _broadcast_command(self, update: Update, context):
        """Broadcast message to all users"""
        user = update.effective_user
        
        if user.id not in self.config.ADMIN_IDS:
            await update.message.reply_text("غير مخول للوصول لهذا الأمر.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "استخدام الأمر:\n"
                "/broadcast رسالتك هنا"
            )
            return
        
        message = " ".join(context.args)
        
        try:
            users = await self.db_manager.get_all_active_students()
            sent_count = 0
            failed_count = 0
            
            await update.message.reply_text(f"بدء إرسال الرسالة إلى {len(users)} مستخدم...")
            
            for user_data in users:
                try:
                    await context.bot.send_message(
                        chat_id=user_data['telegram_id'],
                        text=f"📢 رسالة إدارية\n\n{message}"
                    )
                    sent_count += 1
                    await asyncio.sleep(0.1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Failed to send to user {user_data['telegram_id']}: {e}")
                    failed_count += 1
            
            result_text = (
                f"✅ تم إرسال الرسالة\n\n"
                f"نجح الإرسال: {sent_count}\n"
                f"فشل الإرسال: {failed_count}"
            )
            
            await update.message.reply_text(result_text)
            
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            await update.message.reply_text("حدث خطأ أثناء الإرسال.")

    async def _handle_unknown_message(self, update: Update, context):
        """Handle unknown text messages"""
        await update.message.reply_text(
            "لم أفهم رسالتك 🤔\n\n"
            "يمكنك استخدام الأزرار أدناه أو كتابة /help للمساعدة."
        )

    async def _error_handler(self, update: Update, context):
        """Handle errors"""
        logger.error(f"Update {update} caused error: {context.error}")
        
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "حدث خطأ تقني. الرجاء المحاولة مرة أخرى."
                )
            except Exception:
                pass

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down bot...")
        
        try:
            if self.scheduler:
                await self.scheduler.stop()
            
            if self.app:
                await self.app.stop()
                await self.app.shutdown()
            
            if self.db_manager:
                await self.db_manager.close()
                
            logger.info("Bot shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

def setup_signal_handlers(bot: TelegramBot):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(bot.shutdown())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Main application entry point"""
    try:
        bot = TelegramBot()
        setup_signal_handlers(bot)
    except ValueError as config_error:
        # Configuration error - start minimal health server
        logger.error(f"Configuration error: {config_error}")
        logger.info("Starting minimal health server for Railway...")
        
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        import uvicorn
        
        health_app = FastAPI()
        
        @health_app.get("/health")
        async def health():
            return JSONResponse({
                "status": "waiting_for_config",
                "message": "Set BOT_TOKEN and ADMIN_IDS environment variables",
                "timestamp": datetime.now().isoformat()
            })
        
        @health_app.get("/")
        async def root():
            return JSONResponse({
                "message": "Educational Telegram Bot - Configuration Required",
                "required_vars": ["BOT_TOKEN", "ADMIN_IDS"]
            })
        
        port = int(os.getenv('PORT', 8000))
        await uvicorn.Server(
            uvicorn.Config(health_app, host="0.0.0.0", port=port)
        ).serve()
        return
    
    try:
        # Initialize bot
        await bot.initialize()
        
        # Choose mode based on configuration
        # Force webhook mode on Railway (detected by PORT env var)
        if bot.config.WEBHOOK_URL or os.getenv('PORT'):
            logger.info("Starting in webhook mode...")
            # Use Railway's PORT environment variable if available
            port = int(os.getenv('PORT', bot.config.WEBHOOK_PORT))
            await bot.start_webhook(
                host="0.0.0.0",
                port=port
            )
        else:
            logger.info("Starting in polling mode...")
            await bot.start_polling()
            
        # Keep the application running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await bot.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)