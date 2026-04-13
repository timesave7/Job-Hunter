"""
Dean's TQQQ Daily Signal Checker v2.0
=======================================
GitHub Actions 자동 실행 + 이메일 발송 버전
매일 장 마감 후 자동 실행 → 결과를 이메일로 전송
"""

import sys
import subprocess

def install_packages():
    for package in ['yfinance', 'pandas']:
        try:
            __import__(package)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])

install_packages()

import yfinance as yf
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
CRASH_1_PCT = 0.35
CRASH_2_PCT = 0.20

CONFIG = {
    "sender_email": os.environ.get("SENDER_EMAIL", ""),
    "sender_app_password": os.environ.get("GMAIL_APP_PASSWORD", ""),
    "recipients": [
        "timesave7@gmail.com",
        # "seunggy98@gmail.com",  # ← 아들 추가 시 주석 해제
    ],
}

# ─────────────────────────────────────────────
# 데이터 수집
# ─────────────────────────────────────────────
def get_signals():
    print("\n⏳ 실시간 데이터 수집 중...")

    yf.set_tz_cache_location("/tmp/yf_no_cache")

    qqq_ticker  = yf.Ticker("QQQ")
    tqqq_ticker = yf.Ticker("TQQQ")

    qqq_hist  = qqq_ticker.history(period="18mo", auto_adjust=True, repair=False)
    tqqq_hist = tqqq_ticker.history(period="5y",  auto_adjust=True, repair=False)

    if qqq_hist.empty or tqqq_hist.empty:
        print("❌ 데이터 수집 실패.")
        return None

    now = datetime.now().strftime("%H:%M:%S")
    print(f"✅ 수집 완료 ({now})")

    df = qqq_hist.copy()
    df['MA50']     = df['Close'].rolling(50).mean()
    df['MA150']    = df['Close'].rolling(150).mean()
    df['MA200']    = df['Close'].rolling(200).mean()
    df['above150'] = df['Close'] > df['MA150']
    df['above200'] = df['Close'] > df['MA200']

    tqqq_ath      = tqqq_hist['Close'].max()
    tqqq_ath_date = tqqq_hist['Close'].idxmax().strftime("%Y-%m-%d")
    tqqq_price    = tqqq_hist['Close'].iloc[-1]
    crash_1       = tqqq_ath * CRASH_1_PCT
    crash_2       = tqqq_ath * CRASH_2_PCT

    break_days = 0
    if not df['above150'].iloc[-1]:
        for i in range(len(df) - 1, -1, -1):
            if not df['above150'].iloc[i]:
                break_days += 1
            else:
                break

    above200_2days = bool(df['above200'].iloc[-1]) and bool(df['above200'].iloc[-2])
    golden_cross   = df['MA50'].iloc[-1] > df['MA200'].iloc[-1]
    above150       = bool(df['above150'].iloc[-1])
    buy_ready      = above200_2days and golden_cross and above150

    return {
        'date'          : df.index[-1].strftime("%Y년 %m월 %d일"),
        'fetch_time'    : now,
        'qqq_price'     : round(df['Close'].iloc[-1], 2),
        'tqqq_price'    : round(tqqq_price, 2),
        'tqqq_ath'      : round(tqqq_ath, 2),
        'tqqq_ath_date' : tqqq_ath_date,
        'crash_1'       : round(crash_1, 2),
        'crash_2'       : round(crash_2, 2),
        'ma50'          : round(df['MA50'].iloc[-1], 2),
        'ma150'         : round(df['MA150'].iloc[-1], 2),
        'ma200'         : round(df['MA200'].iloc[-1], 2),
        'above150'      : above150,
        'above200'      : bool(df['above200'].iloc[-1]),
        'above200_2days': above200_2days,
        'golden_cross'  : golden_cross,
        'break_days'    : break_days,
        'buy_ready'     : buy_ready,
    }

