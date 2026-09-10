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
    O = opens

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
    std120 = [NA] * n
    for i in range(119, n):
        window = C[i - 119:i + 1]
        sma120 = _safe_mean(window)
        std120[i] = _safe_stdev(window)
        bb_upper[i] = sma120 + 2 * std120[i]
        bb_lower[i] = sma120 - 2 * std120[i]

    # ---------- 4. MA200 및 기울기 ----------
    ma200 = [NA] * n
    for i in range(199, n):
        ma200[i] = _safe_mean(C[i - 199:i + 1])

    slope200 = [NA] * n
    for i in range(199, n):
        if i - 20 >= 199 and ma200[i - 20]:
            slope200[i] = (ma200[i] / ma200[i - 20] - 1) * 100

    vol_state = [NA] * n  # 대세하락장(AS) — 문자열, "빈칸 아님" 여부만 실질적으로 쓰임
    for i in range(199, n):
        if slope200[i] is not None and slope200[i] > 2 and C[i] > ma200[i] * 0.7:
            vol_state[i] = "강세장"
        elif slope200[i] is not None and slope200[i] < -0.15:
            vol_state[i] = "약세장"
        else:
            vol_state[i] = "변동성"

    # ---------- 4.5 시장국면(BU) + 전량매도/추격매수(BV) — 다른 신호 계산보다
    # 먼저 구해 둬야 아래 최종 매수/매도 신호 조립 시 바로 참조할 수 있다 ----------
    regime, bk_flags, _bq_debug = compute_regime(env_upper, C, H, ma200)
    bv = compute_special_signals(H, C, ma200, regime, bk_flags, std120)

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
            # Excel AF: 기본은 직전 38일 RSI 최고치와 비교.
            # 원본 워크북은 2026-04-29(행 4079)부터 최신 수식이
            # 최근 7일을 제외한 38일 구간(i-45:i-7)으로 변경되어 있음.
            if i >= 4077 and i >= 45:
                window = [x for x in rsi[i - 45:i - 7] if x is not None]
            else:
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

    # Excel BE열: RSI<30 + 거래량>직전 239일 평균 + 당일 저가가 직전 119일 최고종가의 70% 이하
    vol_spike_buy = [NA] * n  # BE
    for i in range(119, n):
        if rsi[i] is None or vol_avg240[i] is None:
            continue
        recent_max_close = max(C[i - 119:i])
        vol_spike_buy[i] = ("2년최대" if
                            (rsi[i] < 30 and V[i] > vol_avg240[i] and
                             L[i] <= recent_max_close * 0.7) else "")

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
    aj_final = [""] * n  # AJ 고점 매도 신호(최종)

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
        # 엑셀 BF: 직전 20일(오늘 포함) 내 "전량매도"가 있으면 모든 매수신호 억제.
        # 그렇지 않으면 찐쌍바닥 > 3X매수 > 추격매수 순으로 판정.
        au_i = rebound_confirm[i]
        sell_off_recent = "전량매도" in bv[max(0, i - 19):i + 1]
        if sell_off_recent:
            bc[i] = ""
        elif bi[i] != "" and au_i != "반등확인":
            bc[i] = "찐쌍바닥"
        elif ba[i] == "2년최대" and au_i != "반등확인":
            bc[i] = "3X매수"
        elif bv[i] == "추격매수":
            bc[i] = "추격매수"
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
        if (vol_state[i] is not None and drop10[i] is not None and slope200[i] is not None):
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

        # --- AJ (고점 매도 신호 최종) ---
        # Excel AJ = IF(AQ="쌍고점","쌍고점", IF(BV="전량매도","전량매도", AX))
        # AX = IF(AND(AU>=30,AT>=3,AG="매도"),"매도","")
        high_sell = (ma200[i] is not None and slope200[i] is not None and
                     (C[i] / ma200[i] - 1) * 100 >= 30 and
                     slope200[i] >= 3 and ag[i] == "매도")
        # MA200/기울기 데이터가 생기기 전 초기 구간은 원본 Excel의
        # 과거 확정 AJ 값이 AG(다이버전스 매도)를 그대로 사용했다.
        # MA200 계산 가능 이후에는 현재 AJ/AX 수식(이격도>=30, 기울기>=3)을 적용.
        if ap[i] == "쌍고점":
            aj_final[i] = "쌍고점"
        elif bv[i] == "전량매도":
            aj_final[i] = "전량매도"
        elif ma200[i] is None:
            aj_final[i] = "매도" if ag[i] == "매도" else ""
        else:
            aj_final[i] = "매도" if high_sell else ""

    results = []
    for i in range(n):
        results.append({
            "date": dates[i],
            "open": opens[i],
            "high": highs[i],
            "low": lows[i],
            "close": C[i],
            "volume": V[i],
            "buy": bc[i] if bc[i] else None,
            "sell": aj_final[i] if aj_final[i] else None,
            "bb_upper": bb_upper[i],
            "bb_lower": bb_lower[i],
            "env_upper": env_upper[i],
            "env_lower": env_lower[i],
            "ma200": ma200[i],
            "rsi": rsi[i],
            "regime": regime[i],
        })
    return results


