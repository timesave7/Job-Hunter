"""
Dean's TQQQ Daily Signal Checker v2.1
=======================================
GitHub Actions 자동 실행 + 이메일 발송 버전
커멘드 창 출력 내용과 동일한 정보를 이메일로 전송
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
CRASH_1_PCT = 0.40
CRASH_2_PCT = 0.20

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
# 이메일 HTML 생성 (커멘드 창 출력과 동일 정보)
# ─────────────────────────────────────────────
def build_signal_html(s):
    tqqq_drop  = (s['tqqq_price'] - s['tqqq_ath']) / s['tqqq_ath'] * 100
    crash1_hit = s['tqqq_price'] <= s['crash_1']
    crash2_hit = s['tqqq_price'] <= s['crash_2']

    # ── 오늘 액션 결정 ──
    action_lines = []
    if crash2_hit:
        action_color = "#e74c3c"
        action_icon = "🎯"
        action_lines.append(f"Crash Hunter 2차 발동! (ATH 대비 {tqqq_drop:.1f}%)")
        action_lines.append("→ SPAXX 잔여 50% 전액 → TQQQ 매수")
    elif crash1_hit:
        action_color = "#e67e22"
        action_icon = "🎯"
        action_lines.append(f"Crash Hunter 1차 발동! (ATH 대비 {tqqq_drop:.1f}%)")
        action_lines.append("→ SPAXX 50% → TQQQ 매수")
    elif not s['above150']:
        if s['break_days'] >= 10:
            action_color = "#e74c3c"
            action_icon = "🔴"
            action_lines.append(f"2단계 매도! ({s['break_days']}거래일 이탈)")
            action_lines.append("→ 나머지 TQQQ 50% → SPAXX 전량 이동")
        else:
            remain = max(0, 10 - s['break_days'])
            action_color = "#f39c12"
            action_icon = "🟡"
            action_lines.append(f"1단계 매도 진행 중 ({s['break_days']}거래일째)")
            action_lines.append(f"→ {remain}거래일 후에도 이탈 지속 시 2단계 실행")
            action_lines.append("→ 2주 내 복귀 시 SPAXX 50% → TQQQ 재매수")
    elif s['buy_ready']:
        action_color = "#27ae60"
        action_icon = "🟢"
        action_lines.append("매수 신호 발동!")
        action_lines.append("→ SPAXX 전액 → TQQQ 100% 매수")
    else:
        action_color = "#27ae60"
        action_icon = "🟢"
        action_lines.append("보유 유지")
        action_lines.append("→ 매도/매수 신호 없음 — TQQQ 100% 보유")

    action_html = "<br>".join(action_lines)

    # ── 체크 아이콘 ──
    def chk(v):
        return "✅" if v else "❌"

    # ── 매도 신호 체크 HTML ──
    if s['above150']:
        sell_html = """
            <tr><td style="padding:8px;">150일선</td>
                <td style="padding:8px;text-align:right;">✅ 이탈 없음</td></tr>"""
    else:
        remain = max(0, 10 - s['break_days'])
        sell_html = f"""
            <tr><td style="padding:8px;">150일선</td>
                <td style="padding:8px;text-align:right;">❌ 이탈 중 ({s['break_days']}거래일째)</td></tr>"""
        if remain > 0:
            sell_html += f"""
            <tr><td style="padding:8px;">2단계까지</td>
                <td style="padding:8px;text-align:right;color:#e67e22;font-weight:bold;">{remain}거래일 남음</td></tr>"""
        else:
            sell_html += """
            <tr><td style="padding:8px;">2단계 조건</td>
                <td style="padding:8px;text-align:right;color:#e74c3c;font-weight:bold;">⚠️ 충족! (10거래일 초과)</td></tr>"""

    # ── 이동평균선 상태 ──
    ma150_status = "✅ 위" if s['above150'] else f"❌ 이탈 ({s['break_days']}거래일째)"
    ma200_status = "✅ 위" if s['above200'] else "❌ 아래"
    gc_status = "✅ 정배열" if s['golden_cross'] else "❌ 역배열"

    # ── 전체 HTML ──
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             max-width:640px;margin:0 auto;padding:16px;background:#f5f5f5;">

    <!-- 헤더 -->
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;
                padding:20px 24px;border-radius:10px 10px 0 0;">
        <h1 style="margin:0;font-size:20px;">📊 Dean's TQQQ 일일 신호</h1>
        <p style="margin:6px 0 0;opacity:0.85;font-size:13px;">
            {s['date']} &nbsp;|&nbsp; 🕐 수집: {s['fetch_time']}
        </p>
    </div>

    <div style="background:white;padding:20px 24px;border-radius:0 0 10px 10px;
                box-shadow:0 2px 10px rgba(0,0,0,0.1);">

        <!-- ⚡ 오늘 액션 -->
        <div style="background:{action_color};color:white;padding:16px 20px;border-radius:8px;
                    margin-bottom:20px;">
            <div style="font-size:15px;font-weight:bold;margin-bottom:6px;">⚡ 오늘 액션</div>
            <div style="font-size:14px;line-height:1.7;">{action_icon} {action_html}</div>
        </div>

        <!-- 💰 현재가 -->
        <div style="display:flex;gap:10px;margin-bottom:20px;">
            <div style="flex:1;background:#f8f9fa;border-radius:8px;padding:12px;text-align:center;">
                <div style="color:#888;font-size:11px;">QQQ</div>
                <div style="font-size:22px;font-weight:bold;color:#2c3e50;">${s['qqq_price']}</div>
            </div>
            <div style="flex:1;background:#f8f9fa;border-radius:8px;padding:12px;text-align:center;">
                <div style="color:#888;font-size:11px;">TQQQ</div>
                <div style="font-size:22px;font-weight:bold;color:#2c3e50;">${s['tqqq_price']}</div>
                <div style="font-size:11px;color:#e74c3c;">ATH 대비 {tqqq_drop:+.1f}%</div>
            </div>
        </div>

        <!-- 📉 이동평균선 -->
        <h3 style="margin:0 0 8px;font-size:14px;color:#555;">📉 이동평균선</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:18px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:7px;color:#888;">50일선</td>
                <td style="padding:7px;text-align:center;font-weight:500;">${s['ma50']}</td>
                <td style="padding:7px;text-align:right;">{gc_status}</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:7px;color:#888;">150일선</td>
                <td style="padding:7px;text-align:center;font-weight:500;">${s['ma150']}</td>
                <td style="padding:7px;text-align:right;">{ma150_status}</td>
            </tr>
            <tr>
                <td style="padding:7px;color:#888;">200일선</td>
                <td style="padding:7px;text-align:center;font-weight:500;">${s['ma200']}</td>
                <td style="padding:7px;text-align:right;">{ma200_status}</td>
            </tr>
        </table>

        <!-- 🔴 매도 신호 체크 -->
        <h3 style="margin:0 0 8px;font-size:14px;color:#555;">🔴 매도 신호 체크</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:18px;">
            {sell_html}
        </table>

        <!-- 🟢 매수 신호 체크 -->
        <h3 style="margin:0 0 8px;font-size:14px;color:#555;">🟢 매수 신호 체크</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:18px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:7px;">200일선 위 2일 연속</td>
                <td style="padding:7px;text-align:right;">{chk(s['above200_2days'])}</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:7px;">정배열 (50 &gt; 200)</td>
                <td style="padding:7px;text-align:right;">{chk(s['golden_cross'])}</td>
            </tr>
            <tr>
                <td style="padding:7px;font-weight:bold;">최종 매수 신호</td>
                <td style="padding:7px;text-align:right;font-weight:bold;">{chk(s['buy_ready'])} {'발동!' if s['buy_ready'] else '미충족'}</td>
            </tr>
        </table>

        <!-- 🎯 Crash Hunter -->
        <h3 style="margin:0 0 8px;font-size:14px;color:#555;">🎯 Crash Hunter</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:18px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:7px;color:#888;">TQQQ ATH</td>
                <td style="padding:7px;text-align:right;">${s['tqqq_ath']} &nbsp;({s['tqqq_ath_date']}) ← 자동 계산</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:7px;color:#888;">현재가</td>
                <td style="padding:7px;text-align:right;">${s['tqqq_price']} &nbsp;({tqqq_drop:+.1f}%)</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:7px;color:#888;">1차 (-60%)</td>
                <td style="padding:7px;text-align:right;">${s['crash_1']} → {'🎯 도달!' if crash1_hit else '미달 ✅'}</td>
            </tr>
            <tr>
                <td style="padding:7px;color:#888;">2차 (-80%)</td>
                <td style="padding:7px;text-align:right;">${s['crash_2']} → {'🎯 도달!' if crash2_hit else '미달 ✅'}</td>
            </tr>
        </table>

        <!-- 하단 안내 -->
        <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
        <p style="color:#aaa;font-size:10px;text-align:center;margin:0;line-height:1.6;">
            장 마감 후 자동 실행 | GitHub Actions<br>
            모든 값 자동 계산 — 수동 입력 불필요 | 투자 참고용
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
    print(f"  📊 Dean's TQQQ 일일 신호  |  {s['date']}")
    print(f"  🕐 수집 시각: {s['fetch_time']} (실시간)")
    print(LINE)

    print(f"\n  💰 현재가")
    print(f"     QQQ:   ${s['qqq_price']:>8.2f}")
    print(f"     TQQQ:  ${s['tqqq_price']:>8.2f}")

    print(f"\n  📉 이동평균선")
    print(f"     50일선:   ${s['ma50']:>8.2f}")
    ma150_str = "✅ 위" if s['above150'] else f"❌ 이탈 중 ({s['break_days']}거래일째)"
    gc_str    = "✅ 정배열" if s['golden_cross'] else "❌ 역배열"
    print(f"     150일선:  ${s['ma150']:>8.2f}  →  {ma150_str}")
    print(f"     200일선:  ${s['ma200']:>8.2f}  →  {'✅ 위' if s['above200'] else '❌ 아래'}  |  {gc_str}")

    print(f"\n  🔴 매도 신호 체크")
    if s['above150']:
        print(f"     150일선: ✅ 이탈 없음")
    else:
        remain = max(0, 10 - s['break_days'])
        print(f"     150일선: ❌ 이탈 중 ({s['break_days']}거래일째)")
        if remain > 0:
            print(f"     2단계까지: {remain}거래일 남음")
        else:
            print(f"     ⚠️  2단계 조건 충족! (10거래일 초과)")

    print(f"\n  🟢 매수 신호 체크")
    print(f"     200일선 위 2일 연속: {'✅' if s['above200_2days'] else '❌'}")
    print(f"     정배열 (50>200):     {'✅' if s['golden_cross'] else '❌'}")
    print(f"     최종 매수 신호:      {'✅ 발동!' if s['buy_ready'] else '❌ 미충족'}")

    print(f"\n  🎯 Crash Hunter")
    print(f"     TQQQ ATH:  ${s['tqqq_ath']:.2f}  ({s['tqqq_ath_date']})  ← 자동 계산")
    print(f"     현재가:    ${s['tqqq_price']:.2f}  ({tqqq_drop:+.1f}%)")
    print(f"     1차(-60%): ${s['crash_1']:.2f}  →  {'🎯 도달!' if crash1_hit else '미달 ✅'}")
    print(f"     2차(-80%): ${s['crash_2']:.2f}  →  {'🎯 도달!' if crash2_hit else '미달 ✅'}")

    print(f"\n{LINE}")
    print(f"  ⚡ 오늘 액션")
    print(LINE)

    if crash2_hit:
        print(f"\n  🎯  Crash Hunter 2차 발동! (ATH 대비 {tqqq_drop:.1f}%)")
        print(f"       → SPAXX 잔여 50% 전액 → TQQQ 매수")
    elif crash1_hit:
        print(f"\n  🎯  Crash Hunter 1차 발동! (ATH 대비 {tqqq_drop:.1f}%)")
        print(f"       → SPAXX 50% → TQQQ 매수")

    if not s['above150']:
        if s['break_days'] >= 10:
            print(f"\n  🔴  2단계 매도! ({s['break_days']}거래일 이탈)")
            print(f"       → 나머지 TQQQ 50% → SPAXX 전량 이동")
        else:
            remain = max(0, 10 - s['break_days'])
            print(f"\n  🟡  1단계 매도 진행 중 ({s['break_days']}거래일째)")
            print(f"       → {remain}거래일 후에도 이탈 지속 시 2단계 실행")
            print(f"       → 2주 내 복귀 시 SPAXX 50% → TQQQ 재매수")
    elif s['buy_ready']:
        print(f"\n  🟢  매수 신호 발동!")
        print(f"       → SPAXX 전액 → TQQQ 100% 매수")
    else:
        print(f"\n  🟢  보유 유지")
        print(f"       → 매도/매수 신호 없음 — TQQQ 100% 보유")

    print(f"\n{LINE}")


# ─────────────────────────────────────────────
# 이메일 발송
# ─────────────────────────────────────────────
def send_email(html_content, s):
    sender = CONFIG["sender_email"]
    password = CONFIG["sender_app_password"]

    if not password:
        print("⚠️  이메일 미설정 → 콘솔 출력만")
        return

    if s['buy_ready']:
        signal = "🟢 매수 발동"
    elif not s['above150'] and s['break_days'] >= 10:
        signal = "🔴 2단계 매도"
    elif not s['above150']:
        signal = f"🟡 이탈 {s['break_days']}일째"
    else:
        signal = "🟢 보유 유지"

    subject = f"[TQQQ] {signal} | QQQ ${s['qqq_price']} | TQQQ ${s['tqqq_price']} | {s['date']}"

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
