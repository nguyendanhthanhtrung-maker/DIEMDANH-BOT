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
MY_ID = 7346983056 
G_JSON = os.getenv('G_SHEETS_JSON')
PORT = int(os.environ.get("PORT", 8000))

# --- KHỞI TẠO WEB SERVER (Để bot không bị sleep) ---
server = Flask(__name__)
@server.route('/')
def ping(): return "Bot is alive!", 200

def run_web_server():
    server.run(host="0.0.0.0", port=PORT)

# --- KẾT NỐI GOOGLE SHEETS ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(G_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
# Bot sẽ luôn mở file "BotData" mỗi khi cần lấy dữ liệu mới nhất
sheet = client.open("BotData").sheet1
bot = telebot.TeleBot(TOKEN)

# --- NHẮC HẸN 6H SÁNG ---
def send_daily_reminder():
    try:
        bot.send_message(MY_ID, "☀️ **6:00 AM:** Đừng quên gõ `/cong` để nhận thưởng hôm nay chủ nhân nhé!", parse_mode="Markdown")
    except Exception as e: print(f"Lỗi gửi nhắc hẹn: {e}")

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
@bot.message_handler(func=lambda message: message.from_user.id == MY_ID)
def handle_commands(message):
    if check_spam(message.from_user.id): return
    
    text = message.text
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    today = datetime.now(tz).strftime("%d/%m/%Y")
    bot.send_chat_action(message.chat.id, 'typing')

    try:
        # Lấy dữ liệu thời gian thực từ Sheets 
        # B1: Số dư, B2: Ngày điểm danh cuối
        data = sheet.batch_get(['B1', 'B2'])
        
        # Xử lý trường hợp bạn đang để trống ô trên Sheet
        raw_balance = data[0][0][0] if len(data[0]) > 0 and len(data[0][0]) > 0 else "0"
        current_balance = int(str(raw_balance).replace(',', '').strip() or 0)
        
        last_date = data[1][0][0] if len(data[1]) > 0 and len(data[1][0]) > 0 else ""

        if text == '/start':
            bot.reply_to(message, "✅ **Kết nối thành công!**\nBạn có thể chỉnh sửa trực tiếp số dư tại ô **B1** trên Google Sheets, Bot sẽ cập nhật ngay lập tức.", parse_mode="Markdown")

        elif text == '/sodu':
            bot.reply_to(message, f"💰 Số dư thực tế trên Sheet: **{current_balance:,} VNĐ**", parse_mode="Markdown")

        elif text.startswith('/rut'):
            try:
                val_rut = int(text.split()[1])
                if val_rut > current_balance:
                    bot.reply_to(message, f"❌ Không đủ! Sheet hiện có: {current_balance:,}đ")
                else:
                    new_val = current_balance - val_rut
                    sheet.update('B1', [[new_val]]) # Cập nhật ngược lại Sheet 
                    bot.reply_to(message, f"💸 Đã rút {val_rut:,}đ.\n💰 Còn lại: **{new_val:,} VNĐ**", parse_mode="Markdown")
            except: bot.reply_to(message, "⚠️ Cú pháp: `/rut 50000`")

        elif text in ['/cong', '/tru']:
            if last_date == today:
                return bot.reply_to(message, "⚠️ Sheet ghi nhận bạn đã điểm danh hôm nay rồi!")

            new_val = current_balance + 30000 if text == '/cong' else current_balance - 10000
            sheet.update('B1', [[new_val]])
            sheet.update('B2', [[today]])
            bot.reply_to(message, f"✅ Đã cập nhật lên Sheet!\n💰 Số dư mới: **{new_val:,} VNĐ**", parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, "❌ Lỗi: Không đọc được dữ liệu từ Sheet. Hãy kiểm tra xem bạn có đang nhập sai định dạng ở ô B1 không.")
        print(f"Error: {e}")

if __name__ == "__main__":
    Thread(target=run_web_server).start()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
