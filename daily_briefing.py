"""
Dean's Daily Briefing v1.0 — 매일 오전 8시 자동 발송
"""
import sys, subprocess
for p in ['yfinance','pandas','feedparser','requests']:
    try: __import__(p)
    except: subprocess.check_call([sys.executable,"-m","pip","install",p,"-q"])

import yfinance as yf
import feedparser
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os, re, warnings
warnings.filterwarnings('ignore')

CONFIG = {
    "sender_email": os.environ.get("SENDER_EMAIL",""),
    "sender_app_password": os.environ.get("GMAIL_APP_PASSWORD",""),
    "recipients": ["timesave7@gmail.com"],
    "gcal_ical_url": os.environ.get("GCAL_ICAL_URL",""),
}
UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ───────────────── 📅 Google Calendar ─────────────────
def fetch_calendar():
    url = CONFIG["gcal_ical_url"]
    if not url:
        return [("[설정필요]","Calendar URL을 등록하면 일정이 표시됩니다","")]
    try:
        r = requests.get(url, headers=UA, timeout=15)
        if r.status_code != 200: return [("-",f"Calendar 접속 실패","")]
        today_s = datetime.now().strftime("%Y%m%d")
        tmrw_s = (datetime.now()+timedelta(days=1)).strftime("%Y%m%d")
        evts = []
        for blk in r.text.split("BEGIN:VEVENT")[1:]:
            summary = location = dtstart = ""
            for ln in blk.split("\n"):
                ln = ln.strip()
                if ln.startswith("SUMMARY:"): summary = ln[8:]
                elif ln.startswith("DTSTART"): m=re.search(r'(\d{8})',ln); dtstart=m.group(1) if m else ""
                elif ln.startswith("LOCATION:"): location = ln[9:]
            if dtstart in [today_s,tmrw_s] and summary:
                tm = re.search(r'T(\d{2})(\d{2})',blk)
                t = f"{tm.group(1)}:{tm.group(2)}" if tm else "종일"
                d = "오늘" if dtstart==today_s else "내일"
                evts.append((f"[{d}] {t}", summary, location))
        return evts if evts else [("-","오늘/내일 예정된 일정 없음","")]
    except Exception as e:
        return [("-",f"오류: {str(e)[:40]}","")]

# ───────────────── 📋 일요일 리마인더 ─────────────────
def get_sunday_reminder():
    if datetime.now().weekday() == 6:  # 0=월, 6=일
        return "🔔 Lawn Mowing 작업 확인 및 송금"
    return ""

# ───────────────── 📰 뉴스 (Google News RSS) ─────────────────
def fetch_rss(query, lang="ko", country="KR", max_items=5, max_hours=24):
    if lang == "ko":
        url = f"https://news.google.com/rss/search?q={query}+when:24h&hl=ko&gl=KR&ceid=KR:ko"
    else:
        url = f"https://news.google.com/rss/search?q={query}+when:{max_hours}h&hl=en&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        items = []
        for e in feed.entries[:max_items]:
            title = re.sub(r'\s*-\s*[^-]+$','',e.get('title',''))  # 출처 제거
            link = e.get('link','')
            source = e.get('source',{}).get('title','')
            items.append({"title":title[:80], "link":link, "source":source})
        return items
    except:
        return []

def fetch_all_news():
    sections = {}
    print("  📰 뉴스 수집 중...")
    sections["🇰🇷 한국 정치/경제"] = fetch_rss("한국 정치 경제", "ko", "KR", 5, 24)
    sections["🇺🇸 미국 정치/경제"] = fetch_rss("US politics economy", "en", "US", 5, 24)
    sections["🤖 IT / AI 동향"] = fetch_rss("AI artificial intelligence technology", "en", "US", 5, 24)
    sections["🏘️ Frisco TX 부동산/개발"] = fetch_rss("Frisco Texas real estate development", "en", "US", 5, 48)
    sections["⚽ 손흥민"] = fetch_rss("손흥민 Son Heung-min", "ko", "KR", 4, 48)
    sections["🏌️ LPGA 한국선수"] = fetch_rss("LPGA Korean player 한국", "en", "US", 4, 48)
    sections["🚗 프리미엄 신차"] = fetch_rss("2026 luxury car new model BMW Mercedes Porsche Genesis", "en", "US", 4, 168)
    for k,v in sections.items():
        print(f"    {k}: {len(v)}건")
    return sections

