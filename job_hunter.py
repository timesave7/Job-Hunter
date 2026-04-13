"""
═══════════════════════════════════════════════════════════════
  Job Hunter v2.0 - 일일 구인정보 자동 이메일 발송
  
  검색 소스:
    [API]  Adzuna, JSearch (RapidAPI)
    [한인] 달사람닷컴, 달코라(KTN), 미주중앙일보
    [대기업] 17개 기업 채용페이지 직접 모니터링
  
  대상: Frisco, TX 기준 40마일 반경
  정렬: 기업규모 우선 (대기업 → 중견 → 소기업)
  포함: 정규직, 인턴, 단기계약직
═══════════════════════════════════════════════════════════════
"""

import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import os
from datetime import datetime, timedelta
import time
import re
import hashlib

# ═══════════════════════════════════════════════════════════
# 📌 CONFIG
# ═══════════════════════════════════════════════════════════

CONFIG = {
    # Gmail (App Password 필요)
    "sender_email": os.environ.get("SENDER_EMAIL", "seunggy98@gmail.com"),
    "sender_app_password": os.environ.get("GMAIL_APP_PASSWORD", ""),

    # 수신자 (테스트: 아버지만)
    "recipients": [
        "timesave7@gmail.com",
        # "seunggy98@gmail.com",  # ← 완성 후 주석 해제
    ],

    # 검색 조건
    "location": "Frisco, TX",
    "radius_miles": 40,
    "max_days_old": 3,

    # 검색 키워드 (정규직 + 인턴 + 계약직)
    "search_keywords": [
        "entry level",
        "junior",
        "associate",
        "analyst",
        "coordinator",
        "intern",
        "internship",
        "contract",
        "temporary",
        "korean bilingual",
    ],

    # API 키 (환경변수에서 읽음 → GitHub Secrets)
    "adzuna_app_id": os.environ.get("ADZUNA_APP_ID", ""),
    "adzuna_app_key": os.environ.get("ADZUNA_APP_KEY", ""),
    "jsearch_api_key": os.environ.get("JSEARCH_API_KEY", ""),

    # 기타
    "seen_jobs_file": "seen_jobs.json",
    "max_jobs_per_email": 60,
}

# ═══════════════════════════════════════════════════════════
# 🏢 대기업 채용페이지 (Frisco 40마일 반경)
# ═══════════════════════════════════════════════════════════

COMPANY_CAREER_PAGES = {
    # 회사명: (채용페이지 URL, Workday API URL 또는 None, 위치)
    "PGA of America": {
        "url": "https://careers.pgahq.com/open-positions.html",
        "workday": "https://pgahq.wd1.myworkdayjobs.com/wday/cxs/pgahq/PGAHQ/jobs",
        "location": "Frisco, TX",
    },
    "Universal Kids Resort": {
        "url": "https://jobs.comcast.com/universal-destinations-experiences-jobs",
        "workday": None,
        "search_url": "https://jobs.comcast.com/search?q=universal+frisco&location=Texas",
        "location": "Frisco, TX",
    },
    "Toyota North America": {
        "url": "https://www.toyota.com/careers",
        "workday": "https://toyota.wd5.myworkdayjobs.com/wday/cxs/toyota/TMNA/jobs",
        "location": "Plano, TX",
    },
    "T-Mobile": {
        "url": "https://www.t-mobile.com/careers",
        "workday": "https://tmobile.wd1.myworkdayjobs.com/wday/cxs/tmobile/External/jobs",
        "location": "Frisco, TX",
    },
    "Samsung Semiconductor": {
        "url": "https://semiconductor.samsung.com/us/careers/",
        "workday": "https://sec.wd3.myworkdayjobs.com/wday/cxs/sec/Samsung_Careers/jobs",
        "location": "Plano, TX",
    },
    "Capital One": {
        "url": "https://www.capitalonecareers.com/",
        "workday": "https://capitalone.wd1.myworkdayjobs.com/wday/cxs/capitalone/Capital_One/jobs",
        "location": "Plano, TX",
    },
    "JPMorgan Chase": {
        "url": "https://careers.jpmorgan.com/",
        "workday": None,
        "location": "Plano, TX",
    },
    "Bank of America": {
        "url": "https://careers.bankofamerica.com/",
        "workday": None,
        "location": "Plano, TX",
    },
    "American Airlines": {
        "url": "https://jobs.aa.com/",
        "workday": "https://americanairlines.wd5.myworkdayjobs.com/wday/cxs/americanairlines/external/jobs",
        "location": "Fort Worth, TX",
    },
    "Southwest Airlines": {
        "url": "https://careers.southwestair.com/",
        "workday": None,
        "location": "Dallas, TX",
    },
    "Frito-Lay / PepsiCo": {
        "url": "https://www.pepsicojobs.com/",
        "workday": None,
        "location": "Plano, TX",
    },
    "Raytheon (RTX)": {
        "url": "https://careers.rtx.com/",
        "workday": "https://rtx.wd1.myworkdayjobs.com/wday/cxs/rtx/External/jobs",
        "location": "McKinney, TX",
    },
    "TIAA": {
        "url": "https://www.tiaa.org/public/about-tiaa/careers",
        "workday": "https://tiaa.wd1.myworkdayjobs.com/wday/cxs/tiaa/Careers/jobs",
        "location": "Frisco, TX",
    },
    "Thomson Reuters": {
        "url": "https://careers.thomsonreuters.com/",
        "workday": None,
        "location": "Frisco, TX",
    },
    "State Farm": {
        "url": "https://jobs.statefarm.com/",
        "workday": None,
        "location": "Richardson, TX",
    },
    "Liberty Mutual": {
        "url": "https://jobs.libertymutual.com/",
        "workday": None,
        "location": "Plano, TX",
    },
    "Keurig Dr Pepper": {
        "url": "https://careers.keurigdrpepper.com/",
        "workday": "https://keurigdrpepper.wd1.myworkdayjobs.com/wday/cxs/keurigdrpepper/KDP_External/jobs",
        "location": "Frisco, TX",
    },
}

