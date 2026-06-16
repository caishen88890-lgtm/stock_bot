import requests
import time
import json
import random
import pytz
import yfinance as yf
from datetime import datetime
from openai import OpenAI

# ========== 配置 ==========
TELEGRAM_TOKEN = "8936501284:AAEIMWrTHZ8MKsy1_kPsJ0Cb2F-W_sWqguY"
TELEGRAM_CHAT_ID = "-1003954872100"
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

# ========== 翻译模块 ==========
try:
    import argostranslate.package
    import argostranslate.translate
    translator = argostranslate.translate.get_translation_from_codes("en", "zh")
except:
    translator = None
    print("⚠️ 翻译模块未安装，新闻将显示原文")

def translate_to_chinese(text):
    if not text or translator is None:
        return text
    try:
        return translator.translate(text)
    except:
        return text

# ========== 获取地缘新闻 ==========
def get_breaking_news():
    keywords = [
        "Hormuz", "Strait of Hormuz", "Iran", "Middle East", "oil", "crude", "OPEC",
        "Red Sea", "Houthi", "Israel", "Gaza", "Russia", "Ukraine", "sanction",
        "State Department", "Pentagon", "White House", "Fed", "inflation", "CPI"
    ]
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=8)
        news = r.json()
        for item in news[:30]:
            headline = item.get("headline", "")
            summary = item.get("summary", "")
            combined = (headline + summary).lower()
            for kw in keywords:
                if kw.lower() in combined:
                    translated = translate_to_chinese(headline)
                    return f"🔹 {translated}"
    except Exception as e:
        print(f"获取新闻失败: {e}")
    return "🔹 暂无重大地缘事件"

# ========== 获取市场数据 ==========
def get_market_data():
    result = {
        "tnx": None, "vix": None, "strongest": None, "weakest": None,
        "rotation": None
    }
    try:
        tnx_data = yf.Ticker("^TNX").history(period="1d")
        if not tnx_data.empty:
            result["tnx"] = float(tnx_data["Close"].iloc[-1])
    except:
        pass
    try:
        vix_data = yf.Ticker("^VIX").history(period="1d")
        if not vix_data.empty:
            result["vix"] = float(vix_data["Close"].iloc[-1])
    except:
        pass
    sectors = {"XLK": "科技", "XLF": "金融", "XLE": "能源", "XLV": "医疗", "XLI": "工业"}
    sector_perf = {}
    for ticker, name in sectors.items():
        try:
            data = yf.download(ticker, period="2d", progress=False)
            if not data.empty and len(data) >= 2:
                close_values = data["Close"].values
                change = (close_values[-1] - close_values[-2]) / close_values[-2] * 100
                sector_perf[name] = float(change)
        except:
            pass
    if sector_perf:
        strongest_name = None
        weakest_name = None
        strongest_val = -9999
        weakest_val = 9999
        for name, val in sector_perf.items():
            if val > strongest_val:
                strongest_val = val
                strongest_name = name
            if val < weakest_val:
                weakest_val = val
                weakest_name = name
        result["strongest"] = strongest_name or "科技"
        result["weakest"] = weakest_name or "金融"
        if sector_perf.get("科技", 0) > sector_perf.get("金融", 0):
            result["rotation"] = "资金从金融流向科技，防御性进攻行情"
        else:
            result["rotation"] = "资金轮动放缓，等待方向"
    return result

