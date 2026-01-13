import telebot
import os
import gspread
import json
import time
from datetime import datetime
import pytz
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

# --- CẤU HÌNH ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
MY_ID = 7346983056
G_JSON = os.getenv("G_SHEETS_JSON")

# ===================== WEB SERVER =====================
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot is alive", 200

# ===================== TELEGRAM BOT =====================
bot = telebot.TeleBot(TOKEN)

# ===================== GOOGLE SHEETS =====================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(G_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("BotData").sheet1

# ===================== NHẮC 6H SÁNG =====================
def send_daily_reminder():
    try:
        bot.send_message(
            MY_ID,
            "☀️ **6:00 AM:** Đừng quên gõ `/cong` để nhận thưởng hôm nay nhé!",
            parse_mode="Markdown"
        )
    except Exception as e:
        print("Reminder error:", e)

scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Ho_Chi_Minh"))
scheduler.add_job(send_daily_reminder, "cron", hour=6, minute=0)
scheduler.start()

# ===================== CHỐNG SPAM =====================
user_last_command_time = {}

def check_spam(user_id):
    now = time.time()
    last = user_last_command_time.get(user_id, 0)
    if now - last < 2:
        return True
    user_last_command_time[user_id] = now
    return False

# ===================== XỬ LÝ LỆNH =====================
@bot.message_handler(func=lambda message: message.from_user.id == MY_ID)
def handle_commands(message):
    if check_spam(message.from_user.id):
        return

    text = message.text
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    today = datetime.now(tz).strftime("%d/%m/%Y")

    try:
        data = sheet.batch_get(["B1", "B2"])

        raw_balance = data[0][0][0] if data[0] and data[0][0] else "0"
        current_balance = int(str(raw_balance).replace(",", "").strip() or 0)

        last_date = data[1][0][0] if data[1] and data[1][0] else ""

        if text == "/start":
            bot.reply_to(message, "✅ Bot đã kết nối với Google Sheets!")

        elif text == "/sodu":
            bot.reply_to(message, f"💰 Số dư: **{current_balance:,} VNĐ**", parse_mode="Markdown")

        elif text.startswith("/rut"):
            try:
                val = int(text.split()[1])
                if val > current_balance:
                    bot.reply_to(message, "❌ Không đủ tiền!")
                else:
                    new_val = current_balance - val
                    sheet.update("B1", [[new_val]])
                    bot.reply_to(message, f"💸 Đã rút {val:,}đ\nCòn lại: **{new_val:,} VNĐ**", parse_mode="Markdown")
            except:
                bot.reply_to(message, "⚠️ Dùng: /rut 50000")

        elif text in ["/cong", "/tru"]:
            if last_date == today:
                bot.reply_to(message, "⚠️ Hôm nay bạn đã điểm danh rồi!")
                return

            new_val = current_balance + 30000 if text == "/cong" else current_balance - 10000
            sheet.update("B1", [[new_val]])
            sheet.update("B2", [[today]])
            bot.reply_to(message, f"✅ Số dư mới: **{new_val:,} VNĐ**", parse_mode="Markdown")

    except Exception as e:
        print("Sheet error:", e)
        bot.reply_to(message, "❌ Lỗi Google Sheets!")

# ===================== CHẠY BOT =====================
def start_bot():
    print("Telegram bot started")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

Thread(target=start_bot).start()