# ═══════════════════════════════════════════════════════════
# 기업규모 분류
# ═══════════════════════════════════════════════════════════

LARGE_COMPANIES = {
    "samsung", "sk hynix", "texas instruments", "toyota", "frito-lay",
    "pepsico", "capital one", "jpmorgan", "chase", "bank of america",
    "wells fargo", "deloitte", "kpmg", "pwc", "ey", "ernst & young",
    "amazon", "google", "meta", "microsoft", "apple", "oracle",
    "at&t", "verizon", "t-mobile", "lg", "hyundai", "kia",
    "korean air", "asiana", "hanwha", "cj", "lotte", "doosan",
    "woongjin", "kotra", "posco", "hyosung", "gs", "kumho",
    "state farm", "allstate", "liberty mutual", "cigna", "unitedhealth",
    "lockheed martin", "raytheon", "rtx", "boeing", "dell", "hp", "cisco",
    "salesforce", "vmware", "nvidia", "amd", "qualcomm", "broadcom",
    "costco", "walmart", "target", "home depot", "kroger",
    "jnd", "fns", "hmm", "hanjin", "coupang",
    "pga of america", "pga", "universal", "comcast", "nbcuniversal",
    "american airlines", "southwest airlines", "tiaa", "thomson reuters",
    "keurig", "dr pepper", "liberty mutual",
}

MID_COMPANIES = {
    "activ8", "geniezip", "chowbus", "aqs", "kennedy access",
    "spacepalm", "gst america", "sbt global", "cosmax",
    "omni hotel", "topgolf",
}


def classify_company_size(company_name: str) -> int:
    if not company_name:
        return 0
    name_lower = company_name.lower().strip()
    for large in LARGE_COMPANIES:
        if large in name_lower:
            return 2
    for mid in MID_COMPANIES:
        if mid in name_lower:
            return 1
    return 0


# ═══════════════════════════════════════════════════════════
# 중복 체크
# ═══════════════════════════════════════════════════════════

def load_seen_jobs() -> set:
    path = CONFIG["seen_jobs_file"]
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
            cutoff = (datetime.now() - timedelta(days=7)).isoformat()
            return {k for k, v in data.items() if v > cutoff}
    return set()


def save_seen_jobs(seen: set):
    now = datetime.now().isoformat()
    data = {job_id: now for job_id in seen}
    with open(CONFIG["seen_jobs_file"], "w") as f:
        json.dump(data, f, indent=2)


def make_job_id(title: str, company: str, url: str) -> str:
    raw = f"{title}|{company}|{url}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════
