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

# --- KHỞI TẠO WEB SERVER ---
server = Flask(__name__)
@server.route('/')
def ping(): return "Bot is alive!", 200

def run_web_server():
    server.run(host="0.0.0.0", port=PORT)

# --- KHỞI TẠO GOOGLE SHEETS & BOT ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(G_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("BotData").sheet1
bot = telebot.TeleBot(TOKEN)

# --- LOGIC NHẮC HẸN 6H SÁNG (Vẫn giữ để nhắc bạn điểm danh sớm) ---
def send_daily_reminder():
    try:
        msg = "☀️ **Chào buổi sáng chủ nhân!**\nĐã đến 6:00 sáng, đừng quên gõ `/cong` để nhận 30,000đ nhé! (Hiện tại đã có thể điểm danh bất cứ lúc nào trong ngày)."
        bot.send_message(MY_ID, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Lỗi gửi nhắc hẹn: {e}")

scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Ho_Chi_Minh'))
scheduler.add_job(send_daily_reminder, 'cron', hour=6, minute=0)
scheduler.start()

# --- QUẢN LÝ SPAM ---
user_last_command_time = {}
SPAM_THRESHOLD = 2 

def check_spam(user_id):
    current_time = time.time()
    last_time = user_last_command_time.get(user_id, 0)
    if current_time - last_time < SPAM_THRESHOLD: return True
    user_last_command_time[user_id] = current_time
    return False

@bot.message_handler(func=lambda message: message.from_user.id == MY_ID)
def handle_commands(message):
    if check_spam(message.from_user.id): return
    
    text = message.text
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    today = datetime.now(tz).strftime("%d/%m/%Y")
    bot.send_chat_action(message.chat.id, 'typing')

    try:
        data = sheet.batch_get(['B1', 'B2'])
        current_balance = int(data[0][0][0] or 0)
        last_date = data[1][0][0] if len(data[1]) > 0 else ""

        if text == '/start':
            help_text = (
                "👋 **Hệ thống đã sẵn sàng!**\n\n"
                "🔓 **Tất cả các lệnh dưới đây có thể dùng 24/7:**\n"
                "• `/cong`: Điểm danh nhận +30,000đ\n"
                "• `/tru`: Khấu trừ -10,000đ\n"
                "• `/sodu`: Kiểm tra số dư hiện tại\n"
                "• `/rut [số tiền]`: Rút tiền từ ví\n\n"
                "*(Lưu ý: `/cong` và `/tru` vẫn giới hạn dùng 1 lần/ngày)*"
            )
            bot.reply_to(message, help_text, parse_mode="Markdown")

        elif text == '/sodu':
            bot.reply_to(message, f"💰 Số dư hiện tại: **{current_balance:,} VNĐ**", parse_mode="Markdown")

        elif text.startswith('/rut'):
            try:
                val_rut = int(text.split()[1])
                if val_rut > current_balance:
                    bot.reply_to(message, f"❌ Không đủ tiền! (Bạn còn {current_balance:,}đ)")
                else:
                    new_val = current_balance - val_rut
                    sheet.update('B1', [[new_val]])
                    bot.reply_to(message, f"💸 Đã rút {val_rut:,}đ.\n💰 Còn lại: **{new_val:,} VNĐ**", parse_mode="Markdown")
            except: bot.reply_to(message, "⚠️ Cú pháp: `/rut 50000`", parse_mode="Markdown")

        elif text in ['/cong', '/tru']:
            # Kiểm tra ngày (giữ lại để chống lạm dụng 1 ngày cộng nhiều lần)
            if last_date == today:
                return bot.reply_to(message, "⚠️ Hôm nay bạn đã điểm danh rồi! Hãy quay lại vào ngày mai.")

            new_val = current_balance + 30000 if text == '/cong' else current_balance - 10000
            
            # Cập nhật Sheets
            sheet.update('B1', [[new_val]])
            sheet.update('B2', [[today]])
            
            msg = f"{'✅' if text == '/cong' else '❌'} Thành công!\n💰 Số dư mới: **{new_val:,} VNĐ**"
            bot.reply_to(message, msg, parse_mode="Markdown")

    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "⚙️ Lỗi kết nối dữ liệu, vui lòng thử lại.")

if __name__ == "__main__":
    Thread(target=run_web_server).start()
    print("Bot đang chạy (Không giới hạn thời gian điểm danh)...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)