# ───────────────── 💰 투자 정보 ─────────────────
def fetch_market_data():
    print("  💰 투자 데이터 수집 중...")
    tickers = {
        "QQQ": "QQQ", "TQQQ": "TQQQ", "VOO": "VOO",
        "S&P 500": "^GSPC", "나스닥": "^IXIC", "다우": "^DJI",
        "비트코인": "BTC-USD", "USD/KRW": "KRW=X",
    }
    data = {}
    for name, sym in tickers.items():
        try:
            t = yf.Ticker(sym)
            h = t.history(period="5d")
            if not h.empty:
                price = h['Close'].iloc[-1]
                prev = h['Close'].iloc[-2] if len(h) >= 2 else price
                chg = ((price - prev) / prev) * 100
                data[name] = {"price": price, "change": chg}
        except:
            pass
    print(f"    수집 완료: {len(data)}개 종목")
    return data

# ───────────────── 🎬 유튜브 ─────────────────
YOUTUBE_CHANNELS = {
    "수페TV": "UCsEVa3MpKMfimCJBKgMg0bA",
    "소수몽키": "UCwkRTnlOaX-1l37MrSSTJ6A",
}

def fetch_youtube():
    print("  🎬 유튜브 수집 중...")
    results = {}
    cutoff = datetime.now() - timedelta(hours=48)
    for name, cid in YOUTUBE_CHANNELS.items():
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        try:
            feed = feedparser.parse(url)
            vids = []
            for e in feed.entries[:5]:
                pub = datetime(*e.published_parsed[:6]) if hasattr(e,'published_parsed') and e.published_parsed else None
                if pub and pub < cutoff:
                    continue
                vids.append({"title": e.get('title','')[:70], "link": e.get('link','')})
            results[name] = vids
        except:
            results[name] = []
        print(f"    {name}: {len(results[name])}건")
    return results

# ───────────────── 이메일 HTML 생성 ─────────────────
def build_html(calendar, reminder, news, market, youtube):
    today = datetime.now().strftime("%Y년 %m월 %d일 (%A)")
    weekday_kr = ["월","화","수","목","금","토","일"][datetime.now().weekday()]
    today_kr = datetime.now().strftime(f"%Y년 %m월 %d일 ({weekday_kr})")

    # 리마인더 HTML
    reminder_html = ""
    if reminder:
        reminder_html = f"""
        <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px 16px;
                    border-radius:0 6px 6px 0;margin-bottom:18px;font-size:14px;">
            {reminder}
        </div>"""

    # 캘린더 HTML
    cal_rows = ""
    for time_s, title, loc in calendar:
        loc_str = f" <span style='color:#999;font-size:11px;'>📍{loc}</span>" if loc else ""
        cal_rows += f"""<tr style="border-bottom:1px solid #f0f0f0;">
            <td style="padding:6px 8px;color:#3498db;font-size:12px;white-space:nowrap;width:90px;">{time_s}</td>
            <td style="padding:6px 8px;font-size:13px;">{title}{loc_str}</td></tr>"""

    # 투자 HTML
    def fmt_price(name, d):
        p = d["price"]
        c = d["change"]
        color = "#e74c3c" if c < 0 else "#27ae60"
        arrow = "▼" if c < 0 else "▲"
        if name == "USD/KRW":
            return f"<td style='padding:8px;font-weight:bold;'>{name}</td><td style='padding:8px;text-align:right;font-size:15px;'>₩{p:,.1f}</td><td style='padding:8px;text-align:right;color:{color};font-size:12px;'>{arrow} {abs(c):.2f}%</td>"
        elif name == "비트코인":
            return f"<td style='padding:8px;font-weight:bold;'>{name}</td><td style='padding:8px;text-align:right;font-size:15px;'>${p:,.0f}</td><td style='padding:8px;text-align:right;color:{color};font-size:12px;'>{arrow} {abs(c):.2f}%</td>"
        else:
            return f"<td style='padding:8px;'>{name}</td><td style='padding:8px;text-align:right;font-size:15px;font-weight:500;'>${p:,.2f}</td><td style='padding:8px;text-align:right;color:{color};font-size:12px;'>{arrow} {abs(c):.2f}%</td>"

    holdings_html = ""
    index_html = ""
    for name in ["QQQ","TQQQ","VOO"]:
        if name in market:
            holdings_html += f"<tr style='border-bottom:1px solid #f0f0f0;'>{fmt_price(name, market[name])}</tr>"
    for name in ["S&P 500","나스닥","다우"]:
        if name in market:
            index_html += f"<tr style='border-bottom:1px solid #f0f0f0;'>{fmt_price(name, market[name])}</tr>"

    fx_crypto_html = ""
    for name in ["USD/KRW","비트코인"]:
        if name in market:
            fx_crypto_html += f"<tr style='border-bottom:1px solid #f0f0f0;'>{fmt_price(name, market[name])}</tr>"

    # 뉴스 섹션 HTML
    def news_section(title, items):
        if not items:
            return f"<h3 style='margin:16px 0 6px;font-size:14px;color:#555;'>{title}</h3><p style='color:#999;font-size:12px;'>관련 뉴스 없음</p>"
        rows = ""
        for item in items:
            src = f" <span style='color:#aaa;font-size:10px;'>— {item['source']}</span>" if item.get('source') else ""
            rows += f"<div style='margin:4px 0;font-size:13px;line-height:1.5;'>• <a href=\"{item['link']}\" style='color:#2c3e50;text-decoration:none;'>{item['title']}</a>{src}</div>"
        return f"<h3 style='margin:16px 0 6px;font-size:14px;color:#555;'>{title}</h3>{rows}"

    all_news_html = ""
    for section_title, items in news.items():
        all_news_html += news_section(section_title, items)

    # 유튜브 HTML
    yt_html = ""
    for ch_name, vids in youtube.items():
        if vids:
            yt_html += f"<h4 style='margin:12px 0 4px;font-size:13px;color:#555;'>{ch_name}</h4>"
            for v in vids:
                yt_html += f"<div style='margin:3px 0;font-size:13px;'>▶ <a href=\"{v['link']}\" style='color:#e74c3c;text-decoration:none;'>{v['title']}</a></div>"
        else:
            yt_html += f"<h4 style='margin:12px 0 4px;font-size:13px;color:#555;'>{ch_name}</h4><p style='color:#999;font-size:12px;'>최근 48시간 내 새 영상 없음</p>"

    # 전체 조립
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             max-width:680px;margin:0 auto;padding:16px;background:#f5f5f5;">

