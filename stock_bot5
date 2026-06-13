import warnings
import yfinance as yf
import requests
import random
import time
import json
import re
import asyncio
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from openai import OpenAI
import mplfinance as mpf
from io import BytesIO

warnings.filterwarnings('ignore')

# ========== 配置 ==========
DEEPSEEK_API_KEY = "sk-60d4fda051f44b10bddfe639847a54eb"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
TELEGRAM_BOT_TOKEN = "8985123714:AAGToRGZKMUZfNqGTGHA-NpeBL5tAQVUIaY"
TELEGRAM_CHAT_ID = "-1003906407266"
FINNHUB_KEY = "d8m9j0pr01qkiso71p8g"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

PERSONALITIES = [
    "宏观策略师", "交易员", "科技分析师", "资金流分析师",
    "行为金融分析师", "波动率专家", "逆向/价值派", "散户情绪观察员"
]

# ========== 全局任务队列 ==========
task_queue = []
processing = False

# ========== 数据获取 ==========
def get_price_yahoo(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return hist["Close"].iloc[-1]
    except:
        pass
    return None

def get_price_finnhub(ticker):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=5)
        price = r.json().get("c")
        if price:
            return float(price)
    except:
        pass
    return None

def get_realtime_price(ticker):
    price = get_price_yahoo(ticker)
    if price:
        return price
    price = get_price_finnhub(ticker)
    if price:
        return price
    return None

def get_stock_data(ticker):
    try:
        price = get_realtime_price(ticker)
        if not price:
            return None
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="5d")
        if hist.empty:
            return None
        change_1d = (hist["Close"].iloc[-1] - hist["Open"].iloc[-1]) / hist["Open"].iloc[-1] * 100
        change_5d = (hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100 if len(hist) >= 5 else 0
        volume_ratio = hist["Volume"].iloc[-1] / (hist["Volume"].mean() or 1)
        volatility = hist["Close"].pct_change().std() * 100
        time.sleep(1)
        return {
            "ticker": ticker,
            "name": info.get("longName", ticker),
            "price": round(price, 2),
            "change_1d": round(change_1d, 2),
            "change_5d": round(change_5d, 2),
            "volume_ratio": round(volume_ratio, 2),
            "volatility": round(volatility, 2),
            "sector": info.get("sector", "科技"),
            "pe": info.get("trailingPE", "N/A"),
            "market_cap": info.get("marketCap", 0)
        }
    except:
        return None

def get_market_snapshot():
    sectors = {"XLK": "科技", "XLF": "金融", "XLE": "能源", "XLV": "医疗"}
    result = {"vix": 18, "tnx": 4.2, "sectors": {}}
    for ticker, name in sectors.items():
        price = get_realtime_price(ticker)
        if price:
            result["sectors"][name] = price
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
        apds = [
            mpf.make_addplot(df['MA5'], color='blue', width=0.8),
            mpf.make_addplot(df['MA20'], color='orange', width=0.8)
        ]
        buf = BytesIO()
        mpf.plot(df, type='candle', addplot=apds, style=s,
                 title=f'{ticker} K线图 (MA5/MA20)',
                 ylabel='价格 (USD)', volume=False,
                 savefig=buf, figsize=(10, 5))
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"生成K线图失败: {e}")
        return None

# ========== V5 定时推送 ==========
def generate_short_comment(report_type, market_data):
    personality = random.choice(PERSONALITIES)
    vix = market_data.get("vix", 18)
    tnx = market_data.get("tnx", 4.2)
    sectors = market_data.get("sectors", {})
    strongest = max(sectors, key=sectors.get) if sectors else "科技"
    weakest = min(sectors, key=sectors.get) if sectors else "能源"
    prompt = f"""
你是{personality}，20年华尔街经验。

请严格按以下框架分析{report_type}（基于实时数据）：

【宏观环境】10年期美债收益率{tnx}%，判断利率预期影响
【市场情绪】VIX={vix}，判断情绪状态
【资金流向】最强{strongest}，最弱{weakest}
【国际局势】中东/俄乌/中美对市场的潜在影响
【行业轮动】当前市场风格
【多空推演】看多 vs 看空逻辑
【最终结论】明确偏多/中性/偏空

禁止复述新闻，必须解释“为什么”。
"""
    try:
        time.sleep(2)  # DeepSeek 不限流，2秒足够
        resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.7)
        return resp.choices[0].message.content.strip()
    except:
        return f"{personality}：数据获取失败，请稍后重试。"

