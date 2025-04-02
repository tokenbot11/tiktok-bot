import os
import instaloader
import aiohttp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN", "7512316456:AAGYLRPdQxTXuswDp2ISeqXSpSBfIcEMx-U")
ADMIN_ID = "7109901365"
CHANNELS = ["@downloaderbe", "@Drops1Drop"]
INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.environ.get("INSTAGRAM_PASSWORD")
PROXY = os.environ.get("INSTAGRAM_PROXY")

async def shorten_url(long_url):
    return long_url

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    for channel in CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logger.error(f"Error checking membership: {e}")
            return False
    return True

def reset_user_data(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 دانلود از اینستاگرام", callback_data="instagram")],
        [InlineKeyboardButton("🎥 دانلود از یوتیوب", callback_data="youtube")],
        [InlineKeyboardButton("🎬 دانلود از تیک‌تاک", callback_data="tiktok")],
    ])

def get_after_download_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 ارسال لینک جدید", callback_data="new_link")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="main_menu")],
    ])

async def fetch_youtube_info(url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post("https://yt1s.com/api/ajaxSearch/index", data={"q": url, "vt": "mp4"}, timeout=aiohttp.ClientTimeout(total=15)) as response:
                data = await response.json()
                if data.get("status") != "ok" or "vid" not in data:
                    raise Exception(data.get("mess", "Error fetching video info"))
                vid, links = data["vid"], data.get("links", {}).get("mp4", {})
                if not links:
                    raise Exception("No quality options found.")
                keyboard = [[InlineKeyboardButton(f"🎥 {info['q']} - {info['size']}", callback_data=f"yt1s_{vid}_{info['k']}")] 
                            for quality_key, info in links.items() if info.get("k")]
                keyboard.append([InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="main_menu")])
                return InlineKeyboardMarkup(keyboard)
        except Exception as e:
            raise Exception(f"Error: {str(e)}")

async def get_youtube_download_link(vid, k):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post("https://yt1s.com/api/ajaxConvert/convert", data={"vid": vid, "k": k}, timeout=aiohttp.ClientTimeout(total=15)) as response:
                data = await response.json()
                if data.get("status") != "ok":
                    raise Exception("Error converting link")
                return data["dlink"]
        except Exception as e:
            raise Exception(str(e))

async def fetch_tiktok_download_link(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post("https://ssstik.io/abc?url=dl", headers=headers, data={"id": url}, timeout=aiohttp.ClientTimeout(total=10)) as response:
                text = await response.text()
                if "error" in text.lower() or "not found" in text.lower():
                    raise Exception("Invalid TikTok link or video unavailable.")
                start = text.find('href="') + 6
                end = text.find('"', start)
                if start == -1 or end == -1:
                    raise Exception("Download link not found.")
                download_url = text[start:end]
                if not download_url.endswith(".mp4"):
                    async with session.get(download_url, headers=headers, allow_redirects=True) as redirect_response:
                        download_url = str(redirect_response.url)
                return download_url
        except Exception as e:
            raise Exception(f"Error: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_user_data(context)
    if await check_membership(update, context):
        await update.message.reply_text("👋 سلام! از کجا می‌خوای دانلود کنی؟", reply_markup=get_main_menu())
    else:
        await update.message.reply_text("⚠️ برای استفاده، توی این کانال‌ها عضو شو:\n" + "\n".join(CHANNELS))

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
    elif data.startswith("yt1s_"):
        _, vid, k = data.split("_", 2)
        await query.edit_message_text("🎥 در حال آماده‌سازی لینک...")
        try:
            download_url = await get_youtube_download_link(vid, k)
            short_url = await shorten_url(download_url)
            await query.edit_message_text(f"✅ لینک آماده‌ست:\n{short_url}", reply_markup=get_after_download_menu())
        except Exception as e:
            await query.edit_message_text(f"❌ خطا: {e}", reply_markup=get_main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership(update, context):
        await update.message.reply_text("⚠️ توی کانال‌ها عضو شو:\n" + "\n".join(CHANNELS))
        return
    url = update.message.text.strip()
    mode = context.user_data.get("mode")
    if mode == "instagram" and "instagram.com" in url:
        await update.message.reply_text("📥 در حال پردازش...")
        L = instaloader.Instaloader()
        if PROXY:
            L.context._session.proxies = {"http": PROXY, "https": PROXY}
        try:
            if INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
                logger.info(f"Trying to login with {INSTAGRAM_USERNAME}")
                L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                logger.info("Logged into Instagram successfully")
            else:
                logger.warning("No Instagram credentials provided")
            shortcode = url.split("/")[-2]
            logger.info(f"Fetching post with shortcode: {shortcode}")
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            download_url = post.video_url if post.is_video else post.url
            short_url = await shorten_url(download_url)
            file_type = "ویدیو" if post.is_video else "عکس"
            await update.message.reply_text(f"✅ لینک {file_type}:\n{short_url}", reply_markup=get_after_download_menu())
        except instaloader.exceptions.LoginRequiredException:
            await update.message.reply_text("❌ نیاز به ورود به اینستاگرام داره.", reply_markup=get_main_menu())
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            await update.message.reply_text("❌ تأیید دو مرحله‌ای نیازه. لطفاً با پشتیبانی تماس بگیر.", reply_markup=get_main_menu())
        except Exception as e:
            logger.error(f"Error processing Instagram link: {str(e)}")
            await update.message.reply_text(f"❌ خطا: {str(e)}", reply_markup=get_after_download_menu())
    elif mode == "youtube" and ("youtube.com" in url or "youtu.be" in url):
        await update.message.reply_text("🎥 در حال بررسی کیفیت‌ها...")
        try:
            quality_menu = await fetch_youtube_info(url)
            await update.message.reply_text("🎥 کیفیت رو انتخاب کن:", reply_markup=quality_menu)
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {str(e)}", reply_markup=get_main_menu())
            reset_user_data(context)
    elif mode == "tiktok" and "tiktok.com" in url:
        await update.message.reply_text("🎬 در حال پردازش لینک تیک‌تاک...")
        try:
            download_url = await fetch_tiktok_download_link(url)
            short_url = await shorten_url(download_url)
            await update.message.reply_text(f"✅ لینک ویدیوی تیک‌تاک آماده‌ست:\n{short_url}", reply_markup=get_after_download_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {str(e)}", reply_markup=get_main_menu())
            reset_user_data(context)
    else:
        await update.message.reply_text("👋 لینک معتبر بفرست!", reply_markup=get_main_menu())

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("Bot started...")

    port = int(os.environ.get("PORT", 8443))
    hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "tiktok-bot.onrender.com")
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/webhook",
        webhook_url=f"https://{hostname}/webhook"
    )

if __name__ == "__main__":
    main()