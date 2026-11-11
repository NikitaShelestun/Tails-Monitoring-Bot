import logging
import feedparser
import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Settings ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
TAILS_RSS_URL = "https://tails.net/news/index.en.rss"

DEFAULT_INTERVAL = 3600
MIN_INTERVAL = 300
MAX_INTERVAL = 86400

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- Global Variables ---
last_title = ""
interval = DEFAULT_INTERVAL
owner_id = None

# --- Helper: Format time ---
def format_interval(seconds):
    """Converts seconds to a string like '5 min', '1 hour', '6 hours'."""
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    else:
        hours = minutes // 60
        return f"{hours} hour" if hours == 1 else f"{hours} hours"

# --- Supportive function for sending messages ---
async def send_msg(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, keyboard=None):
    chat_id = None
    if update and update.effective_chat:
        chat_id = update.effective_chat.id
    elif owner_id:
        chat_id = owner_id
    elif context and context.job:
        chat_id = context.job.data.get("chat_id")
    
    if not chat_id:
        logging.error("chat_id couldn't be determined")
        return False
    
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
        return True
    except Exception as e:
        logging.error(f"Sending error: {e}")
        return False

# --- Main Menu Keyboard ---
def get_main_menu():
    keyboard = [
        [
            InlineKeyboardButton("▶️ Start", callback_data="start"),
            InlineKeyboardButton("⏹️ Stop", callback_data="stop"),
        ],
        [
            InlineKeyboardButton("📊 Status", callback_data="status"),
            InlineKeyboardButton("⚙️ Interval", callback_data="interval_menu"),
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Interval Menu Keyboard ---
def get_interval_menu():
    keyboard = [
        [
            InlineKeyboardButton("5 min", callback_data="set_5"),
            InlineKeyboardButton("15 min", callback_data="set_15"),
        ],
        [
            InlineKeyboardButton("30 min", callback_data="set_30"),
            InlineKeyboardButton("60 min", callback_data="set_60"),
        ],
        [
            InlineKeyboardButton("6 hours", callback_data="set_360"),
            InlineKeyboardButton("24 hours", callback_data="set_1440"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="back"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Check Updates ---
async def check_updates(context: ContextTypes.DEFAULT_TYPE):
    global last_title, owner_id
    
    chat_id = owner_id
    if context.job:
        chat_id = context.job.data.get("chat_id")
    
    if not chat_id:
        return
    
    try:
        feed = feedparser.parse(TAILS_RSS_URL)
        if not feed.entries:
            return
        
        news = feed.entries[0]
        title = news.title
        
        if last_title == "":
            last_title = title
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Monitoring is running\nCurrent version: {title}\nInterval: {format_interval(interval)}"
            )
        elif last_title != title:
            last_title = title
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔔 NEW VERSION!\n{title}\n\n{news.description[:200]}...\n{news.link}"
            )
    except Exception as e:
        logging.error(f"Error: {e}")

# --- Helper: Start Monitoring ---
async def do_start(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    job_name = f"monitor_{chat_id}"
    if context.job_queue.get_jobs_by_name(job_name):
        return False
    
    context.job_queue.run_repeating(
        check_updates,
        interval=interval,
        first=5,
        data={"chat_id": chat_id},
        name=job_name
    )
    await check_updates(context)
    return True

# --- Helper: Stop Monitoring ---
async def do_stop(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    job_name = f"monitor_{chat_id}"
    jobs = context.job_queue.get_jobs_by_name(job_name)
    if not jobs:
        return False
    for job in jobs:
        job.schedule_removal()
    return True

# --- Helper: Status Info ---
def get_status_info(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    job_name = f"monitor_{chat_id}"
    is_running = bool(context.job_queue.get_jobs_by_name(job_name))
    
    status_text = "✅ Running" if is_running else "⛔ Stopped"
    
    msg = f"📊 Status: {status_text}\n"
    msg += f"⏱️ Interval: {format_interval(interval)}\n"
    msg += f"📦 Version: {last_title if last_title else 'No data'}"
    return msg

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global owner_id
    chat_id = update.effective_chat.id if update and update.effective_chat else None
    if not chat_id:
        return
    
    if owner_id is None:
        owner_id = chat_id
    
    if owner_id != chat_id:
        await send_msg(update, context, "❌ Access denied")
        return
    
    menu_text = (
        "🤖 **Tails Monitor Bot**\n\n"
        "Following new Tails version releases.\n\n"
        f"**Current settings:**\n"
        f"⏱️ Interval: {format_interval(interval)}\n"
        f"📦 Version: {last_title if last_title else 'No data'}\n\n"
        "Use buttons below. Press ▶️ **Start** to begin monitoring."
    )
    
    await send_msg(update, context, menu_text, keyboard=get_main_menu())

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update and update.effective_chat else None
    if not chat_id or owner_id != chat_id:
        return
    if await do_stop(context, chat_id):
        await send_msg(update, context, "⏹️ Monitoring is stopped", keyboard=get_main_menu())
    else:
        await send_msg(update, context, "⚠️ Monitoring isn't running", keyboard=get_main_menu())

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update and update.effective_chat else None
    if not chat_id or owner_id != chat_id:
        return
    await send_msg(update, context, get_status_info(context, chat_id), keyboard=get_main_menu())

async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global interval
    chat_id = update.effective_chat.id if update and update.effective_chat else None
    if not chat_id or owner_id != chat_id:
        return
    
    if not context.args:
        await send_msg(update, context, "❌ Set the number of minutes\nExample: /setinterval 30")
        return
    
    try:
        minutes = int(context.args[0])
        if minutes < MIN_INTERVAL // 60:
            await send_msg(update, context, f"❌ Minimum {MIN_INTERVAL // 60} min")
            return
        elif minutes > MAX_INTERVAL // 60:
            await send_msg(update, context, f"❌ Maximum {MAX_INTERVAL // 60} min")
            return
        
        interval = minutes * 60
        await do_stop(context, chat_id)
        await do_start(context, chat_id)
        await send_msg(update, context, f"✅ Interval: {format_interval(interval)}", keyboard=get_main_menu())
    except ValueError:
        await send_msg(update, context, "❌ Set the number")

# --- Callback Handler for Buttons ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global interval
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id if query.message else None
    if not chat_id or owner_id != chat_id:
        await query.edit_message_text("❌ Access denied")
        return
    
    data = query.data
    
    if data == "start":
        if await do_start(context, chat_id):
            await query.edit_message_text(
                f"▶️ Monitoring started\n⏱️ Interval: {format_interval(interval)}",
                reply_markup=get_main_menu()
            )
        else:
            await query.edit_message_text(
                "⚠️ Monitoring is already running",
                reply_markup=get_main_menu()
            )
    
    elif data == "stop":
        if await do_stop(context, chat_id):
            await query.edit_message_text(
                "⏹️ Monitoring stopped",
                reply_markup=get_main_menu()
            )
        else:
            await query.edit_message_text(
                "⚠️ Monitoring isn't running",
                reply_markup=get_main_menu()
            )
    
    elif data == "status":
        await query.edit_message_text(
            get_status_info(context, chat_id),
            reply_markup=get_main_menu()
        )
    
    elif data == "interval_menu":
        await query.edit_message_text(
            f"⚙️ Select check interval\n\nCurrent: {format_interval(interval)}",
            reply_markup=get_interval_menu()
        )
    
    elif data.startswith("set_"):
        minutes = int(data.split("_")[1])
        interval = minutes * 60
        
        was_running = bool(context.job_queue.get_jobs_by_name(f"monitor_{chat_id}"))
        if was_running:
            await do_stop(context, chat_id)
            await do_start(context, chat_id)
        
        await query.edit_message_text(
            f"✅ Interval changed to {format_interval(interval)}" + ("\n▶️ Monitoring restarted" if was_running else ""),
            reply_markup=get_main_menu()
        )
    
    elif data == "back":
        menu_text = (
            "🤖 **Tails Monitor Bot**\n\n"
            f"**Current settings:**\n"
            f"⏱️ Interval: {format_interval(interval)}\n"
            f"📦 Version: {last_title if last_title else 'No data'}\n\n"
            "Use buttons below."
        )
        await query.edit_message_text(menu_text, reply_markup=get_main_menu(), parse_mode="Markdown")
    
    elif data == "help":
        help_text = (
            "ℹ️ **Info**\n\n"
            "This BOT monitors new Tails version releases.\n\n"
            "**Buttons:**\n"
            "▶️ Start — start monitoring\n"
            "⏹️ Stop — stop monitoring\n"
            "📊 Status — current status\n"
            "⚙️ Interval — change check frequency\n\n"
            "**Notification:**\n"
            "Bot sends message only when new Tails version is released.\n\n"
            f"**Current settings:**\n"
            f"⏱️ Interval: {format_interval(interval)}\n"
            f"📦 Version: {last_title if last_title else 'No data'}"
        )
        await query.edit_message_text(help_text, reply_markup=get_main_menu(), parse_mode="Markdown")

# --- Telegram Bot Runner ---
def run_bot():
    if not TOKEN:
        logging.error("TELEGRAM_TOKEN is not set in Environment Variables!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("setinterval", set_interval))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 BOT is running (Polling mode)")
    app.run_polling()

# --- Web Server for Render (Health Check) ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is alive and running", 200

# --- Running ---
if __name__ == "__main__":
    # 1. Run Flask in background thread
    import threading
    from flask import Flask
    web_app = Flask(__name__)

    @web_app.route('/')
    def health_check():
        return "Bot is alive and running", 200

    def run_flask():
        port = int(os.environ.get("PORT", 5000))
        print(f"🌐 Web server starting on port {port}")
        web_app.run(host='0.0.0.0', port=port)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # 2. Run BOT in the main thread (to avoid set_wakeup_fd error)
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN is not set!")
    else:
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("stop", stop))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("setinterval", set_interval))
        app.add_handler(CallbackQueryHandler(button_handler))
        
        print("🤖 BOT is running (Polling mode in Main Thread)")
        app.run_polling()
