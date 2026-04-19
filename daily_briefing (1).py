"""
Dean's Daily Briefing v3.2 — 매일 오전 8시 자동 발송
v3.2: 보유종목 재편 (QQQI,VYM,VNQ,O,SMCI,SUI,Bitcoin 추가 / USD/KRW 보유종목으로 이동)
v3.1: 정치/경제/국제 → 한겨레,경향,MBC,오마이,조선 / IT → 전자신문 추가
v3.0: 속보,글로벌,증시분석,경제이벤트,스포츠보강,투자키워드확대
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
import os, re, json, warnings
warnings.filterwarnings('ignore')
 
CONFIG = {
    "sender_email": os.environ.get("SENDER_EMAIL",""),
    "sender_app_password": os.environ.get("GMAIL_APP_PASSWORD",""),
    "recipients": ["timesave7@gmail.com","seunggy98@gmail.com"],
    "gcal_ical_url": os.environ.get("GCAL_ICAL_URL",""),
}
UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
 
def fetch_calendar():
    url = CONFIG["gcal_ical_url"]
    if not url:
        return [("[설정필요]","Calendar URL을 등록하면 일정이 표시됩니다","")]
    try:
        r = requests.get(url, headers=UA, timeout=15)
        if r.status_code != 200: return [("-","Calendar 접속 실패","")]
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
 
def get_sunday_reminder():
    if datetime.now().weekday() == 6:
        return "🔔 Lawn Mowing 작업 확인 및 송금"
    return ""
 
# ═══════════════════════════════════════════════════════
# 📰 뉴스 RSS 피드 설정
# 정치/경제/국제: 한겨레, 경향신문, MBC, 오마이뉴스, 조선일보
# IT/AI: 전자신문 + 기존   |  투자: 한경, 매경, 머니투데이
# 부동산: Community Impact, Dallas Morning News
# 자동차: Car and Driver, Motor Trend
# ═══════════════════════════════════════════════════════
 
DIRECT_RSS_FEEDS = {
    "📢 속보 / Breaking News": [
        ("한겨레",     "https://www.hani.co.kr/rss/"),
        ("경향신문",   "https://www.khan.co.kr/rss/rssdata/total_news.xml"),
        ("MBC",       "https://imnews.imbc.com/rss/news/"),
        ("오마이뉴스", "http://www.ohmynews.com/rss/ohmynews.xml"),
        ("조선일보",   "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ],
    "🇰🇷 한국 정치/경제": [
        ("한겨레",     "https://www.hani.co.kr/rss/"),
        ("경향신문",   "https://www.khan.co.kr/rss/rssdata/total_news.xml"),
        ("MBC",       "https://imnews.imbc.com/rss/news/"),
        ("오마이뉴스", "http://www.ohmynews.com/rss/ohmynews.xml"),
        ("조선일보",   "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ],
    "🇺🇸 미국 정치/경제": [
        ("한겨레",     "https://www.hani.co.kr/rss/"),
        ("경향신문",   "https://www.khan.co.kr/rss/rssdata/total_news.xml"),
        ("MBC",       "https://imnews.imbc.com/rss/news/"),
        ("오마이뉴스", "http://www.ohmynews.com/rss/ohmynews.xml"),
        ("조선일보",   "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ],
    "🌍 글로벌 뉴스": [
        ("한겨레",     "https://www.hani.co.kr/rss/"),
        ("경향신문",   "https://www.khan.co.kr/rss/rssdata/total_news.xml"),
        ("MBC",       "https://imnews.imbc.com/rss/news/"),
        ("오마이뉴스", "http://www.ohmynews.com/rss/ohmynews.xml"),
        ("조선일보",   "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ],
    "📊 미국 증시 / 투자 분석": [
        ("한국경제",   "https://www.hankyung.com/feed/all-news"),
        ("매일경제",   "https://www.mk.co.kr/rss/30000001/"),
        ("머니투데이", "https://rss.mt.co.kr/mt/mtview/mt_all.xml"),
        ("연합뉴스",   "https://www.yna.co.kr/rss/news.xml"),
        ("한겨레",     "https://www.hani.co.kr/rss/"),
        ("조선일보",   "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ],
    "🤖 IT / AI 동향": [
        ("전자신문",   "https://rss.etnews.com/Section901.xml"),
        ("한국IT뉴스", "https://akngs.github.io/knews-rss/categories/tech.xml"),
        ("한국경제",   "https://www.hankyung.com/feed/all-news"),
        ("매일경제",   "https://www.mk.co.kr/rss/30000001/"),
    ],
    "🏘️ Frisco TX 부동산/개발": [
        ("Community Impact",    "https://communityimpact.com/feed/"),
        ("Dallas Morning News", "https://www.dallasnews.com/arcio/rss/"),
    ],
    "⚽ 손흥민 / LAFC": [
        ("한국스포츠", "https://akngs.github.io/knews-rss/categories/sports.xml"),
        ("연합뉴스",   "https://www.yna.co.kr/rss/news.xml"),
        ("매일경제",   "https://www.mk.co.kr/rss/30000001/"),
    ],
    "🏌️ PGA / LPGA 한국선수": [
        ("한국스포츠", "https://akngs.github.io/knews-rss/categories/sports.xml"),
        ("연합뉴스",   "https://www.yna.co.kr/rss/news.xml"),
        ("매일경제",   "https://www.mk.co.kr/rss/30000001/"),
    ],
    "🚗 프리미엄 신차": [
        ("Car and Driver", "https://www.caranddriver.com/rss/all.xml/"),
        ("MotorTrend",     "https://www.motortrend.com/feed/"),
    ],
}
 
SECTION_KEYWORDS = {
    "📢 속보 / Breaking News": ["속보","긴급","breaking","사망","지진","전쟁","탄핵","계엄","비상","테러","폭발","총격","대통령"],
    "🇰🇷 한국 정치/경제": None,
    "🇺🇸 미국 정치/경제": ["미국","트럼프","바이든","워싱턴","백악관","연준","fed","달러","월가","wall","us","america","관세","무역","의회","상원","하원","국무"],
    "🌍 글로벌 뉴스": ["중국","일본","러시아","우크라이나","유럽","eu","nato","중동","이란","이스라엘","대만","인도","영국","프랑스","독일","un","유엔","g7","g20","opec","아프리카","남미","북한","핵"],
    "📊 미국 증시 / 투자 분석": [
        "증시","주가","나스닥","nasdaq","s&p","다우","dow","코스피","코스닥","선물","옵션",
        "금리","기준금리","인플레","cpi","ppi","고용","실업","비농업","fomc","연준","fed","파월","powell","금리인하","금리인상","국채","채권","환율","달러","원화","엔화",
        "엔비디아","nvidia","애플","apple","테슬라","tesla","마이크로소프트","아마존","구글","메타","반도체","ai","매그니피센트","빅테크","실적","어닝","분기",
        "etf","qqq","tqqq","voo","spy","배당","매수","매도","공매도","투자","펀드","자산","포트폴리오",
        "비트코인","bitcoin","이더리움","코인","금값","유가","원유","wti",
        "gdp","소비자물가","생산자물가","소매판매","ism","pmi","무역수지","경상수지",
    ],
    "🤖 IT / AI 동향": ["ai","인공지능","로봇","자율주행","스마트","반도체","칩","gpu","테슬라","엔비디아","삼성전자","애플","구글","챗gpt","클로드","llm","생성형","오픈ai","openai","딥러닝","머신러닝"],
    "🏘️ Frisco TX 부동산/개발": ["frisco","texas","tx","real estate","부동산","개발","plano","mckinney","dfw","dallas"],
    "⚽ 손흥민 / LAFC": ["손흥민","son heung","lafc","los angeles fc","mls","축구","football","soccer","토트넘","tottenham","spurs","premier","k리그","이강인","김민재","황희찬"],
    "🏌️ PGA / LPGA 한국선수": ["lpga","pga","골프","golf","한국","korea","korean","고진영","ko jin","김효주","전인지","양희영","이민지","임성재","김시우","김주형","안병훈","이경훈","tom kim","masters","open","championship","tour"],
    "🚗 프리미엄 신차": ["bmw","mercedes","porsche","genesis","audi","2026","2027","luxury","new model","electric"],
}
 
SECTION_CONFIG = {
    "📢 속보 / Breaking News":    {"max_hours": 12, "max_items": 5},
    "🇰🇷 한국 정치/경제":          {"max_hours": 24, "max_items": 5},
    "🇺🇸 미국 정치/경제":          {"max_hours": 24, "max_items": 5},
    "🌍 글로벌 뉴스":              {"max_hours": 24, "max_items": 5},
    "📊 미국 증시 / 투자 분석":     {"max_hours": 24, "max_items": 7},
    "🤖 IT / AI 동향":            {"max_hours": 24, "max_items": 5},
    "🏘️ Frisco TX 부동산/개발":    {"max_hours": 48, "max_items": 3},
    "⚽ 손흥민 / LAFC":            {"max_hours": 48, "max_items": 5},
    "🏌️ PGA / LPGA 한국선수":     {"max_hours": 48, "max_items": 5},
    "🚗 프리미엄 신차":            {"max_hours": 168, "max_items": 3},
}
 
def fetch_direct_rss(feed_url, source_name, max_items=5, max_hours=48):
    try:
        feed = feedparser.parse(feed_url, request_headers=UA)
        if not feed.entries: return []
        cutoff = datetime.now() - timedelta(hours=max_hours)
        items = []
        for e in feed.entries[:max_items*3]:
            pub = None
            if hasattr(e,'published_parsed') and e.published_parsed:
                try: pub = datetime(*e.published_parsed[:6])
                except: pass
            elif hasattr(e,'updated_parsed') and e.updated_parsed:
                try: pub = datetime(*e.updated_parsed[:6])
                except: pass
            if pub and pub < cutoff: continue
            title = e.get('title','').strip()
            if not title: continue
            title = re.sub(r'\s*-\s*[^-]{0,30}$','',title)
            link = e.get('link','')
            items.append({"title": title[:80], "link": link, "source": source_name})
            if len(items) >= max_items: break
        return items
    except Exception as ex:
        print(f"      ⚠️ {source_name} RSS 오류: {str(ex)[:50]}")
        return []
 
def keyword_filter(items, keywords):
    if keywords is None: return items
    return [i for i in items if any(kw in i["title"].lower() for kw in keywords)]
 
def fetch_all_news():
    sections = {}
    print("  📰 뉴스 수집 중 (직접 RSS)...")
    for section_name, feeds in DIRECT_RSS_FEEDS.items():
        all_items = []
        cfg = SECTION_CONFIG.get(section_name, {"max_hours":48,"max_items":5})
        for source_name, feed_url in feeds:
            all_items.extend(fetch_direct_rss(feed_url, source_name, max_items=5, max_hours=cfg["max_hours"]))
        all_items = keyword_filter(all_items, SECTION_KEYWORDS.get(section_name))
        seen, unique = set(), []
        for item in all_items:
            key = item["title"][:30].lower()
            if key not in seen: seen.add(key); unique.append(item)
        sections[section_name] = unique[:cfg["max_items"]]
        print(f"    {section_name}: {len(sections[section_name])}건")
    return sections
 
def fetch_market_data():
    print("  💰 투자 데이터 수집 중...")
    tickers = {
        "USD/KRW":"KRW=X",
        "VOO":"VOO","QQQ":"QQQ","TQQQ":"TQQQ","QQQI":"QQQI",
        "VYM":"VYM","VNQ":"VNQ","O":"O","SCHD":"SCHD","SMCI":"SMCI",
        "Bitcoin":"BTC-USD","SUI":"SUI-USD",
        "QLD":"QLD","JEPQ":"JEPQ",
        "S&P 500":"^GSPC","나스닥":"^IXIC","다우":"^DJI",
        "금(Gold)":"GC=F","WTI 원유":"CL=F",
        "미국10년국채":"^TNX","VIX":"^VIX",
    }
    data = {}
    for name, sym in tickers.items():
        try:
            h = yf.Ticker(sym).history(period="5d")
            if not h.empty:
                price = h['Close'].iloc[-1]
                prev = h['Close'].iloc[-2] if len(h)>=2 else price
                data[name] = {"price":price,"change":((price-prev)/prev)*100}
        except: pass
    print(f"    수집 완료: {len(data)}개 종목")
    return data
 
def fetch_economic_events():
    print("  📅 경제 이벤트 수집 중...")
    events = []
    feeds = [("한국경제","https://www.hankyung.com/feed/all-news"),("매일경제","https://www.mk.co.kr/rss/30000001/"),("연합뉴스","https://www.yna.co.kr/rss/news.xml")]
    kw = ["cpi","ppi","고용","실업","비농업","fomc","연준","금리","파월","powell","gdp","소매판매","ism","pmi","소비자물가","생산자물가","경제지표","잭슨홀","jackson","연방공개시장","기자회견","의사록","ecb","boj","일본은행","유럽중앙","인민은행","opec","g7","g20","imf","world bank"]
    for sn, url in feeds:
        try:
            feed = feedparser.parse(url, request_headers=UA)
            cutoff = datetime.now() - timedelta(hours=18)
            for e in feed.entries[:30]:
                pub = None
                if hasattr(e,'published_parsed') and e.published_parsed:
                    try: pub = datetime(*e.published_parsed[:6])
                    except: pass
                if pub and pub < cutoff: continue
                if any(k in e.get('title','').lower() for k in kw):
                    events.append({"title":e.get('title','').strip()[:80],"link":e.get('link',''),"source":sn})
        except: pass
    seen, unique = set(), []
    for ev in events:
        key = ev["title"][:25].lower()
        if key not in seen: seen.add(key); unique.append(ev)
    print(f"    경제 이벤트: {len(unique[:5])}건")
    return unique[:5]
 
YOUTUBE_CHANNELS = {"수페TV":"UCfnqgWlC5IvJEAPTmyjaixA","소수몽키":"UCC3yfxS5qC6PCwDzetUuEWg","미주미 (미국주식)":"UCfOYRKJYgMjUqfS6v29UpBw","박곰희TV":"UCM7tLqKC9MhSFQ3M2dEJSLw"}
 
def fetch_youtube():
    print("  🎬 유튜브 수집 중...")
    results = {}
    cutoff = datetime.now() - timedelta(hours=48)
    for name, cid in YOUTUBE_CHANNELS.items():
        try:
            feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", request_headers=UA)
            vids = []
            for e in feed.entries[:5]:
                pub = None
                if hasattr(e,'published_parsed') and e.published_parsed:
                    try: pub = datetime(*e.published_parsed[:6])
                    except: pass
                if pub and pub < cutoff: continue
                vids.append({"title":e.get('title','')[:70],"link":e.get('link','')})
            results[name] = vids
        except: results[name] = []
        print(f"    {name}: {len(results[name])}건")
    return results
 
def build_html(calendar, reminder, news, market, econ_events, youtube):
    weekday_kr = ["월","화","수","목","금","토","일"][datetime.now().weekday()]
    today_kr = datetime.now().strftime(f"%Y년 %m월 %d일 ({weekday_kr})")
    reminder_html = f'<div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:18px;font-size:14px;">{reminder}</div>' if reminder else ""
    cal_rows = ""
    for ts, title, loc in calendar:
        ls = f" <span style='color:#999;font-size:11px;'>📍{loc}</span>" if loc else ""
        cal_rows += f'<tr style="border-bottom:1px solid #f0f0f0;"><td style="padding:6px 8px;color:#3498db;font-size:12px;white-space:nowrap;width:90px;">{ts}</td><td style="padding:6px 8px;font-size:13px;">{title}{ls}</td></tr>'
 
    def fmt(name, d):
        p,c = d["price"],d["change"]
        color = "#e74c3c" if c<0 else "#27ae60"
        arrow = "▼" if c<0 else "▲"
        if name=="USD/KRW": pf=f"₩{p:,.1f}"
        elif name=="비트코인": pf=f"${p:,.0f}"
        elif name in ["미국10년국채","VIX"]: pf=f"{p:.2f}"
        elif name in ["금(Gold)","WTI 원유"]: pf=f"${p:,.1f}"
        else: pf=f"${p:,.2f}"
        return f"<td style='padding:8px;font-weight:500;'>{name}</td><td style='padding:8px;text-align:right;font-size:15px;font-weight:600;'>{pf}</td><td style='padding:8px;text-align:right;color:{color};font-size:12px;'>{arrow} {abs(c):.2f}%</td>"
 
    def tbl(names):
        return "".join(f"<tr style='border-bottom:1px solid #f0f0f0;'>{fmt(n,market[n])}</tr>" for n in names if n in market)
 
    econ_html = ""
    if econ_events:
        for ev in econ_events:
            econ_html += f"<div style='margin:4px 0;font-size:13px;line-height:1.5;'>📌 <a href=\"{ev['link']}\" style='color:#2c3e50;text-decoration:none;'>{ev['title']}</a> <span style='color:#aaa;font-size:10px;'>— {ev['source']}</span></div>"
    else:
        econ_html = "<p style='color:#999;font-size:12px;'>오늘 주요 경제 이벤트 정보 없음</p>"
 
    def nsec(title, items):
        if not items: return f"<h3 style='margin:16px 0 6px;font-size:14px;color:#555;'>{title}</h3><p style='color:#999;font-size:12px;'>관련 뉴스 없음</p>"
        rows = "".join(f"<div style='margin:4px 0;font-size:13px;line-height:1.5;'>• <a href=\"{i['link']}\" style='color:#2c3e50;text-decoration:none;'>{i['title']}</a> <span style='color:#aaa;font-size:10px;'>— {i.get('source','')}</span></div>" for i in items)
        return f"<h3 style='margin:16px 0 6px;font-size:14px;color:#555;'>{title}</h3>{rows}"
 
    news_html = ""
    for s in ["📢 속보 / Breaking News","📊 미국 증시 / 투자 분석","🇰🇷 한국 정치/경제","🇺🇸 미국 정치/경제","🌍 글로벌 뉴스","🤖 IT / AI 동향","🏘️ Frisco TX 부동산/개발","⚽ 손흥민 / LAFC","🏌️ PGA / LPGA 한국선수","🚗 프리미엄 신차"]:
        if s in news: news_html += nsec(s, news[s])
 
    yt_html = ""
    for ch, vids in youtube.items():
        if vids:
            yt_html += f"<h4 style='margin:12px 0 4px;font-size:13px;color:#555;'>{ch}</h4>"
            yt_html += "".join(f"<div style='margin:3px 0;font-size:13px;'>▶ <a href=\"{v['link']}\" style='color:#e74c3c;text-decoration:none;'>{v['title']}</a></div>" for v in vids)
        else:
            yt_html += f"<h4 style='margin:12px 0 4px;font-size:13px;color:#555;'>{ch}</h4><p style='color:#999;font-size:12px;'>최근 48시간 내 새 영상 없음</p>"
 
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:680px;margin:0 auto;padding:16px;background:#f5f5f5;">
<div style="background:linear-gradient(135deg,#0f2027,#203a43,#2c5364);color:white;padding:22px 26px;border-radius:10px 10px 0 0;">
    <h1 style="margin:0;font-size:20px;">☀️ Dean's Daily Briefing</h1>
    <p style="margin:6px 0 0;opacity:0.85;font-size:13px;">{today_kr}</p>
</div>
<div style="background:white;padding:20px 26px;border-radius:0 0 10px 10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
    {reminder_html}
    <h2 style="margin:0 0 10px;font-size:16px;color:#2c3e50;">📅 오늘의 일정</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">{cal_rows}</table>
    <h2 style="margin:0 0 10px;font-size:16px;color:#2c3e50;">💰 투자 현황</h2>
    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">📈 보유 종목</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">{tbl(["USD/KRW","VOO","QQQ","TQQQ","QQQI","VYM","VNQ","O","SCHD","SMCI","Bitcoin","SUI"])}</table>
    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">💱 원자재</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">{tbl(["금(Gold)","WTI 원유"])}</table>
    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">📊 주요 지수</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">{tbl(["S&P 500","나스닥","다우"])}</table>
    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">🔧 시장 지표</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">{tbl(["미국10년국채","VIX"])}</table>
    <h2 style="margin:0 0 10px;font-size:16px;color:#2c3e50;">📅 오늘의 경제 이벤트</h2>
    <div style="background:#f8f9fa;border-radius:6px;padding:12px 16px;margin-bottom:20px;">{econ_html}</div>
    <h2 style="margin:0 0 6px;font-size:16px;color:#2c3e50;">📰 뉴스</h2>
    {news_html}
    <h2 style="margin:20px 0 6px;font-size:16px;color:#2c3e50;">🎬 유튜브 신규 영상</h2>
    {yt_html}
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0 12px;">
    <p style="color:#aaa;font-size:10px;text-align:center;">
        Dean's Daily Briefing v3.2 | 매일 오전 8시 자동 발송 | GitHub Actions<br>
        뉴스: 한겨레·경향·MBC·오마이뉴스·조선일보 | IT: 전자신문 | 투자: yfinance + 한경·매경·머니투데이<br>
        유튜브: 수페TV, 소수몽키, 미주미, 박곰희TV
    </p>
</div>
</body></html>"""
 