# ─────────────────────────────────────────────
# 이메일 HTML 생성
# ─────────────────────────────────────────────
def build_signal_html(s):
    tqqq_drop  = (s['tqqq_price'] - s['tqqq_ath']) / s['tqqq_ath'] * 100
    crash1_hit = s['tqqq_price'] <= s['crash_1']
    crash2_hit = s['tqqq_price'] <= s['crash_2']

    # 오늘 액션 결정
    if crash2_hit:
        action_color = "#e74c3c"
        action_icon = "🎯"
        action_text = f"Crash Hunter 2차 발동! (ATH 대비 {tqqq_drop:.1f}%)<br>→ SPAXX 잔여 50% 전액 → TQQQ 매수"
    elif crash1_hit:
        action_color = "#e67e22"
        action_icon = "🎯"
        action_text = f"Crash Hunter 1차 발동! (ATH 대비 {tqqq_drop:.1f}%)<br>→ SPAXX 50% → TQQQ 매수"
    elif not s['above150']:
        if s['break_days'] >= 10:
            action_color = "#e74c3c"
            action_icon = "🔴"
            action_text = f"2단계 매도! ({s['break_days']}거래일 이탈)<br>→ 나머지 TQQQ 50% → SPAXX 전량 이동"
        else:
            remain = max(0, 10 - s['break_days'])
            action_color = "#f39c12"
            action_icon = "🟡"
            action_text = f"1단계 매도 진행 중 ({s['break_days']}거래일째)<br>→ {remain}거래일 후에도 이탈 지속 시 2단계<br>→ 2주 내 복귀 시 SPAXX 50% → TQQQ 재매수"
    elif s['buy_ready']:
        action_color = "#27ae60"
        action_icon = "🟢"
        action_text = "매수 신호 발동!<br>→ SPAXX 전액 → TQQQ 100% 매수"
    else:
        action_color = "#27ae60"
        action_icon = "🟢"
        action_text = "보유 유지<br>→ 매도/매수 신호 없음 — TQQQ 100% 보유"

    # 체크 아이콘
    def chk(v): return "✅" if v else "❌"

    ma150_status = "✅ 위" if s['above150'] else f"❌ 이탈 ({s['break_days']}거래일째)"
    ma200_status = "✅ 위" if s['above200'] else "❌ 아래"
    gc_status = "✅ 정배열" if s['golden_cross'] else "❌ 역배열"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             max-width:600px;margin:0 auto;padding:20px;background:#f5f5f5;">

    <!-- 헤더 -->
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;
                padding:25px 30px;border-radius:10px 10px 0 0;">
        <h1 style="margin:0;font-size:22px;">📊 TQQQ 일일 신호</h1>
        <p style="margin:8px 0 0;opacity:0.9;font-size:14px;">{s['date']}</p>
    </div>

    <div style="background:white;padding:25px 30px;border-radius:0 0 10px 10px;
                box-shadow:0 2px 10px rgba(0,0,0,0.1);">

        <!-- 오늘 액션 (가장 중요) -->
        <div style="background:{action_color};color:white;padding:20px;border-radius:8px;
                    margin-bottom:25px;font-size:16px;">
            <strong>{action_icon} 오늘 액션</strong><br>
            <span style="font-size:15px;">{action_text}</span>
        </div>

        <!-- 현재가 -->
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
            <tr>
                <td style="padding:12px;background:#f8f9fa;border-radius:8px 0 0 8px;text-align:center;width:50%;">
                    <div style="color:#888;font-size:12px;">QQQ</div>
                    <div style="font-size:24px;font-weight:bold;color:#2c3e50;">${s['qqq_price']}</div>
                </td>
                <td style="padding:12px;background:#f8f9fa;border-radius:0 8px 8px 0;text-align:center;width:50%;">
                    <div style="color:#888;font-size:12px;">TQQQ</div>
                    <div style="font-size:24px;font-weight:bold;color:#2c3e50;">${s['tqqq_price']}</div>
                    <div style="font-size:11px;color:#e74c3c;">ATH 대비 {tqqq_drop:+.1f}%</div>
                </td>
            </tr>
        </table>

        <!-- 이동평균선 -->
        <h3 style="margin:0 0 10px;font-size:14px;color:#555;">📉 이동평균선</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">50일선</td>
                <td style="padding:8px;text-align:right;font-weight:500;">${s['ma50']}</td>
                <td style="padding:8px;text-align:right;">{gc_status}</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">150일선</td>
                <td style="padding:8px;text-align:right;font-weight:500;">${s['ma150']}</td>
                <td style="padding:8px;text-align:right;">{ma150_status}</td>
            </tr>
            <tr>
                <td style="padding:8px;color:#888;">200일선</td>
                <td style="padding:8px;text-align:right;font-weight:500;">${s['ma200']}</td>
                <td style="padding:8px;text-align:right;">{ma200_status}</td>
            </tr>
        </table>

        <!-- 매수 신호 체크 -->
        <h3 style="margin:0 0 10px;font-size:14px;color:#555;">🟢 매수 신호</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;">200일선 위 2일 연속</td>
                <td style="padding:8px;text-align:right;">{chk(s['above200_2days'])}</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;">정배열 (50 &gt; 200)</td>
                <td style="padding:8px;text-align:right;">{chk(s['golden_cross'])}</td>
            </tr>
            <tr>
                <td style="padding:8px;font-weight:bold;">최종 매수 신호</td>
                <td style="padding:8px;text-align:right;font-weight:bold;">{chk(s['buy_ready'])} {'발동!' if s['buy_ready'] else '미충족'}</td>
            </tr>
        </table>

        <!-- Crash Hunter -->
        <h3 style="margin:0 0 10px;font-size:14px;color:#555;">🎯 Crash Hunter</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:15px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">TQQQ ATH</td>
                <td style="padding:8px;text-align:right;">${s['tqqq_ath']} ({s['tqqq_ath_date']})</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">1차 (-65%)</td>
                <td style="padding:8px;text-align:right;">${s['crash_1']} → {'🎯 도달!' if crash1_hit else '미달'}</td>
            </tr>
            <tr>
                <td style="padding:8px;color:#888;">2차 (-80%)</td>
                <td style="padding:8px;text-align:right;">${s['crash_2']} → {'🎯 도달!' if crash2_hit else '미달'}</td>
            </tr>
        </table>

        <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
        <p style="color:#999;font-size:11px;text-align:center;">
            장 마감 후 자동 실행 | GitHub Actions | 투자 참고용
        </p>
    </div>