def compute_regime(env_upper, closes, highs, ma200):
    """
    상승장/하락장 판정 — 엑셀 BU열 수식을 그대로 이식 (2026-09 재검증 버전).

    엑셀 BU 수식:
        =IF(E="", "", IF(OR(AND(BQ<>"", E>BQ), AND(O<>"", AR<>"", O>AR)),
                          "상승장", "하락장"))
    여기서 O열은 시가(Open)가 아니라 "Env_Upper(+20%)"(엔벨로프 상단, 20일
    SMA*1.2) 컬럼이다 — 컬럼 문자 O와 필드명 "Open"의 앞글자가 같아서
    착각하기 쉬운 부분이니 주의. 즉 "기준가격(BQ)이 있고 종가가 그걸
    넘었다" 또는 "엔벨로프 상단이 MA200(AR)을 넘었다" 둘 중 하나만 참이면
    상승장 — 두 조건은 서로 독립적인 OR.

    BQ(기준가격) 계산 체인:
      BK(하락 기준 시작): 종가가 MA200을 아래로 처음 뚫는 날
      BL(첫 기술적 반등): 그 이후 첫 국지 고점(앞뒤 3거래일보다 고가가 높거나
                          같음), 단 그 BK 구간에서 아직 반등이 없었을 때만
      BQ: 가장 최근 BK가 가장 최근 BL보다 나중이 아닐 때(=반등이 이미 기록됨)
          그 반등일의 종가

    반환값: (regime, bk_flags, bq_values)
      regime[i]: "bull" | "bear" | None
      bk_flags[i]: bool — BV(전량매도) 계산에 재사용
      bq_values[i]: 기준가격 또는 None — 디버그/검증용
    """
    n = len(closes)
    C, H, EU = closes, highs, env_upper

    # BK: 종가가 MA200 아래로 첫 크로스하는 날
    BK = [False] * n
    for i in range(1, n):
        if ma200[i] is None or ma200[i - 1] is None:
            continue
        if C[i] < ma200[i] and C[i - 1] >= ma200[i - 1]:
            BK[i] = True

    # BL: 직전 BK 이후 첫 국지 고점(앞뒤 3일 대비 고가 최고)
    BL = [False] * n
    bl_event_indices = []
    last_bk_idx = None
    for i in range(n):
        if last_bk_idx is not None and i - 3 >= 0 and i + 3 < n:
            has_existing = any(last_bk_idx <= b <= i - 1 for b in bl_event_indices)
            if not has_existing:
                if H[i] >= max(H[i - 3:i]) and H[i] >= max(H[i + 1:i + 4]):
                    BL[i] = True
                    bl_event_indices.append(i)
        if BK[i]:
            last_bk_idx = i

    # BQ: 기준가격(반등일 종가) — 최근 BK가 최근 BL보다 나중이 아닐 때만 유효
    BQ = [None] * n
    last_bk_row = None
    last_bl_row = None
    for i in range(n):
        if BK[i]:
            last_bk_row = i
        if BL[i]:
            last_bl_row = i
        if last_bk_row is not None and last_bl_row is not None and last_bk_row <= last_bl_row:
            BQ[i] = C[last_bl_row]

    # BU: 최종 시장국면 — 엑셀과 동일한 순수 OR 조건 (O열=Env_Upper)
    regime = [None] * n
    for i in range(n):
        if C[i] is None:
            continue
        cond1 = BQ[i] is not None and C[i] > BQ[i]
        cond2 = (EU[i] is not None and ma200[i] is not None and EU[i] > ma200[i])
        regime[i] = "bull" if (cond1 or cond2) else "bear"

    return regime, BK, BQ


def compute_special_signals(highs, closes, ma200, regime, bk_flags, std120):
    """
    전량매도 / 추격매수 — 엑셀 BV열("전량매도/추격매수") 수식을 그대로 이식.

    엑셀 BV 수식(요지):
      전량매도: 오늘이 BK(하락 기준 시작)일 &&
                직전 60일 고가 최고치 == 직전 240일 고가 최고치(최근 1년 내
                신고가 경신 없이 정체) &&
                오늘 종가 <= (직전 60일 고가 최고치)*0.85(고점대비 -15%) &&
                직전 60일 내 이미 "전량매도"가 없었음(중복 방지) &&
                StDev%(=BB표준편차120/종가) < 0.14
      추격매수: 위 조건이 아니고, 오늘 국면이 상승장으로 전환된 첫날
                (오늘 상승장 && 어제 하락장)
    """
    n = len(closes)
    H, C = highs, closes
    bv = [None] * n

    for i in range(n):
        is_full_sell = False
        if bk_flags[i] and i >= 1:
            win60_start = max(0, i - 60)
            win240_start = max(0, i - 240)
            max60 = max(H[win60_start:i]) if H[win60_start:i] else None
            max240 = max(H[win240_start:i]) if H[win240_start:i] else None
            if (max60 is not None and max240 is not None and max60 == max240
                    and C[i] is not None and C[i] <= max60 * 0.85
                    and std120[i] is not None and C[i] and (std120[i] / C[i]) < 0.14):
                dedup_start = max(0, i - 60)
                if "전량매도" not in bv[dedup_start:i]:
                    is_full_sell = True

        if is_full_sell:
            bv[i] = "전량매도"
        elif (regime[i] == "bull" and i >= 1 and regime[i - 1] == "bear"):
            bv[i] = "추격매수"

    return bv





def compute_from_bars(bars):
    """bars: list of dict with keys date/open/high/low/close/volume (date: datetime)"""
    dates = [b["date"] for b in bars]
    opens = [b["open"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    volumes = [b["volume"] for b in bars]
    return compute_signals(dates, opens, highs, lows, closes, volumes)
