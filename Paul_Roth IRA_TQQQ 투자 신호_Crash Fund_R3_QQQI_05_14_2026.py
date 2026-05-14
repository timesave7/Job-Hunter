"""
Paul_Roth IRA TQQQ 투자 신호 - Crash Fund 전략 R3 + QQQI (V2.4)
================================================================
GitHub Actions 자동 실행 + 이메일 발송

변경 이력:
- 2026-04-21: V2.3 (R1 룰 +50%/50%, SCHD)
- 2026-05-14: V2.4 (R3 룰 +30%/30%, QQQI 전환)

핵심 룰:
- 트리거: TQQQ 가격 ≥ CB × 1.30
- 매도: 수익분의 30%를 QQQI + 현금 50:50 분할
- Crash Hunter L1/L2/L3: ATH -55%/-70%/-80%
- 매수자금 한도: 포트폴리오 40%

state.json 기반 동적 로딩:
- cost_basis, trigger_pct, transfer_pct, div_etf, rule_version
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
import json
import os
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# state.json에서 동적 로딩 (없으면 V2.4 기본값 사용)
# ─────────────────────────────────────────────
STATE_FILE = "Paul_Roth IRA_state.json"

# V2.4 기본값 (fallback) - state.json 없을 때만 사용
DEFAULT_COST_BASIS  = 65.65          # V2.4 기준 (구 43.50)
DEFAULT_TRIGGER_PCT = 0.30           # R3 룰 (구 0.50)
DEFAULT_TRANSFER_PCT = 0.30          # R3 룰 (구 0.50)
DEFAULT_DIV_ETF     = "QQQI"         # V2.4 (구 SCHD)
DEFAULT_RULE_VERSION = "R3 (V2.4)"

def load_state():
    """state.json에서 모든 운용 파라미터를 동적으로 로드"""
    state = {
        'cost_basis'  : DEFAULT_COST_BASIS,
        'trigger_pct' : DEFAULT_TRIGGER_PCT,
        'transfer_pct': DEFAULT_TRANSFER_PCT,
        'div_etf'     : DEFAULT_DIV_ETF,
        'rule_version': DEFAULT_RULE_VERSION,
        'last_updated': 'unknown',
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            # state.json의 값으로 덮어쓰기 (없으면 기본값 유지)
            for k in ['cost_basis', 'trigger_pct', 'transfer_pct',
                      'div_etf', 'rule_version', 'last_updated']:
                if k in loaded:
                    state[k] = loaded[k]
            print(f"✅ state.json 로드:")
            print(f"   COST_BASIS = ${state['cost_basis']}")
            print(f"   RULE       = {state['rule_version']}")
            print(f"   TRIGGER    = +{state['trigger_pct']*100:.0f}% / 매도 {state['transfer_pct']*100:.0f}%")
            print(f"   DIV_ETF    = {state['div_etf']}")
            print(f"   업데이트   = {state['last_updated']}")
        except Exception as e:
            print(f"⚠️  state.json 읽기 오류 ({e}) → 기본값 사용")
    else:
        print(f"⚠️  state.json 없음 → V2.4 기본값 사용 (CB=${DEFAULT_COST_BASIS}, R3, QQQI)")
    return state

# ─────────────────────────────────────────────
# 설정 로딩
# ─────────────────────────────────────────────
_STATE        = load_state()
COST_BASIS    = _STATE['cost_basis']
TRIGGER_PCT   = _STATE['trigger_pct']    # R3: 0.30 (전환 트리거: CB × 1.30)
TRANSFER_PCT  = _STATE['transfer_pct']   # R3: 0.30 (수익분의 30% 매도)
DIV_ETF       = _STATE['div_etf']        # V2.4: QQQI
RULE_VERSION  = _STATE['rule_version']   # "R3 (V2.4)"

MAX_DIV_PCT   = 0.40   # 매수자금 최대 비중 40% (현금 + QQQI 합산)

# Crash Hunter 재매수 기준 (L1/L2/L3)
CRASH_1_PCT   = 0.45   # ATH 대비 -55% → 매수자금 40% 재투입
CRASH_2_PCT   = 0.30   # ATH 대비 -70% → 매수자금 40% 재투입
CRASH_3_PCT   = 0.20   # ATH 대비 -80% → 매수자금 잔여 20% 전액 재투입

# GitHub Actions 업데이트 링크
GITHUB_REPO        = "timesave7/Dean-Automation"
UPDATE_WORKFLOW    = "Paul_Roth IRA_update_cost_basis_05_01_2026.yml"
GITHUB_UPDATE_URL  = f"https://github.com/{GITHUB_REPO}/actions/workflows/{UPDATE_WORKFLOW}"

CONFIG = {
    "sender_email": os.environ.get("SENDER_EMAIL", ""),
    "sender_app_password": os.environ.get("GMAIL_APP_PASSWORD", ""),
    "recipients": [
        "seunggy98@gmail.com",
        "timesave7@gmail.com",
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
    div_ticker  = yf.Ticker(DIV_ETF)   # V2.4: QQQI

    qqq_hist  = qqq_ticker.history(period="18mo", auto_adjust=True, repair=False)
    tqqq_hist = tqqq_ticker.history(period="5y",  auto_adjust=True, repair=False)
    div_hist  = div_ticker.history(period="5d",   auto_adjust=True, repair=False)

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
    crash_3_price = tqqq_ath * CRASH_3_PCT

    # R3 룰: 전환 트리거 계산 (per-share Cost Basis × 1.30)
    trigger_price   = COST_BASIS * (1 + TRIGGER_PCT)
    conv_triggered  = tqqq_price >= trigger_price
    gain_pct        = (tqqq_price - COST_BASIS) / COST_BASIS * 100

    # Crash Hunter 발동 여부
    crash_1_hit = tqqq_price <= crash_1_price and tqqq_price > crash_2_price
    crash_2_hit = tqqq_price <= crash_2_price and tqqq_price > crash_3_price
    crash_3_hit = tqqq_price <= crash_3_price

    # 배당ETF 현재가 (QQQI)
    div_price = div_hist['Close'].iloc[-1] if not div_hist.empty else None

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
        'crash_3_price'  : round(crash_3_price, 2),
        'crash_1_hit'    : crash_1_hit,
        'crash_2_hit'    : crash_2_hit,
        'crash_3_hit'    : crash_3_hit,
        'cost_basis'     : COST_BASIS,
        'trigger_price'  : round(trigger_price, 2),
        'conv_triggered' : conv_triggered,
        'gain_pct'       : gain_pct,
        'div_price'      : round(div_price, 2) if div_price else 'N/A',
        'div_etf'        : DIV_ETF,
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
    if s['crash_3_hit']:
        action_color = "#7b241c"
        action_icon  = "🚨"
        action_title = "Crash Hunter L3 발동! (ATH -80%)"
        action_lines = [
            f"TQQQ ATH 대비 {s['tqqq_drop_pct']:.1f}% 폭락",
            f"→ 매수자금 잔여 20% 전액 → TQQQ 매수 (현금 우선, 부족 시 {DIV_ETF} 매도)",
        ]
        conv_warning_html = ""
        update_button_html = ""

    elif s['crash_2_hit']:
        action_color = "#c0392b"
        action_icon  = "🚨"
        action_title = "Crash Hunter L2 발동! (ATH -70%)"
        action_lines = [
            f"TQQQ ATH 대비 {s['tqqq_drop_pct']:.1f}% 폭락",
            f"→ 매수자금(현금+{DIV_ETF}) 40% → TQQQ 매수 (현금 우선, 부족 시 {DIV_ETF} 매도)",
        ]
        conv_warning_html = ""
        update_button_html = ""

    elif s['crash_1_hit']:
        action_color = "#e67e22"
        action_icon  = "🎯"
        action_title = "Crash Hunter L1 발동! (ATH -55%)"
        action_lines = [
            f"TQQQ ATH 대비 {s['tqqq_drop_pct']:.1f}% 폭락",
            f"→ 매수자금(현금+{DIV_ETF}) 40% → TQQQ 매수 (현금 우선, 부족 시 {DIV_ETF} 매도)",
        ]
        conv_warning_html = ""
        update_button_html = ""

    elif s['conv_triggered']:
        action_color = "#1e8449"
        action_icon  = "💰"
        action_title = f"{DIV_ETF} 전환 신호! ({RULE_VERSION})"
        action_lines = [
            f"기준단가 ${s['cost_basis']} 대비 +{s['gain_pct']:.1f}% 달성 (목표 +{TRIGGER_PCT*100:.0f}%)",
            f"→ TQQQ 수익분의 {TRANSFER_PCT*100:.0f}% → {DIV_ETF} + 현금 50:50 분할 전환",
        ]
        # ★ 전환 신호 시에만 40% 한도 경고 표시
        conv_warning_html = f"""
        <div style="background:#fffde7;border-left:4px solid #f9a825;padding:12px 16px;
                    border-radius:4px;margin-bottom:16px;font-size:13px;color:#5d4037;">
            ⚠️ <strong>전환 전 확인:</strong> 현재 매수자금(현금+{DIV_ETF}) 비중이 포트폴리오의
            <strong>{MAX_DIV_PCT*100:.0f}%를 초과하지 않도록</strong> 할 것
        </div>"""
        # ★ 전환 신호 시에만 업데이트 버튼 표시
        update_button_html = f"""
        <div style="margin-top:16px;padding:14px 18px;background:#f0faf4;
                    border:2px solid #27ae60;border-radius:8px;text-align:center;">
            <p style="margin:0 0 10px;font-size:13px;color:#1e8449;font-weight:bold;">
                ⚠️ 거래 체결 후 COST_BASIS를 업데이트하세요 (새 CB = 체결가)
            </p>
            <a href="{GITHUB_UPDATE_URL}"
               style="display:inline-block;background:#27ae60;color:white;
                      padding:10px 24px;border-radius:6px;text-decoration:none;
                      font-size:14px;font-weight:bold;">
                ✅ COST_BASIS 업데이트하러 가기
            </a>
            <p style="margin:8px 0 0;font-size:11px;color:#888;">
                현재 신호가: ${s['tqqq_price']} | 실제 체결가로 입력하세요
            </p>
        </div>"""

    else:
        action_color = "#2471a3"
        action_icon  = "🔵"
        action_title = "보유 유지"
        action_lines = [
            f"기준단가 ${s['cost_basis']} 대비 현재 {s['gain_pct']:+.1f}%",
            f"전환 목표가: ${s['trigger_price']} ({TRIGGER_PCT*100:.0f}% 상승 시, {RULE_VERSION})",
            "→ 전환/재매수 신호 없음",
        ]
        conv_warning_html = ""
        update_button_html = ""

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
        <h1 style="margin:0;font-size:20px;">📊 Paul - Roth IRA TQQQ 투자 신호</h1>
        <p style="margin:6px 0 0;opacity:0.8;font-size:13px;">
            {s['date']} &nbsp;|&nbsp; 🕐 수집: {s['fetch_time']} &nbsp;|&nbsp; 룰: {RULE_VERSION}
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

        <!-- ★ 40% 한도 경고 (전환 신호 시에만 표시) -->
        {conv_warning_html}

        <!-- ★ COST_BASIS 업데이트 버튼 (전환 신호 시에만 표시) -->
        {update_button_html}

        <!-- 💹 현재가 -->
        <div style="display:flex;gap:10px;margin-bottom:20px;margin-top:20px;">
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
                <div style="color:#888;font-size:11px;">{DIV_ETF}</div>
                <div style="font-size:22px;font-weight:bold;color:#27ae60;">${s['div_price']}</div>
            </div>
        </div>

        <!-- 💰 배당주 전환 트리거 (R3 룰) -->
        <h3 style="margin:0 0 8px;font-size:14px;color:#555;">💰 {DIV_ETF} 전환 트리거 ({RULE_VERSION})</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:18px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">기준단가 (per-share CB)</td>
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
                <td style="padding:8px;color:#888;">전환 목표가 (CB × 1.{int(TRIGGER_PCT*100):02d})</td>
                <td style="padding:8px;text-align:right;">${s['trigger_price']}</td>
            </tr>
            <tr>
                <td style="padding:8px;font-weight:bold;">{DIV_ETF} 전환 신호</td>
                <td style="padding:8px;text-align:right;font-weight:bold;">
                    {chk(s['conv_triggered'])} {'발동! (수익분 ' + str(int(TRANSFER_PCT*100)) + '%)' if s['conv_triggered'] else '미충족'}
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
                    {'🚨 도달! 매수자금 40% 투입' if s['crash_1_hit'] else '미달 ✅'}
                </td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;color:#888;">L2 재매수 (-70% / ${s['crash_2_price']})</td>
                <td style="padding:8px;text-align:right;
                    color:{'#e74c3c' if s['crash_2_hit'] else '#27ae60'};">
                    {'🚨 도달! 매수자금 40% 투입' if s['crash_2_hit'] else '미달 ✅'}
                </td>
            </tr>
            <tr>
                <td style="padding:8px;color:#888;">L3 재매수 (-80% / ${s['crash_3_price']})</td>
                <td style="padding:8px;text-align:right;
                    color:{'#e74c3c' if s['crash_3_hit'] else '#27ae60'};">
                    {'🚨 도달! 매수자금 잔여 20% 투입' if s['crash_3_hit'] else '미달 ✅'}
                </td>
            </tr>
        </table>

        <!-- 하단 안내 -->
        <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
        <p style="color:#aaa;font-size:10px;text-align:center;margin:0;line-height:1.8;">
            장 마감 후 자동 실행 | GitHub Actions | {RULE_VERSION} + {DIV_ETF}<br>
            전환 발생 시 이메일 내 버튼으로 COST_BASIS 업데이트 | 투자 참고용
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
    print(f"  💰 Paul's TQQQ {RULE_VERSION} + {DIV_ETF} 신호  |  {s['date']}")
    print(f"  🕐 수집 시각: {s['fetch_time']}")
    print(LINE)

    print(f"\n  💹 현재가")
    print(f"     QQQ:   ${s['qqq_price']:>8.2f}")
    print(f"     TQQQ:  ${s['tqqq_price']:>8.2f}  (ATH 대비 {s['tqqq_drop_pct']:+.1f}%)")
    print(f"     {DIV_ETF}:  ${s['div_price']}")

    print(f"\n  💰 {DIV_ETF} 전환 트리거 ({RULE_VERSION})")
    print(f"     기준단가:    ${s['cost_basis']:.2f}")
    print(f"     현재가:      ${s['tqqq_price']:.2f}  ({s['gain_pct']:+.1f}%)")
    print(f"     전환 목표가: ${s['trigger_price']:.2f}  (+{TRIGGER_PCT*100:.0f}%)")
    print(f"     전환 신호:   {'✅ 발동! (수익분 ' + str(int(TRANSFER_PCT*100)) + '%)' if s['conv_triggered'] else '❌ 미충족'}")

    print(f"\n  🎯 Crash Hunter 재매수 트리거")
    print(f"     ATH:  ${s['tqqq_ath']:.2f}  ({s['tqqq_ath_date']})")
    print(f"     L1(-55%): ${s['crash_1_price']:.2f}  →  {'🚨 도달! 매수자금 40% 투입' if s['crash_1_hit'] else '미달 ✅'}")
    print(f"     L2(-70%): ${s['crash_2_price']:.2f}  →  {'🚨 도달! 매수자금 40% 투입' if s['crash_2_hit'] else '미달 ✅'}")
    print(f"     L3(-80%): ${s['crash_3_price']:.2f}  →  {'🚨 도달! 매수자금 잔여 20% 투입' if s['crash_3_hit'] else '미달 ✅'}")

    print(f"\n  📉 추세 참고")
    print(f"     150일선: {'✅ 위' if s['above150'] else '❌ 아래'}   정배열: {'✅' if s['golden_cross'] else '❌'}")

    print(f"\n{LINE}")
    print(f"  ⚡ 오늘 액션")
    print(LINE)

    if s['crash_3_hit']:
        print(f"\n  🚨  Crash Hunter L3 발동! (ATH 대비 {s['tqqq_drop_pct']:.1f}%)")
        print(f"       → 매수자금 잔여 20% 전액 → TQQQ 매수 (현금 우선, 부족 시 {DIV_ETF} 매도)")
    elif s['crash_2_hit']:
        print(f"\n  🚨  Crash Hunter L2 발동! (ATH 대비 {s['tqqq_drop_pct']:.1f}%)")
        print(f"       → 매수자금(현금+{DIV_ETF}) 40% → TQQQ 매수 (현금 우선, 부족 시 {DIV_ETF} 매도)")
    elif s['crash_1_hit']:
        print(f"\n  🎯  Crash Hunter L1 발동! (ATH 대비 {s['tqqq_drop_pct']:.1f}%)")
        print(f"       → 매수자금(현금+{DIV_ETF}) 40% → TQQQ 매수 (현금 우선, 부족 시 {DIV_ETF} 매도)")
    elif s['conv_triggered']:
        print(f"\n  💰  {DIV_ETF} 전환 신호! (+{s['gain_pct']:.1f}% 달성, {RULE_VERSION})")
        print(f"       → TQQQ 수익분 {TRANSFER_PCT*100:.0f}% → {DIV_ETF} + 현금 50:50 분할 전환")
        print(f"       ⚠️  전환 후 GitHub Actions에서 COST_BASIS 업데이트 (새 CB = 체결가):")
        print(f"       {GITHUB_UPDATE_URL}")
    else:
        print(f"\n  🔵  보유 유지 (현재 {s['gain_pct']:+.1f}%, 목표 +{TRIGGER_PCT*100:.0f}%, {RULE_VERSION})")
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

    if s['crash_3_hit']:
        signal = "🚨 L3 재매수"
    elif s['crash_2_hit']:
        signal = "🚨 L2 재매수"
    elif s['crash_1_hit']:
        signal = "🎯 L1 재매수"
    elif s['conv_triggered']:
        signal = f"💰 {DIV_ETF} 전환!"
    else:
        signal = f"🔵 보유 ({s['gain_pct']:+.1f}%)"

    subject = f"[Paul - Roth IRA TQQQ투자신호] {signal} | TQQQ ${s['tqqq_price']} | {s['date']}"

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
    if sys.stdin.isatty():
        input("\n✅ 완료. 아무 키나 누르면 창이 닫힙니다...")