</body></html>"""
    return html


# ─────────────────────────────────────────────
# 콘솔 출력 (로컬 테스트용)
# ─────────────────────────────────────────────
def print_signal(s):
    tqqq_drop  = (s['tqqq_price'] - s['tqqq_ath']) / s['tqqq_ath'] * 100
    crash1_hit = s['tqqq_price'] <= s['crash_1']
    crash2_hit = s['tqqq_price'] <= s['crash_2']

    LINE = "=" * 58
    print(f"\n{LINE}")
    print(f"  📊 TQQQ 일일 신호  |  {s['date']}")
    print(f"  🕐 수집: {s['fetch_time']}")
    print(LINE)
    print(f"\n  💰 QQQ: ${s['qqq_price']}  |  TQQQ: ${s['tqqq_price']} ({tqqq_drop:+.1f}%)")
    print(f"  📉 50일: ${s['ma50']}  150일: ${s['ma150']}  200일: ${s['ma200']}")
    print(f"  🟢 매수신호: {'✅ 발동!' if s['buy_ready'] else '❌ 미충족'}")
    print(f"  🎯 Crash1: ${s['crash_1']} {'🎯도달' if crash1_hit else '미달'}")
    print(f"  🎯 Crash2: ${s['crash_2']} {'🎯도달' if crash2_hit else '미달'}")
    print(LINE)


# ─────────────────────────────────────────────
# 이메일 발송
# ─────────────────────────────────────────────
def send_email(html_content, s):
    sender = CONFIG["sender_email"]
    password = CONFIG["sender_app_password"]

    if not password:
        print("⚠️  이메일 미설정 → 콘솔 출력만")
        return

    # 제목에 핵심 신호 포함
    if s['buy_ready']:
        signal = "🟢 매수 발동"
    elif not s['above150'] and s['break_days'] >= 10:
        signal = "🔴 2단계 매도"
    elif not s['above150']:
        signal = f"🟡 이탈 {s['break_days']}일째"
    else:
        signal = "🟢 보유 유지"

    subject = f"[TQQQ] {signal} | QQQ ${s['qqq_price']} | {s['date']}"

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
            print(f"  ✉️  발송 → {recipient}")
        except Exception as e:
            print(f"  ❌ 발송 실패 ({recipient}): {e}")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
if __name__ == "__main__":
    s = get_signals()
    if s:
        print_signal(s)
        html = build_signal_html(s)
        send_email(html, s)
