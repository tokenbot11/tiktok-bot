import instaloader
import requests
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# توکن ربات تلگرام
TOKEN = "7512316456:AAGYLRPdQxTXuswDp2ISeqXSpSBfIcEMx-U"
ADMIN_ID = "7109901365"
CHANNELS = ["@downloaderbe", "@Drops1Drop"]
PROXY = None  # اگه پروکسی داری، اینجا بذار (مثل "http://your_proxy:port")

# تابع کوتاه کردن لینک
def shorten_url(long_url):
    try:
        response = requests.get(f"https://tinyurl.com/api-create.php?url={long_url}", timeout=5)
        return response.text if response.status_code == 200 else long_url
    except Exception as e:
        logger.error(f"خطا در کوتاه کردن لینک: {e}")
        return long_url

# تابع فرمت اندازه
def format_size(size_in_bytes):
    if not size_in_bytes:
        return "N/A"
    size_in_bytes = int(size_in_bytes) / 1024
    for unit in ['KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.1f}{unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.1f}TB"

# چک کردن عضویت
async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    for channel in CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logger.error(f"خطا در چک کردن عضویت: {e}")
            await (update.message.reply_text if update.message else update.callback_query.edit_message_text)(
                "خطا در چک کردن عضویت. لطفاً دوباره امتحان کن یا با پشتیبانی تماس بگیر."
            )
            return False
    return True

# ریست داده‌های کاربر
def reset_user_data(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

# منوها
def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 دانلود از اینستاگرام", callback_data="instagram")],
        [InlineKeyboardButton("🎥 دانلود از یوتیوب", callback_data="youtube")],
        [InlineKeyboardButton("🎬 دانلود از تیک‌تاک", callback_data="tiktok")],
        [InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about")],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data="support")],
    ])

def get_after_download_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 ارسال لینک جدید", callback_data="new_link")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="main_menu")],
    ])

# تابع یوتیوب
async def fetch_youtube_info(url):
    try:
        response = requests.post("https://yt1s.com/api/ajaxSearch/index", data={"q": url, "vt": "mp4"}, timeout=10)
        data = response.json()
        if data.get("status") != "ok" or "vid" not in data:
            raise Exception(data.get("mess", "خطا در گرفتن اطلاعات ویدیو"))
        vid, links = data["vid"], data.get("links", {}).get("mp4", {})
        if not links:
            raise Exception("هیچ کیفیتی پیدا نشد.")
        keyboard = [[InlineKeyboardButton(f"🎥 {info['q']} - {info['size']}", callback_data=f"yt1s_{vid}_{info['k']}")] for quality_key, info in links.items() if info.get("k")]
        keyboard.append([InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="main_menu")])
        return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        raise Exception(f"خطا: {str(e)}. لطفاً لینک رو چک کن یا VPN رو عوض کن.")

async def get_youtube_download_link(vid, k):
    try:
        response = requests.post("https://yt1s.com/api/ajaxConvert/convert", data={"vid": vid, "k": k}, timeout=10)
        data = response.json()
        if data.get("status") != "ok":
            raise Exception("خطا در تبدیل لینک")
        return data["dlink"]
    except Exception as e:
        raise Exception(str(e))

