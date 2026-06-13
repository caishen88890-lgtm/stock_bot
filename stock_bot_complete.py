from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yfinance as yf
import requests
import random
import time
import re
import json
import os
from datetime import datetime, timedelta
import pytz
from openai import OpenAI
import mplfinance as mpf
from io import BytesIO

# ========== 配置 ==========
TELEGRAM_TOKEN = "8985123714:AAGToRGZKMUZfNqGTGHA-NpeBL5tAQVUIaY"
DEEPSEEK_API_KEY = "sk-60d4fda051f44b10bddfe639847a54eb"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
FINNHUB_KEY = "d8m9j0pr01qkiso71p8g"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# ========== 20种分析师人格 ==========
PERSONALITIES = [
    "宏观策略师", "交易员", "科技分析师", "资金流分析师",
    "行为金融分析师", "波动率专家", "逆向/价值派", "散户情绪观察员",
    "技术面狙击手", "价值捕手", "动量交易员", "财报猎手",
    "地缘政治分析师", "美联储喉舌", "行业轮动专家", "事件驱动投机者"
]

# ========== 股票池 ==========
STOCK_POOL = [
    "F","GM","UBER","NIO","LI","XPEV","RIVN","LCID","TSLA",
    "INTC","AMD","MU","PLTR","SOFI","SNAP","TWLO","ZM","DOCU","NVDA","AAPL","MSFT","META",
    "JD","BABA","PDD","TME","BIDU","VIPS","IQ","BILI","NTES",
    "AAL","DAL","UAL","CCL","NCLH","RCL","LUV",
    "WBA","KSS","M","GPS","TGT","BBY","COST","WMT",
    "T","VZ","TMUS","CMCSA","DIS","WBD","FOXA",
    "GE","CAT","BA","HON","MMM",
    "TEVA","BMY","MRK","PFE","JNJ","ABBV",
    "O","SPG","PLD","AMT"
]

# ========== 历史记录文件 ==========
HISTORY_FILE = "stock_history.json"
PURCHASED_FILE = "purchased_history.json"
CACHE_FILE = "daily_cache.json"

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return default

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data[-200:], f)

stock_history = load_json(HISTORY_FILE, [])
purchased_history = load_json(PURCHASED_FILE, [])

def was_recommended_recently(ticker, days=2):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for rec in stock_history[-100:]:
        if rec["ticker"] == ticker and rec["date"] >= cutoff:
            return True
    return False

def was_purchased_recently(ticker, days=7):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for rec in purchased_history[-50:]:
        if rec["ticker"] == ticker and rec["date"] >= cutoff:
            return True
    return False

def get_cached_77():
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
            if cache.get("date") == today:
                return cache.get("result")
    return None

def save_cached_77(result):
    today = datetime.now().strftime("%Y-%m-%d")
    with open(CACHE_FILE, 'w') as f:
        json.dump({"date": today, "result": result}, f)

# ========== 数据获取 ==========
def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return None
        price = hist["Close"].iloc[-1]
        change_1d = (hist["Close"].iloc[-1] - hist["Open"].iloc[-1]) / hist["Open"].iloc[-1] * 100
        change_5d = (hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100 if len(hist) >= 5 else 0
        volume_ratio = hist["Volume"].iloc[-1] / (hist["Volume"].mean() or 1)
        info = stock.info
        return {
            "ticker": ticker,
            "name": info.get("longName", ticker),
            "price": round(price, 2),
            "change_1d": round(change_1d, 2),
            "change_5d": round(change_5d, 2),
            "volume_ratio": round(volume_ratio, 2),
            "sector": info.get("sector", "科技"),
            "pe": info.get("trailingPE", "N/A"),
            "market_cap": info.get("marketCap", 0)
        }
    except:
        return None

def get_news_sentiment(ticker):
    try:
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={datetime.now().strftime('%Y-%m-%d')}&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=8)
        news = r.json()
        if news:
            pos = neg = 0
            for item in news[:10]:
                headline = item.get("headline", "").lower()
                if any(k in headline for k in ["beat", "upgrade", "positive", "surpass", "growth"]):
                    pos += 1
                elif any(k in headline for k in ["miss", "downgrade", "negative", "delay", "drop"]):
                    neg += 1
            if pos > neg:
                return "偏多"
            elif neg > pos:
                return "偏空"
    except:
        pass
    return "中性"

