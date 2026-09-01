# TQQQ 매수/매도 신호 자동 알림 봇 + 실시간 연동 앱 (순수 파이썬 버전)

> 🔰 **GitHub이 처음이거나 설치 과정을 클릭 몇 번으로 따라 하고 싶다면
> [`GITHUB_설치가이드.md`](./GITHUB_설치가이드.md) 를 먼저 보세요.**
>
> 🔒 **테스트 단계라 지정한 사람에게만 앱을 공개하고 싶다면
> [`CLOUDFLARE_ACCESS_가이드.md`](./CLOUDFLARE_ACCESS_가이드.md) 를 참고하세요**
> (이메일 허용목록 방식, 비밀번호 공유 없이 무료로 접근 제한 가능).
>
> ⏰ **매일 알림이 오는 정확한 시각을 직접 조정하고 싶다면
> [`CRONJOB_ORG_가이드.md`](./CRONJOB_ORG_가이드.md) 를 참고하세요**
> (GitHub Actions 자체 스케줄은 지연이 잦아, 외부 무료 스케줄러로
> 정시 실행을 보장하는 방법입니다).

매일 아침 6시(KST), TQQQ 최신 시세를 가져와 **엑셀/LibreOffice 없이 순수
파이썬으로** 매수신호·매도신호를 계산하고, 새 신호가 발생하면 텔레그램으로
알려줍니다. 텔레그램 메시지는 폰에 텔레그램 앱만 설치되어 있으면 그대로
일반 푸시 알림(잠금화면 알림)으로 옵니다. **여러 명에게 동시에** 알림을
보낼 수도 있습니다 (`TELEGRAM_CHAT_IDS`에 chat_id를 쉼표로 나열).

그리고 이 저장소는 **웹앱(PWA)도 함께 호스팅**합니다 — `index.html`을
GitHub Pages로 열면, 앱이 열릴 때마다 자동으로 이 저장소의 최신
`data.json`을 불러와 차트·신호·모의투자가 항상 최신 상태로 표시됩니다.

서버를 직접 켜둘 필요 없이 **GitHub Actions**가 매일 정해진 시간에 대신
실행해줍니다.

---

## 이 저장소 하나로 되는 일

| 구성요소 | 역할 |
|---|---|
| `scripts/update_and_notify.py` | 매일 최신 시세 수집 + 텔레그램 알림 |
| `scripts/export_app_data.py` | 앱이 읽을 `data.json` 생성 (신호+지표 포함) |
| `index.html` | 증권앱 스타일 웹앱 (PWA) — 열릴 때마다 `data.json`을 fetch |
| `manifest.json`, `sw.js`, `icons/` | 폰 홈 화면 설치, 오프라인 캐싱 |
| `.github/workflows/daily-signal.yml` | cron-job.org가 호출하면 실행 (위 전부 포함) — [`CRONJOB_ORG_가이드.md`](./CRONJOB_ORG_가이드.md) 참고 |

**앱이 최신 데이터를 못 가져오는 경우** (오프라인, 또는 GitHub Pages를 아직
설정 안 한 경우)에는 `index.html`에 내장된 스냅샷 데이터로 자동
대체되고, 화면 상단에 "오프라인 · 저장된 데이터 사용 중"이라고 표시됩니다
— 앱이 하얗게 깨지거나 멈추지 않습니다.

---

## GitHub Pages 켜기 (앱을 실제로 웹에서 열려면 필요)

1. 저장소 **Settings → Pages**
2. **Source: Deploy from a branch**, Branch: `main` / `(root)` → **Save**
3. 1~2분 후 `https://사용자명.github.io/저장소명/` 주소로 접속 가능

> ⚠️ GitHub Pages 무료 티어(개인 계정)는 **Public 저장소만** 지원합니다.
> 지금 이 저장소가 Private이라면 Public으로 전환해야 합니다. 저장소가
> Public이 되어도 `TWELVEDATA_API_KEY`/`TELEGRAM_BOT_TOKEN`/
> `TELEGRAM_CHAT_IDS` 같은 **GitHub Secrets는 노출되지 않습니다** (Secrets는
> 저장소 파일이 아니라 GitHub이 별도로 암호화 보관). 노출되는 건 코드와
> 시세 데이터뿐입니다.

Private을 꼭 유지하고 싶다면, Cloudflare Pages(Private 저장소 연결 가능,
무료)로 호스팅하는 대안도 있습니다.

---

## 폰에 앱처럼 설치하기

Pages 주소로 접속 후:
- **iPhone(Safari)**: 공유 버튼 → 홈 화면에 추가
- **Android(Chrome)**: 메뉴 → 앱 설치

설치 후에도 앱을 열 때마다 최신 `data.json`을 자동으로 불러옵니다.

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
- **자동 실행 시각은 이 워크플로 파일이 아니라 cron-job.org가 결정합니다.**
  [`CRONJOB_ORG_가이드.md`](./CRONJOB_ORG_가이드.md)를 따라 설정하면
  원하는 정확한 시각(예: 매일 06:35)에 실행되고, 이후 시각을 바꾸고
  싶을 때도 cron-job.org 대시보드에서만 수정하면 됩니다 (코드 수정 불필요).

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


## BF/AJ 1:1 검증 보정 (v5)
- 기준: Excel `TQQQ_Data`의 BF(매수신호 통합), AJ(고점 매도 신호 최종)
- `signal_overrides.json`에 Excel 역사 신호를 기준값으로 저장합니다.
- `export_app_data.py`, `update_and_notify.py`는 계산 후 기준값이 있는 과거 날짜에 BF/AJ를 1:1 적용합니다.
- 신규 날짜(Excel 기준값이 없는 날짜)는 `tqqq_signals.py` 계산 로직을 그대로 사용합니다.


## BF/AJ 수식 역검증 완료 (v6)
- Excel `TQQQ_Data`의 BF/AJ 캐시 결과와 Python 계산엔진을 2010-02-11~2026-08-31 전 기간 1:1 대조했습니다.
- BF의 2010-08-03 `#VALUE!`는 신호가 아닌 Excel 오류값으로 제외하면 매수/매도 불일치 0건입니다.
- AJ 초기 MA200 미산출 구간의 과거 확정 로직(AG 직접 사용)과, 2026-04-29 이후 AF RSI 약세 다이버전스의 최신 비교구간(최근 7일 제외, 그 이전 38일)을 엔진에 반영했습니다.
- v5의 `signal_overrides.json` 보정 없이 `compute_signals()` 자체 결과가 Excel BF/AJ와 일치합니다.
- 차트의 매수/매도 삼각형 마커 옆에 신호 날짜를 상시 표시합니다.
