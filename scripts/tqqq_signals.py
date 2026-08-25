"""
TQQQ 매수/매도 신호 계산 엔진 — 순수 파이썬 구현 (엑셀/LibreOffice 불필요)

원본 워크북(TQQQ_Data 시트)의 수식을 그대로 파이썬으로 옮긴 것입니다.
RSI(11), Envelope(20일 ±20%), Bollinger Band(120일 ±2σ), MA200, 그리고
쌍바닥/쌍고점 패턴 감지(최근 30일 내 저점/고점 매칭 + 되돌림 확인)까지
전부 이 파일 하나로 계산합니다.

핵심 함수:
    compute_signals(dates, opens, highs, lows, closes, volumes) -> list[dict]
        각 행에 대해 buy(매수신호 통합), sell(매도신호 최종) 등을 포함한
        결과를 반환합니다.
"""

import math
from datetime import datetime


def _safe_mean(vals):
    return sum(vals) / len(vals)


def _safe_stdev(vals):
    # Excel STDEV = 표본표준편차 (ddof=1)
    n = len(vals)
    m = _safe_mean(vals)
    var = sum((x - m) ** 2 for x in vals) / (n - 1)
    return math.sqrt(var)


def compute_signals(dates, opens, highs, lows, closes, volumes):
    n = len(closes)
    C, H, L, V = closes, highs, lows, volumes

    NA = None  # 빈 셀(엑셀의 "") 표현

    # ---------- 1. RSI(11), Wilder 방식 ----------
    change = [NA] * n
    gain = [NA] * n
    loss = [NA] * n
    for i in range(1, n):
        change[i] = C[i] - C[i - 1]
        gain[i] = max(change[i], 0)
        loss[i] = max(-change[i], 0)

    avg_gain = [NA] * n
    avg_loss = [NA] * n
    rsi = [NA] * n
    for i in range(n):
        if i == 11:
            avg_gain[i] = _safe_mean(gain[1:12])
            avg_loss[i] = _safe_mean(loss[1:12])
        elif i > 11:
            avg_gain[i] = (avg_gain[i - 1] * 10 + gain[i]) / 11
            avg_loss[i] = (avg_loss[i - 1] * 10 + loss[i]) / 11
        if avg_gain[i] is not None and avg_loss[i] is not None:
            rs = 999 if avg_loss[i] == 0 else avg_gain[i] / avg_loss[i]
            rsi[i] = 100 - 100 / (1 + rs)

    # ---------- 2. Envelope(20일 SMA ±20%) ----------
    env_upper = [NA] * n
    env_lower = [NA] * n
    for i in range(19, n):
        sma20 = _safe_mean(C[i - 19:i + 1])
        env_upper[i] = sma20 * 1.2
        env_lower[i] = sma20 * 0.8

    # ---------- 3. Bollinger Band(120일 SMA ±2σ) ----------
    bb_upper = [NA] * n
    bb_lower = [NA] * n
    for i in range(119, n):
        window = C[i - 119:i + 1]
        sma120 = _safe_mean(window)
        std120 = _safe_stdev(window)
        bb_upper[i] = sma120 + 2 * std120
        bb_lower[i] = sma120 - 2 * std120

    # ---------- 4. MA200 및 기울기 ----------
    ma200 = [NA] * n
    for i in range(199, n):
        ma200[i] = _safe_mean(C[i - 199:i + 1])

    slope200 = [NA] * n
    for i in range(199, n):
        if i - 20 >= 199 and ma200[i - 20]:
            slope200[i] = (ma200[i] / ma200[i - 20] - 1) * 100

    regime = [NA] * n  # 대세하락장(AR) — 문자열, "빈칸 아님" 여부만 실질적으로 쓰임
    for i in range(199, n):
        if slope200[i] is not None and slope200[i] > 2 and C[i] > ma200[i] * 0.7:
            regime[i] = "강세장"
        elif slope200[i] is not None and slope200[i] < -0.15:
            regime[i] = "약세장"
        else:
            regime[i] = "변동성"

    # ---------- 5. 10일 -20%(AT), E-B 3% 근접(AU) ----------
    drop10 = [NA] * n
    for i in range(9, n):
        recent_max = max(C[i - 9:i + 1])
        drop10[i] = (recent_max - C[i]) / recent_max > 0.17

    rebound_confirm = [NA] * n  # AU
    for i in range(20, n):
        if env_lower[i] is None or bb_lower[i] is None:
            continue
        if env_lower[i - 1] is None or bb_lower[i - 1] is None:
            continue
        p, t = env_lower[i], bb_lower[i]
        p1, t1 = env_lower[i - 1], bb_lower[i - 1]
        cond1 = abs(p - t) / t <= 0.035 and abs(p1 - t1) / t1 > 0.035
        cond2 = p < t and p1 >= t1
        rebound_confirm[i] = "반등확인" if (cond1 or cond2) else ""

    # ---------- 6. 매도신호 다이버전스 재료 (AD/AE/AF/AJ) ----------
    bb_break = [NA] * n     # AD: 종가가 BB상단 돌파
    new_high_wick = [NA] * n  # AE: 전일 고가가 최근 39일 종가 최고치 상회
    rsi_bearish_div = [NA] * n  # AF: RSI가 최근 38일 최고치보다 낮음
    rsi_down_today = [NA] * n   # AJ
    rsi_up_today = [NA] * n     # BJ

    for i in range(n):
        if bb_upper[i] is not None:
            bb_break[i] = C[i] > bb_upper[i]
        if i >= 39:
            new_high_wick[i] = H[i - 1] > max(C[i - 39:i])
        if i >= 38 and rsi[i] is not None:
            window = [x for x in rsi[i - 38:i] if x is not None]
            if window:
                rsi_bearish_div[i] = rsi[i] < max(window)
        if i >= 1 and rsi[i] is not None and rsi[i - 1] is not None:
            rsi_down_today[i] = rsi[i] < rsi[i - 1]
            rsi_up_today[i] = rsi[i] > rsi[i - 1]

    # ---------- 7. 거래량 급증 매수(BB열) + 240일 평균거래량(AZ) ----------
    vol_avg240 = [NA] * n
    for i in range(239, n):
        vol_avg240[i] = _safe_mean(V[i - 239:i])

    vol_spike_buy = [NA] * n  # BB
    for i in range(119, n):
        if rsi[i] is None or vol_avg240[i] is None:
            continue
        recent_max_close = max(C[i - 119:i])
        if rsi[i] < 30 and V[i] > vol_avg240[i] and L[i] <= recent_max_close * 0.7:
            vol_spike_buy[i] = "2년최대"
        else:
            vol_spike_buy[i] = ""

    # ---------- 8. 순차 계산이 필요한 신호들 (행 순서대로) ----------
    bc = [""] * n     # 매수신호(통합) — 최종
    bd = [NA] * n     # 하락 1차저점
    be = [NA] * n     # 하락 반등고점
    bf = [NA] * n     # 하락 2차저점
    bg = [NA] * n     # 1/2차 저점차이
    bh = [False] * n  # 쌍바닥조건
    bi = [""] * n     # 쌍바닥확인
    ba = [""] * n     # 매수신호(2년최대 재확인)

    ag = [""] * n     # 매도신호(다이버전스)
    ah = [""] * n     # 매도신호(하락+다이)
    av = [""] * n     # 매도신호(하락장반등)
    ak = [NA] * n     # 상승 1차고점
    al = [NA] * n     # 눌림저점
    am = [NA] * n     # 상승 2차고점
    an = [NA] * n     # 1/2차 고점차이
    ao = [False] * n  # 쌍고점조건
    ap = [""] * n     # 쌍고점확인
    ai_final = [""] * n  # 매도신호(최종)

    for i in range(n):
        win_start = max(0, i - 30)

        # --- BD: 하락 1차저점 ---
        bc_window = bc[win_start:i]
        if any(x in ("매수", "2X매수", "3X매수") for x in bc_window):
            bd[i] = min(C[win_start:i]) if bc_window else NA
        else:
            bd[i] = NA

        # --- BE, BF, BG, BH ---
        trough_idx = None
        if bd[i] is not None and bc_window:
            sub = C[win_start:i]
            pos = sub.index(bd[i])  # 첫 번째 일치 위치
            trough_idx = win_start + pos
            be[i] = max(C[trough_idx:i]) if trough_idx < i else NA

        if bd[i] is not None and i >= 2 and i + 2 < n:
            window5 = C[i - 2:i + 3]
            if C[i] == min(window5) and C[i] != bd[i]:
                bf[i] = C[i]

        if bd[i] is not None and bf[i] is not None:
            bg[i] = abs(bf[i] / bd[i] - 1)

        if (bd[i] is not None and be[i] is not None and bf[i] is not None
                and bg[i] is not None and trough_idx is not None):
            dist = i - trough_idx
            bh[i] = (dist >= 5 and be[i] >= bd[i] * 1.08
                      and bg[i] <= 0.10 and bf[i] <= bd[i] * 1.2)

        # --- BJ / BI ---
        if i >= 1 and bh[i - 1] and rsi_up_today[i] and bb_lower[i] is not None:
            if C[i] > bb_lower[i]:
                bi[i] = "찐쌍바닥"

        # --- BA (2년최대 재확인) ---
        ba_win_start = max(0, i - 30)
        bb_window = vol_spike_buy[ba_win_start:i]
        if "2년최대" not in bb_window:
            ba[i] = vol_spike_buy[i] if vol_spike_buy[i] is not None else NA
        else:
            close_window = C[ba_win_start:i]
            # 가장 최근에 "2년최대"였던 날의 종가
            last_idx = max(k for k, tag in enumerate(bb_window) if tag == "2년최대")
            base_close = close_window[last_idx]
            ba[i] = "2년최대" if C[i] <= base_close * 0.85 else ""

        # --- BC (최종 매수신호) ---
        au_i = rebound_confirm[i]
        if bi[i] != "" and au_i != "반등확인":
            bc[i] = "찐쌍바닥"
        elif ba[i] == "2년최대" and au_i != "반등확인":
            bc[i] = "3X매수"
        else:
            bc[i] = ""

        # --- AG (매도신호 다이버전스) ---
        if (bb_break[i] is not None and new_high_wick[i] is not None
                and rsi_bearish_div[i] is not None and rsi_down_today[i] is not None):
            ag[i] = "매도" if (bb_break[i] and new_high_wick[i]
                               and rsi_bearish_div[i] and rsi_down_today[i]) else ""

        # --- AV (하락장반등매도) ---
        bi_win_start = max(0, i - 29)
        bi_window = bi[bi_win_start:i + 1]
        if (regime[i] is not None and drop10[i] is not None and slope200[i] is not None):
            if drop10[i] and slope200[i] <= -0.05 and "찐쌍바닥" not in bi_window:
                av[i] = "하락반등매도"

        # --- AH ---
        ah[i] = "하락장매도" if av[i] != "" else ag[i]

        # --- AK: 상승 1차고점 ---
        ah_window = ah[win_start:i]
        if any(x in ("매도", "하락장매도") for x in ah_window):
            ak[i] = max(C[win_start:i]) if ah_window else NA

        # --- AL, AM, AN, AO ---
        peak_idx = None
        if ak[i] is not None and ah_window:
            sub = C[win_start:i]
            pos = sub.index(ak[i])
            peak_idx = win_start + pos
            al[i] = min(C[peak_idx:i]) if peak_idx < i else NA

        if ak[i] is not None and i >= 2 and i + 2 < n:
            window5 = C[i - 2:i + 3]
            if C[i] == max(window5) and C[i] != bd[i]:
                am[i] = C[i]

        if ak[i] is not None and am[i] is not None:
            an[i] = abs(am[i] / ak[i] - 1)

        if (ak[i] is not None and al[i] is not None and am[i] is not None
                and an[i] is not None and peak_idx is not None):
            ao[i] = (al[i] >= ak[i] * 0.8 and an[i] <= 0.05 and am[i] <= ak[i] * 1.2)

        # --- AP (쌍고점확인) ---
        if (bb_break[i] is not None and new_high_wick[i] is not None
                and rsi_bearish_div[i] is not None and rsi_down_today[i] is not None):
            if bb_break[i] and new_high_wick[i] and rsi_bearish_div[i]:
                if ao[i] and bb_upper[i] is not None and C[i] >= bb_upper[i] and rsi[i] is not None and rsi[i] >= 75:
                    ap[i] = "쌍고점"

        # --- AI (최종 매도신호) ---
        ai_final[i] = "쌍고점" if ap[i] == "쌍고점" else ag[i]

    results = []
    for i in range(n):
        results.append({
            "date": dates[i],
            "close": C[i],
            "buy": bc[i] if bc[i] else None,
            "sell": ai_final[i] if ai_final[i] else None,
            "bb_upper": bb_upper[i],
            "bb_lower": bb_lower[i],
            "env_upper": env_upper[i],
            "env_lower": env_lower[i],
            "ma200": ma200[i],
        })
    return results


def compute_from_bars(bars):
    """bars: list of dict with keys date/open/high/low/close/volume (date: datetime)"""
    dates = [b["date"] for b in bars]
    opens = [b["open"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    volumes = [b["volume"] for b in bars]
    return compute_signals(dates, opens, highs, lows, closes, volumes)