# 소스 1: Adzuna API
# ═══════════════════════════════════════════════════════════

def fetch_adzuna_jobs() -> list:
    jobs = []
    app_id = CONFIG["adzuna_app_id"]
    app_key = CONFIG["adzuna_app_key"]
    if not app_id or not app_key:
        print("  ⚠️  Adzuna API 키 미설정 - 건너뜀")
        return jobs

    base_url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
    for keyword in CONFIG["search_keywords"][:6]:
        params = {
            "app_id": app_id, "app_key": app_key,
            "what": keyword, "where": CONFIG["location"],
            "distance": int(CONFIG["radius_miles"] * 1.6),
            "results_per_page": 20,
            "max_days_old": CONFIG["max_days_old"],
            "sort_by": "date",
        }
        try:
            resp = requests.get(base_url, params=params, timeout=15)
            if resp.status_code == 200:
                for item in resp.json().get("results", []):
                    jobs.append({
                        "title": item.get("title", ""),
                        "company": item.get("company", {}).get("display_name", ""),
                        "location": item.get("location", {}).get("display_name", ""),
                        "url": item.get("redirect_url", ""),
                        "date": item.get("created", "")[:10],
                        "source": "Adzuna",
                    })
            time.sleep(0.5)
        except Exception as e:
            print(f"  ❌ Adzuna ({keyword}): {e}")
    print(f"  ✅ Adzuna: {len(jobs)}건")
    return jobs


# ═══════════════════════════════════════════════════════════
# 소스 2: JSearch (RapidAPI)
# ═══════════════════════════════════════════════════════════