def generate_kline_chart(ticker, period="3mo"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if df.empty:
            return None
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        mc = mpf.make_marketcolors(up='red', down='green', inherit=True)
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=False)
        apds = [mpf.make_addplot(df['MA5'], color='blue', width=0.8), mpf.make_addplot(df['MA20'], color='orange', width=0.8)]
        buf = BytesIO()
        mpf.plot(df, type='candle', addplot=apds, style=s, title=f'{ticker} K线图 (MA5/MA20)', ylabel='价格 (USD)', volume=False, savefig=buf, figsize=(10, 5))
        buf.seek(0)
        return buf
    except:
        return None

# ========== 77 市场扫描 ==========
async def cmd_77(update, context):
    cached = get_cached_77()
    if cached:
        await update.message.reply_text(cached, parse_mode="Markdown")
        return
    
    msg = await update.message.reply_text("🔍 正在扫描市场机会，请稍等...")
    candidates = []
    for t in STOCK_POOL:
        if was_purchased_recently(t):
            continue
        data = get_stock_data(t)
        if not data or data["price"] < 10 or data["price"] > 100 or "金融" in data.get("sector", ""):
            continue
        if not was_recommended_recently(t):
            candidates.append(data)
        time.sleep(0.3)
    
    if not candidates:
        await msg.edit_text("暂未发现合适机会")
        return
    
    strong = [c for c in candidates if c["change_1d"] > 2 and c["volume_ratio"] > 1.5][:5]
    oversold = [c for c in candidates if c["change_5d"] < -5][:5]
    sideways = [c for c in candidates if c["volatility"] < 3][:5] if 'volatility' in candidates[0] else []
    selected = strong + oversold + sideways
    selected = selected[:15]
    random.shuffle(selected)
    
    today = datetime.now().strftime("%Y-%m-%d")
    for s in selected:
        stock_history.append({"ticker": s["ticker"], "date": today})
    save_json(HISTORY_FILE, stock_history)
    
    date_str = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y-%m-%d %H:%M EST")
    out = f"📊 *77 机会扫描（{date_str}）*\n\n"
    for idx, s in enumerate(selected, 1):
        arrow = "🟢" if s["change_1d"] > 0 else "🔴"
        out += f"{idx:02d} *{s['ticker']}* · {s['sector']}\n   价格 ${s['price']:.2f}  {arrow} {s['change_1d']:+.2f}%\n   5日涨跌 {s['change_5d']:+.2f}%  量比 {s['volume_ratio']:.1f}x\n\n"
    out += "👉 使用 `99 代码` 深度分析\n👉 使用 `00 代码` 生成交易计划\n💡 买入后发送 `/buy 代码`，7天内不会重复推荐"
    
    save_cached_77(out)
    await msg.edit_text(out, parse_mode="Markdown")

# ========== 99 深度分析 ==========
async def cmd_99(update, ticker, data):
    personality = random.choice(PERSONALITIES)
    sentiment = get_news_sentiment(ticker)
    prompt = f"""你是{personality}，20年华尔街经验。

请对{ticker}（{data['name']}）进行深度分析，200-400字：

当前数据：价格${data['price']}，{data['change_1d']:+.2f}%
5日涨跌{data['change_5d']:+.2f}%，量比{data['volume_ratio']:.1f}x
PE {data['pe']}，市值{data['market_cap']/1e9:.1f}亿
近期新闻情绪: {sentiment}

1. 市场共识可能错在哪里？
2. 决定未来2-3年价值的关键因素
3. 短期压力和波动来源
4. 最乐观情形是什么？
5. 最大的风险是什么？
6. 向上空间 vs 向下空间？

要求：敢说真话，200-400字。"""
    try:
        resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.8)
        comment = resp.choices[0].message.content
    except:
        comment = "AI分析暂时失败，请稍后重试。"
    up = "🟢" if data['change_1d'] > 0 else "🔴"
    await update.message.reply_text(
        f"📊 *99 深度分析* | {ticker} {data['name']}\n💰 ${data['price']} {up} {data['change_1d']:+.2f}%\n📰 新闻情绪: {sentiment}\n🎭 分析师: {personality}\n\n{comment}\n\n⚠️ 仅供参考",
        parse_mode="Markdown"
    )
    chart = generate_kline_chart(ticker)
    if chart:
        await update.message.reply_photo(photo=chart, caption=f"📈 {ticker} 日线K线图 (MA5/MA20)")

