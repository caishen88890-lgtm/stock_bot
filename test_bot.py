import yfinance as yf
import argostranslate.package
import argostranslate.translate
import requests
import random
import re
import mplfinance as mpf
import pandas as pd
import tempfile
import json
import os
import time
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import pytz

# ========== 美国东部时区 ==========
US_EASTERN = pytz.timezone('America/New_York')

def get_us_date():
    return datetime.now(US_EASTERN).strftime("%Y-%m-%d")

def get_us_datetime():
    return datetime.now(US_EASTERN)

# ========== 翻译模块 ==========
try:
    translator = argostranslate.translate.get_translation_from_codes("en", "zh")
except:
    argostranslate.package.update_package_index()
    available_packages = argostranslate.package.get_available_packages()
    package_to_install = next(
        filter(lambda x: x.from_code == "en" and x.to_code == "zh", available_packages)
    )
    argostranslate.package.install_from_path(package_to_install.download())
    translator = argostranslate.translate.get_translation_from_codes("en", "zh")

def translate_to_chinese(text):
    if not text:
        return ""
    try:
        return translator.translate(text)
    except:
        return text

# ========== 配置 ==========
TELEGRAM_TOKEN = "8307944671:AAHb3uHL68HTOFYjqTg1F_jZx-AhpZwughg"
TELEGRAM_CHAT_ID = "1003906407266"
TIANYU_API_KEY = "sk-40ZnhDFlBQXfBMqpUjylHjr6BdY9CzbtbFDELHvrp4YjKqTQ"
TIANYU_BASE_URL = "https://tianyuai.lol/v1"
NEWS_API_KEY = "e7c5feb8a5aa48ad9636d5d0541df238"

client = OpenAI(api_key=TIANYU_API_KEY, base_url=TIANYU_BASE_URL)

# ========== 推荐历史记录 ==========
HISTORY_FILE_77 = "stock_history_77_new.json"
PURCHASED_FILE = "purchased_history_new.json"
CACHE_FILE_77 = "daily_recommendation_cache_new.json"

if os.path.exists(HISTORY_FILE_77):
    with open(HISTORY_FILE_77, "r") as f:
        stock_history_77 = json.load(f)
else:
    stock_history_77 = []

def save_history_77():
    with open(HISTORY_FILE_77, "w") as f:
        json.dump(stock_history_77[-200:], f)

if os.path.exists(PURCHASED_FILE):
    with open(PURCHASED_FILE, "r") as f:
        purchased_history = json.load(f)
else:
    purchased_history = []

def save_purchased():
    with open(PURCHASED_FILE, "w") as f:
        json.dump(purchased_history[-200:], f)

def get_today_recommendation():
    today = get_us_date()
    if os.path.exists(CACHE_FILE_77):
        with open(CACHE_FILE_77, "r") as f:
            cache = json.load(f)
            if cache.get("date") == today:
                return cache.get("result")
    return None

def save_today_recommendation(result_text):
    today = get_us_date()
    with open(CACHE_FILE_77, "w") as f:
        json.dump({"date": today, "result": result_text}, f)

def was_purchased_recently(ticker, days=7):
    cutoff = (get_us_datetime() - timedelta(days=days)).strftime("%Y-%m-%d")
    for rec in purchased_history[-50:]:
        if rec["ticker"] == ticker and rec["date"] >= cutoff:
            return True
    return False

def was_just_recommended(ticker, days=2):
    cutoff = (get_us_datetime() - timedelta(days=days)).strftime("%Y-%m-%d")
    for rec in stock_history_77[-100:]:
        if rec["ticker"] == ticker and rec["date"] >= cutoff:
            return True
    return False

def is_eligible_for_recommendation(ticker):
    if was_purchased_recently(ticker, days=7):
        return False
    if was_just_recommended(ticker, days=2):
        return False
    return True

PERSONALITIES = [
    "技术面狙击手", "宏观对冲策略师", "价值捕手", "动量交易员",
    "波动率专家", "行为金融学家", "量化因子分析师", "财报猎手",
    "地缘政治分析师", "散户情绪观察员", "美联储喉舌", "行业轮动专家",
    "破产清算师", "股东回报策略师", "ESG整合师", "全球宏观交易员",
    "事件驱动投机者", "流动性猎人", "保罗·都铎·琼斯派", "雷·达里奥原则派"
]

