#!/usr/bin/env python3
"""
Simple local runner for the Telegram bot
"""

import logging
import asyncio
import os
from datetime import datetime

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Simple configuration
class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./telebot.db')

# Simple imports - create minimal versions if full imports fail
try:
    from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
    from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters
    telegram_available = True
except ImportError:
    telegram_available = False
    logger.error("python-telegram-bot not installed. Install with: pip install python-telegram-bot")

# Simple database for testing
import sqlite3
import json

class SimpleDatabase:
    def __init__(self):
        self.db_path = 'telebot_simple.db'
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                name TEXT,
                section TEXT,
                registration_date TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_student(self, telegram_id, name, section):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO students (telegram_id, name, section, registration_date)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, name, section, datetime.now().isoformat()))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding student: {e}")
            return False
        finally:
            conn.close()
    
    def get_student(self, telegram_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM students WHERE telegram_id = ?', (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'telegram_id': result[1],
                'name': result[2],
                'section': result[3],
                'registration_date': result[4]
            }
        return None

# Simple bot implementation
class SimpleTelegramBot:
    def __init__(self):
        self.config = Config()
        self.db = SimpleDatabase()
        
        if not self.config.BOT_TOKEN:
            logger.error("BOT_TOKEN not found in environment variables!")
            logger.error("Please set BOT_TOKEN=your_bot_token in .env file")
            return
        
        if not telegram_available:
            return
            
        self.app = Application.builder().token(self.config.BOT_TOKEN).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.Regex('^📚 المواد الأسبوعية$'), self.weekly_materials))
        self.app.add_handler(MessageHandler(filters.Regex('^📝 الاختبارات$'), self.quizzes))
        self.app.add_handler(MessageHandler(filters.Regex('^📊 تقدمي$'), self.my_progress))
        self.app.add_handler(MessageHandler(filters.Regex('^ℹ️ المساعدة$'), self.help_command))
        
        # Callback query handler
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Unknown message handler
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.unknown_message))
    
    async def start_command(self, update: Update, context):
        """Handle /start command"""
        user = update.effective_user
        student = self.db.get_student(user.id)
        
        if student:
            # Existing student
            keyboard = [
                [KeyboardButton("📚 المواد الأسبوعية"), KeyboardButton("📝 الاختبارات")],
                [KeyboardButton("📊 تقدمي"), KeyboardButton("ℹ️ المساعدة")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"مرحباً بك مرة أخرى {student['name']}! 👋\n\n"
                "كيف يمكنني مساعدتك اليوم؟",
                reply_markup=reply_markup
            )
        else:
            # New student - simple registration
            await update.message.reply_text(
                "أهلاً وسهلاً بك في بوت التعلم! 📚\n\n"
                "مرحباً بك في النظام التعليمي\n"
                "سيتم تسجيلك باستخدام بيانات حسابك في تيليجرام"
            )
            
            # Auto-register with basic info
            name = user.full_name or user.first_name or f"User_{user.id}"
            section = "الصف الأول"  # Default section
            
            success = self.db.add_student(user.id, name, section)
            
            if success:
                keyboard = [
                    [KeyboardButton("📚 المواد الأسبوعية"), KeyboardButton("📝 الاختبارات")],
                    [KeyboardButton("📊 تقدمي"), KeyboardButton("ℹ️ المساعدة")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                await update.message.reply_text(
                    f"تم تسجيلك بنجاح! 🎉\n\n"
                    f"الاسم: {name}\n"
                    f"الصف: {section}\n\n"
                    "يمكنك الآن استخدام البوت",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("حدث خطأ في التسجيل، حاول مرة أخرى")
    
    async def help_command(self, update: Update, context):
        """Help command"""
        help_text = (
            "ℹ️ المساعدة\n\n"
            "الأوامر المتاحة:\n\n"
            "📚 المواد الأسبوعية - لمراجعة المواد الدراسية\n"
            "📝 الاختبارات - لحل الاختبارات والواجبات\n"
            "📊 تقدمي - لمتابعة تقدمك الأكاديمي\n\n"
            "نصائح:\n"
            "• استخدم الأزرار للتنقل السريع\n"
            "• البوت يدعم اللغة العربية بالكامل\n"
            "• يمكنك التواصل في أي وقت"
        )
        
        await update.message.reply_text(help_text)
    
    async def stats_command(self, update: Update, context):
        """Stats command (for admins)"""
        user = update.effective_user
        
        if user.id not in self.config.ADMIN_IDS:
            await update.message.reply_text("غير مخول للوصول لهذا الأمر.")
            return
        
        # Simple stats
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM students')
        total_students = cursor.fetchone()[0]
        conn.close()
        
        stats_text = (
            f"📊 إحصائيات البوت\n\n"
            f"👥 إجمالي الطلاب: {total_students}\n"
            f"📅 تاريخ التحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        await update.message.reply_text(stats_text)
    
    async def weekly_materials(self, update: Update, context):
        """Weekly materials"""
        keyboard = [
            [InlineKeyboardButton("📄 مادة الأسبوع الأول", callback_data="material_1")],
            [InlineKeyboardButton("📄 مادة الأسبوع الثاني", callback_data="material_2")],
            [InlineKeyboardButton("📄 مادة الأسبوع الثالث", callback_data="material_3")],
            [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📚 المواد الأسبوعية\n\n"
            "اختر المادة التي تريد مراجعتها:",
            reply_markup=reply_markup
        )
    
    async def quizzes(self, update: Update, context):
        """Quizzes"""
        keyboard = [
            [InlineKeyboardButton("📝 اختبار الأسبوع الأول", callback_data="quiz_1")],
            [InlineKeyboardButton("📝 اختبار الأسبوع الثاني", callback_data="quiz_2")],
            [InlineKeyboardButton("📝 اختبار شامل", callback_data="quiz_3")],
            [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📝 الاختبارات المتاحة\n\n"
            "اختر الاختبار الذي تريد حله:",
            reply_markup=reply_markup
        )
    
    async def my_progress(self, update: Update, context):
        """Student progress"""
        user = update.effective_user
        student = self.db.get_student(user.id)
        
        if not student:
            await update.message.reply_text("الرجاء التسجيل أولاً باستخدام /start")
            return
        
        progress_text = (
            f"📊 تقدمك الأكاديمي\n\n"
            f"👤 الاسم: {student['name']}\n"
            f"📚 الصف: {student['section']}\n"
            f"📅 تاريخ التسجيل: {student['registration_date'][:10]}\n\n"
            f"📈 الإحصائيات:\n"
            f"• الاختبارات المكتملة: 0\n"
            f"• المواد المراجعة: 0\n"
            f"• متوسط الدرجات: 0%\n\n"
            f"🎯 نصيحة: ابدأ بمراجعة المواد الأسبوعية!"
        )
        
        await update.message.reply_text(progress_text)
    
    async def handle_callback(self, update: Update, context):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "main_menu":
            keyboard = [
                [KeyboardButton("📚 المواد الأسبوعية"), KeyboardButton("📝 الاختبارات")],
                [KeyboardButton("📊 تقدمي"), KeyboardButton("ℹ️ المساعدة")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await query.edit_message_text(
                "🏠 القائمة الرئيسية\n\nكيف يمكنني مساعدتك؟"
            )
        
        elif data.startswith("material_"):
            material_num = data.split("_")[1]
            await query.edit_message_text(
                f"📄 محتوى المادة {material_num}\n\n"
                f"هذه مادة تعليمية تجريبية للأسبوع رقم {material_num}\n\n"
                f"📝 الموضوع: مقدمة في الموضوع {material_num}\n"
                f"⏱️ وقت القراءة المتوقع: 15 دقيقة\n"
                f"📊 مستوى الصعوبة: متوسط\n\n"
                f"المحتوى سيكون متاحاً قريباً..."
            )
        
        elif data.startswith("quiz_"):
            quiz_num = data.split("_")[1]
            keyboard = [
                [InlineKeyboardButton("🎯 ابدأ الاختبار", callback_data=f"start_quiz_{quiz_num}")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_quizzes")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📝 اختبار رقم {quiz_num}\n\n"
                f"📊 عدد الأسئلة: 10 أسئلة\n"
                f"⏱️ الوقت المحدد: 15 دقيقة\n"
                f"🎯 درجة النجاح: 60%\n"
                f"🔄 عدد المحاولات: 3\n\n"
                f"هل تريد البدء؟",
                reply_markup=reply_markup
            )
        
        elif data.startswith("start_quiz_"):
            quiz_num = data.split("_")[2]
            await query.edit_message_text(
                f"🎯 جاري تحضير الاختبار رقم {quiz_num}...\n\n"
                f"هذه ميزة تجريبية وستكون متاحة قريباً!\n"
                f"سيتضمن الاختبار أسئلة متنوعة مع تصحيح فوري."
            )
    
    async def unknown_message(self, update: Update, context):
        """Handle unknown messages"""
        await update.message.reply_text(
            "لم أفهم رسالتك 🤔\n\n"
            "يمكنك استخدام الأزرار أدناه أو كتابة /help للمساعدة."
        )
    
    async def run(self):
        """Run the bot"""
        if not telegram_available:
            logger.error("Cannot run bot: telegram library not available")
            return
        
        if not self.config.BOT_TOKEN:
            logger.error("Cannot run bot: BOT_TOKEN not configured")
            return
        
        logger.info("Starting Telegram bot in polling mode...")
        
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        
        logger.info("Bot is running! Press Ctrl+C to stop.")
        
        try:
            # Keep running until interrupted
            await asyncio.Future()  # run forever
        except KeyboardInterrupt:
            logger.info("Received stop signal")
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

async def main():
    """Main function"""
    print("🤖 Telegram Educational Bot - Local Test Version")
    print("=" * 50)
    
    # Check environment
    bot_token = os.getenv('BOT_TOKEN', '')
    if not bot_token or bot_token == 'your_bot_token_here':
        print("❌ Error: BOT_TOKEN not configured!")
        print("\n📝 Please follow these steps:")
        print("1. Edit the .env file in this directory")
        print("2. Replace 'your_bot_token_here' with your actual bot token")
        print("3. Get bot token from @BotFather on Telegram")
        print("4. Add your Telegram user ID to ADMIN_IDS")
        print("\nExample .env configuration:")
        print("BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ")
        print("ADMIN_IDS=123456789")
        return
    
    if not telegram_available:
        print("❌ Error: python-telegram-bot library not installed!")
        print("\n📦 Install it with:")
        print("pip install python-telegram-bot")
        return
    
    print("✅ Configuration looks good!")
    print(f"🔑 Bot token: {bot_token[:10]}...")
    print(f"👑 Admin IDs: {os.getenv('ADMIN_IDS', 'Not set')}")
    print("\n🚀 Starting bot...")
    
    # Create and run bot
    bot = SimpleTelegramBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        logger.error(f"Bot crashed: {e}", exc_info=True)