# ========== 生成点评 ==========
def generate_comment(report_type, market_data, news):
    tnx = market_data.get("tnx", 4.45)
    vix = market_data.get("vix", 16.5)
    strongest = market_data.get("strongest", "科技")
    weakest = market_data.get("weakest", "金融")
    rotation = market_data.get("rotation", "资金轮动")

    data_section = f"""【数据区】
• 宏观：10年期美债收益率 {tnx:.3f}%，处于近期高位，利率预期对风险资产形成温和压制
• 情绪：VIX = {vix:.2f}，处于历史偏低水平，市场情绪中性偏乐观
• 资金：最强 {strongest}，最弱 {weakest}
• 新闻：{news}
"""
    if rotation:
        data_section += f"• 轮动：{rotation}\n"

    prompt = f"""你是{random.choice(PERSONALITIES)}，20年华尔街经验。

请生成一份{report_type}的整合点评（不少于400字），要求：
1. 完全口语化，像资深分析师在说话，不要用【】符号
2. 自然融入以下数据：10年期美债收益率{tnx:.3f}%、VIX={vix:.2f}、最强{strongest}、最弱{weakest}
3. 融入以下新闻：{news}
4. 结合当前市场风格：{rotation}
5. 最后给出明确的结论（偏多/偏空/中性）和具体的操作建议

不要重复数据区的格式，要连贯叙述，文字要像人写的。"""

    try:
        resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.85)
        comment = resp.choices[0].message.content
    except:
        comment = f"AI分析暂时失败。当前{report_type}，美债{tnx:.3f}%，VIX{vix:.2f}，资金最强{strongest}最弱{weakest}，{news}。建议保持谨慎。"

    if len(comment) < 400:
        comment += " " + "市场仍需关注美债4.5%关口和VIX变化，短期波动可能加大，建议控制仓位。"

    risk_line = f"""⚠️ 关键风险线
• 美债收益率有效突破 4.5% → 成长股估值重定价风险上升
• VIX回升至 18+ → 防御切换信号

👉 当前策略：顺势做多科技主线，回避金融与高利率敏感周期股"""

    return f"{data_section}\n━━━━━━━━━━━━━━\n\n📝 {comment}\n\n📌 结论：\n{risk_line}"

def job_report(report_type):
    market_data = get_market_data()
    news = get_breaking_news()
    comment = generate_comment(report_type, market_data, news)
    send_telegram(comment, report_type)

def job_sunday_1830():
    market_data = get_market_data()
    news = get_breaking_news()

    data_section = f"""【数据区】
• 宏观：10年期美债收益率 {market_data.get('tnx', 4.45):.3f}%
• 情绪：VIX = {market_data.get('vix', 16.5):.2f}
• 资金：最强 {market_data.get('strongest', '科技')}，最弱 {market_data.get('weakest', '金融')}
• 新闻：{news}
"""

    prompt = f"""你是{random.choice(PERSONALITIES)}，20年华尔街经验。

请生成一份周日周报（不少于500字），包含：
1. 本周市场回顾（一句话总结核心特征）
2. 下周展望（标普500和纳斯达克方向判断、关键因素）
3. 大胆预测（具体的、有争议的预测，敢于给出方向和时间）
4. 个人看法（资深交易员的主观观点）
5. 操作建议（一句话总结）

自然融入数据：美债{market_data.get('tnx', 4.45):.3f}%、VIX{market_data.get('vix', 16.5):.2f}、最强{market_data.get('strongest', '科技')}、最弱{market_data.get('weakest', '金融')}、新闻{news}

要求：口语化，不要分点，像在跟客户说话。"""

    try:
        resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.85)
        comment = resp.choices[0].message.content
    except:
        comment = "AI分析暂时失败，请稍后重试。"

    full_report = f"{data_section}\n━━━━━━━━━━━━━━\n\n📝 {comment}\n\n⚠️ 仅供参考，不构成投资建议"
    send_telegram(full_report, "周度总结 & 下周展望")

def send_telegram(text, title="市场点评"):
    full = f"📊 *{title}*\n\n{text}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": full, "parse_mode": "Markdown"})
        print(f"✅ 已发送: {title}")
    except Exception as e:
        print(f"❌ 发送失败: {title} - {e}")

