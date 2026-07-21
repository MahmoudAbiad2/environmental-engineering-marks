import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from supabase import create_client, Client

# --- إعداد خادم Web بسيط لمنع نوم البوت ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- إعداد التسجيل ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت **علاماتي - هندسة تقنية - بيئة** 🌿\n\n"
        "يرجى إرسال **اسمك الثلاثي** أو **رقمك الجامعي** لمشاهدة علاماتك.",
        parse_mode="Markdown"
    )

def build_student_keyboard(student_id, student_grades):
    keyboard = [
        [InlineKeyboardButton(text="📋 اجلب كل علاماتي", callback_data=f"all_{student_id}")]
    ]
    for row in student_grades:
        keyboard.append([InlineKeyboardButton(text=f"📚 {row['subject']}", callback_data=f"sub_{row['id']}")])
        
    return InlineKeyboardMarkup(keyboard)

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()

    try:
        response = supabase.table("grades").select("*").or_(
            f"student_id.eq.{query_text},student_name.ilike.%{query_text}%"
        ).execute()

        results = response.data

        if not results:
            await update.message.reply_text("❌ لم يتم العثور على طالب بهذا الاسم أو الرقم الجامعي. يرجى التأكد وإعادة المحاولة.")
            return

        student_name = results[0]['student_name']
        student_id = results[0]['student_id']

        student_grades = [r for r in results if r['student_id'] == student_id]
        reply_markup = build_student_keyboard(student_id, student_grades)

        await update.message.reply_text(
            f"👤 الطالب: **{student_name}**\n"
            f"الرقم الجامعي: `{student_id}`\n\n"
            f"اختر مادة لعرض تفاصيلها، أو اضغط على (اجلب كل علاماتي):",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error querying Supabase: {e}")
        await update.message.reply_text("عذراً، حدث خطأ أثناء الاتصال بقاعدة البيانات.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    try:
        if data.startswith("all_"):
            student_id = data.split("_")[1]
            response = supabase.table("grades").select("*").eq("student_id", student_id).execute()
            student_grades = response.data

            if not student_grades:
                await query.edit_message_text("لم يتم العثور على علامات.")
                return

            student_name = student_grades[0]['student_name']
            
            message = f"📊 **كشف العلامات الشامل**\n"
            message += f"👤 **الطالب:** {student_name}\n"
            message += f"🆔 **الرقم الجامعي:** `{student_id}`\n"
            message += "----------------------------------\n\n"

            for row in student_grades:
                total = float(row['total'])
                status = "✅ نجاح" if total >= 60 else "❌ رسوب"
                
                message += f"📖 **{row['subject']}**\n"
                message += f"├ العملي: {row['practical']} | النظري: {row['theoretical']}\n"
                message += f"├ المجموع: **{total:g}** ({status})\n"
                message += f"└ التفاصيل: {row['details'] or 'لا يوجد'}\n"
                message += "----------------------------------\n"

            keyboard = [[InlineKeyboardButton("⬅️ العودة للقائمة", callback_data=f"back_{student_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")

        elif data.startswith("sub_"):
            record_id = int(data.split("_")[1])
            response = supabase.table("grades").select("*").eq("id", record_id).execute()
            
            if response.data:
                row = response.data[0]
                total = float(row['total'])
                status = "✅ نجاح" if total >= 60 else "❌ رسوب"
                
                message = (
                    f"📘 **مادة: {row['subject']}**\n"
                    f"👤 الطالب: {row['student_name']}\n"
                    f"----------------------------------\n"
                    f"🔹 **العملي:** {row['practical']}\n"
                    f"📝 **تفاصيل العملي:** {row['details'] or 'لا يوجد'}\n"
                    f"🔹 **النظري:** {row['theoretical']}\n"
                    f"----------------------------------\n"
                    f"📊 **المجموع النهائي:** {total:g} ({status})\n"
                )
                
                keyboard = [[InlineKeyboardButton("⬅️ العودة للقائمة", callback_data=f"back_{row['student_id']}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")

        elif data.startswith("back_"):
            student_id = data.split("_")[1]
            response = supabase.table("grades").select("*").eq("student_id", student_id).execute()
            student_grades = response.data

            reply_markup = build_student_keyboard(student_id, student_grades)
            
            await query.edit_message_text(
                text=f"👤 الطالب: **{student_grades[0]['student_name']}**\n"
                     f"اختر مادة لعرض تفاصيلها، أو اضغط على (اجلب كل علاماتي):",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logging.error(f"Callback error: {e}")
        await query.edit_message_text("حدث خطأ أثناء معالجة الطلب.")

def main():
    # تشغيل سيرفر الويب في خلفية المنشور لإبقاء الـ Port مفتوحاً
    server_thread = Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("البوت يعمل ويتصل بـ Supabase...")
    app.run_polling()

if __name__ == "__main__":
    main()