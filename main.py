import os
import asyncio
import threading
from flask import Flask, render_template, request, jsonify
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    LabeledPrice,
    SuccessfulPayment
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    ConversationHandler,
    filters
)
import requests

# إعدادات البوت
TOKEN = "8622474758:AAFcIwB0EOHK1luEnYig6yxE4ZxmbU0XOxo"
ADMIN_ID = 1056007305

app = Flask(__name__)

# قاعدة بيانات مبسطة مؤقتة (يمكن استبدالها بقاعدة بيانات حقيقية لاحقاً)
db = {
    "products": [
        {
            "id": 1,
            "title": "ملف عسكري",
            "description": "ملف عسكري شامل ومطور",
            "price_sar": 10,
            "stars": 115,  # سعر تقريبي بالنجمات بناء على 10 ريال
            "image_url": "https://images.unsplash.com/photo-1508614589041-895b88991e3e?q=80&w=600",
            "group_link": "https://t.me/+example_group_link"
        }
    ],
    "reviews": [
        {"name": "سلطان الحربي", "text": "متجر ممتاز جداً والملفات دقيقة"},
        {"name": "نايف القحطاني", "text": "شكراً على سرعة الخدمة"}
    ],
    "users": set([ADMIN_ID]),
    "orders_count": 0
}

# حالات المحادثة للأدمن
TITLE, PRICE, DESC, PHOTO, GROUP_LINK = range(5)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/store-data')
def get_store_data():
    return jsonify({
        "products": db["products"],
        "reviews": db["reviews"]
    })

@app.route('/create-invoice', methods=['POST'])
def create_invoice_route():
    data = request.json
    product_id = data.get('product_id')
    
    product = next((p for p in db["products"] if p["id"] == product_id), None)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    url = f"https://api.telegram.org/bot{TOKEN}/createInvoiceLink"
    payload = {
        "title": f"شراء: {product['title']}",
        "description": product['description'],
        "payload": f"product_{product['id']}",
        "currency": "XTR",
        "prices": [{"label": "نجوم تليجرام", "amount": product['stars']}]
    }
    
    response = requests.post(url, json=payload).json()
    if response.get("ok"):
        return jsonify({"invoice_link": response["result"]})
    return jsonify({"error": "Failed to create invoice"}), 400

# تشغيل خادم Flask في الخلفية
def run_flask():
    app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db["users"].add(user.id)
    
    keyboard = [
        [InlineKeyboardButton("🎖️ فتح متجر العاقل", web_app={"url": "https://al3agle.onrender.com"})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"أهلاً بك يا {user.first_name} في 🎖️ متجر العاقل للملفات العسكرية.\n\n"
        "اضغط على الزر بالأسفل لفتح المتجر المصغر واستعراض الملفات والتقييمات بكل سلاسة وفخامة!"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة منتج", callback_data="add_prod")],
        [InlineKeyboardButton("📋 حذف/إدارة المنتجات", callback_data="del_prod_list")],
        [InlineKeyboardButton("📊 إحصائيات الطلبات", callback_data="stats")],
        [InlineKeyboardButton("⭐ إدارة التقييمات", callback_data="manage_reviews")],
        [InlineKeyboardButton("📢 رسالة جماعية", callback_data="broadcast")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎛️ لوحة تحكم الأدمن لمتجر العاقل:", reply_markup=reply_markup, parse_mode="Markdown")

# إضافة منتج (ConversationHandler)
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("أدخل اسم المنتج الجديد:")
    return TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("أدخل سعر المنتج بالريال السعودي (مثال: 15):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price_sar = float(update.message.text)
        # حساب النجوم تلقائياً (نفترض كل ريال يعادل تقريباً 11.5 نجمة أو حسب معادلتك)
        stars = int(price_sar * 11.5)
        context.user_data['price_sar'] = price_sar
        context.user_data['stars'] = stars
        await update.message.reply_text(f"تم حساب السعر بـ ⭐ {stars} نجمة.\nالآن أدخل وصف المنتج:")
        return DESC
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم صحيح للسعر بالريال:")
        return PRICE

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desc'] = update.message.text
    await update.message.reply_text("أرسل صورة المنتج (صورة مباشرة):")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    context.user_data['image_url'] = photo_file.file_path
    await update.message.reply_text("أدخل رابط القروب الخاص بالملفات (الذي سيحصل عليه المشتري تلقائياً):")
    return GROUP_LINK

async def get_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_link = update.message.text
    new_id = len(db["products"]) + 1
    
    new_product = {
        "id": new_id,
        "title": context.user_data['title'],
        "description": context.user_data['desc'],
        "price_sar": context.user_data['price_sar'],
        "stars": context.user_data['stars'],
        "image_url": context.user_data['image_url'],
        "group_link": group_link
    }
    
    db["products"].append(new_product)
    
    # إرسال إشعار رسالة جماعية للزبائن بالمنتج الجديد
    for uid in db["users"]:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"🔥 منتج عسكري جديد في متجر العاقل!\n\n*{new_product['title']}*\n{new_product['description']}\n💰 السعر: {new_product['price_sar']} ر.س (⭐ {new_product['stars']} نجمة)",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    await update.message.reply_text("✅ تم إضافة المنتج بنجاح وإرساله كرسالة جماعية للزبائن!")
    return ConversationHandler.END

# إدارة الحذف والإحصائيات والتقييمات
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "stats":
        stats_text = (
            f"📊 إحصائيات متجر العاقل:\n\n"
            f"- إجمالي الطلبات: {db['orders_count']}\n"
            f"- عدد الزبائن المسجلين: {len(db['users'])}\n"
            f"- عدد المنتجات: {len(db['products'])}"
        )
        await query.message.reply_text(stats_text, parse_mode="Markdown")
    
    elif data == "manage_reviews":
        keyboard = []
        for i, rev in enumerate(db["reviews"]):
            keyboard.append([InlineKeyboardButton(f"❌ حذف تقييم: {rev['name']}", callback_data=f"del_rev_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await query.message.reply_text("اختر التقييم المراد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("del_rev_"):
        idx = int(data.split("_")[2])
        if idx < len(db["reviews"]):
            removed = db["reviews"].pop(idx)
            await query.message.reply_text(f"🗑️ تم حذف تقييم: {removed['name']}")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment: SuccessfulPayment = update.message.successful_payment
    payload = payment.invoice_payload
    db["orders_count"] += 1
    
    if payload.startswith("product_"):
        pid = int(payload.split("_")[1])
        product = next((p for p in db["products"] if p["id"] == pid), None)
        if product:
            success_text = (
                f"🎉 تم عملية الشراء بنجاح!\n\n"
                f"شكراً لثقتك بمتجر العاقل.\n"
                f"📦 المنتج: {product['title']}\n\n"
                f"🔗 رابط القروب الخاص بالملفات العسكرية:\n{product['group_link']}"
            )
            await update.message.reply_text(success_text, parse_mode="Markdown")

def run_bot():
    application = Application.builder().token(TOKEN).build()
    
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
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(stats|manage_reviews|del_rev_.*)$"))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    application.run_polling()

if _name_ == '_main_':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    run_bot()