def send_email(html):
    sender = CONFIG["sender_email"]
    pw = CONFIG["sender_app_password"]
    if not pw:
        fname = f"briefing_{datetime.now().strftime('%Y%m%d')}.html"
        with open(fname,"w",encoding="utf-8") as f: f.write(html)
        print(f"  ⚠️ 이메일 미설정 → {fname} 저장"); return
    weekday_kr = ["월","화","수","목","금","토","일"][datetime.now().weekday()]
    subject = f"[Daily Briefing] {datetime.now().strftime(f'%m/%d ({weekday_kr})')}"
    for to in CONFIG["recipients"]:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"],msg["From"],msg["To"] = subject,sender,to
            msg.attach(MIMEText(html,"html","utf-8"))
            with smtplib.SMTP_SSL("smtp.gmail.com",465) as s:
                s.login(sender,pw); s.sendmail(sender,to,msg.as_string())
            print(f"  ✉️ 발송 → {to}")
        except Exception as e:
            print(f"  ❌ 실패 ({to}): {e}")
 
def main():
    print("="*55)
    print(f"  ☀️ Daily Briefing v3.2 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*55)
    print("\n🔎 데이터 수집 중...")
    calendar = fetch_calendar()
    reminder = get_sunday_reminder()
    news = fetch_all_news()
    market = fetch_market_data()
    econ_events = fetch_economic_events()
    youtube = fetch_youtube()
    print("\n📧 이메일 생성 중...")
    html = build_html(calendar, reminder, news, market, econ_events, youtube)
    send_email(html)
    print(f"\n✅ 완료! ({datetime.now().strftime('%H:%M')})")
 
if __name__ == "__main__":
    main()