def send_telegram(text, title="市场点评"):
    full = f"📊 *{title}*\n\n{text}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": full, "parse_mode": "Markdown"})
        print(f"✅ 已发送: {title}")
    except:
        print(f"❌ 发送失败: {title}")

def job_short(report_type):
    market = get_market_snapshot()
    comment = generate_short_comment(report_type, market)
    send_telegram(comment, report_type)

def job_sunday_1830():
    send_telegram("📆 周日周报：基于八层框架的综合复盘与下周展望。", "周度总结 & 下周展望")

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
            job_sunday_1830()

# ========== 77 市场扫描器 ==========
STOCK_POOL = ["F","GM","UBER","NIO","LI","XPEV","INTC","AMD","MU","PLTR","SOFI","SNAP","JD","BABA","PDD","AAL","DAL","CCL","WBA","T","VZ","GE","BA"]

async def cmd_77(update, context):
    msg = await update.message.reply_text("🔍 正在扫描市场机会，请稍等（约30-60秒）...")
    candidates = []
    for t in STOCK_POOL:
        data = get_stock_data(t)
        if not data:
            continue
        if data["price"] < 10 or data["price"] > 80:
            continue
        if "金融" in data.get("sector", ""):
            continue
        candidates.append(data)
        time.sleep(1)
    if not candidates:
        await msg.edit_text("暂未发现合适机会")
        return
    strong = [c for c in candidates if c["change_1d"] > 2 and c["volume_ratio"] > 1.5]
    oversold = [c for c in candidates if c["change_5d"] < -5]
    sideways = [c for c in candidates if c["volatility"] < 3]
    selected = strong[:5] + oversold[:5] + sideways[:5]
    selected = selected[:15]
    random.shuffle(selected)
    date_str = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y-%m-%d %H:%M EST")
    out = f"📊 *77 机会扫描（{date_str}）*\n\n"
    for idx, s in enumerate(selected, 1):
        arrow = "🟢" if s["change_1d"] > 0 else "🔴"
        out += f"{idx:02d} *{s['ticker']}* · {s['sector']}\n"
        out += f"   价格 ${s['price']:.2f}  {arrow} {s['change_1d']:+.2f}%\n"
        out += f"   5日涨跌 {s['change_5d']:+.2f}%  量比 {s['volume_ratio']:.1f}x\n\n"
    out += "👉 使用 `99 代码` 深度分析\n👉 使用 `00 代码` 生成交易计划"
    await msg.edit_text(out, parse_mode="Markdown")

# ========== 99 深度分析 ==========
async def cmd_99(update, ticker, data):
    personality = random.choice(PERSONALITIES)
    prompt = f"""
你是{personality}，20年华尔街经验。

请对{ticker}（{data['name']}）进行深度分析，200-400字：

不要写格式化报告，像专业投资者那样思考：
1. 市场共识可能错在哪里？
2. 决定未来2-3年价值的关键因素
3. 短期压力和波动来源
4. 最乐观情形是什么？
5. 最大的风险是什么？
6. 向上空间 vs 向下空间？

当前数据：价格${data['price']}，{data['change_1d']:+.2f}%
5日涨跌{data['change_5d']:+.2f}%，量比{data['volume_ratio']:.1f}x
PE {data['pe']}，市值{data['market_cap']/1e9:.1f}亿

要求：敢说真话，200-400字。
"""
    try:
        time.sleep(2)  # DeepSeek 不限流
        resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.8)
        comment = resp.choices[0].message.content
    except Exception as e:
        print(f"AI分析失败: {e}")
        comment = "AI分析暂时失败，请稍后重试。"
    up = "🟢" if data['change_1d'] > 0 else "🔴"
    await update.message.reply_text(
        f"📊 *99 深度分析* | {ticker} {data['name']}\n"
        f"💰 ${data['price']} {up} {data['change_1d']:+.2f}%\n"
        f"🎭 分析师: {personality}\n\n{comment}\n\n⚠️ 仅供参考",
        parse_mode="Markdown"
    )
    chart = generate_kline_chart(ticker)
    if chart:
        await update.message.reply_photo(photo=chart, caption=f"📈 {ticker} 日线K线图 (MA5/MA20)")

