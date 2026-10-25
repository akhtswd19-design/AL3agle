import os
import json
import threading
from flask import Flask, render_template, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, PreCheckoutQueryHandler
)

# ----------------- الإعدادات والتوكن -----------------
TOKEN = "8622474758:AAFcIwB0EOHK1luEnYig6yxE4ZxmbU0XOxo"
ADMIN_ID = 1056007305
SAR_TO_STARS_RATE = 11.5  # معامل التحويل التلقائي للريال إلى نجوم تليجرام

DATA_FILE = "store_db.json"

def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "products": [],
        "reviews": [
            {"id": 1, "user_name": "سلطان الحربي", "rating": 5, "comment": "ملفات عسكرية دقيقة وذات قيمة عالية جداً."},
            {"id": 2, "user_name": "نايف القحطاني", "rating": 5, "comment": "تم الدفع بالنجوم واستلام الرابط فوراً، شكراً متجر العاقل."}
        ],
        "users": [],
        "orders_count": 0
    }

def save_db(db):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

db = load_db()

# ----------------- إعداد خادم Flask -----------------
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

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ----------------- بوت التليجرام والمحادثات -----------------
TITLE, PRICE, DESC, PHOTO, GROUP_LINK = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)
    
    web_app_url = os.getenv("RENDER_EXTERNAL_URL", "https://al3agle.onrender.com")
    keyboard = [[
        InlineKeyboardButton("🚀 فتح متجر العاقل", web_app={"url": web_app_url})
    ]]
    await update.message.reply_text(
        "أهلاً بك في *متجر العاقل للملفات العسكرية* 🎖️\nاضغط على الزر أدناه لتصفح المتجر المصغر:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# لوحة تحكم الأدمن
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("➕ إضافة منتج جديد", callback_data="add_prod"), InlineKeyboardButton("🗑️ حذف منتج", callback_data="del_prod_list")],
        [InlineKeyboardButton("📊 إحصائيات الطلبات", callback_data="stats"), InlineKeyboardButton("📢 رسالة جماعية", callback_data="broadcast_start")],
        [InlineKeyboardButton("⭐ إدارة التقييمات", callback_data="manage_reviews")]
    ]
    await update.message.reply_text("مرحباً بك في لوحة تحكم الأدمن لـ متجر العاقل:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "stats":
        msg = f"📊 *إحصائيات متجر العاقل:*\n\n- إجمالي الطلبات: {db['orders_count']}\n- عدد العملاء المسجلين: {len(db['users'])}\n- عدد المنتجات المتاحة: {len(db['products'])}"
        await query.edit_message_text(msg, parse_mode="Markdown")
        
    elif query.data == "del_prod_list":
        if not db["products"]:
            await query.edit_message_text("لا توجد منتجات لحذفها.")
            return
        keyboard = []
        for p in db["products"]:
            keyboard.append([InlineKeyboardButton(f"❌ حذف: {p['title']}", callback_data=f"remove_p_{p['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_admin")])
        await query.edit_message_text("اختر المنتج المراد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data.startswith("remove_p_"):
        pid = int(query.data.split("_")[2])
        db["products"] = [p for p in db["products"] if p["id"] != pid]
        save_db(db)
        await query.edit_message_text("✅ تم حذف المنتج بنجاح.")

    elif query.data == "manage_reviews":
        if not db["reviews"]:
            await query.edit_message_text("لا توجد تقييمات حالياً.")
            return
        keyboard = []
        for r in db["reviews"]:
            keyboard.append([InlineKeyboardButton(f"❌ حذف تقييم: {r['user_name']}", callback_data=f"del_rev_{r['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_admin")])
        await query.edit_message_text("اختر التقييم المراد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data.startswith("del_rev_"):
        rid = int(query.data.split("_")[2])
        db["reviews"] = [r for r in db["reviews"] if r["id"] != rid]
        save_db(db)
        await query.edit_message_text("✅ تم حذف التقييم بنجاح.")

# خطوات إضافة منتج جديد
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("أدخل اسم المنتج الجديد:")
    return TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['prod_title'] = update.message.text
    await update.message.reply_text("أدخل سعر المنتج بالريال السعودي (سيتم حسابه تلقائياً بالنجوم):")
    return PRICE

async def get_price(update: ContextTypes.DEFAULT_TYPE, update_obj=None):
    # توافقية مع رسائل المستخدم
    pass

async def get_price_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price_sar = float(update.message.text)
        stars = int(price_sar * SAR_TO_STARS_RATE)
        context.user_data['prod_price_sar'] = price_sar
        context.user_data['prod_stars'] = stars
        await update.message.reply_text(f"السعر بالريال: {price_sar} ر.س\nالمعادل التلقائي بالنجوم: ★ {stars} نجمة\n\nالآن أدخل وصف المنتج:")
        return DESC
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم صحيح للسعر بالريال.")
        return PRICE

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['prod_desc'] = update.message.text
    await update.message.reply_text("أرسل صورة المنتج الآن (كمرفق صورة مباشرة وليست رابط):")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("الرجاء إرسال صورة صحيحة كمرفق.")
        return PHOTO
    
    photo_file = await update.message.photo[-1].get_file()
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
    
    await update.message.reply_text("✅ تم إضافة المنتج بنجاح! جاري إرساله كرسالة جماعية لكل الزبائن...")
    
    # إرسال رسالة جماعية بالمنتج الجديد لكل الزبائن
    for uid in db["users"]:
        try:
            await context.bot.send_photo(
                chat_id=uid,
                photo=new_product["image_url"],
                caption=f"🔥 *وصول منتج عسكري جديد في متجر العاقل!\n\n📌 *{new_product['title']}**\n📝 {new_product['description']}\n\n💰 السعر: {new_product['price_sar']} ر.س (★ {new_product['stars']} نجمة)",
                parse_mode="Markdown"
            )
        except Exception:
            pass
            
    return ConversationHandler.END

def main():
    # تشغيل الفلاسك في خلفية منفصلة لمنع تعارض الـ Event Loop ولضمان العمل 24 ساعة
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # تشغيل بوت التليجرام
    application = Application.builder().token(TOKEN).build()

    add_prod_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_product_start, pattern="^add_prod$")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price_msg)],
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

    application.run_polling()

if __name__ == '__main__':
    main()