# ========== 00 交易计划 ==========
async def cmd_00(update, ticker, data):
    personality = random.choice(PERSONALITIES)
    sentiment = get_news_sentiment(ticker)
    price = data['price']
    target = round(price * 1.09, 2)
    profit = round((target - price) / price * 100, 1)
    trend = "稳步上涨" if data['change_1d'] > 1 else "小幅收涨" if data['change_1d'] > 0 else "窄幅震荡" if data['change_1d'] > -1 else "短期回调"
    
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if not hist.empty:
            year_high = hist["High"].max()
            year_low = hist["Low"].min()
            pos_1y = (price - year_low) / (year_high - year_low) * 100
            trend_1y = "近一年低位区域" if pos_1y < 30 else "近一年高位区域" if pos_1y > 70 else "近一年中位区域"
        else:
            year_high, year_low, pos_1y, trend_1y = price * 1.2, price * 0.8, 50, "近一年中位区域"
    except:
        year_high, year_low, pos_1y, trend_1y = price * 1.2, price * 0.8, 50, "近一年中位区域"
    
    plan = f"""🎯 *00 交易计划* | {ticker} {data['name']}

💰 价格: ${price}
📈 目标: ${target}（+{profit}%）
📊 趋势: {trend}
⚡ 量比: {data['volume_ratio']:.1f}x
📰 新闻情绪: {sentiment}
📅 近1年位置: {trend_1y}（{pos_1y:.0f}%）

📋 方案:
• 入场: ${price * 0.97:.2f} ~ ${price * 1.02:.2f}
• 止损: ${price * 0.94:.2f}（-6%）
• 止盈: ${target}

💡 *{personality} 的建议*
该股当前{trend}，新闻情绪{sentiment}，{'处于低位区域，可分批布局。' if pos_1y < 30 else '处于高位区域，注意风险。' if pos_1y > 70 else '处于中位区域，等待方向。'}

⚠️ 仅供参考，不构成投资建议"""
    await update.message.reply_text(plan, parse_mode="Markdown")
    chart = generate_kline_chart(ticker)
    if chart:
        await update.message.reply_photo(photo=chart, caption=f"📈 {ticker} 日线K线图 (MA5/MA20)")

# ========== V5 定时推送 ==========
def get_market_snapshot():
    sectors = {"XLK": "科技", "XLF": "金融", "XLE": "能源", "XLV": "医疗"}
    result = {"vix": 18, "tnx": 4.2, "sectors": {}}
    for ticker, name in sectors.items():
        price = get_stock_data(ticker)
        if price:
            result["sectors"][name] = price["price"]
        time.sleep(0.5)
    try:
        vix_data = yf.Ticker("^VIX").history(period="1d")
        if not vix_data.empty:
            result["vix"] = vix_data["Close"].iloc[-1]
    except:
        pass
    try:
        tnx_data = yf.Ticker("^TNX").history(period="1d")
        if not tnx_data.empty:
            result["tnx"] = tnx_data["Close"].iloc[-1]
    except:
        pass
    return result

def generate_short_comment(report_type, market_data):
    personality = random.choice(PERSONALITIES)
    vix = market_data.get("vix", 18)
    tnx = market_data.get("tnx", 4.2)
    sectors = market_data.get("sectors", {})
    strongest = max(sectors, key=sectors.get) if sectors else "科技"
    weakest = min(sectors, key=sectors.get) if sectors else "能源"
    prompt = f"""你是{personality}，20年华尔街经验。

请严格按以下框架分析{report_type}（基于实时数据）：

【宏观环境】10年期美债收益率{tnx}%，判断利率预期影响
【市场情绪】VIX={vix}，判断情绪状态
【资金流向】最强{strongest}，最弱{weakest}
【行业轮动】当前市场风格
【多空推演】看多 vs 看空逻辑
【最终结论】明确偏多/中性/偏空

禁止复述新闻，必须解释“为什么”。"""
    try:
        resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.7)
        return resp.choices[0].message.content.strip()
    except:
        return f"{personality}：数据获取失败，请稍后重试。"

