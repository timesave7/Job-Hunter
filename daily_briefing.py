"""
Dean's Daily Briefing v3.0a — 매일 오전 8시 자동 발송
v3.0 변경사항:
  - 📢 뉴스 속보 섹션 추가
  - 🌍 글로벌 뉴스 섹션 추가
  - 📊 미국 증시 사후 분석 섹션 추가 ("어제 왜 움직였나")
  - 📅 오늘의 경제 이벤트 캘린더 추가
  - ⚽ 스포츠 보강 (LAFC 손흥민, PGA/LPGA 한국선수)
  - 투자 관련 RSS 소스 및 키워드 대폭 확대
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
    if datetime.now().weekday() == 6:
        return "🔔 Lawn Mowing 작업 확인 및 송금"
    return ""
 
# ───────────────── 📰 뉴스 (직접 RSS 피드) ─────────────────
DIRECT_RSS_FEEDS = {
    # ── 📢 속보 ──
    "📢 속보 / Breaking News": [
        ("연합뉴스",     "https://www.yna.co.kr/rss/news.xml"),
        ("한국뉴스종합",  "https://akngs.github.io/knews-rss/all.xml"),
        ("조선일보",     "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
        ("한겨레",       "https://akngs.github.io/knews-rss/publishers/hani.xml"),
    ],
    # ── 🇰🇷 한국 정치/경제 ──
    "🇰🇷 한국 정치/경제": [
        ("한국뉴스종합",  "https://akngs.github.io/knews-rss/all.xml"),
        ("한겨레",       "https://akngs.github.io/knews-rss/publishers/hani.xml"),
        ("연합뉴스",     "https://www.yna.co.kr/rss/news.xml"),
        ("한국경제",     "https://www.hankyung.com/feed/all-news"),
        ("조선일보",     "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ],
    # ── 🇺🇸 미국 정치/경제 ──
    "🇺🇸 미국 정치/경제": [
        ("연합뉴스",     "https://www.yna.co.kr/rss/news.xml"),
        ("한국경제",     "https://www.hankyung.com/feed/all-news"),
        ("한겨레",       "https://akngs.github.io/knews-rss/publishers/hani.xml"),
        ("조선일보",     "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
        ("국제뉴스종합", "https://akngs.github.io/knews-rss/categories/international.xml"),
    ],
    # ── 🌍 글로벌 뉴스 ──
    "🌍 글로벌 뉴스": [
        ("국제뉴스종합", "https://akngs.github.io/knews-rss/categories/international.xml"),
        ("연합뉴스",     "https://www.yna.co.kr/rss/news.xml"),
        ("한국경제",     "https://www.hankyung.com/feed/all-news"),
        ("조선일보",     "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
        ("한겨레",       "https://akngs.github.io/knews-rss/publishers/hani.xml"),
    ],
    # ── 📊 미국 증시 / 투자 분석 ──
    "📊 미국 증시 / 투자 분석": [
        ("한국경제",     "https://www.hankyung.com/feed/all-news"),
        ("매일경제",     "https://www.mk.co.kr/rss/30000001/"),
        ("머니투데이",   "https://rss.mt.co.kr/mt/mtview/mt_all.xml"),
        ("연합뉴스",     "https://www.yna.co.kr/rss/news.xml"),
        ("한겨레경제",   "https://akngs.github.io/knews-rss/categories/economy.xml"),
        ("조선일보",     "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ],
    # ── 🤖 IT / AI ──
    "🤖 IT / AI 동향": [
        ("한국IT뉴스",   "https://akngs.github.io/knews-rss/categories/tech.xml"),
        ("한국경제",     "https://www.hankyung.com/feed/all-news"),
        ("연합뉴스",     "https://www.yna.co.kr/rss/news.xml"),
        ("매일경제",     "https://www.mk.co.kr/rss/30000001/"),
    ],
    # ── 🏘️ 부동산 ──
    "🏘️ Frisco TX 부동산/개발": [
        ("Community Impact", "https://communityimpact.com/feed/"),
        ("Dallas Morning News", "https://www.dallasnews.com/arcio/rss/"),
    ],
    # ── ⚽ 축구 (손흥민 / LAFC) ──
    "⚽ 손흥민 / LAFC": [
        ("한국스포츠",    "https://akngs.github.io/knews-rss/categories/sports.xml"),
        ("연합뉴스",     "https://www.yna.co.kr/rss/news.xml"),
        ("매일경제",     "https://www.mk.co.kr/rss/30000001/"),
    ],
    # ── 🏌️ 골프 PGA/LPGA 한국선수 ──
    "🏌️ PGA / LPGA 한국선수": [
        ("한국스포츠",    "https://akngs.github.io/knews-rss/categories/sports.xml"),
        ("연합뉴스",     "https://www.yna.co.kr/rss/news.xml"),
        ("매일경제",     "https://www.mk.co.kr/rss/30000001/"),
    ],
    # ── 🚗 프리미엄 신차 ──
    "🚗 프리미엄 신차": [
        ("MotorTrend",    "https://www.motortrend.com/feed/"),
        ("Car and Driver","https://www.caranddriver.com/rss/all.xml/"),
    ],
}
 
# 섹션별 키워드 필터
SECTION_KEYWORDS = {
    "📢 속보 / Breaking News": ["속보","긴급","breaking","사망","지진","전쟁","탄핵","계엄","비상","테러","폭발","총격","대통령"],
    "🇰🇷 한국 정치/경제": None,
    "🇺🇸 미국 정치/경제": ["미국","트럼프","바이든","워싱턴","백악관","연준","fed","달러","월가","wall","us","america","관세","무역","의회","상원","하원","국무"],
    "🌍 글로벌 뉴스": ["중국","일본","러시아","우크라이나","유럽","eu","nato","중동","이란","이스라엘","대만","인도","영국","프랑스","독일","un","유엔","g7","g20","opec","아프리카","남미","북한","핵"],
    "📊 미국 증시 / 투자 분석": [
        # 시장/지수
        "증시","주가","나스닥","nasdaq","s&p","다우","dow","코스피","코스닥","선물","옵션",
        # 통화/금리
        "금리","기준금리","인플레","cpi","ppi","고용","실업","비농업","fomc","연준","fed","파월","powell","금리인하","금리인상","국채","채권","환율","달러","원화","엔화",
        # 종목/산업
        "엔비디아","nvidia","애플","apple","테슬라","tesla","마이크로소프트","아마존","구글","메타","반도체","ai","매그니피센트","빅테크","실적","어닝","분기",
        # ETF/투자
        "etf","qqq","tqqq","voo","spy","배당","매수","매도","공매도","투자","펀드","자산","포트폴리오",
        # 원자재/크립토
        "비트코인","bitcoin","이더리움","코인","금값","유가","원유","wti",
        # 경제지표
        "gdp","소비자물가","생산자물가","소매판매","ism","pmi","무역수지","경상수지",
    ],
    "🤖 IT / AI 동향": ["ai","인공지능","로봇","자율주행","스마트","반도체","칩","gpu","테슬라","엔비디아","삼성전자","애플","구글","챗gpt","클로드","llm","생성형","오픈ai","openai","딥러닝","머신러닝"],
    "🏘️ Frisco TX 부동산/개발": ["frisco","texas","tx","real estate","부동산","개발","plano","mckinney","dfw","dallas"],
    "⚽ 손흥민 / LAFC": ["손흥민","son heung","lafc","los angeles fc","mls","축구","football","soccer","토트넘","tottenham","spurs","premier","k리그","이강인","김민재","황희찬"],
    "🏌️ PGA / LPGA 한국선수": ["lpga","pga","골프","golf","한국","korea","korean","고진영","ko jin","김효주","전인지","양희영","이민지","임성재","김시우","김주형","안병훈","이경훈","tom kim","masters","open","championship","tour"],
    "🚗 프리미엄 신차": ["bmw","mercedes","porsche","genesis","audi","2026","2027","luxury","new model","electric"],
}
 
# 섹션별 수집 시간 범위 및 최대 건수
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
        if not feed.entries:
            return []
        cutoff = datetime.now() - timedelta(hours=max_hours)
        items = []
        for e in feed.entries[:max_items*3]:
            pub = None
            if hasattr(e, 'published_parsed') and e.published_parsed:
                try: pub = datetime(*e.published_parsed[:6])
                except: pass
            elif hasattr(e, 'updated_parsed') and e.updated_parsed:
                try: pub = datetime(*e.updated_parsed[:6])
                except: pass
            if pub and pub < cutoff:
                continue
            title = e.get('title','').strip()
            if not title:
                continue
            title = re.sub(r'\s*-\s*[^-]{0,30}$','',title)
            link = e.get('link','')
            items.append({"title": title[:80], "link": link, "source": source_name})
            if len(items) >= max_items:
                break
        return items
    except Exception as ex:
        print(f"      ⚠️ {source_name} RSS 오류: {str(ex)[:50]}")
        return []
 
def keyword_filter(items, keywords):
    if keywords is None:
        return items
    filtered = []
    for item in items:
        text = item["title"].lower()
        if any(kw in text for kw in keywords):
            filtered.append(item)
    return filtered
 
def fetch_all_news():
    sections = {}
    print("  📰 뉴스 수집 중 (직접 RSS)...")
    for section_name, feeds in DIRECT_RSS_FEEDS.items():
        all_items = []
        cfg = SECTION_CONFIG.get(section_name, {"max_hours": 48, "max_items": 5})
        keywords = SECTION_KEYWORDS.get(section_name)
        for source_name, feed_url in feeds:
            items = fetch_direct_rss(feed_url, source_name, max_items=5, max_hours=cfg["max_hours"])
            all_items.extend(items)
        all_items = keyword_filter(all_items, keywords)
        # 중복 제거
        seen = set()
        unique = []
        for item in all_items:
            key = item["title"][:30].lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        sections[section_name] = unique[:cfg["max_items"]]
        print(f"    {section_name}: {len(sections[section_name])}건")
    return sections
 
# ───────────────── 💰 투자 정보 ─────────────────
def fetch_market_data():
    print("  💰 투자 데이터 수집 중...")
    tickers = {
        "QQQ": "QQQ", "TQQQ": "TQQQ", "QLD": "QLD",
        "VOO": "VOO", "JEPQ": "JEPQ", "SCHD": "SCHD",
        "S&P 500": "^GSPC", "나스닥": "^IXIC", "다우": "^DJI",
        "비트코인": "BTC-USD", "USD/KRW": "KRW=X",
        "금(Gold)": "GC=F", "WTI 원유": "CL=F",
        "미국10년국채": "^TNX", "VIX": "^VIX",
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
 
# ───────────────── 📅 오늘의 경제 이벤트 ─────────────────
def fetch_economic_events():
    """Investing.com 경제 캘린더 RSS 또는 대체 소스에서 오늘 이벤트 수집"""
    print("  📅 경제 이벤트 수집 중...")
    events = []
    # 방법 1: 한국경제/매일경제에서 경제지표 관련 기사 수집
    indicator_feeds = [
        ("한국경제", "https://www.hankyung.com/feed/all-news"),
        ("매일경제", "https://www.mk.co.kr/rss/30000001/"),
        ("연합뉴스", "https://www.yna.co.kr/rss/news.xml"),
    ]
    event_keywords = [
        "cpi","ppi","고용","실업","비농업","fomc","연준","금리","파월","powell",
        "gdp","소매판매","ism","pmi","소비자물가","생산자물가","경제지표",
        "잭슨홀","jackson","연방공개시장","기자회견","의사록",
        "ecb","boj","일본은행","유럽중앙","인민은행",
        "opec","g7","g20","imf","world bank",
    ]
    for source_name, feed_url in indicator_feeds:
        try:
            feed = feedparser.parse(feed_url, request_headers=UA)
            cutoff = datetime.now() - timedelta(hours=18)
            for e in feed.entries[:30]:
                pub = None
                if hasattr(e, 'published_parsed') and e.published_parsed:
                    try: pub = datetime(*e.published_parsed[:6])
                    except: pass
                if pub and pub < cutoff:
                    continue
                title = e.get('title','').strip().lower()
                if any(kw in title for kw in event_keywords):
                    events.append({
                        "title": e.get('title','').strip()[:80],
                        "link": e.get('link',''),
                        "source": source_name
                    })
        except:
            pass
    # 중복 제거
    seen = set()
    unique = []
    for ev in events:
        key = ev["title"][:25].lower()
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    print(f"    경제 이벤트: {len(unique[:5])}건")
    return unique[:5]
 
# ───────────────── 🎬 유튜브 ─────────────────
YOUTUBE_CHANNELS = {
    "수페TV":     "UCfnqgWlC5IvJEAPTmyjaixA",
    "소수몽키":   "UCC3yfxS5qC6PCwDzetUuEWg",
    "미주미 (미국주식)": "UCfOYRKJYgMjUqfS6v29UpBw",
    "박곰희TV":   "UCM7tLqKC9MhSFQ3M2dEJSLw",
}
 
def fetch_youtube():
    print("  🎬 유튜브 수집 중...")
    results = {}
    cutoff = datetime.now() - timedelta(hours=48)
    for name, cid in YOUTUBE_CHANNELS.items():
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        try:
            feed = feedparser.parse(url, request_headers=UA)
            vids = []
            for e in feed.entries[:5]:
                pub = None
                if hasattr(e,'published_parsed') and e.published_parsed:
                    try: pub = datetime(*e.published_parsed[:6])
                    except: pass
                if pub and pub < cutoff:
                    continue
                vids.append({"title": e.get('title','')[:70], "link": e.get('link','')})
            results[name] = vids
        except:
            results[name] = []
        print(f"    {name}: {len(results[name])}건")
    return results
 
# ───────────────── 이메일 HTML 생성 ─────────────────
def build_html(calendar, reminder, news, market, econ_events, youtube):
    weekday_kr = ["월","화","수","목","금","토","일"][datetime.now().weekday()]
    today_kr = datetime.now().strftime(f"%Y년 %m월 %d일 ({weekday_kr})")
 
    # 리마인더
    reminder_html = ""
    if reminder:
        reminder_html = f"""
        <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px 16px;
                    border-radius:0 6px 6px 0;margin-bottom:18px;font-size:14px;">
            {reminder}
        </div>"""
 
    # 캘린더
    cal_rows = ""
    for time_s, title, loc in calendar:
        loc_str = f" <span style='color:#999;font-size:11px;'>📍{loc}</span>" if loc else ""
        cal_rows += f"""<tr style="border-bottom:1px solid #f0f0f0;">
            <td style="padding:6px 8px;color:#3498db;font-size:12px;white-space:nowrap;width:90px;">{time_s}</td>
            <td style="padding:6px 8px;font-size:13px;">{title}{loc_str}</td></tr>"""
 
    # ── 투자 테이블 생성 ──
    def fmt_price(name, d):
        p = d["price"]
        c = d["change"]
        color = "#e74c3c" if c < 0 else "#27ae60"
        arrow = "▼" if c < 0 else "▲"
        if name == "USD/KRW":
            pf = f"₩{p:,.1f}"
        elif name == "비트코인":
            pf = f"${p:,.0f}"
        elif name in ["미국10년국채","VIX"]:
            pf = f"{p:.2f}"
        elif name in ["금(Gold)","WTI 원유"]:
            pf = f"${p:,.1f}"
        else:
            pf = f"${p:,.2f}"
        return f"""<td style='padding:8px;font-weight:500;'>{name}</td>
            <td style='padding:8px;text-align:right;font-size:15px;font-weight:600;'>{pf}</td>
            <td style='padding:8px;text-align:right;color:{color};font-size:12px;'>{arrow} {abs(c):.2f}%</td>"""
 
    def make_table(names):
        rows = ""
        for n in names:
            if n in market:
                rows += f"<tr style='border-bottom:1px solid #f0f0f0;'>{fmt_price(n, market[n])}</tr>"
        return rows
 
    holdings_html = make_table(["QQQ","TQQQ","QLD","VOO","JEPQ","SCHD"])
    index_html = make_table(["S&P 500","나스닥","다우"])
    fx_crypto_html = make_table(["USD/KRW","비트코인","금(Gold)","WTI 원유"])
    indicator_html = make_table(["미국10년국채","VIX"])
 
    # ── 경제 이벤트 ──
    econ_html = ""
    if econ_events:
        for ev in econ_events:
            src = f" <span style='color:#aaa;font-size:10px;'>— {ev['source']}</span>"
            econ_html += f"<div style='margin:4px 0;font-size:13px;line-height:1.5;'>📌 <a href=\"{ev['link']}\" style='color:#2c3e50;text-decoration:none;'>{ev['title']}</a>{src}</div>"
    else:
        econ_html = "<p style='color:#999;font-size:12px;'>오늘 주요 경제 이벤트 정보 없음</p>"
 
    # ── 뉴스 섹션 ──
    def news_section(title, items):
        if not items:
            return f"<h3 style='margin:16px 0 6px;font-size:14px;color:#555;'>{title}</h3><p style='color:#999;font-size:12px;'>관련 뉴스 없음</p>"
        rows = ""
        for item in items:
            src = f" <span style='color:#aaa;font-size:10px;'>— {item['source']}</span>" if item.get('source') else ""
            rows += f"<div style='margin:4px 0;font-size:13px;line-height:1.5;'>• <a href=\"{item['link']}\" style='color:#2c3e50;text-decoration:none;'>{item['title']}</a>{src}</div>"
        return f"<h3 style='margin:16px 0 6px;font-size:14px;color:#555;'>{title}</h3>{rows}"
 
    all_news_html = ""
    # 뉴스 섹션 순서 지정
    news_order = [
        "📢 속보 / Breaking News",
        "📊 미국 증시 / 투자 분석",
        "🇰🇷 한국 정치/경제",
        "🇺🇸 미국 정치/경제",
        "🌍 글로벌 뉴스",
        "🤖 IT / AI 동향",
        "🏘️ Frisco TX 부동산/개발",
        "⚽ 손흥민 / LAFC",
        "🏌️ PGA / LPGA 한국선수",
        "🚗 프리미엄 신차",
    ]
    for section_title in news_order:
        if section_title in news:
            all_news_html += news_section(section_title, news[section_title])
 
    # ── 유튜브 ──
    yt_html = ""
    for ch_name, vids in youtube.items():
        if vids:
            yt_html += f"<h4 style='margin:12px 0 4px;font-size:13px;color:#555;'>{ch_name}</h4>"
            for v in vids:
                yt_html += f"<div style='margin:3px 0;font-size:13px;'>▶ <a href=\"{v['link']}\" style='color:#e74c3c;text-decoration:none;'>{v['title']}</a></div>"
        else:
            yt_html += f"<h4 style='margin:12px 0 4px;font-size:13px;color:#555;'>{ch_name}</h4><p style='color:#999;font-size:12px;'>최근 48시간 내 새 영상 없음</p>"
 
    # ── 전체 HTML 조립 ──
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
 
    <!-- 💰 투자 현황 -->
    <h2 style="margin:0 0 10px;font-size:16px;color:#2c3e50;">💰 투자 현황</h2>
 
    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">💱 환율 / 크립토 / 원자재</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">{fx_crypto_html}</table>
 
    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">📈 보유 종목</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">{holdings_html}</table>
 
    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">📊 주요 지수</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">{index_html}</table>
 
    <h4 style="margin:8px 0 4px;font-size:12px;color:#888;">🔧 시장 지표</h4>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">{indicator_html}</table>
 
    <!-- 📅 경제 이벤트 -->
    <h2 style="margin:0 0 10px;font-size:16px;color:#2c3e50;">📅 오늘의 경제 이벤트</h2>
    <div style="background:#f8f9fa;border-radius:6px;padding:12px 16px;margin-bottom:20px;">
        {econ_html}
    </div>
 
    <!-- 📰 뉴스 -->
    <h2 style="margin:0 0 6px;font-size:16px;color:#2c3e50;">📰 뉴스</h2>
    {all_news_html}
 
    <!-- 🎬 유튜브 -->
    <h2 style="margin:20px 0 6px;font-size:16px;color:#2c3e50;">🎬 유튜브 신규 영상</h2>
    {yt_html}
 
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0 12px;">
    <p style="color:#aaa;font-size:10px;text-align:center;">
        Dean's Daily Briefing v3.0 | 매일 오전 8시 자동 발송 | GitHub Actions<br>
        뉴스: 직접 RSS 피드 | 투자: yfinance + 경제이벤트 | 유튜브: 수페TV, 소수몽키, 미주미, 박곰희TV
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
    print(f"  ☀️ Daily Briefing v3.0 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
