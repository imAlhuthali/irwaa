import logging
from typing import Dict, Any, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
import asyncio

from models import get_database_manager
from services.content_service import ContentService
from services.quiz_service import QuizService
from services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

# Conversation states (kept for compatibility, may be used for other features)
AWAITING_NAME, AWAITING_PHONE, AWAITING_SECTION = range(3)

class StudentHandler:
    def __init__(self, db_manager, content_service: ContentService, 
                 quiz_service: QuizService, analytics_service: AnalyticsService, 
                 learning_service=None):
        self.db = db_manager
        self.content_service = content_service
        self.quiz_service = quiz_service
        self.analytics_service = analytics_service
        self.learning_service = learning_service

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /start command in Arabic"""
        user = update.effective_user
        
        # Check if user is already registered
        existing_student = await self.db.get_student_by_telegram_id(user.id)
        if existing_student:
            keyboard = [
                [KeyboardButton("📚 المواد الأسبوعية"), KeyboardButton("📝 الاختبارات")],
                [KeyboardButton("📊 تقدمي"), KeyboardButton("⚙️ الإعدادات")],
                [KeyboardButton("📞 التواصل"), KeyboardButton("ℹ️ المساعدة")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            display_name = existing_student.get('name') or user.first_name or user.username or 'صديق'
            await update.message.reply_text(
                f"مرحباً بك مرة أخرى {display_name}! 👋\n\n"
                "كيف يمكنني مساعدتك اليوم؟",
                reply_markup=reply_markup
            )
            
            # Log student activity
            await self.analytics_service.log_student_activity(
                existing_student['id'], 'start_command', {'action': 'returning_user'}
            )
            return ConversationHandler.END

        # Auto-register new user with Telegram info
        await self._auto_register_user(update, context)
        return ConversationHandler.END

    async def _auto_register_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Automatically register user using Telegram information"""
        user = update.effective_user
        
        # Use Telegram's built-in information
        display_name = user.first_name or user.username or f"مستخدم{user.id}"
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or display_name
        
        # Create student record with Telegram info
        student_data = {
            'telegram_id': user.id,
            'username': user.username or '',
            'name': full_name,
            'phone': '',  # Not required anymore
            'section': 'عام',  # Default section, can be changed in settings
            'registration_date': datetime.now(),
            'is_active': True,
            'notification_enabled': True
        }
        
        try:
            student_id = await self.db.create_student(student_data)
            
            # Main menu keyboard
            keyboard = [
                [KeyboardButton("📚 المواد الأسبوعية"), KeyboardButton("📝 الاختبارات")],
                [KeyboardButton("📊 تقدمي"), KeyboardButton("⚙️ الإعدادات")],
                [KeyboardButton("📞 التواصل"), KeyboardButton("ℹ️ المساعدة")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            welcome_message = (
                f"مرحباً بك {display_name}! 🎉\n\n"
                f"تم تسجيلك تلقائياً في النظام\n"
                f"الاسم: {full_name}\n"
                f"الصف: عام (يمكنك تغييره في الإعدادات)\n\n"
                "يمكنك الآن الوصول إلى جميع الميزات. استخدم الأزرار أدناه للتنقل."
            )
            
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)
            
            # Log registration
            await self.analytics_service.log_student_activity(
                student_id, 'auto_registration', {'telegram_username': user.username}
            )
            
        except Exception as e:
            logger.error(f"Auto registration error: {e}")
            await update.message.reply_text(
                f"مرحباً بك {display_name}! 👋\n\n"
                "حدث خطأ بسيط في التسجيل، ولكن يمكنك المتابعة واستخدام البوت.\n"
                "سيتم إعادة المحاولة تلقائياً عند استخدام أي ميزة."
            )

    async def weekly_materials(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show weekly materials"""
        user = update.effective_user
        student = await self.db.get_student_by_telegram_id(user.id)
        
        if not student:
            await update.message.reply_text("الرجاء التسجيل أولاً باستخدام /start")
            return
        
        try:
            materials = await self.content_service.get_weekly_materials(student['section'])
            
            if not materials:
                await update.message.reply_text(
                    "لا توجد مواد متاحة حالياً لصفك.\n"
                    "سيتم إشعارك عند توفر مواد جديدة! 📚"
                )
                return
            
            # Create materials keyboard
            keyboard = []
            for material in materials[:10]:  # Limit to 10 items
                keyboard.append([
                    InlineKeyboardButton(
                        f"📄 {material['title']}", 
                        callback_data=f"material:{material['id']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("🔄 تحديث", callback_data="refresh_materials"),
                InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"📚 المواد الأسبوعية - {student['section']}\n\n"
                f"عدد المواد المتاحة: {len(materials)}\n"
                "اختر المادة التي تريد مراجعتها:",
                reply_markup=reply_markup
            )
            
            # Log activity
            await self.analytics_service.log_student_activity(
                student['id'], 'view_materials', {'materials_count': len(materials)}
            )
            
        except Exception as e:
            logger.error(f"Error fetching materials: {e}")
            await update.message.reply_text("حدث خطأ في جلب المواد. حاول مرة أخرى.")

    async def quizzes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available quizzes"""
        user = update.effective_user
        student = await self.db.get_student_by_telegram_id(user.id)
        
        if not student:
            await update.message.reply_text("الرجاء التسجيل أولاً باستخدام /start")
            return
        
        try:
            quizzes = await self.quiz_service.get_available_quizzes(student['section'])
            
            if not quizzes:
                await update.message.reply_text(
                    "لا توجد اختبارات متاحة حالياً.\n"
                    "سيتم إشعارك عند توفر اختبارات جديدة! 📝"
                )
                return
            
            keyboard = []
            for quiz in quizzes[:8]:  # Limit to 8 quizzes
                status_emoji = "✅" if quiz.get('completed') else "📝"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status_emoji} {quiz['title']}", 
                        callback_data=f"quiz:{quiz['id']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("📊 نتائجي", callback_data="quiz_results"),
                InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"📝 الاختبارات المتاحة - {student['section']}\n\n"
                f"عدد الاختبارات: {len(quizzes)}\n"
                "اختر الاختبار الذي تريد حله:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error fetching quizzes: {e}")
            await update.message.reply_text("حدث خطأ في جلب الاختبارات. حاول مرة أخرى.")

    async def student_progress(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show student progress and analytics"""
        user = update.effective_user
        student = await self.db.get_student_by_telegram_id(user.id)
        
        if not student:
            await update.message.reply_text("الرجاء التسجيل أولاً باستخدام /start")
            return
        
        try:
            progress = await self.analytics_service.get_student_progress(student['id'])
            
            progress_text = f"📊 تقدمك الأكاديمي\n\n"
            progress_text += f"👤 الاسم: {student['name']}\n"
            progress_text += f"📚 الصف: {student['section']}\n"
            progress_text += f"📅 تاريخ التسجيل: {student['registration_date'].strftime('%Y-%m-%d')}\n\n"
            
            if progress:
                progress_text += f"📈 إحصائيات الأداء:\n"
                progress_text += f"• الاختبارات المكتملة: {progress.get('completed_quizzes', 0)}\n"
                progress_text += f"• متوسط الدرجات: {progress.get('average_score', 0):.1f}%\n"
                progress_text += f"• المواد المراجعة: {progress.get('materials_viewed', 0)}\n"
                progress_text += f"• أيام النشاط: {progress.get('active_days', 0)}\n"
                
                # Performance badge
                avg_score = progress.get('average_score', 0)
                if avg_score >= 90:
                    progress_text += f"\n🏆 مستواك: ممتاز"
                elif avg_score >= 80:
                    progress_text += f"\n🥈 مستواك: جيد جداً"
                elif avg_score >= 70:
                    progress_text += f"\n🥉 مستواك: جيد"
                else:
                    progress_text += f"\n📈 مستواك: يحتاج تحسين"
            else:
                progress_text += "لم تبدأ بعد! ابدأ بحل الاختبارات ومراجعة المواد."
            
            keyboard = [
                [InlineKeyboardButton("📊 تفاصيل أكثر", callback_data="detailed_progress")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(progress_text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error fetching progress: {e}")
            await update.message.reply_text("حدث خطأ في جلب التقدم. حاول مرة أخرى.")

    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user settings"""
        user = update.effective_user
        student = await self.db.get_student_by_telegram_id(user.id)
        
        if not student:
            await update.message.reply_text("الرجاء التسجيل أولاً باستخدام /start")
            return
        
        notification_status = "مفعلة ✅" if student['notification_enabled'] else "معطلة ❌"
        
        keyboard = [
            [InlineKeyboardButton("🔔 إعدادات الإشعارات", callback_data="toggle_notifications")],
            [InlineKeyboardButton("📚 تغيير الصف", callback_data="change_section")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        display_name = student['name'] or user.first_name or user.username or 'مستخدم'
        phone_display = student.get('phone', '') or 'غير محدد'
        
        settings_text = (
            f"⚙️ الإعدادات\n\n"
            f"👤 الاسم: {display_name}\n"
            f"📱 معرف التيليجرام: @{user.username or 'غير محدد'}\n"
            f"📚 الصف: {student['section']}\n"
            f"🔔 الإشعارات: {notification_status}\n\n"
            "اختر الإعداد الذي تريد تغييره:"
        )
        
        await update.message.reply_text(settings_text, reply_markup=reply_markup)

    async def contact_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show contact information"""
        contact_text = (
            "📞 التواصل والدعم\n\n"
            "يمكنك التواصل معنا من خلال:\n\n"
            "📧 البريد الإلكتروني: support@example.com\n"
            "📱 واتساب: +1234567890\n"
            "⏰ أوقات العمل: 8:00 ص - 8:00 م\n\n"
            "أو يمكنك ترك رسالة هنا وسنرد عليك قريباً! 💬"
        )
        
        keyboard = [
            [InlineKeyboardButton("💬 إرسال رسالة", callback_data="send_message")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(contact_text, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        help_text = (
            "ℹ️ المساعدة\n\n"
            "الأوامر المتاحة:\n\n"
            "📚 المواد الأسبوعية - لمراجعة المواد الدراسية\n"
            "📝 الاختبارات - لحل الاختبارات والواجبات\n"
            "📊 تقدمي - لمتابعة تقدمك الأكاديمي\n"
            "⚙️ الإعدادات - لتعديل بياناتك وإعداداتك\n"
            "📞 التواصل - للتواصل مع الدعم\n\n"
            "نصائح:\n"
            "• استخدم الأزرار للتنقل السريع\n"
            "• ستصلك إشعارات بالمواد الجديدة\n"
            "• يمكنك حل الاختبارات أكثر من مرة\n"
            "• تابع تقدمك بانتظام للحصول على أفضل النتائج"
        )
        
        keyboard = [
            [InlineKeyboardButton("📞 التواصل", callback_data="contact_support")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup)

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = update.effective_user
        
        try:
            if data == "main_menu":
                await self._show_main_menu(query, user.id)
            elif data.startswith("material:"):
                material_id = int(data.split(":")[1])
                await self._show_material_content(query, user.id, material_id)
            elif data.startswith("quiz:"):
                quiz_id = int(data.split(":")[1])
                await self._start_quiz(query, user.id, quiz_id)
            elif data == "refresh_materials":
                await self._refresh_materials(query, user.id)
            elif data == "toggle_notifications":
                await self._toggle_notifications(query, user.id)
            elif data == "change_section":
                await self._show_section_selection(query, user.id)
            elif data.startswith("select_section:"):
                section = data.replace("select_section:", "")
                await self._update_user_section(query, user.id, section)
            elif data == "settings_menu":
                await self._show_settings_menu(query, user.id)
            elif data == "detailed_progress":
                await self._show_detailed_progress(query, user.id)
            # Add more callback handlers as needed
                
        except Exception as e:
            logger.error(f"Callback query error: {e}")
            await query.edit_message_text("حدث خطأ. الرجاء المحاولة مرة أخرى.")

    async def _show_main_menu(self, query, user_id: int):
        """Show main menu"""
        keyboard = [
            [KeyboardButton("📚 المواد الأسبوعية"), KeyboardButton("📝 الاختبارات")],
            [KeyboardButton("📊 تقدمي"), KeyboardButton("⚙️ الإعدادات")],
            [KeyboardButton("📞 التواصل"), KeyboardButton("ℹ️ المساعدة")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await query.edit_message_text(
            "🏠 القائمة الرئيسية\n\nكيف يمكنني مساعدتك؟",
            reply_markup=reply_markup
        )

    async def _show_material_content(self, query, user_id: int, material_id: int):
        """Show specific material content"""
        student = await self.db.get_student_by_telegram_id(user_id)
        if not student:
            await query.edit_message_text("الرجاء التسجيل أولاً.")
            return
        
        try:
            material = await self.content_service.get_material_by_id(material_id)
            if not material:
                await query.edit_message_text("المادة غير متاحة.")
                return
            
            # Log material view
            await self.analytics_service.log_student_activity(
                student['id'], 'view_material', {'material_id': material_id}
            )
            
            content_text = f"📄 {material['title']}\n\n"
            content_text += f"📅 تاريخ النشر: {material['date_published']}\n"
            content_text += f"📝 الوصف: {material['description']}\n\n"
            
            if material.get('content'):
                content_text += material['content'][:1000]  # Limit content length
                if len(material['content']) > 1000:
                    content_text += "\n\n... (اضغط لقراءة المزيد)"
            
            keyboard = [
                [InlineKeyboardButton("📥 تحميل الملف", callback_data=f"download:{material_id}")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="refresh_materials")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(content_text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error showing material: {e}")
            await query.edit_message_text("حدث خطأ في عرض المادة.")

    async def _toggle_notifications(self, query, user_id: int):
        """Toggle notification settings"""
        try:
            current_setting = await self.db.get_student_notification_setting(user_id)
            new_setting = not current_setting
            
            await self.db.update_student_notification_setting(user_id, new_setting)
            
            status = "مفعلة ✅" if new_setting else "معطلة ❌"
            keyboard = [[InlineKeyboardButton("🔙 الإعدادات", callback_data="settings_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"تم تحديث إعدادات الإشعارات!\n\nالحالة الحالية: {status}",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error toggling notifications: {e}")
            await query.edit_message_text("حدث خطأ في تحديث الإعدادات.")

    async def _show_section_selection(self, query, user_id: int):
        """Show available sections for selection"""
        try:
            sections = await self.db.get_available_sections()
            if not sections:
                sections = ["الصف الأول", "الصف الثاني", "الصف الثالث", "الصف الرابع", "عام"]
            
            keyboard = []
            for section in sections:
                keyboard.append([InlineKeyboardButton(section, callback_data=f"select_section:{section}")])
            
            keyboard.append([InlineKeyboardButton("🔙 الإعدادات", callback_data="settings_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📚 اختر صفك الدراسي:\n\nيمكنك تغيير الصف في أي وقت من الإعدادات",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error showing section selection: {e}")
            await query.edit_message_text("حدث خطأ في عرض الأقسام.")

    async def _update_user_section(self, query, user_id: int, section: str):
        """Update user's section"""
        try:
            await self.db.update_student_section(user_id, section)
            
            keyboard = [[InlineKeyboardButton("🔙 الإعدادات", callback_data="settings_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ تم تحديث صفك الدراسي!\n\nالصف الحالي: {section}",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error updating section: {e}")
            await query.edit_message_text("حدث خطأ في تحديث الصف.")

    async def _show_settings_menu(self, query, user_id: int):
        """Show settings menu"""
        try:
            student = await self.db.get_student_by_telegram_id(user_id)
            if not student:
                await query.edit_message_text("الرجاء التسجيل أولاً.")
                return
            
            notification_status = "مفعلة ✅" if student['notification_enabled'] else "معطلة ❌"
            display_name = student['name'] or query.from_user.first_name or query.from_user.username or 'مستخدم'
            
            keyboard = [
                [InlineKeyboardButton("🔔 إعدادات الإشعارات", callback_data="toggle_notifications")],
                [InlineKeyboardButton("📚 تغيير الصف", callback_data="change_section")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            settings_text = (
                f"⚙️ الإعدادات\n\n"
                f"👤 الاسم: {display_name}\n"
                f"📱 معرف التيليجرام: @{query.from_user.username or 'غير محدد'}\n"
                f"📚 الصف: {student['section']}\n"
                f"🔔 الإشعارات: {notification_status}\n\n"
                "اختر الإعداد الذي تريد تغييره:"
            )
            
            await query.edit_message_text(settings_text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            await query.edit_message_text("حدث خطأ في عرض الإعدادات.")

    def get_conversation_handler(self):
        """Return the conversation handler for registration"""
        return ConversationHandler(
            entry_points=[],  # Will be set in main app
            states={
                AWAITING_NAME: [],
                AWAITING_PHONE: [],
                AWAITING_SECTION: []
            },
            fallbacks=[]
        )