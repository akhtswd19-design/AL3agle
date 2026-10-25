import os
import json
import asyncio
from flask import Flask, render_template, jsonify, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, PreCheckoutQueryHandler
)

# ----------------- الإعدادات والرموز -----------------
TOKEN = "8622474758:AAFcIwB0EOHK1luEnYig6yxE4ZxmbU0XOxo"
ADMIN_ID = 1056007305
SAR_TO_STARS_RATE = 11.5  # معامل التحويل التلقائي للنجوم

# قاعدة بيانات مصغرة بالذاكرة/الملفات
DATA_FILE = "store_db.json"

def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "products": [],
        "reviews": [
            {"id": 1, "user_name": "أبو فهد", "rating": 5, "comment": "ملفات ممتازة ومكتملة جداً، أنصح بها."},
            {"id": 2, "user_name": "سعد العتيبي", "rating": 5, "comment": "تسليم سريع فور الدفع بالنجوم."}
        ],
        "users": [],
        "orders_count": 0
    }

def save_db(db):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

db = load_db()

# ----------------- تطبيق Flask (تطبيق مصغر) -----------------
app = Flask(__name__, template_folder=".")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/store-data')
def store_data():
    return jsonify({
        "products": db["products"],
        "reviews": db["reviews"]
    })

# ----------------- منطق بوت التليجرام -----------------
TITLE, PRICE, DESC, PHOTO, GROUP_LINK = range(5)
BROADCAST_MSG = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)
    
    keyboard = [[
        InlineKeyboardButton("🚀 فتح متجر العاقل", web_app={"url": os.getenv("RENDER_EXTERNAL_URL", "https://your-render-app.onrender.com")})
    ]]
    await update.message.reply_text(
        "أهلاً بك في *متجر العاقل للملفات العسكرية* 🎖️\nاضغط على الزر أدناه لفتح المتجر المصغر:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# --- لوحة التحكم (/admin) ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("➕ إضافة منتج", callback_data="add_prod"), InlineKeyboardButton("✏️ تعديل/حذف منتج", callback_data="manage_prods")],
        [InlineKeyboardButton("📊 إحصائيات الطلبات", callback_data="stats"), InlineKeyboardButton("📢 رسالة جماعية", callback_data="broadcast")],
        [InlineKeyboardButton("⭐ إدارة التقييمات", callback_data="manage_reviews")]
    ]
    await update.message.reply_text("لوحة تحكم الأدمن:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "stats":
        msg = f"📊 *إحصائيات المتجر:*\n\n- إجمالي الطلبات: {db['orders_count']}\n- عدد المشتركين/المستخدمين: {len(db['users'])}\n- عدد المنتجات: {len(db['products'])}"
        await query.edit_message_text(msg, parse_mode="Markdown")
        
    elif query.data == "manage_reviews":
        keyboard = []
        for r in db["reviews"]:
            keyboard.append([InlineKeyboardButton(f"❌ حذف تقييم: {r['user_name']}", callback_data=f"del_rev_{r['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_admin")])
        await query.edit_message_text("اختر التقييم المراد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data.startswith("del_rev_"):
        rev_id = int(query.data.split("_")[2])
        db["reviews"] = [r for r in db["reviews"] if r["id"] != rev_id]
        save_db(db)
        await query.edit_message_text("✅ تم حذف التقييم بنجاح.")

# --- إضافة منتج ---
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("أدخل اسم المنتج:")
    return TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['prod_title'] = update.message.text
    await update.message.reply_text("أدخل سعر المنتج بالريال السعودي (سيتم حسابه تلقائياً بالنجوم):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price_sar = float(update.message.text)
        stars = int(price_sar * SAR_TO_STARS_RATE)
        context.user_data['prod_price_sar'] = price_sar
        context.user_data['prod_stars'] = stars
        await update.message.reply_text(f"السعر بالريال: {price_sar}\nالمعادل بالنجوم: ★ {stars}\n\nالآن أدخل وصف المنتج:")
        return DESC
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم صحيح للسعر.")
        return PRICE

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['prod_desc'] = update.message.text
    await update.message.reply_text("أرسل صورة المنتج كـ (مرفق صورة مباشرة وليست رابط):")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    # حفظ رابط الصورة
    context.user_data['prod_photo'] = photo_file.file_path
    await update.message.reply_text("أدخل رابط قروب التليجرام الخاص بالملفات (سيتم إرساله للعميل تلقائياً بعد الشراء):")
    return GROUP_LINK

async def get_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_link = update.message.text
    
    new_product = {
        "id": len(db["products"]) + 1,
        "title": context.user_data['prod_title'],
        "price_sar": context.user_data['prod_price_sar'],
        "stars": context.user_data['prod_stars'],
        "description": context.user_data['prod_desc'],
        "image_url": context.user_data['prod_photo'],
        "group_link": group_link
    }
    db["products"].append(new_product)
    save_db(db)
    
    await update.message.reply_text("✅ تم إضافة المنتج بنجاح! جاري إرسال إشعار لكافة الزبائن...")
    
    # إرسال رسالة جماعية بالمنتج الجديد
    for uid in db["users"]:
        try:
            await context.bot.send_photo(
                chat_id=uid,
                photo=new_product["image_url"],
                caption=f"🔥 *منتج جديد في متجر العاقل!\n\n📌 *{new_product['title']}**\n📝 {new_product['description']}\n\n💰 السعر: {new_product['price_sar']} ر.س (★ {new_product['stars']} نجمة)",
                parse_mode="Markdown"
            )
        except Exception:
            pass
            
    return ConversationHandler.END

# --- إشعار دفع نجوم تليجرام ---
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db["orders_count"] += 1
    save_db(db)
    
    # الحصول على رابط القروب الخاص بالمنتج وإرساله
    await update.message.reply_text(
        "🎉 *شكراً لشرائك من متجر العاقل!*\n\nيمكنك الانضمام لقروب الملفات العسكرية عبر الرابط التالي:\nhttps://t.me/+ExampleGroupLink",
        parse_mode="Markdown"
    )

# ----------------- التشغيل الرئيسي -----------------
def main():
    application = Application.builder().token(TOKEN).build()

    # المحادثات
    add_prod_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_product_start, pattern="^add_prod$")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_desc)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            GROUP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_link)],
        },
        fallbacks=[]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(add_prod_handler)
    application.add_handler(CallbackQueryHandler(admin_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # تشغيل البوت
    application.run_polling()

if _name_ == '_main_':
    main()
