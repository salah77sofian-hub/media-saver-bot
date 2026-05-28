#!/usr/bin/env python3                                                                                                import os
import re                                                  import asyncio                                             import tempfile
import logging                                             import yt_dlp                                              import httpx
from pathlib import Path                                   from urllib.parse import urlparse                          
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup                                               from telegram.ext import (
    Application, CommandHandler, MessageHandler,               CallbackQueryHandler, ContextTypes, filters,           )
from telegram.constants import ParseMode, ChatAction                                                                  BOT_TOKEN = "8631965370:AAGNapiaV2d6rO_hCmnvB4S_8heQxZCCc4s"                                                                                                                     logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",        datefmt="%H:%M:%S",                                        level=logging.INFO,
)                                                          logger = logging.getLogger("MediaBot")                     
PLATFORM_PATTERNS = {                                          "youtube":   r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/|youtube\.com/live/)",
    "tiktok":    r"(tiktok\.com|vm\.tiktok\.com)",             "instagram": r"(instagram\.com/(p|reel|tv|stories)/)",     "facebook":  r"(facebook\.com|fb\.com|fb\.watch)",
    "pinterest": r"(pinterest\.(com|ca|co\.uk|fr|de|es|it|com\.au|com\.br)/pin/|pin\.it/)",                               "snapchat":  r"(snapchat\.com|story\.snapchat\.com)",
}                                                                                                                     PLATFORM_EMOJIS = {
    "youtube": "▶️", "tiktok": "🎵", "instagram": "📸",         "facebook": "📘", "pinterest": "📌", "snapchat": "👻",
}                                                                                                                     PLATFORM_NAMES = {                                             "youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram",
    "facebook": "Facebook", "pinterest": "Pinterest", "snapchat": "Snapchat",                                         }
                                                           def detect_platform(url):                                      for platform, pattern in PLATFORM_PATTERNS.items():
        if re.search(pattern, url, re.IGNORECASE):                     return platform                                    return "unknown"
                                                           def is_valid_url(url):                                         try:
        r = urlparse(url)                                          return r.scheme in ("http", "https") and bool(r.netloc)
    except:                                                        return False                                       
def get_ydl_opts(output_path, platform=""):                    base = {                                                       "outtmpl": output_path,
        "quiet": True,                                             "no_warnings": True,                                       "noplaylist": True,
        "merge_output_format": "mp4",                              "http_headers": {                                              "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "                                                             "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Mobile/15E148 Safari/604.1"              ),                                                     },
    }                                                                                                                     if platform == "youtube":
        base["format"] = (                                             "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
            "best[height<=720][ext=mp4]/best[height<=720]/best"                                                               )
    elif platform == "tiktok":                                     base["format"] = "best[ext=mp4]/best"                      base["http_headers"]["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "               "AppleWebKit/537.36 Chrome/124 Safari/537.36"          )
    elif platform == "instagram":                                  # محاولات متعددة للصيغ                                     base["format"] = "best[ext=mp4]/best[ext=jpg]/best"
        base["http_headers"]["User-Agent"] = (                         "Instagram 319.0.0.34.109 Android"                     )
    elif platform == "facebook":                                   base["format"] = "best[ext=mp4]/best"                  else:
        base["format"] = "best[ext=mp4]/best"
                                                               return base                                            
