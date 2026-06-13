from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yfinance as yf
import requests
import random
import time
import re
import json
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

def get_realtime_price(ticker):
    price = get_price_yahoo(ticker)
    return price

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

# ========== K线图生成 ==========
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

# ========== 77 市场扫描 ==========
async def cmd_77(update, context):
    msg = await update.message.reply_text("🔍 正在扫描市场机会，请稍等（约30-60秒）...")
    candidates = []
    for t in STOCK_POOL:
        data = get_stock_data(t)
        if not data:
            continue
        if data["price"] < 10 or data["price"] > 100:
            continue
        if "金融" in data.get("sector", ""):
            continue
        candidates.append(data)
        time.sleep(0.5)
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
    out += "👉 使用 `99 代码` 深度分析（带K线图）\n"
    out += "👉 使用 `00 代码` 生成交易计划（带K线图）"
    await msg.edit_text(out, parse_mode="Markdown")

# ========== 99 深度分析 ==========
async def cmd_99(update, ticker, data):
    personality = random.choice(PERSONALITIES)
    prompt = f"""你是{personality}，20年华尔街经验。

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

要求：敢说真话，200-400字。"""
    try:
        time.sleep(2)
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
            f"预计 {time_horizon} 内股价存在修复机会，但并非强烈反转信号。"
        )

    plan = f"""🎯 *00 交易计划* | {ticker} {data['name']}

💰 价格: ${price}
📈 目标: ${target}（+{profit}%）
📊 趋势: {trend}
⚡ 量比: {data['volume_ratio']:.1f}x
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
    text = update.message.text.strip()
    
    if text == "77":
        await cmd_77(update, context)
        return
    
    match99 = re.match(r'^99\s+([A-Za-z]+)$', text)
    if match99:
        ticker = match99.group(1).upper()
        await update.message.reply_text(f"🔍 正在分析 {ticker}...")
        data = get_stock_data(ticker)
        if not data:
            await update.message.reply_text(f"无法获取 {ticker} 数据")
            return
        await cmd_99(update, ticker, data)
        return
    
    match00 = re.match(r'^00\s+([A-Za-z]+)$', text)
    if match00:
        ticker = match00.group(1).upper()
        await update.message.reply_text(f"🔍 正在生成 {ticker} 交易计划...")
        data = get_stock_data(ticker)
        if not data:
            await update.message.reply_text(f"无法获取 {ticker} 数据")
            return
        await cmd_00(update, ticker, data)
        return

# ========== 主程序 ==========
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("✅ 完整功能版机器人已启动")
    print("77 → 机会扫描")
    print("99 代码 → 深度分析 + K线图")
    print("00 代码 → 交易计划 + K线图")
    app.run_polling()

if __name__ == "__main__":
    main()