# ========== 00 交易计划 ==========
async def cmd_00(update, ticker, data):
    personality = random.choice(PERSONALITIES)
    price = data['price']
    target = round(price * 1.09, 2)
    profit = round((target - price) / price * 100, 1)

    if data['change_1d'] > 1:
        trend = "稳步上涨"
    elif data['change_1d'] > 0:
        trend = "小幅收涨"
    elif data['change_1d'] > -1:
        trend = "窄幅震荡"
    else:
        trend = "短期回调"

    # ----- 获取近一年高低点 -----
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if not hist.empty:
            year_high = hist["High"].max()
            year_low = hist["Low"].min()
            pos_1y = (price - year_low) / (year_high - year_low) * 100
            if pos_1y < 30:
                trend_1y = "近一年低位区域"
                weak_stock = True
            elif pos_1y > 70:
                trend_1y = "近一年高位区域"
                weak_stock = False
            else:
                trend_1y = "近一年中位区域"
                weak_stock = False
        else:
            year_high = price * 1.2
            year_low = price * 0.8
            weak_stock = False
    except:
        year_high = price * 1.2
        year_low = price * 0.8
        weak_stock = False

    # ----- 获取新闻情绪 -----
    news_sentiment = "中性"
    try:
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from=2026-05-01&to=2026-06-13&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=8)
        news = r.json()
        if news:
            pos = neg = 0
            for item in news[:20]:
                headline = item.get("headline", "").lower()
                if any(k in headline for k in ["beat", "upgrade", "buy", "positive", "surpass"]):
                    pos += 1
                elif any(k in headline for k in ["miss", "downgrade", "sell", "negative", "delay"]):
                    neg += 1
            if pos > neg:
                news_sentiment = "偏多"
            elif neg > pos:
                news_sentiment = "偏空"
    except:
        pass

    # ----- 判断活跃度 -----
    is_active = data['volume_ratio'] > 1.2
    is_weak = weak_stock

    if is_active:
        time_horizon = "1个月内"
    elif is_weak:
        time_horizon = "3–6个月内"
    else:
        time_horizon = "2–4个月内"

    if is_weak and pos_1y < 20:
        advice = (
            f"该股目前处于{trend_1y}（{pos_1y:.0f}%），近一年反弹力度极弱，长期下跌趋势未见扭转。"
            f"若你的成本较高且亏损已超20%，建议考虑在反弹至 ${year_low + (year_high - year_low) * 0.2:.2f} 附近分批减仓，"
            f"而不是死扛。除非公司基本面发生重大变化，否则弱势状态可能持续较长时间。"
            f"预计未来3-6个月内仍以筑底为主，大幅回升概率较低。"
        )
    elif is_active and not is_weak:
        advice = (
            f"该股近期活跃（量比 {data['volume_ratio']:.1f}x），趋势{trend}，市场关注度较高。"
            f"若你当前亏损较小（5%以内），建议继续持有，短期有机会挑战 ${target}。"
            f"从技术面看，该股过去一年曾触及 ${year_high:.2f}，说明并非没有弹性。"
            f"预计 {time_horizon} 内可能回到成本价附近，届时可再决定去留。"
        )
    else:
        advice = (
            f"该股当前{trend}，处于{trend_1y}（{pos_1y:.0f}%），量比 {data['volume_ratio']:.1f}x。"
            f"若亏损不大，可考虑持有观察，目标看 ${target}。"
            f"若亏损较重且不愿止损，则需关注关键支撑位 ${year_low:.2f}。"
            f"综合新闻情绪{news_sentiment}，短期波动可能加大。"
            f"预计 {time_horizon} 内股价存在修复机会，但并非强烈反转信号。"
        )

    if news_sentiment == "偏多":
        advice += f" 近期新闻整体偏暖，情绪支撑尚在。"
    elif news_sentiment == "偏空":
        advice += f" 近期新闻偏冷，注意短期不确定性。"

    plan = f"""🎯 *00 交易计划* | {ticker} {data['name']}

💰 价格: ${price}
📈 目标: ${target}（+{profit}%）
📊 趋势: {trend}
⚡ 量比: {data['volume_ratio']:.1f}x
📰 新闻情绪: {news_sentiment}
📅 近1年位置: {trend_1y}（{pos_1y:.0f}%）

📋 方案:
• 入场: ${price * 0.97:.2f} ~ ${price * 1.02:.2f}
• 止损: ${price * 0.94:.2f}（-6%）
• 止盈: ${target}

💡 *{personality} 的建议*
{advice}

⚠️ 仅供参考，不构成投资建议"""
    await update.message.reply_text(plan, parse_mode="Markdown")
    chart = generate_kline_chart(ticker)
    if chart:
        await update.message.reply_photo(photo=chart, caption=f"📈 {ticker} 日线K线图 (MA5/MA20)")