async def download_media(url, tmpdir, platform=""):            output_template = os.path.join(tmpdir, "media.%(ext)s")    ydl_opts = get_ydl_opts(output_template, platform)
    loop = asyncio.get_event_loop()                                                                                       def _dl():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:                        return ydl.extract_info(url, download=True)    
    # محاولة أولى                                              try:                                                           info = await loop.run_in_executor(None, _dl)
    except Exception as e:                                         # محاولة ثانية بصيغة أبسط
        ydl_opts["format"] = "best"                                try:
            info = await loop.run_in_executor(None, _dl)
        except Exception as e2:
            raise RuntimeError(str(e2))

    files = sorted(Path(tmpdir).iterdir(), key=lambda f: f.stat().st_size, reverse=True)
    if not files:
        raise RuntimeError("لم يتم تحميل أي ملف")

    f = files[0]
    ext = f.suffix.lower()                                     mtype = "video" if ext in (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v") else "photo"
                                                               return {                                                       "type": mtype,
        "path": str(f),
        "title": info.get("title", "")[:80],                       "duration": info.get("duration", 0),                       "uploader": info.get("uploader", ""),
        "view_count": info.get("view_count", 0),               }                                                      
async def download_pinterest(url, tmpdir):                     headers = {                                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",                "Accept-Language": "en-US,en;q=0.9",                   }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:                                                r = await client.get(url, headers=headers)
        html = r.text                                              patterns = [                                                   r'"url"\s*:\s*"(https://i\.pinimg\.com/originals/[^"]+)"',                                                            r'"url"\s*:\s*"(https://i\.pinimg\.com/\d+x/[^"]+)"',
            r'<meta property="og:image" content="([^"]+)"',        ]                                                          img_url = None
        for p in patterns:                                             m = re.search(p, html)                                     if m:
                img_url = m.group(1).replace("\\u002F", "/")                                                                          break
        if not img_url:                                                raise RuntimeError("Could not extract Pinterest image")
        ir = await client.get(img_url, headers=headers)            ir.raise_for_status()                                      ext = ".jpg"
        ct = ir.headers.get("content-type", "")                    if "png" in ct: ext = ".png"                               elif "webp" in ct: ext = ".webp"
        path = os.path.join(tmpdir, f"pin{ext}")                   with open(path, "wb") as fh:                                   fh.write(ir.content)
        return {"type": "photo", "path": path, "title": "Pinterest", "duration": 0, "uploader": "", "view_count": 0}                                                             def build_caption(info, platform):
    emoji = PLATFORM_EMOJIS.get(platform, "🔗")                name  = PLATFORM_NAMES.get(platform, platform)             lines = [f"{emoji} {name} ✅"]
    if info.get("title"): lines.append(f"📝 {info['title']}")                                                             if info.get("uploader"): lines.append(f"👤 {info['uploader']}")                                                       if info.get("duration"):                                       m, s = divmod(int(info["duration"]), 60)
        lines.append(f"⏱ {m}:{s:02d}")                         lines.append("🤖 All Social Media Saver")                  return "\n".join(lines)
                                                           async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [                                                   [InlineKeyboardButton("▶️ YouTube", callback_data="info_youtube"),
         InlineKeyboardButton("🎵 TikTok", callback_data="info_tiktok")],                                                     [InlineKeyboardButton("📸 Instagram", callback_data="info_instagram"),                                                 InlineKeyboardButton("📘 Facebook", callback_data="info_facebook")],
        [InlineKeyboardButton("📌 Pinterest", callback_data="info_pinterest"),                                                 InlineKeyboardButton("👻 Snapchat", callback_data="info_snapchat")],                                             ]                                                          text = (
        "👋 *Welcome to All Social Media Saver!*\n\n"              "مرحباً! أنا بوت تحميل الوسائط\n\n"                         "📥 Send me a link from:\n\n"
        "▶️ YouTube\n"                                              "🎵 TikTok\n"                                              "📸 Instagram\n"
        "📘 Facebook\n"                                            "📌 Pinterest\n"                                           "👻 Snapchat\n\n"
        "⚡ Fast • Free • No Watermark\n\n"                        "Type /help for more info"                             )
    await update.message.reply_text(                               text,                                                      parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),           )                                                      
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):                                               text = (
        "📖 *How to use / كيف تستخدمني*\n\n"                       "1️⃣ Copy the video/photo link\n"                            "2️⃣ Send it here\n"
        "3️⃣ Wait a few seconds\n"                                   "4️⃣ Save your file! 🎉\n\n"                                 "❓ *FAQ:*\n"
        "• Free? Yes 100%\n"
        "• Watermark? Never\n"                                     "• Best quality? Always\n\n"                               "⚠️ Private content cannot be downloaded"
    )                                                          await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                                                           async def info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query                              await query.answer()                                       platform = query.data.replace("info_", "")
    tips = {                                                       "youtube":   "Example:\nhttps://youtu.be/VIDEO_ID\nhttps://youtube.com/shorts/ID",
        "tiktok":    "Example:\nhttps://vm.tiktok.com/ID",         "instagram": "Example:\nhttps://instagram.com/reel/ID\nhttps://instagram.com/p/ID",
        "facebook":  "Example:\nhttps://fb.watch/ID",              "pinterest": "Example:\nhttps://pin.it/ID\nhttps://pinterest.com/pin/ID",
        "snapchat":  "Example:\nhttps://story.snapchat.com/...",                                                          }
    emoji = PLATFORM_EMOJIS.get(platform, "🔗")                name  = PLATFORM_NAMES.get(platform, platform.title())     await query.message.reply_text(
        f"{emoji} *{name}*\n\n{tips.get(platform, 'Send the link directly')}",                                                parse_mode=ParseMode.MARKDOWN,
    )                                                                                                                 async def url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):                                                url = update.message.text.strip()                      
    if not is_valid_url(url):                                      await update.message.reply_text(                               "❌ Invalid link!\nMake sure it starts with https://"                                                             )                                                          return
                                                               platform = detect_platform(url)
    if platform == "unknown":                                      await update.message.reply_text(                               "⚠️ This platform is not supported!\n\n"
            "Supported: YouTube • TikTok • Instagram • Facebook • Pinterest • Snapchat"                                       )
        return                                                                                                            emoji = PLATFORM_EMOJIS[platform]
    pname = PLATFORM_NAMES[platform]                                                                                      await update.message.reply_chat_action(ChatAction.TYPING)                                                             msg = await update.message.reply_text(f"{emoji} {pname}\n⏳ Downloading...")
                                                               try:                                                           with tempfile.TemporaryDirectory() as tmpdir:
            await msg.edit_text(f"{emoji} {pname}\n🔄 Processing...")                                                 
            if platform == "pinterest":                                    info = await download_pinterest(url, tmpdir)
            else:                                                          info = await download_media(url, tmpdir, platform)
                                                                       size = os.path.getsize(info["path"])                       if size > 50 * 1024 * 1024:
                await msg.edit_text(
                    "⚠️ File too large (max 50MB)\n"                            "Try a shorter video."                                 )
                return                                     
            await msg.edit_text(f"{emoji} {pname}\n📤 Sending...")
            caption = build_caption(info, platform)        
            with open(info["path"], "rb") as mf:
                if info["type"] == "video":
                    await update.message.reply_chat_action(ChatAction.UPLOAD_VIDEO)
                    await update.message.reply_video(
                        video=mf, caption=caption,
                        parse_mode=ParseMode.MARKDOWN,
                        supports_streaming=True,                                   read_timeout=180, write_timeout=180,
                    )
                else:
                    await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)                                                       await update.message.reply_photo(
                        photo=mf, caption=caption,
                        parse_mode=ParseMode.MARKDOWN,                             read_timeout=60, write_timeout=60,
                    )
            await msg.delete()                                         logger.info(f"✅ {platform} | {info['type']} | user={update.effective_user.id}")                          
    except RuntimeError as e:
        err = str(e).lower()                                       logger.warning(f"Error [{platform}]: {e}")
        if any(w in err for w in ("private", "login", "sign in")):
            m = "🔒 This content is private or requires login."
        elif any(w in err for w in ("unavailable", "not found", "removed", "deleted")):                                           m = "🚫 Content not available or deleted."
        elif "copyright" in err:
            m = "⚖️ Content is copyright protected."
        else:                                                          m = f"❌ Download failed!\n\n`{str(e)[:200]}`"
        await msg.edit_text(m, parse_mode=ParseMode.MARKDOWN)                                                         
    except Exception as e:
        logger.error(f"Unexpected: {e}", exc_info=True)
        await msg.edit_text(                                           f"❌ Unexpected error!\n`{str(e)[:150]}`",
            parse_mode=ParseMode.MARKDOWN,
        )

async def unknown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a link only!\n\nExample: https://youtu.be/...\n\n/start for help"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error:", exc_info=context.error)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CallbackQueryHandler(info_callback, pattern=r"^info_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, unknown_handler))
    app.add_error_handler(error_handler)
    logger.info("🚀 Bot is running...")                        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":                                     main()