<div style="background:linear-gradient(135deg,#0f2027,#203a43,#2c5364);color:white;
            padding:22px 26px;border-radius:10px 10px 0 0;">
    <h1 style="margin:0;font-size:20px;">☀️ Dean's Daily Briefing</h1>
    <p style="margin:6px 0 0;opacity:0.85;font-size:13px;">{today_kr}</p>
</div>

<div style="background:white;padding:20px 26px;border-radius:0 0 10px 10px;
            box-shadow:0 2px 10px rgba(0,0,0,0.1);">

    {reminder_html}

    <!-- 📅 일정 -->
    <h2 style="margin:0 0 10px;font-size:16px;color:#2c3e50;">📅 오늘의 일정</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">{cal_rows}</table>

    <!-- 💰 투자 -->
    <h2 style="margin:0 0 10px;font-size:16px;color:#2c3e50;">💰 투자 현황</h2>

    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">환율 / 크립토</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">{fx_crypto_html}</table>

    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">보유 종목</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">{holdings_html}</table>

    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">주요 지수</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">{index_html}</table>

    <!-- 📰 뉴스 -->
    <h2 style="margin:0 0 6px;font-size:16px;color:#2c3e50;">📰 뉴스</h2>
    {all_news_html}

    <!-- 🎬 유튜브 -->
    <h2 style="margin:20px 0 6px;font-size:16px;color:#2c3e50;">🎬 유튜브 신규 영상</h2>
    {yt_html}

    <hr style="border:none;border-top:1px solid #eee;margin:20px 0 12px;">
    <p style="color:#aaa;font-size:10px;text-align:center;">
        Dean's Daily Briefing v1.0 | 매일 오전 8시 자동 발송 | GitHub Actions
    </p>
</div>
</body></html>"""
    return html

# ───────────────── 이메일 발송 ─────────────────
def send_email(html):
    sender = CONFIG["sender_email"]
    pw = CONFIG["sender_app_password"]
    if not pw:
        fname = f"briefing_{datetime.now().strftime('%Y%m%d')}.html"
        with open(fname,"w",encoding="utf-8") as f: f.write(html)
        print(f"  ⚠️ 이메일 미설정 → {fname} 저장")
        return

    weekday_kr = ["월","화","수","목","금","토","일"][datetime.now().weekday()]
    subject = f"[Daily Briefing] {datetime.now().strftime(f'%m/%d ({weekday_kr})')}"

    for to in CONFIG["recipients"]:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to
            msg.attach(MIMEText(html,"html","utf-8"))
            with smtplib.SMTP_SSL("smtp.gmail.com",465) as s:
                s.login(sender,pw)
                s.sendmail(sender,to,msg.as_string())
            print(f"  ✉️ 발송 → {to}")
        except Exception as e:
            print(f"  ❌ 실패 ({to}): {e}")

# ───────────────── 메인 ─────────────────
def main():
    print("="*55)
    print(f"  ☀️ Daily Briefing - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*55)

    print("\n🔎 데이터 수집 중...")
    calendar = fetch_calendar()
    reminder = get_sunday_reminder()
    news = fetch_all_news()
    market = fetch_market_data()
    youtube = fetch_youtube()

    print("\n📧 이메일 생성 중...")
    html = build_html(calendar, reminder, news, market, youtube)
    send_email(html)

    print(f"\n✅ 완료! ({datetime.now().strftime('%H:%M')})")

if __name__ == "__main__":
    main()