NAME_TO_TICKER = {
    "英伟达": "NVDA", "nvidia": "NVDA", "NVDA": "NVDA",
    "特斯拉": "TSLA", "tesla": "TSLA", "TSLA": "TSLA",
    "苹果": "AAPL", "apple": "AAPL", "AAPL": "AAPL",
    "优步": "UBER", "uber": "UBER", "UBER": "UBER",
}

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return None
        info = stock.info
        price = hist["Close"].iloc[-1]
        open_price = hist["Open"].iloc[-1]
        change = (price - open_price) / open_price * 100
        volume = hist["Volume"].iloc[-1]
        avg_volume = hist["Volume"].mean()
        vol_ratio = volume / avg_volume if avg_volume > 0 else 1
        week_low = info.get("fiftyTwoWeekLow", price * 0.8)
        week_high = info.get("fiftyTwoWeekHigh", price * 1.2)
        week_pos = (price - week_low) / (week_high - week_low) * 100
        return {
            "name": info.get("longName", ticker),
            "price": round(price, 2),
            "change": round(change, 2),
            "vol_ratio": round(vol_ratio, 1),
            "week_pos": round(week_pos, 1),
            "pe": info.get("trailingPE", "N/A"),
            "market_cap": info.get("marketCap", 0),
            "sector": info.get("sector", "科技"),
            "volume": volume
        }
    except:
        return None

def search_news(query):
    try:
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}&language=en&sortBy=publishedAt&pageSize=5"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("status") != "ok":
            return []
        articles = data.get("articles", [])
        res = []
        for a in articles:
            res.append({
                "title": translate_to_chinese(a["title"]),
                "link": a["url"],
                "summary": translate_to_chinese(a["description"] or a["title"])[:200]
            })
        return res
    except:
        return []

def news_sentiment(news_list):
    if not news_list:
        return None
    pos_kw = ["上涨", "新高", "超预期", "利好", "批准", "合作"]
    neg_kw = ["下跌", "调查", "诉讼", "下调", "延迟", "停产"]
    pos = neg = 0
    for n in news_list[:5]:
        t = n['title']
        if any(k in t for k in pos_kw):
            pos += 1
        if any(k in t for k in neg_kw):
            neg += 1
    return "利多" if pos > neg else "利空" if neg > pos else None

def generate_chart(ticker):
    try:
        df = yf.download(ticker, period="60d", interval="1d", progress=False)
        if df.empty:
            return None
        df = df.dropna()
        if len(df) < 10:
            return None
        df.index = pd.to_datetime(df.index)
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        apds = [
            mpf.make_addplot(df['MA5'], color='blue', width=1),
            mpf.make_addplot(df['MA20'], color='orange', width=1)
        ]
        mpf.plot(df[['Close']], type='line', addplot=apds,
                 title=f'{ticker} - 60日收盘价与均线',
                 savefig=temp_file.name, figsize=(10, 5))
        return temp_file.name
    except:
        return None

async def trigger_99(update, ticker, stock_data):
    personality = random.choice(PERSONALITIES)
    news = search_news(ticker)
    sentiment = news_sentiment(news)
    sentiment_text = f"近期新闻情绪偏向 {sentiment}。" if sentiment else ""
    prompt = f"""
你是顶级华尔街分析师，角色「{personality}」。

实时数据：
{ticker} ({stock_data['name']})
价格: ${stock_data['price']} {'🟢' if stock_data['change']>0 else '🔴'} {stock_data['change']:+.2f}%
成交量: {stock_data['vol_ratio']}x均量
52周位置: {stock_data['week_pos']}%

{sentiment_text}

请按以下格式输出（200字以内）：

【核心判断】明确写 利多/利空/中性
【观点逻辑】一针见血
【短期预测】未来1~3天涨跌方向 + 幅度（±5%～±8%）
【风险坦白】这个判断最可能错在哪里
【一句话策略】买/卖/等/减仓/加仓
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85
        )
        comment = resp.choices[0].message.content
    except Exception as e:
        comment = f"AI分析失败: {str(e)[:50]}"
    response = f"""📊 {ticker} {stock_data['name']}

价格: ${stock_data['price']} {'🟢' if stock_data['change']>0 else '🔴'} {stock_data['change']:+.2f}%
趋势评分: {stock_data['vol_ratio']}/100

🎭 分析师: {personality}

