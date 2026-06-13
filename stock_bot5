from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yfinance as yf
import requests
import random
import time
import re
from datetime import datetime
import pytz

# ========== 配置 ==========
TELEGRAM_TOKEN = "8985123714:AAGToRGZKMUZfNqGTGHA-NpeBL5tAQVUIaY"

# ========== 简单测试命令 ==========
async def start(update, context):
    await update.message.reply_text("机器人已启动！发送 /test 测试")

async def test(update, context):
    await update.message.reply_text("测试成功！机器人正常工作")

# ========== 主程序 ==========
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    print("✅ 测试机器人已启动")
    print("发送 /start 或 /test 测试")
    app.run_polling()

if __name__ == "__main__":
    main()