def fetch_jsearch_jobs() -> list:
    jobs = []
    api_key = CONFIG["jsearch_api_key"]
    if not api_key:
        print("  ⚠️  JSearch API 키 미설정 - 건너뜀")
        return jobs

    url = "https://jsearch.p.rapidapi.com/search"
    headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}

    # 일반 키워드 + 대기업 이름으로 검색
    queries = [f"{kw} in {CONFIG['location']}" for kw in CONFIG["search_keywords"][:5]]
    for company in ["PGA of America", "Universal Frisco", "Toyota Plano",
                     "Samsung Plano", "Capital One Plano", "American Airlines"]:
        queries.append(f"{company} entry level")

    for query in queries:
        params = {
            "query": query, "page": "1", "num_pages": "1",
            "date_posted": "3days", "radius": str(CONFIG["radius_miles"]),
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                for item in resp.json().get("data", []):
                    jobs.append({
                        "title": item.get("job_title", ""),
                        "company": item.get("employer_name", ""),
                        "location": (item.get("job_city", "") or "") + ", " + (item.get("job_state", "") or ""),
                        "url": item.get("job_apply_link", "") or item.get("job_google_link", ""),
                        "date": (item.get("job_posted_at_datetime_utc", "") or "")[:10],
                        "source": "JSearch",
                    })
            time.sleep(1)
        except Exception as e:
            print(f"  ❌ JSearch: {e}")
    print(f"  ✅ JSearch: {len(jobs)}건")
    return jobs


# ═══════════════════════════════════════════════════════════
# 소스 3: Workday 기업 채용페이지 (자동 모니터링)
# ═══════════════════════════════════════════════════════════

def fetch_workday_jobs(company_name: str, info: dict) -> list:
    """Workday 기반 채용페이지에서 Entry/Intern/Contract 공고 수집"""
    jobs = []
    workday_url = info.get("workday")
    if not workday_url:
        return jobs

    headers = {"Content-Type": "application/json"}
    texas_keywords = ["texas", "tx", "frisco", "plano", "dallas",
                      "mckinney", "richardson", "fort worth", "irving"]
    level_keywords = ["entry", "junior", "associate", "intern", "contract",
                      "temporary", "temp", "coordinator", "analyst", "clerk"]

    payload = {
        "appliedFacets": {},
        "limit": 20,
        "offset": 0,
        "searchText": "Texas entry level intern",
    }

    try:
        resp = requests.post(workday_url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for posting in data.get("jobPostings", []):
                title = posting.get("title", "")
                location = posting.get("locationsText", "")
                ext_path = posting.get("externalPath", "")

                # 텍사스 위치 필터
                loc_lower = location.lower()
                if not any(kw in loc_lower for kw in texas_keywords):
                    continue

                # 레벨 필터 (느슨하게)
                title_lower = title.lower()
                is_relevant = any(kw in title_lower for kw in level_keywords)
                # 제목에 레벨 키워드 없어도 일단 포함 (대기업이므로)
                if not is_relevant:
                    is_relevant = True  # 대기업은 모두 포함

                if is_relevant:
                    base = workday_url.replace("/wday/cxs/", "/").rsplit("/jobs", 1)[0]
                    job_url = f"{base}{ext_path}" if ext_path else info["url"]

                    jobs.append({
                        "title": title,
                        "company": company_name,
                        "location": location,
                        "url": job_url,
                        "date": posting.get("postedOn", "")[:10],
                        "source": f"🏢 {company_name}",
                    })
    except Exception as e:
        print(f"    ⚠️  {company_name} Workday: {e}")

    return jobs


def fetch_all_company_jobs() -> list:
    """전체 대기업 채용페이지 모니터링"""
    all_jobs = []
    for company_name, info in COMPANY_CAREER_PAGES.items():
        jobs = fetch_workday_jobs(company_name, info)
        if jobs:
            print(f"    ✅ {company_name}: {len(jobs)}건")
        else:
            print(f"    ⏭️  {company_name}: Workday 미지원 또는 0건")
        all_jobs.extend(jobs)
        time.sleep(0.3)

    print(f"  ✅ 대기업 채용페이지 합계: {len(all_jobs)}건")
    return all_jobs


# ═══════════════════════════════════════════════════════════
# 소스 4: 달사람닷컴
# ═══════════════════════════════════════════════════════════

def fetch_dalsaram_jobs() -> list:
    jobs = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = "https://www.dalsaram.com/job/?boardgubun=view&code=dallas_101&page=1"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if "id=" in href and text and len(text) > 5:
                    skip = ["식당", "미용", "네일", "세탁", "도넛", "카페", "서버"]
                    if any(s in text for s in skip):
                        continue
                    full_url = href if href.startswith("http") else f"https://www.dalsaram.com/job/{href}"
                    cat = re.search(r'\[([^\]]+)\]', text)
                    jobs.append({
                        "title": re.sub(r'\[[^\]]*\]', '', text).strip(),
                        "company": cat.group(1) if cat else "",
                        "location": "Dallas, TX (한인)",
                        "url": full_url, "date": "",
                        "source": "🇰🇷 달사람닷컴",
                    })
    except Exception as e:
        print(f"  ❌ 달사람닷컴: {e}")
    print(f"  ✅ 달사람닷컴: {len(jobs)}건")
    return jobs[:20]


# ═══════════════════════════════════════════════════════════
# 소스 5: 달코라 / Dallas KTN
# ═══════════════════════════════════════════════════════════

def fetch_dalkora_jobs() -> list:
    jobs = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = "https://www.dalkora.com/bbs/board.php?bo_table=dk_offer&sca=%EA%B5%AC%EC%9D%B8"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.select("a.bo_tit, td.td_subject a, .td_subject a")
            if not links:
                links = [a for a in soup.find_all("a", href=True) if "wr_id=" in a.get("href", "")]
            for link in links[:20]:
                text = link.get_text(strip=True)
                href = link.get("href", "")
                if not text or len(text) < 3 or "공지" in text:
                    continue
                full_url = href if href.startswith("http") else f"https://www.dalkora.com{href}"
                cat = re.search(r'\[([^\]]+)\]', text)
                jobs.append({
                    "title": re.sub(r'\[[^\]]*\]', '', text).strip(),
                    "company": cat.group(1) if cat else "",
                    "location": "Dallas, TX (한인)",
                    "url": full_url, "date": "",
                    "source": "🇰🇷 달코라(KTN)",
                })
    except Exception as e:
        print(f"  ❌ 달코라: {e}")
    print(f"  ✅ 달코라(KTN): {len(jobs)}건")
    return jobs


# ═══════════════════════════════════════════════════════════
# 소스 6: 미주중앙일보
# ═══════════════════════════════════════════════════════════

def fetch_koreadaily_jobs() -> list:
    jobs = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = "https://ktown.koreadaily.com/ad_job/recruit"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            texas_kw = ["dallas", "texas", "tx", "frisco", "plano",
                        "달라스", "텍사스", "mckinney", "allen", "richardson"]
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True)
                href = link.get("href", "")
                if text and len(text) > 5 and any(kw in text.lower() for kw in texas_kw):
                    full_url = href if href.startswith("http") else f"https://ktown.koreadaily.com{href}"
                    jobs.append({
                        "title": text[:100], "company": "",
                        "location": "Dallas/TX (한인)",
                        "url": full_url, "date": "",
                        "source": "🇰🇷 미주중앙일보",
                    })
    except Exception as e:
        print(f"  ❌ 미주중앙일보: {e}")
    print(f"  ✅ 미주중앙일보: {len(jobs)}건")
    return jobs[:15]


# ═══════════════════════════════════════════════════════════
# 중복 제거 & 정렬
# ═══════════════════════════════════════════════════════════

def deduplicate_and_sort(all_jobs: list, seen: set) -> list:
    unique = {}
    for job in all_jobs:
        job_id = make_job_id(job["title"], job["company"], job["url"])
        if job_id not in seen and job_id not in unique:
            job["_id"] = job_id
            job["_size"] = classify_company_size(job["company"])
            unique[job_id] = job
    return sorted(unique.values(), key=lambda x: -x["_size"])[:CONFIG["max_jobs_per_email"]]


# ═══════════════════════════════════════════════════════════
# 이메일 HTML 생성
# ═══════════════════════════════════════════════════════════

def build_email_html(jobs: list) -> str:
    today = datetime.now().strftime("%Y년 %m월 %d일 (%A)")
    source_counts = {}
    for job in jobs:
        src = job["source"]
        source_counts[src] = source_counts.get(src, 0) + 1
    source_summary = " | ".join([f"{k}: {v}건" for k, v in source_counts.items()])
    size_labels = {2: "🏢 대기업", 1: "🏣 중견기업", 0: "🏠 일반"}

    # 인턴/계약직 태그
    def get_badge(title):
        t = title.lower()
        if "intern" in t:
            return '<span style="background:#e74c3c;color:white;padding:2px 6px;border-radius:3px;font-size:11px;margin-left:5px;">인턴</span>'
        if any(w in t for w in ["contract", "temporary", "temp "]):
            return '<span style="background:#f39c12;color:white;padding:2px 6px;border-radius:3px;font-size:11px;margin-left:5px;">계약직</span>'
        return ""

    rows = ""
    current_size = None
    for job in jobs:
        size = job.get("_size", 0)
        if size != current_size:
            current_size = size
            rows += f"""
            <tr><td colspan="5" style="background:#2c3e50;color:white;padding:10px 15px;
                font-size:15px;font-weight:bold;">{size_labels.get(size, "기타")}</td></tr>"""

        title_display = job["title"][:55] + ("..." if len(job["title"]) > 55 else "")
        badge = get_badge(job["title"])
        rows += f"""
        <tr style="border-bottom:1px solid #eee;">
            <td style="padding:8px 10px;">
                <a href="{job['url']}" style="color:#2980b9;text-decoration:none;font-weight:500;">{title_display}</a>{badge}
            </td>
            <td style="padding:8px 10px;color:#555;">{job['company']}</td>
            <td style="padding:8px 10px;color:#777;font-size:13px;">{job['location']}</td>
            <td style="padding:8px 10px;color:#777;font-size:13px;">{job.get('date', '')}</td>
            <td style="padding:8px 10px;color:#888;font-size:12px;">{job['source']}</td>
        </tr>"""

    # 대기업 채용페이지 바로가기 링크
    career_links = ""
    for name, info in COMPANY_CAREER_PAGES.items():
        career_links += f'<a href="{info["url"]}" style="color:#3498db;text-decoration:none;margin-right:15px;font-size:13px;">{name}</a> '

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             max-width:950px;margin:0 auto;padding:20px;background:#f5f5f5;">
    <div style="background:linear-gradient(135deg,#2c3e50,#3498db);color:white;
                padding:25px 30px;border-radius:10px 10px 0 0;">
        <h1 style="margin:0;font-size:22px;">🔍 오늘의 구인정보</h1>
        <p style="margin:8px 0 0;opacity:0.9;font-size:14px;">
            {today} | Frisco, TX 40마일 | 기업규모순 | 정규직·인턴·계약직
        </p>
    </div>
    <div style="background:white;padding:20px 30px;border-radius:0 0 10px 10px;
                box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <p style="color:#666;font-size:13px;margin-bottom:20px;">
            📊 총 <strong>{len(jobs)}건</strong> 신규 | {source_summary}
        </p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <thead><tr style="background:#ecf0f1;text-align:left;">
                <th style="padding:10px;">포지션</th>
                <th style="padding:10px;">회사</th>
                <th style="padding:10px;">위치</th>
                <th style="padding:10px;">게시일</th>
                <th style="padding:10px;">소스</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>

        <div style="margin-top:25px;padding:15px;background:#f8f9fa;border-radius:8px;">
            <p style="margin:0 0 10px;font-weight:bold;font-size:14px;">🔗 대기업 채용페이지 바로가기</p>
            <p style="margin:0;line-height:2;">{career_links}</p>
        </div>

        <hr style="border:none;border-top:1px solid #eee;margin:20px 0 15px;">
        <p style="color:#999;font-size:12px;text-align:center;">
            Job Hunter v2.0 | 매일 자동 발송 | GitHub Actions
        </p>
    </div>
</body></html>"""
    return html


def build_no_jobs_html() -> str:
    today = datetime.now().strftime("%Y년 %m월 %d일")

    career_links = ""
    for name, info in COMPANY_CAREER_PAGES.items():
        career_links += f'<a href="{info["url"]}" style="color:#3498db;text-decoration:none;display:block;margin:3px 0;">{name} → {info["location"]}</a>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
    <h2>🔍 오늘의 구인정보 ({today})</h2>
    <p style="color:#666;">오늘은 새로 올라온 공고가 없습니다.</p>
    <div style="margin-top:15px;padding:15px;background:#f8f9fa;border-radius:8px;">
        <p style="font-weight:bold;">🔗 직접 확인해 보세요:</p>
        {career_links}
    </div>
</body></html>"""


# ═══════════════════════════════════════════════════════════
# 이메일 발송
# ═══════════════════════════════════════════════════════════

def send_email(html_content: str, job_count: int):
    sender = CONFIG["sender_email"]
    password = CONFIG["sender_app_password"]

    if not password:
        print("\n⚠️  Gmail App Password 미설정 → HTML 파일로 저장")
        filename = f"job_report_{datetime.now().strftime('%Y%m%d')}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"   📄 저장: {filename}")
        return

    today = datetime.now().strftime("%m/%d")
    subject = f"[Job Hunter] {today} 구인정보 ({job_count}건)" if job_count > 0 \
              else f"[Job Hunter] {today} 신규 공고 없음"

    for recipient in CONFIG["recipients"]:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient
            msg.attach(MIMEText(html_content, "html", "utf-8"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender, password)
                server.sendmail(sender, recipient, msg.as_string())
            print(f"  ✉️  발송 완료 → {recipient}")
        except Exception as e:
            print(f"  ❌ 발송 실패 ({recipient}): {e}")


# ═══════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print(f"  🔍 Job Hunter v2.0 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    seen = load_seen_jobs()
    print(f"\n📋 기존 이력: {len(seen)}건")

    print("\n🔎 구인정보 수집 중...")
    all_jobs = []

    print("\n  [API 소스]")
    all_jobs.extend(fetch_adzuna_jobs())
    all_jobs.extend(fetch_jsearch_jobs())

    print("\n  [🏢 대기업 채용페이지]")
    all_jobs.extend(fetch_all_company_jobs())

    print("\n  [🇰🇷 한인 사이트]")
    all_jobs.extend(fetch_dalsaram_jobs())
    all_jobs.extend(fetch_dalkora_jobs())
    all_jobs.extend(fetch_koreadaily_jobs())

    print(f"\n📊 총 수집: {len(all_jobs)}건")

    new_jobs = deduplicate_and_sort(all_jobs, seen)
    print(f"🆕 신규: {len(new_jobs)}건")

    if new_jobs:
        html = build_email_html(new_jobs)
        send_email(html, len(new_jobs))
        for job in new_jobs:
            seen.add(job["_id"])
    else:
        send_email(build_no_jobs_html(), 0)

    save_seen_jobs(seen)
    print(f"\n✅ 완료! ({datetime.now().strftime('%H:%M')})")


if __name__ == "__main__":
    main()