{comment}"""
    await update.message.reply_text(response, parse_mode="Markdown")

async def trigger_00(update, ticker, stock_data):
    price = stock_data['price']
    target = round(price * 1.09, 2)
    profit_pct = round((target - price) / price * 100, 1)
    change = stock_data['change']
    if change > 1:
        trend = "股价稳步上涨，成交量配合良好，资金关注度提升"
    elif change > 0:
        trend = "股价小幅收涨，走势稳健，市场情绪偏暖"
    elif change > -1:
        trend = "股价窄幅震荡，多空平衡，等待方向选择"
    else:
        trend = "股价短期回调，关注支撑位有效性"
    sector = stock_data.get('sector', '科技')
    business = f"{stock_data['name']} 是{sector}行业的领先企业"
    response = f"""🎯 *今日精选股票（{get_us_datetime().strftime('%Y-%m-%d %H:%M')} 美东）*
🚀 股票名称｜代码：{stock_data['name']}（{ticker}）
📂 股票板块：{sector}
💰 购买价格：{price} 美元
📍 目标售出价格：{target} 美元
💵 预期利润占比：约{profit_pct}%
⏳ 持有时间：1-15天
📈 当天趋势：
{trend}

📊 公司市值：约{stock_data['market_cap']/1e9:.1f}亿美元
📉 市盈率（PE）：约{stock_data['pe']}倍
📈 今日成交量：约{stock_data['volume']/1e6:.1f}万股

🔍 *公司核心业务*
{business}，业务覆盖全球多个市场，具有较强竞争优势。

