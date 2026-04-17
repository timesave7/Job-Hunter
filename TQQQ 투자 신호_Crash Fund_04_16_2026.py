"""
Dean's TQQQ Daily Signal Checker v3.0
=======================================
배당 Crash Fund 전략 기준 버전
GitHub Actions 자동 실행 + 이메일 발송
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

# ★ 배당CF전략 핵심 파라미터
COST_BASIS    = 43.50  # TQQQ 취득단가 — 전환 발생 시 이메일 안내에 따라 수동 업데이트
TRIGGER_PCT   = 0.50   # 전환 트리거: 취득단가 대비 +50%
TRANSFER_PCT  = 0.50   # 수익분의 50%를 배당ETF로 전환
MAX_DIV_PCT   = 0.30   # 배당ETF 최대 비중 30% (포트폴리오 대비)

# Crash Hunter 재매수 기준
CRASH_1_PCT   = 0.45   # ATH 대비 -55% → 현금 50% 재투입
CRASH_2_PCT   = 0.20   # ATH 대비 -80% → 잔여 전액 재투입

CONFIG = {
    "sender_email": os.environ.get("SENDER_EMAIL", ""),
    "sender_app_password": os.environ.get("GMAIL_APP_PASSWORD", ""),
    "recipients": [
        "timesave7@gmail.com",
        "seunggy98@gmail.com",
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
    jepi_ticker = yf.Ticker("JEPI")
    jepq_ticker = yf.Ticker("JEPQ")

    qqq_hist  = qqq_ticker.history(period="18mo", auto_adjust=True, repair=False)
    tqqq_hist = tqqq_ticker.history(period="5y",  auto_adjust=True, repair=False)
    jepi_hist = jepi_ticker.history(period="5d",  auto_adjust=True, repair=False)
    jepq_hist = jepq_ticker.history(period="5d",  auto_adjust=True, repair=False)

    if qqq_hist.empty or tqqq_hist.empty:
        print("❌ 데이터 수집 실패.")
        return None

    now = datetime.now().strftime("%H:%M:%S")
    print(f"✅ 수집 완료 ({now})")

    # QQQ 이동평균 (추세 참고용)
    df = qqq_hist.copy()
    df['MA50']  = df['Close'].rolling(50).mean()
    df['MA150'] = df['Close'].rolling(150).mean()
    df['MA200'] = df['Close'].rolling(200).mean()

    # TQQQ 기본값
    tqqq_price    = tqqq_hist['Close'].iloc[-1]
    tqqq_ath      = tqqq_hist['Close'].max()
    tqqq_ath_date = tqqq_hist['Close'].idxmax().strftime("%Y-%m-%d")
    tqqq_drop_pct = (tqqq_price - tqqq_ath) / tqqq_ath * 100
    crash_1_price = tqqq_ath * CRASH_1_PCT
    crash_2_price = tqqq_ath * CRASH_2_PCT

    # 배당CF전략: 전환 트리거 계산
    trigger_price   = COST_BASIS * (1 + TRIGGER_PCT)
    conv_triggered  = tqqq_price >= trigger_price
    gain_pct        = (tqqq_price - COST_BASIS) / COST_BASIS * 100

    # Crash Hunter 발동 여부
    crash_1_hit = tqqq_price <= crash_1_price
    crash_2_hit = tqqq_price <= crash_2_price

    # 배당ETF 현재가
    jepi_price = jepi_hist['Close'].iloc[-1] if not jepi_hist.empty else None
    jepq_price = jepq_hist['Close'].iloc[-1] if not jepq_hist.empty else None

    # 추세 참고 지표
    above150     = bool(df['MA150'].iloc[-1] > 0 and df['Close'].iloc[-1] > df['MA150'].iloc[-1])
    golden_cross = bool(df['MA50'].iloc[-1] > df['MA200'].iloc[-1])

    return {
        'date'           : df.index[-1].strftime("%Y년 %m월 %d일"),
        'fetch_time'     : now,
        'qqq_price'      : round(df['Close'].iloc[-1], 2),
        'tqqq_price'     : round(tqqq_price, 2),
        'tqqq_ath'       : round(tqqq_ath, 2),
        'tqqq_ath_date'  : tqqq_ath_date,
        'tqqq_drop_pct'  : tqqq_drop_pct,
        'crash_1_price'  : round(crash_1_price, 2),
        'crash_2_price'  : round(crash_2_price, 2),
        'crash_1_hit'    : crash_1_hit,
        'crash_2_hit'    : crash_2_hit,
        'cost_basis'     : COST_BASIS,
        'trigger_price'  : round(trigger_price, 2),
        'conv_triggered' : conv_triggered,
        'gain_pct'       : gain_pct,
        'jepi_price'     : round(jepi_price, 2) if jepi_price else 'N/A',
        'jepq_price'     : round(jepq_price, 2) if jepq_price else 'N/A',
        'above150'       : above150,
        'golden_cross'   : golden_cross,
        'ma50'           : round(df['MA50'].iloc[-1], 2),
        'ma150'          : round(df['MA150'].iloc[-1], 2),
        'ma200'          : round(df['MA200'].iloc[-1], 2),
    }

# ─────────────────────────────────────────────
# 이메일 HTML 생성
# ─────────────────────────────────────────────
def build_signal_html(s):

    # ── 오늘 액션 결정 ──
    if s['crash_2_hit']:
        action_color = "#c0392b"
        action_icon  = "🚨"
        action_title = "Crash Hunter L2 발동!"
        action_lines = [
            f"TQQQ ATH 대비 {s['tqqq_drop_pct']:.1f}% 폭락",
            "→ 배당ETF 현금 잔여 전액 → TQQQ 재매수",
        ]
    elif s['crash_1_hit']:
        action_color = "#e67e22"
        action_icon  = "🎯"
        action_title = "Crash Hunter L1 발동!"
        action_lines = [
            f"TQQQ ATH 대비 {s['tqqq_drop_pct']:.1f}% 폭락",
            "→ 배당ETF 현금 50% → TQQQ 재매수",
        ]
    elif s['conv_triggered']:
        action_color = "#1e8449"
        action_icon  = "💰"
        action_title = "배당ETF 전환 신호!"
        action_lines = [
            f"취득단가 ${s['cost_basis']} 대비 +{s['gain_pct']:.1f}% 달성 (목표 +{TRIGGER_PCT*100:.0f}%)",
            f"→ TQQQ 수익분의 {TRANSFER_PCT*100:.0f}% → JEPI 또는 JEPQ 전환",
            f"⚠️ 전환 완료 후 이 스크립트의 COST_BASIS를 ${s['tqqq_price']}로 업데이트하세요",
        ]
    else:
        action_color = "#2471a3"
        action_icon  = "🔵"
        action_title = "보유 유지"
        action_lines = [
            f"취득단가 ${s['cost_basis']} 대비 현재 {s['gain_pct']:+.1f}%",
            f"전환 목표가: ${s['trigger_price']} ({TRIGGER_PCT*100:.0f}% 상승 시)",
            "→ 전환/재매수 신호 없음",
        ]

    action_html = "<br>".join(action_lines)

    def chk(v):
        return "✅" if v else "❌"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             max-width:660px;margin:0 auto;padding:16px;background:#f0f2f5;">

    <!-- 헤더 -->
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;
                padding:20px 24px;border-radius:10px 10px 0 0;">
        <h1 style="margin:0;font-size:20px;">💰 Dean's TQQQ 배당CF 전략 신호</h1>
        <p style="margin:6px 0 0;opacity:0.8;font-size:13px;">
            {s['date']} &nbsp;|&nbsp; 🕐 수집: {s['fetch_time']}
        </p>
    </div>

    <div style="background:white;padding:20px 24px;border-radius:0 0 10px 10px;
                box-shadow:0 2px 10px rgba(0,0,0,0.1);">

        <!-- ⚡ 오늘 액션 -->
        <div style="background:{action_color};color:white;padding:16px 20px;border-radius:8px;
                    margin-bottom:20px;">
            <div style="font-size:15px;font-weight:bold;margin-bottom:6px;">{action_icon} {action_title}</div>
            <div style="font-size:14px;line-height:1.8;">{action_html}</div>
        </div>

        <!-- 💹 현재가 -->
        <div style="display:flex;gap:10px;margin-bottom:20px;">
            <div style="flex:1;background:#f8f9fa;border-radius:8px;padding:12px;text-align:center;">
                <div style="color:#888;font-size:11px;">QQQ</div>
                <div style="font-size:22px;font-weight:bold;color:#2c3e50;">${s['qqq_price']}</div>
            </div>
            <div style="flex:1;background:#f8f9fa;border-radius:8px;padding:12px;text-align:center;">
                <div style="color:#888;font-size:11px;">TQQQ</div>
                <div style="font-size:22px;font-weight:bold;color:#e67e22;">${s['tqqq_price']}</div>
                <div style="font-size:11px;color:#e74c3c;">ATH 대비 {s['tqqq_drop_pct']:+.1f}%</div>
            </div>
            <div style="flex:1;background:#f8f9fa;border-radius:8px;padding:12px;text-align:center;">
                <div style="color:#888;font-size:11px;">JEPI / JEPQ</div>
                <div style="font-size:16px;font-weight:bold;color:#27ae60;">${s['jepi_price']}</div>
                <div style="font-size:14px;font-weight:bold;color:#f39c12;">${s['jepq_price']}</div>
            </div>
        </div>

        <!-- 💰 배당CF전략 현황 -->
        <h3 style="margin:0 0 8px;font-size:14px;color:#555;">💰 배당CF전략 전환 트리거</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:18px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">취득단가 (기준가)</td>
                <td style="padding:8px;text-align:right;font-weight:bold;">${s['cost_basis']}</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">현재가 / 수익률</td>
                <td style="padding:8px;text-align:right;font-weight:bold;
                    color:{'#27ae60' if s['gain_pct']>=0 else '#e74c3c'};">
                    ${s['tqqq_price']} &nbsp; ({s['gain_pct']:+.1f}%)
                </td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">전환 목표가 (+{TRIGGER_PCT*100:.0f}%)</td>
                <td style="padding:8px;text-align:right;">${s['trigger_price']}</td>
            </tr>
            <tr>
                <td style="padding:8px;font-weight:bold;">전환 신호</td>
                <td style="padding:8px;text-align:right;font-weight:bold;">
                    {chk(s['conv_triggered'])} {'발동!' if s['conv_triggered'] else '미충족'}
                </td>
            </tr>
        </table>

        <!-- 🎯 Crash Hunter -->
        <h3 style="margin:0 0 8px;font-size:14px;color:#555;">🎯 Crash Hunter 재매수 트리거</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:18px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">TQQQ ATH</td>
                <td style="padding:8px;text-align:right;">${s['tqqq_ath']} &nbsp;({s['tqqq_ath_date']})</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">L1 재매수 (-55% / ${s['crash_1_price']})</td>
                <td style="padding:8px;text-align:right;
                    color:{'#e74c3c' if s['crash_1_hit'] else '#27ae60'};">
                    {'🚨 도달! 현금 50% 투입' if s['crash_1_hit'] else '미달 ✅'}
                </td>
            </tr>
            <tr>
                <td style="padding:8px;color:#888;">L2 재매수 (-80% / ${s['crash_2_price']})</td>
                <td style="padding:8px;text-align:right;
                    color:{'#e74c3c' if s['crash_2_hit'] else '#27ae60'};">
                    {'🚨 도달! 잔여 전액 투입' if s['crash_2_hit'] else '미달 ✅'}
                </td>
            </tr>
        </table>

        <!-- 📉 추세 참고 (보조 지표) -->
        <h3 style="margin:0 0 8px;font-size:14px;color:#aaa;">📉 추세 참고 (보조)</h3>
        <table style="width:100%;border-collapse:collapse;font-size:12px;color:#aaa;margin-bottom:18px;">
            <tr style="border-bottom:1px solid #f0f0f0;">
                <td style="padding:6px;">QQQ 150일선 ${s['ma150']}</td>
                <td style="padding:6px;text-align:right;">{'✅ 위' if s['above150'] else '❌ 아래'}</td>
            </tr>
            <tr>
                <td style="padding:6px;">정배열 (MA50 > MA200)</td>
                <td style="padding:6px;text-align:right;">{'✅' if s['golden_cross'] else '❌'}</td>
            </tr>
        </table>

        <!-- 하단 안내 -->
        <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
        <p style="color:#aaa;font-size:10px;text-align:center;margin:0;line-height:1.8;">
            장 마감 후 자동 실행 | GitHub Actions<br>
            전환 발생 시 COST_BASIS를 현재가로 수동 업데이트 필요 | 투자 참고용
        </p>
    </div>
</body></html>"""
    return html