def send_telegram(text, title="市场点评"):
    full = f"📊 *{title}*\n\n{text}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": "-1003906407266", "text": full, "parse_mode": "Markdown"})
        print(f"✅ 已发送: {title}")
    except:
        print(f"❌ 发送失败: {title}")

def job_short(report_type):
    market = get_market_snapshot()
    comment = generate_short_comment(report_type, market)
    send_telegram(comment, report_type)

def run_scheduled_jobs():
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est)
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    
    if weekday == 5 and hour == 18 and minute < 30:
        send_telegram("✅ 周六系统测试，机器人运行正常，明晚周报将按时推送。", "系统测试")
    elif 0 <= weekday <= 4:
        if hour == 8 and minute >= 10 and minute < 30:
            send_telegram("✅ 系统正常，20分钟后推送盘前点评", "系统检查")
        elif hour == 8:
            job_short("盘前点评")
        elif hour == 10 and minute >= 10 and minute < 30:
            send_telegram("✅ 系统正常，20分钟后推送早盘点评", "系统检查")
        elif hour == 10:
            job_short("早盘点评")
        elif hour == 12 and minute >= 10 and minute < 30:
            send_telegram("✅ 系统正常，20分钟后推送午盘点评", "系统检查")
        elif hour == 12:
            job_short("午盘点评")
        elif hour == 15 and minute >= 10 and minute < 30:
            send_telegram("✅ 系统正常，20分钟后推送收盘点评", "系统检查")
        elif hour == 15:
            job_short("收盘点评")
    elif weekday == 6 and hour == 18:
        if minute >= 10 and minute < 30:
            send_telegram("✅ 系统正常，20分钟后推送周报", "系统检查")
        elif minute >= 30:
            send_telegram("📆 周日周报：基于八层框架的综合复盘与下周展望。", "周度总结 & 下周展望")

# ========== 买入记录 ==========
async def cmd_buy(update, context):
    match = re.match(r'^/buy\s+([A-Za-z]+)$', update.message.text.strip())
    if not match:
        await update.message.reply_text("格式错误，请发送：/buy NVDA")
        return
    ticker = match.group(1).upper()
    today = datetime.now().strftime("%Y-%m-%d")
    purchased_history.append({"ticker": ticker, "date": today})
    save_json(PURCHASED_FILE, purchased_history)
    await update.message.reply_text(f"✅ 已记录买入 {ticker}（{today}），7天内不会重复推荐")

# ========== 消息路由 ==========
async def handle(update, context):
    text = update.message.text.strip()
    
    if text == "77":
        await cmd_77(update, context)
    elif text.startswith("99 "):
        ticker = text.split()[1].upper()
        await update.message.reply_text(f"🔍 正在分析 {ticker}...")
        data = get_stock_data(ticker)
        if not data:
            await update.message.reply_text(f"无法获取 {ticker} 数据")
            return
        await cmd_99(update, ticker, data)
    elif text.startswith("00 "):
        ticker = text.split()[1].upper()
        await update.message.reply_text(f"🔍 正在生成 {ticker} 交易计划...")
        data = get_stock_data(ticker)
        if not data:
            await update.message.reply_text(f"无法获取 {ticker} 数据")
            return
        await cmd_00(update, ticker, data)

# ========== 主程序 ==========
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CommandHandler("buy", cmd_buy))
    print("✅ 完整功能版机器人已启动（含定时推送、新闻情绪、买入记录）")
    print("77 → 机会扫描 | 99 代码 → 深度分析+情绪+K线 | 00 代码 → 交易计划+K线 | /buy 代码 → 记录买入")
    print("V5 定时推送运行中（美东时间 8:30/10:30/12:30/15:30）")
    
    import threading
    def scheduler_loop():
        while True:
            run_scheduled_jobs()
            time.sleep(60)
    threading.Thread(target=scheduler_loop, daemon=True).start()
    
    app.run_polling()

if __name__ == "__main__":
    main()