⚠️ 仅供参考，不构成投资建议"""
    await update.message.reply_text(response, parse_mode="Markdown")

FALLBACK_TICKERS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL", "NFLX", "UBER",
    "INTC", "PLTR", "SOFI", "SNAP", "TWLO", "ZM", "JD", "BABA", "PDD",
    "AAL", "DAL", "UAL", "CCL", "DIS", "GE", "CAT", "BA", "WMT", "COST"
]

def get_reliable_candidates():
    results = []
    for t in FALLBACK_TICKERS:
        try:
            data = yf.Ticker(t).history(period="5d")
            if data.empty or len(data) < 2:
                continue
            price = data["Close"].iloc[-1]
            if price < 10 or price > 100:
                continue
            change_1d = (data["Close"].iloc[-1] - data["Open"].iloc[-1]) / data["Open"].iloc[-1] * 100
            change_5d = (data["Close"].iloc[-1] - data["Close"].iloc[0]) / data["Close"].iloc[0] * 100 if len(data) >= 5 else 0
            vol_ratio = data["Volume"].iloc[-1] / (data["Volume"].mean() or 1)
            volatility = data["Close"].pct_change().std() * 100
            if is_eligible_for_recommendation(t):
                try:
                    info_simple = yf.Ticker(t).info
                    sector = info_simple.get("sector", "其他")
                except:
                    sector = "其他"
                results.append({
                    "ticker": t,
                    "sector": sector or "—",
                    "price": price,
                    "change_1d": change_1d,
                    "change_5d": change_5d,
                    "vol_ratio": vol_ratio,
                    "volatility": volatility
                })
            time.sleep(0.2)
        except:
            continue
    return results

async def trigger_77(update, force_refresh=False):
    today = get_us_date()
    if not force_refresh:
        cached = get_today_recommendation()
        if cached:
            await update.message.reply_text(
                f"📋 今日推荐（{today} 美东）已存在，直接返回缓存结果。\n如需重新筛选，请发送「111+ 重新推荐」\n\n{cached}",
                parse_mode="Markdown"
            )
            return
    msg = await update.message.reply_text("🔍 正在筛选优质股票...\n⏳ 数据获取约需1-2分钟，请耐心等待")
    candidates = get_reliable_candidates()
    if not candidates:
        await msg.edit_text("❌ 暂未筛选到合适股票，请稍后重试")
        return
    qiangshi = sorted(candidates, key=lambda x: (x["change_1d"] + x["vol_ratio"]), reverse=True)[:8]
    chaodie = sorted(candidates, key=lambda x: x["change_5d"])[:8]
    hengpan = sorted(candidates, key=lambda x: x["volatility"])[:8]
    selected = []
    for s in qiangshi:
        if s not in selected:
            selected.append(s)
    for s in chaodie:
        if s not in selected and len(selected) < 15:
            selected.append(s)
    for s in hengpan:
        if s not in selected and len(selected) < 15:
            selected.append(s)
    selected = selected[:15]
    today = get_us_date()
    for s in selected:
        stock_history_77.append({"ticker": s["ticker"], "date": today})
    save_history_77()
    date_str = get_us_datetime().strftime("%Y-%m-%d %H:%M EST")
    output = f"📊 个股机会\n\n🎯 *今日选股推荐（{date_str}）*\n筛选条件：价格 $10~$100\n\n"
    for idx, s in enumerate(selected, 1):
        arrow = "▲" if s["change_1d"] >= 0 else "▼"
        week_low = s["price"] * 0.7
        week_high = s["price"] * 1.3
        pos = (s["price"] - week_low) / (week_high - week_low) * 100
        tag = "趋势向好" if s["change_1d"] > 1 else "等待企稳" if s["change_1d"] < -1 else "小幅波动"
        output += f"{idx:02d} *{s['ticker']}* · {s['sector']}\n"
        output += f"   价格 ${s['price']:.2f}  {arrow}{s['change_1d']:+.2f}%\n"
        output += f"   成交量 {s['vol_ratio']:.1f}x  52周位置 {pos:.0f}%\n"
        output += f"   📌 {tag}\n\n"
    output += "\n💡 买入后请发送 /buy 股票代码（如 /buy NVDA），该股票7天内不会重复推荐\n"
    output += "⚠️ 仅供参考，不构成投资建议\n\n"
    output += "📌 强制重新推荐请发送「111+ 重新推荐」"
    save_today_recommendation(output)
    await update.message.reply_text(output, parse_mode="Markdown")

async def start(update, context):
    await update.message.reply_text(
        "📊 解票机器人（完整版）\n\n"
        "• 发送「111+」获取批量选股推荐\n"
        "• 发送「111+ 重新推荐」强制重新筛选\n"
        "• 发送「222 股票代码」获取技术面解票（AI+新闻+人格）\n"
        "• 发送「333 股票代码」获取基本面精选票\n"
        "• 发送「/buy 股票代码」记录买入（锁7天不推荐）\n\n"
        "示例：\n111+\n111+ 重新推荐\n222 NVDA\n333 UBER\n/buy NVDA"
    )

async def handle_message(update, context):
    if update.message.text is None:
        return
    text = update.message.text.strip()
    
    match_buy = re.match(r'^/buy\s+([A-Za-z]+)$', text)
    if match_buy:
        ticker = match_buy.group(1).upper()
        today = get_us_date()
        purchased_history.append({"ticker": ticker, "date": today})
        save_purchased()
        await update.message.reply_text(f"✅ 已记录买入 {ticker}（美国时间 {today}），7天内不会重复推荐")
        return
    
    if text == "111+ 重新推荐" or text == "111+ -f" or text == "111+ 刷新":
        await trigger_77(update, force_refresh=True)
        return
    if text == "111+":
        await trigger_77(update, force_refresh=False)
        return
    
    match99 = re.match(r'^222\s+([A-Za-z]+)$', text)
    if match99:
        ticker = match99.group(1).upper()
        if ticker in NAME_TO_TICKER:
            ticker = NAME_TO_TICKER[ticker]
        await update.message.reply_text(f"🔍 技术面解票 {ticker} 中...")
        stock_data = get_stock_data(ticker)
        if not stock_data:
            await update.message.reply_text(f"无法获取 {ticker} 数据")
            return
        await trigger_99(update, ticker, stock_data)
        return
    
    match00 = re.match(r'^333\s+([A-Za-z]+)$', text)
    if match00:
        ticker = match00.group(1).upper()
        if ticker in NAME_TO_TICKER:
            ticker = NAME_TO_TICKER[ticker]
        await update.message.reply_text(f"🔍 基本面分析 {ticker} 中...")
        stock_data = get_stock_data(ticker)
        if not stock_data:
            await update.message.reply_text(f"无法获取 {ticker} 数据")
            return
        await trigger_00(update, ticker, stock_data)
        return

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ 解票机器人已启动（111+批量 / 222技术 / 333基本面）")
    print(f"📍 当前使用美国东部时间: {get_us_datetime().strftime('%Y-%m-%d %H:%M:%S')}")
    app.run_polling()