# ─────────────────────────────────────────────
# 콘솔 출력 (로컬 테스트용)
# ─────────────────────────────────────────────
def print_signal(s):
    LINE = "=" * 58
    print(f"\n{LINE}")
    print(f"  💰 Dean's TQQQ 배당CF 전략 신호  |  {s['date']}")
    print(f"  🕐 수집 시각: {s['fetch_time']}")
    print(LINE)

    print(f"\n  💹 현재가")
    print(f"     QQQ:   ${s['qqq_price']:>8.2f}")
    print(f"     TQQQ:  ${s['tqqq_price']:>8.2f}  (ATH 대비 {s['tqqq_drop_pct']:+.1f}%)")
    print(f"     JEPI:  ${s['jepi_price']}   JEPQ: ${s['jepq_price']}")

    print(f"\n  💰 배당CF전략 전환 트리거")
    print(f"     취득단가:    ${s['cost_basis']:.2f}")
    print(f"     현재가:      ${s['tqqq_price']:.2f}  ({s['gain_pct']:+.1f}%)")
    print(f"     전환 목표가: ${s['trigger_price']:.2f}  (+{TRIGGER_PCT*100:.0f}%)")
    print(f"     전환 신호:   {'✅ 발동!' if s['conv_triggered'] else '❌ 미충족'}")

    print(f"\n  🎯 Crash Hunter 재매수 트리거")
    print(f"     ATH:  ${s['tqqq_ath']:.2f}  ({s['tqqq_ath_date']})")
    print(f"     L1(-55%): ${s['crash_1_price']:.2f}  →  {'🚨 도달!' if s['crash_1_hit'] else '미달 ✅'}")
    print(f"     L2(-80%): ${s['crash_2_price']:.2f}  →  {'🚨 도달!' if s['crash_2_hit'] else '미달 ✅'}")

    print(f"\n  📉 추세 참고")
    print(f"     150일선: {'✅ 위' if s['above150'] else '❌ 아래'}   정배열: {'✅' if s['golden_cross'] else '❌'}")

    print(f"\n{LINE}")
    print(f"  ⚡ 오늘 액션")
    print(LINE)

    if s['crash_2_hit']:
        print(f"\n  🚨  Crash Hunter L2 발동! (ATH 대비 {s['tqqq_drop_pct']:.1f}%)")
        print(f"       → 배당ETF 현금 잔여 전액 → TQQQ 재매수")
    elif s['crash_1_hit']:
        print(f"\n  🎯  Crash Hunter L1 발동! (ATH 대비 {s['tqqq_drop_pct']:.1f}%)")
        print(f"       → 배당ETF 현금 50% → TQQQ 재매수")
    elif s['conv_triggered']:
        print(f"\n  💰  배당ETF 전환 신호! (+{s['gain_pct']:.1f}% 달성)")
        print(f"       → TQQQ 수익분 {TRANSFER_PCT*100:.0f}% → JEPI 또는 JEPQ 전환")
        print(f"       ⚠️  전환 후 COST_BASIS를 ${s['tqqq_price']}로 업데이트하세요")
    else:
        print(f"\n  🔵  보유 유지 (현재 {s['gain_pct']:+.1f}%, 목표 +{TRIGGER_PCT*100:.0f}%)")
        print(f"       → 전환/재매수 신호 없음")

    print(f"\n{LINE}\n")


# ─────────────────────────────────────────────
# 이메일 발송
# ─────────────────────────────────────────────
def send_email(html_content, s):
    sender   = CONFIG["sender_email"]
    password = CONFIG["sender_app_password"]

    if not password:
        print("⚠️  이메일 미설정 → 콘솔 출력만")
        return

    if s['crash_2_hit']:
        signal = "🚨 L2 재매수"
    elif s['crash_1_hit']:
        signal = "🎯 L1 재매수"
    elif s['conv_triggered']:
        signal = "💰 배당ETF 전환!"
    else:
        signal = f"🔵 보유 ({s['gain_pct']:+.1f}%)"

    subject = f"[CF전략] {signal} | TQQQ ${s['tqqq_price']} | {s['date']}"

    for recipient in CONFIG["recipients"]:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = sender
            msg["To"]      = recipient
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