# ========== 消息路由 ==========
async def handle(update, context):
    global processing, task_queue
    text = update.message.text.strip()
    
    # 只处理三个命令
    if not (text == "77" or re.match(r'^99\s+([A-Z]{2,5})$', text, re.IGNORECASE) or re.match(r'^00\s+([A-Z]{2,5})$', text, re.IGNORECASE)):
        return  # 其他消息忽略
    
    async def process():
        global processing
        status_msg = await update.message.reply_text("🔍 正在查询中，请稍等...（请耐心等待）")
        try:
            if text == "77":
                await cmd_77(update, context)
            else:
                m99 = re.match(r'^99\s+([A-Z]{2,5})$', text, re.IGNORECASE)
                if m99:
                    ticker = m99.group(1).upper()
                    data = get_stock_data(ticker)
                    if not data:
                        await update.message.reply_text(f"无法获取 {ticker} 数据")
                    else:
                        await cmd_99(update, ticker, data)
                else:
                    m00 = re.match(r'^00\s+([A-Z]{2,5})$', text, re.IGNORECASE)
                    if m00:
                        ticker = m00.group(1).upper()
                        data = get_stock_data(ticker)
                        if not data:
                            await update.message.reply_text(f"无法获取 {ticker} 数据")
                        else:
                            await cmd_00(update, ticker, data)
        finally:
            await status_msg.delete()
            processing = False
            if task_queue:
                next_task = task_queue.pop(0)
                processing = True
                asyncio.create_task(next_task())
    
    if processing:
        task_queue.append(process)
        await update.message.reply_text("⏳ 正在处理上一个查询，请稍等，我会自动排队处理。")
    else:
        processing = True
        asyncio.create_task(process())

# ========== 主程序 ==========
def main():
    import threading
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    def run_bot():
        app.run_polling()
    threading.Thread(target=run_bot, daemon=True).start()
    print("✅ 机器人已启动（DeepSeek + 串行队列）")
    print("77 → 发现机会 | 99 代码 → 深度分析 + K线图 | 00 代码 → 交易计划 + K线图")
    print("V5 定时推送运行中（美东时间）")
    while True:
        run_scheduled_jobs()
        time.sleep(60)

if __name__ == "__main__":
    main()