# تابع تیک‌تاک
async def fetch_tiktok_download_link(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
        data = json.dumps({"url": url})
        logger.info(f"در حال ارسال درخواست به tikcdn برای لینک: {url}")
        response = requests.post("https://tikcdn.io/api/download", headers=headers, data=data, timeout=5)
        response_data = response.json()
        logger.info(f"پاسخ tikcdn: {json.dumps(response_data[:500], ensure_ascii=False)}")
        if "error" in response_data or "url" not in response_data:
            raise Exception("لینک تیک‌تاک نامعتبر یا ویدیو در دسترس نیست.")
        download_url = response_data["url"]
        if not download_url.endswith(".mp4"):
            response = requests.get(download_url, headers=headers, allow_redirects=True, timeout=5)
            download_url = response.url
            if not download_url.endswith(".mp4"):
                raise Exception("لینک مستقیم ویدیو پیدا نشد.")
        return download_url
    except Exception as e:
        logger.error(f"خطا در گرفتن لینک تیک‌تاک: {e}")
        raise Exception(f"خطا: {str(e)}. لطفاً لینک رو چک کن یا VPN رو عوض کن.")

# دستورات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_user_data(context)
    if await check_membership(update, context):
        await update.message.reply_text("👋 سلام! از کجا می‌خوای دانلود کنی؟", reply_markup=get_main_menu())
    else:
        await update.message.reply_text("⚠️ برای استفاده، توی این کانال‌ها عضو شو:\n" + "\n".join(CHANNELS) + "\nبعد /start بزن!")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.from_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ فقط ادمین می‌تونه از این دستور استفاده کنه!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("لطفاً از این فرمت استفاده کن:\n/reply user_id پیام")
        return
    try:
        user_id, message = context.args[0], " ".join(context.args[1:])
        await context.bot.send_message(chat_id=user_id, text=f"📩 پاسخ ادمین:\n{message}")
        await update.message.reply_text(f"✅ پیام به {user_id} ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

# مدیریت دکمه‌ها
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_membership(update, context):
        await query.edit_message_text("⚠️ توی کانال‌ها عضو شو:\n" + "\n".join(CHANNELS))
        return
    data = query.data
    if data == "instagram":
        await query.edit_message_text("📸 لینک اینستاگرام رو بفرست:")
        context.user_data["mode"] = "instagram"
    elif data == "youtube":
        await query.edit_message_text("🎥 لینک یوتیوب رو بفرست:")
        context.user_data["mode"] = "youtube"
    elif data == "tiktok":
        await query.edit_message_text("🎬 لینک تیک‌تاک رو بفرست:")
        context.user_data["mode"] = "tiktok"
    elif data == "new_link":
        reset_user_data(context)
        await query.edit_message_text("🔗 از کجا می‌خوای دانلود کنی؟", reply_markup=get_main_menu())
    elif data == "main_menu":
        reset_user_data(context)
        await query.edit_message_text("🏠 به منوی اصلی خوش اومدی!", reply_markup=get_main_menu())
    elif data == "about":
        await query.edit_message_text("ℹ️ ربات دانلود از اینستاگرام، یوتیوب و تیک‌تاک!", reply_markup=get_after_download_menu())
    elif data == "support":
        await query.edit_message_text("📞 سؤالت رو بنویس:")
        context.user_data["mode"] = "support"
    elif data.startswith("yt1s_"):
        _, vid, k = data.split("_", 2)
        await query.edit_message_text("🎥 در حال آماده‌سازی لینک...")
        try:
            download_url = await get_youtube_download_link(vid, k)
            short_url = shorten_url(download_url)
            await query.edit_message_text(f"✅ لینک آماده‌ست:\n{short_url}", reply_markup=get_after_download_menu())
        except Exception as e:
            await query.edit_message_text(f"❌ خطا: {e}\nلطفاً VPN رو عوض کن یا با پشتیبانی تماس بگیر.", reply_markup=get_main_menu())

# مدیریت پیام‌ها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership(update, context):
        await update.message.reply_text("⚠️ توی کانال‌ها عضو شو:\n" + "\n".join(CHANNELS))
        return
    url = update.message.text.strip()
    mode = context.user_data.get("mode")
    if mode == "support":
        user_id, username = update.message.from_user.id, update.message.from_user.username or "بدون نام"
        try:
            await context.bot.send_message(ADMIN_ID, text=f"📩 از {user_id} (@{username}):\n{url}")
            await update.message.reply_text("✅ پیامت به ادمین رسید!", reply_markup=get_main_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}", reply_markup=get_main_menu())
        context.user_data["mode"] = None
        return
    if mode == "instagram" and "instagram.com" in url:
        await update.message.reply_text("📥 در حال پردازش...")
        L = instaloader.Instaloader()
        if PROXY:
            L.context._session.proxies = {"http": PROXY, "https": PROXY}
        try:
            shortcode = url.split("/")[-2]
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            download_url = post.video_url if post.is_video else post.url
            short_url = shorten_url(download_url)
            file_type = "ویدیو" if post.is_video else "عکس"
            await update.message.reply_text(f"✅ لینک {file_type}:\n{short_url}", reply_markup=get_after_download_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}\nلطفاً VPN رو عوض کن.", reply_markup=get_after_download_menu())
    elif mode == "youtube" and ("youtube.com" in url or "youtu.be" in url):
        context.user_data["youtube_url"] = url
        await update.message.reply_text("🎥 در حال بررسی کیفیت‌ها...")
        try:
            quality_menu = await fetch_youtube_info(url)
            await update.message.reply_text("🎥 کیفیت رو انتخاب کن:", reply_markup=quality_menu)
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {str(e)}\nلطفاً لینک رو چک کن یا VPN رو عوض کن.", reply_markup=get_main_menu())
            reset_user_data(context)
    elif mode == "tiktok" and "tiktok.com" in url:
        await update.message.reply_text("🎬 در حال پردازش لینک تیک‌تاک...")
        try:
            download_url = await fetch_tiktok_download_link(url)
            short_url = shorten_url(download_url)
            await update.message.reply_text(f"✅ لینک ویدیوی تیک‌تاک آماده‌ست:\n{short_url}", reply_markup=get_after_download_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {str(e)}\nلطفاً لینک رو چک کن یا VPN رو عوض کن.", reply_markup=get_main_menu())
            reset_user_data(context)
    else:
        await update.message.reply_text("👋 لینک معتبر بفرست!", reply_markup=get_main_menu())

# اجرای ربات با Webhook
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reply", reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("ربات شروع به کار کرد...")

    import os
    port = int(os.environ.get("PORT", 8443))  # Render پورت رو از متغیر محیطی می‌گیره
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/webhook",
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    )

if __name__ == "__main__":
    main()