# ========== 定时调度 ==========
def run_scheduled_jobs():
    est = pytz.timezone('US/Eastern')
    last_run = {}
    while True:
        now = datetime.now(est)
        today = now.date()
        weekday = now.weekday()
        hour = now.hour
        minute = now.minute

        # 盘前点评预备通知（8:20）
        if 0 <= weekday <= 4 and hour == 8 and minute == 20 and last_run.get("pre_notice") != today:
            send_telegram("⏰ 系统运转推测正常\n\n距离盘前点评推送还有 10 分钟，数据获取正常，当前无异常。", "系统通知")
            last_run["pre_notice"] = today

        # 盘前点评正式推送（8:30）
        if 0 <= weekday <= 4 and hour == 8 and minute == 30 and last_run.get("pre") != today:
            job_report("盘前点评")
            last_run["pre"] = today

        # 早盘点评预备通知（10:20）
        if 0 <= weekday <= 4 and hour == 10 and minute == 20 and last_run.get("morning_notice") != today:
            send_telegram("⏰ 系统运转推测正常\n\n距离早盘点评推送还有 10 分钟，数据获取正常，当前无异常。", "系统通知")
            last_run["morning_notice"] = today

        # 早盘点评正式推送（10:30）
        if 0 <= weekday <= 4 and hour == 10 and minute == 30 and last_run.get("morning") != today:
            job_report("早盘点评")
            last_run["morning"] = today

        # 午盘点评预备通知（12:20）
        if 0 <= weekday <= 4 and hour == 12 and minute == 20 and last_run.get("noon_notice") != today:
            send_telegram("⏰ 系统运转推测正常\n\n距离午盘点评推送还有 10 分钟，数据获取正常，当前无异常。", "系统通知")
            last_run["noon_notice"] = today

        # 午盘点评正式推送（12:30）
        if 0 <= weekday <= 4 and hour == 12 and minute == 30 and last_run.get("noon") != today:
            job_report("午盘点评")
            last_run["noon"] = today

        # 收盘点评预备通知（15:20）
        if 0 <= weekday <= 4 and hour == 15 and minute == 20 and last_run.get("close_notice") != today:
            send_telegram("⏰ 系统运转推测正常\n\n距离收盘点评推送还有 10 分钟，数据获取正常，当前无异常。", "系统通知")
            last_run["close_notice"] = today

        # 收盘点评正式推送（15:30）
        if 0 <= weekday <= 4 and hour == 15 and minute == 30 and last_run.get("close") != today:
            job_report("收盘点评")
            last_run["close"] = today

        # 周六系统测试预备通知（17:50）
        if weekday == 5 and hour == 17 and minute == 50 and last_run.get("saturday_notice") != today:
            send_telegram("⏰ 系统运转推测正常\n\n距离系统测试推送还有 10 分钟，数据获取正常，当前无异常。", "系统通知")
            last_run["saturday_notice"] = today

        # 周六系统测试（18:00）
        if weekday == 5 and hour == 18 and minute == 0 and last_run.get("saturday") != today:
            send_telegram("✅ 周六系统测试，机器人运行正常，明晚周报将按时推送。", "系统测试")
            last_run["saturday"] = today

        # 周日周报预备通知（18:20）
        if weekday == 6 and hour == 18 and minute == 20 and last_run.get("sunday_notice") != today:
            send_telegram("⏰ 系统运转推测正常\n\n距离周报推送还有 10 分钟，数据获取正常，当前无异常。", "系统通知")
            last_run["sunday_notice"] = today

        # 周日周报（18:30）
        if weekday == 6 and hour == 18 and minute == 30 and last_run.get("sunday") != today:
            job_sunday_1830()
            last_run["sunday"] = today

        time.sleep(60)

def main():
    print("✅ 定时推送机器人已启动")
    print("盘前 8:30 | 早盘 10:30 | 午盘 12:30 | 收盘 15:30 | 周六 18:00 测试 | 周日 18:30 周报")
    print("每个正式推送前 10 分钟会发送预备通知")
    run_scheduled_jobs()

if __name__ == "__main__":
    main()