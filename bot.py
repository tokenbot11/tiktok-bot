import os
import aiohttp
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import instaloader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN", "7512316456:AAGYLRPdQxTXuswDp2ISeqXSpSBfIcEMx-U")
ADMIN_ID = "7109901365"
CHANNELS = ["@downloaderbe", "@Drops1Drop"]
INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.environ.get("INSTAGRAM_PASSWORD")
PROXY = os.environ.get("INSTAGRAM_PROXY")

async def shorten_url(long_url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://tinyurl.com/api-create.php?url={long_url}", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    short_url = await response.text()
                    logger.info(f"Shortened URL: {short_url}")
                    return short_url
                return long_url
        except Exception as e:
            logger.error(f"Error shortening URL: {str(e)}")
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://y2mate.is/",
        "Origin": "https://y2mate.is",
        "Content-Type": "application/json"
    }
    payload = {"url": url}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            logger.info(f"Fetching YouTube info for URL: {url}")
            async with session.post("https://y2mate.is/api/button", json=payload, timeout=aiohttp.ClientTimeout(total=15)) as response:
                text = await response.text()
                logger.info(f"Response from y2mate: {text[:500]}")
                if "error" in text.lower():
                    raise Exception("Error fetching video info from y2mate")
                
                # پارس ساده برای گرفتن vid و کیفیت‌ها
                vid_start = text.find('vid="') + 5
                vid_end = text.find('"', vid_start)
                vid = text[vid_start:vid_end] if vid_start > 4 else "unknown"
                
                qualities = []
                if "1080p" in text:
                    qualities.append({"q": "1080p", "k": "1080p"})
                if "720p" in text:
                    qualities.append({"q": "720p", "k": "720p"})
                if "480p" in text:
                    qualities.append({"q": "480p", "k": "480p"})
                if "360p" in text:
                    qualities.append({"q": "360p", "k": "360p"})
                
                if not qualities:
                    raise Exception("No quality options found")
                
                keyboard = [[InlineKeyboardButton(f"🎥 {info['q']}", callback_data=f"y2mate_{vid}_{info['k']}")] 
                            for info in qualities]
                keyboard.append([InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="main_menu")])
                return InlineKeyboardMarkup(keyboard)
        except Exception as e:
            logger.error(f"Error fetching YouTube info: {str(e)}")
            raise Exception(f"خطا: {str(e)}. لطفاً لینک رو چک کن یا بعداً امتحان کن.")

async def get_youtube_download_link(vid, k):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://y2mate.is/",
        "Origin": "https://y2mate.is",
        "Content-Type": "application/json"
    }
    payload = {"vid": vid, "k": k}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            logger.info(f"Converting YouTube link: vid={vid}, k={k}")
            async with session.post("https://y2mate.is/api/convert", json=payload, timeout=aiohttp.ClientTimeout(total=15)) as response:
                data = await response.json()
                logger.info(f"Convert response: {data}")
                if data.get("status") != "ok":
                    raise Exception(data.get("mess", "Error converting link"))
                return data["dlink"]
        except Exception as e:
            logger.error(f"Error converting YouTube link: {str(e)}")
            raise Exception(str(e))

async def fetch_tiktok_download_link(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.post("https://ssstik.io/abc?url=dl", data={"id": url}, timeout=aiohttp.ClientTimeout(total=10)) as response:
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
    elif data.startswith("y2mate_"):
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
                L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                logger.info("Logged into Instagram successfully")
            shortcode = url.split("/")[-2]
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            download_url = post.video_url if post.is_video else post.url
            short_url = await shorten_url(download_url)
            file_type = "ویدیو" if post.is_video else "عکس"
            await update.message.reply_text(f"✅ لینک {file_type}:\n{short_url}", reply_markup=get_after_download_menu())
        except Exception as e:
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