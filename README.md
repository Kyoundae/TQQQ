# TQQQ 매수/매도 신호 자동 알림 봇 (순수 파이썬 버전)

> 🔰 **GitHub이 처음이거나 설치 과정을 클릭 몇 번으로 따라 하고 싶다면
> [`GITHUB_설치가이드.md`](./GITHUB_설치가이드.md) 를 먼저 보세요.**
> (명령어 없이 웹 브라우저만으로 설치 가능, 여러 사람이 함께 알림
> 받는 방법도 포함)

매일 아침 6시(KST), TQQQ 최신 시세를 가져와 **엑셀/LibreOffice 없이 순수
파이썬으로** 매수신호·매도신호를 계산하고, 새 신호가 발생하면 텔레그램으로
알려줍니다. 텔레그램 메시지는 폰에 텔레그램 앱만 설치되어 있으면 그대로
일반 푸시 알림(잠금화면 알림)으로 옵니다. **여러 명에게 동시에** 알림을
보낼 수도 있습니다 (`TELEGRAM_CHAT_IDS`에 chat_id를 쉼표로 나열).

서버를 직접 켜둘 필요 없이 **GitHub Actions**가 매일 정해진 시간에 대신
실행해줍니다 (공개/비공개 저장소 모두 무료 티어로 충분).

---

## 이전 버전과 무엇이 다른가

| | v1 (엑셀 기반) | v2 (이 버전) |
|---|---|---|
| 신호 계산 | 원본 엑셀 수식 + LibreOffice 재계산 | `scripts/tqqq_signals.py` (순수 파이썬) |
| 실행 시간 | 수십 초 (LibreOffice 구동) | 1초 이내 |
| 의존성 | LibreOffice 설치 필요 | 파이썬 표준 라이브러리 + requests |
| 데이터 저장 | engine.xlsx (8MB) | price_history.json (수백 KB) |

`scripts/tqqq_signals.py`는 원본 워크북의 RSI(11)·Envelope(20일)·
Bollinger Band(120일)·MA200·쌍바닥/쌍고점 패턴 로직을 그대로 옮긴 것이며,
**16년치(4,153일) 전체 이력을 원본 엑셀 결과와 대조 검증**했습니다.
매수신호는 36/36 100% 일치, 매도신호는 146개 중 144개 일치했고, 남은
2개는 원본 엑셀 자체의 수식 복사 오류(2026년 5월 이후 일부 행에서 참조
범위가 7칸 밀려있던 문제)로 밝혀져, 오히려 이 파이썬 버전이 "의도된
로직"을 더 정확히 따릅니다.

---

## 1. 준비물 (모두 무료)

| 항목 | 용도 | 발급처 |
|---|---|---|
| GitHub 계정 | 코드 저장 + 자동 실행(Actions) | github.com |
| Twelve Data API 키 | 매일 최신 TQQQ 시세 조회 | https://twelvedata.com/apikey |
| 텔레그램 봇 토큰 | 알림 발송 (= 폰 푸시 알림) | @BotFather |
| 텔레그램 chat_id | 알림 받을 대상 지정 | 아래 3단계 참고 |

---

## 2. 저장소 만들기

```bash
git init
git add .
git commit -m "init: TQQQ 신호 알림 봇 (순수 파이썬)"
git branch -M main
git remote add origin https://github.com/사용자명/저장소명.git
git push -u origin main
```

---

## 3. 텔레그램 봇 만들기 (5분) — 이게 곧 폰 알림입니다

1. 텔레그램 앱에서 **@BotFather** 검색 → 대화 시작
2. `/newbot` 입력 → 봇 이름과 아이디(예: `tqqq_signal_bot`) 설정
3. 완료되면 `1234567890:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` 형태의
   **봇 토큰**을 받습니다 → 이게 `TELEGRAM_BOT_TOKEN`
4. 만든 봇과 아무 메시지나 한 번 주고받기 (`/start` 등) — **이 앱이 폰에
   깔려 있고 알림 권한만 켜져 있으면, 봇이 보내는 메시지가 다른 앱들과
   똑같이 잠금화면 푸시 알림으로 옵니다.** 별도 앱 개발이 필요 없습니다.
5. chat_id 확인:
   - 브라우저에서 (BOT_TOKEN 자리에 방금 받은 토큰 입력):
     ```
     https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
     ```
   - 응답 JSON의 `"chat":{"id":123456789,...}` 숫자가 **chat_id**
   - (더 쉬운 방법: 텔레그램에서 **@userinfobot** 검색 후 대화하면 본인
     chat_id를 바로 알려줍니다)

> 텔레그램 앱 대신 정말로 별도의 자체 앱/웹앱에서 브라우저 푸시로
> 받고 싶다면 — 가능은 하지만 VAPID 키 발급, 알림 구독을 저장할
> 백엔드 서버, 서비스워커 등록 등 훨씬 큰 인프라가 필요합니다.
> 필요하시면 별도로 설계해드릴 수 있습니다.

---

## 4. GitHub Secrets 등록

저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `TWELVEDATA_API_KEY` | Twelve Data에서 발급받은 키 |
| `TELEGRAM_BOT_TOKEN` | 3단계에서 받은 봇 토큰 |
| `TELEGRAM_CHAT_IDS` | 알림받을 사람들의 chat_id를 쉼표로 이어붙인 값 (예: `111,222,333`) |

---

## 5. 동작 확인

- 저장소 → **Actions** 탭 → `TQQQ 매수/매도 신호 체크` → **Run workflow**
  로 수동 실행해서 먼저 확인하세요
- 로그에 `새로운 시세 데이터가 없습니다` 또는 `알림 발송: ...` 이 뜨면 정상
- 이후로는 매일 06:00(KST)에 자동 실행됩니다 (cron 특성상 몇 분 정도
  지연될 수 있습니다)

---

## 6. 로컬에서 신호 계산 로직만 테스트하기

```bash
pip install -r requirements.txt
python3 -c "
import json, sys
sys.path.insert(0, 'scripts')
from datetime import datetime
from tqqq_signals import compute_signals

h = json.load(open('price_history.json'))
dates = [datetime.strptime(r['date'], '%Y-%m-%d') for r in h]
results = compute_signals(dates, [r['open'] for r in h], [r['high'] for r in h],
                           [r['low'] for r in h], [r['close'] for r in h], [r['volume'] for r in h])
for r in results[-10:]:
    print(r['date'].date(), r['close'], r['buy'], r['sell'])
"
```

---

## 7. 신호 판정 로직을 바꾸고 싶다면

`scripts/tqqq_signals.py`의 `compute_signals()` 함수 안에서 각 신호의
조건문을 직접 수정하면 됩니다. 예를 들어 RSI 과매도 기준을 30 대신
25로 낮추고 싶다면 `vol_spike_buy` 계산 부분의 `rsi[i] < 30` 을
`rsi[i] < 25` 로 바꾸면 됩니다.

## 8. 알려진 제한사항

- Twelve Data 무료 플랜은 하루 800회 호출 제한 — 하루 1회 실행에는 충분
- 미국 공휴일 등 휴장일에는 신규 데이터가 없어 조용히 종료됨
- 쌍바닥/쌍고점 확인(찐쌍바닥/쌍고점 신호)은 원본 로직상 앞뒤 2일을
  봐야 확정되는 패턴이라, 가장 최근 2거래일에 대해서는 확정이 하루~이틀
  늦게 나타날 수 있습니다 (원본 엑셀에서도 동일하게 발생하는 특성입니다)
