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

# Conversation states
AWAITING_NAME, AWAITING_PHONE, AWAITING_SECTION = range(3)

class StudentHandler:
    def __init__(self, db_manager, content_service: ContentService, 
                 quiz_service: QuizService, analytics_service: AnalyticsService):
        self.db = db_manager
        self.content_service = content_service
        self.quiz_service = quiz_service
        self.analytics_service = analytics_service

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
            
            await update.message.reply_text(
                f"مرحباً بك مرة أخرى {existing_student['name']}! 👋\n\n"
                "كيف يمكنني مساعدتك اليوم؟",
                reply_markup=reply_markup
            )
            
            # Log student activity
            await self.analytics_service.log_student_activity(
                existing_student['id'], 'start_command', {'action': 'returning_user'}
            )
            return ConversationHandler.END

        # New user registration
        await update.message.reply_text(
            "أهلاً وسهلاً بك في بوت التعلم! 📚\n\n"
            "لنقوم بتسجيل بياناتك أولاً\n"
            "الرجاء إدخال اسمك الكامل:"
        )
        return AWAITING_NAME

    async def register_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Register student name"""
        name = update.message.text.strip()
        
        if len(name) < 2:
            await update.message.reply_text("الرجاء إدخال اسم صحيح (أكثر من حرفين):")
            return AWAITING_NAME
        
        context.user_data['name'] = name
        await update.message.reply_text(
            f"شكراً {name}! 😊\n\n"
            "الرجاء إدخال رقم هاتفك (مطلوب للتواصل):"
        )
        return AWAITING_PHONE

    async def register_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Register student phone"""
        phone = update.message.text.strip()
        
        # Basic phone validation
        if not phone.replace('+', '').replace('-', '').replace(' ', '').isdigit() or len(phone) < 8:
            await update.message.reply_text("الرجاء إدخال رقم هاتف صحيح:")
            return AWAITING_PHONE
        
        context.user_data['phone'] = phone
        
        # Get available sections
        sections = await self.db.get_available_sections()
        if not sections:
            sections = ["الصف الأول", "الصف الثاني", "الصف الثالث"]
        
        keyboard = []
        for section in sections:
            keyboard.append([InlineKeyboardButton(section, callback_data=f"section:{section}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "اختر صفك الدراسي:",
            reply_markup=reply_markup
        )
        return AWAITING_SECTION

    async def register_section(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Complete student registration"""
        query = update.callback_query
        await query.answer()
        
        section = query.data.replace("section:", "")
        user = update.effective_user
        
        # Create student record
        student_data = {
            'telegram_id': user.id,
            'username': user.username or '',
            'name': context.user_data['name'],
            'phone': context.user_data['phone'],
            'section': section,
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
                f"تم تسجيلك بنجاح! 🎉\n\n"
                f"الاسم: {context.user_data['name']}\n"
                f"الصف: {section}\n\n"
                "يمكنك الآن الوصول إلى جميع الميزات. استخدم الأزرار أدناه للتنقل."
            )
            
            await query.edit_message_text(welcome_message, reply_markup=reply_markup)
            
            # Log registration
            await self.analytics_service.log_student_activity(
                student_id, 'registration', {'section': section}
            )
            
            # Clear user data
            context.user_data.clear()
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            await query.edit_message_text(
                "حدث خطأ أثناء التسجيل. الرجاء المحاولة مرة أخرى لاحقاً."
            )
        
        return ConversationHandler.END

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
            [InlineKeyboardButton("✏️ تعديل البيانات", callback_data="edit_profile")],
            [InlineKeyboardButton("🔄 إعادة تعيين التقدم", callback_data="reset_progress")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        settings_text = (
            f"⚙️ الإعدادات\n\n"
            f"👤 الاسم: {student['name']}\n"
            f"📞 الهاتف: {student['phone']}\n"
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
            await query.edit_message_text(
                f"تم تحديث إعدادات الإشعارات!\n\nالحالة الحالية: {status}"
            )
            
        except Exception as e:
            logger.error(f"Error toggling notifications: {e}")
            await query.edit_message_text("حدث خطأ في تحديث الإعدادات.")

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