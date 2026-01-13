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

# --- CẤU HÌNH HỆ THỐNG ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = 7346983056 
G_JSON = os.getenv('G_SHEETS_JSON')
# [cite_start]Koyeb cung cấp biến PORT, nếu không có sẽ mặc định chạy 8000 [cite: 1]
PORT = int(os.environ.get("PORT", 8000))

# --- KHỞI TẠO WEB SERVER (Để Cron-job.org ping) ---
server = Flask(__name__)

@server.route('/')
def ping():
    return "Bot is alive and healthy!", 200

# --- KẾT NỐI GOOGLE SHEETS ---
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(G_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("BotData").sheet1

sheet = get_sheet()
bot = telebot.TeleBot(TOKEN)

# --- NHẮC HẸN 6H SÁNG ---
def send_daily_reminder():
    try:
        bot.send_message(ADMIN_ID, "☀️ **6:00 AM:** Đừng quên gõ `/cong` để nhận thưởng hôm nay chủ nhân nhé!", parse_mode="Markdown")
    except Exception as e: 
        print(f"Lỗi gửi nhắc hẹn: {e}")

scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Ho_Chi_Minh'))
scheduler.add_job(send_daily_reminder, 'cron', hour=6, minute=0)
scheduler.start()

# --- CHỐNG SPAM ---
user_last_command_time = {}
def check_spam(user_id):
    current_time = time.time()
    last_time = user_last_command_time.get(user_id, 0)
    if current_time - last_time < 2: return True
    user_last_command_time[user_id] = current_time
    return False

# --- XỬ LÝ LỆNH ---
@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID)
def handle_commands(message):
    if check_spam(message.from_user.id): return
    
    text = message.text
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    today = datetime.now(tz).strftime("%d/%m/%Y")
    bot.send_chat_action(message.chat.id, 'typing')

    try:
        data = sheet.batch_get(['B1', 'B2'])
        raw_balance = data[0][0][0] if len(data[0]) > 0 and len(data[0][0]) > 0 else "0"
        current_balance = int(str(raw_balance).replace(',', '').strip() or 0)
        last_date = data[1][0][0] if len(data[1]) > 0 and len(data[1][0]) > 0 else ""

        if text == '/start':
            bot.reply_to(message, "✅ **Kết nối Koyeb thành công!**\nSố dư cập nhật từ Google Sheets.", parse_mode="Markdown")
        elif text == '/sodu':
            bot.reply_to(message, f"💰 Số dư: **{current_balance:,} VNĐ**", parse_mode="Markdown")
        elif text.startswith('/rut'):
            try:
                val_rut = int(text.split()[1])
                if val_rut > current_balance:
                    bot.reply_to(message, f"❌ Không đủ! Có: {current_balance:,}đ")
                else:
                    new_val = current_balance - val_rut
                    sheet.update('B1', [[new_val]])
                    bot.reply_to(message, f"💸 Đã rút {val_rut:,}đ.\n💰 Còn lại: **{new_val:,} VNĐ**", parse_mode="Markdown")
            except: 
                bot.reply_to(message, "⚠️ Cú pháp: `/rut 50000`")
        elif text in ['/cong', '/tru']:
            if last_date == today:
                return bot.reply_to(message, "⚠️ Hôm nay bạn đã điểm danh rồi!")
            new_val = current_balance + 30000 if text == '/cong' else current_balance - 10000
            sheet.update('B1', [[new_val]])
            sheet.update('B2', [[today]])
            bot.reply_to(message, f"✅ Đã cập nhật!\n💰 Số dư mới: **{new_val:,} VNĐ**", parse_mode="Markdown")
    except Exception as e:
        print(f"Error: {e}")

# --- KHỞI CHẠY ---
def run_bot():
    bot.infinity_polling(timeout=20, long_polling_timeout=10)

if __name__ == "__main__":
    # 1. Chạy bot ở luồng phụ (Thread)
    t = Thread(target=run_bot)
    t.start()
    
    # [cite_start]2. Chạy Flask ở luồng chính (Main Thread) [cite: 1]
    # [cite_start]host="0.0.0.0" là bắt buộc để Koyeb có thể truy cập [cite: 1]
    server.run(host="0.0.0.0", port=PORT)
